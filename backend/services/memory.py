"""Obsidian vault integration with ChromaDB-backed RAG.

Gracefully disabled when:
  - OBSIDIAN_VAULT_PATH is not set in .env, or
  - chromadb is not installed.

When enabled:
  - On startup: indexes all .md files in the vault (incremental, skips
    unchanged files based on mtime).
  - On each /chat request: queries top-3 relevant chunks and returns them
    as a string for injection into the system prompt.
  - After each reply: appends a timestamped entry to
    {vault}/AI-Butler-Memory/YYYY-MM-DD.md and incrementally updates
    the ChromaDB collection with the new chunk.
"""

from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import requests

from backend.config import (
    CHROMA_DB_PATH,
    EMBED_MODEL,
    OBSIDIAN_VAULT_PATH,
    OLLAMA_BASE_URL,
)

if TYPE_CHECKING:
    from backend.models.character import CharacterState

try:
    import chromadb
    _CHROMADB_OK = True
except ImportError:
    _CHROMADB_OK = False


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

class MemoryService:
    """Manages Obsidian vault indexing and ChromaDB semantic search."""

    def __init__(self) -> None:
        self.enabled = bool(OBSIDIAN_VAULT_PATH) and _CHROMADB_OK

        if not self.enabled:
            if not OBSIDIAN_VAULT_PATH:
                print("Memory: OBSIDIAN_VAULT_PATH not set — memory disabled.")
            elif not _CHROMADB_OK:
                print("Memory: chromadb not installed — run `pip install chromadb`.")
            return

        self.vault     = Path(OBSIDIAN_VAULT_PATH)
        self._lock     = threading.Lock()
        self._client   = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
        self._col      = self._client.get_or_create_collection(
            name="obsidian_vault",
            metadata={"hnsw:space": "cosine"},
        )
        # Index in background so startup is not blocked
        threading.Thread(target=self._index_vault, daemon=True).start()

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def query(self, text: str, n_results: int = 3) -> str:
        """Return the top *n_results* relevant chunks as a formatted string."""
        if not self.enabled or self._col.count() == 0:
            return ""
        try:
            embedding = self._embed(text)
            results   = self._col.query(
                query_embeddings=[embedding],
                n_results=min(n_results, self._col.count()),
                include=["documents", "metadatas"],
            )
            chunks = results["documents"][0]
            sources = [m.get("source", "") for m in results["metadatas"][0]]
            lines = []
            for chunk, src in zip(chunks, sources):
                lines.append(f"[{Path(src).name}]\n{chunk}")
            return "\n\n".join(lines)
        except Exception as exc:
            print(f"Memory query error: {exc}")
            return ""

    # ------------------------------------------------------------------
    # Writing memories
    # ------------------------------------------------------------------

    def write_memory(
        self,
        user_msg:  str,
        reply:     str,
        emotion:   str,
        state:     "CharacterState",
    ) -> None:
        """Append a conversation entry to today's memory file and re-index it."""
        if not self.enabled:
            return
        try:
            memory_dir = self.vault / "AI-Butler-Memory"
            memory_dir.mkdir(parents=True, exist_ok=True)

            today     = datetime.now().strftime("%Y-%m-%d")
            timestamp = datetime.now().strftime("%H:%M")
            file_path = memory_dir / f"{today}.md"

            entry = (
                f"\n## {timestamp} — {emotion}\n"
                f"**你說：** {user_msg}\n"
                f"**八千代：** {reply}\n"
                f"*[trust: {state.trust_level} | "
                f"stress: {state.stress_level} | "
                f"energy: {state.energy_level}]*\n"
            )

            with open(file_path, "a", encoding="utf-8") as f:
                f.write(entry)

            # Incremental ChromaDB update for this new chunk
            chunk_id = f"{file_path}:{timestamp}"
            embedding = self._embed(entry.strip())
            with self._lock:
                self._col.upsert(
                    ids=[chunk_id],
                    embeddings=[embedding],
                    documents=[entry.strip()],
                    metadatas=[{"source": str(file_path)}],
                )
        except Exception as exc:
            print(f"Memory write error: {exc}")

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def _index_vault(self) -> None:
        """Walk the vault and embed any .md file whose mtime has changed."""
        print(f"Memory: indexing vault at {self.vault} …")
        count = 0
        for md_file in self.vault.rglob("*.md"):
            try:
                mtime   = str(md_file.stat().st_mtime)
                file_id = str(md_file)

                # Check if file is already indexed with the same mtime
                existing = self._col.get(
                    where={"source": file_id},
                    include=["metadatas"],
                )
                if existing["ids"]:
                    stored_mtime = existing["metadatas"][0].get("mtime", "")
                    if stored_mtime == mtime:
                        continue  # Up-to-date, skip

                    # File changed — remove old chunks before re-indexing
                    with self._lock:
                        self._col.delete(ids=existing["ids"])

                chunks    = _chunk_markdown(md_file.read_text(encoding="utf-8", errors="ignore"))
                for idx, chunk in enumerate(chunks):
                    embedding = self._embed(chunk)
                    chunk_id  = f"{file_id}:{idx}"
                    with self._lock:
                        self._col.upsert(
                            ids=[chunk_id],
                            embeddings=[embedding],
                            documents=[chunk],
                            metadatas=[{"source": file_id, "mtime": mtime}],
                        )
                count += len(chunks)
            except Exception as exc:
                print(f"Memory index error ({md_file.name}): {exc}")

        print(f"Memory: indexed {count} chunks from vault.")

    # ------------------------------------------------------------------
    # Embedding helper
    # ------------------------------------------------------------------

    def _embed(self, text: str) -> list[float]:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/embed",
            json={"model": EMBED_MODEL, "input": text},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["embeddings"][0]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chunk_markdown(text: str, max_chars: int = 400) -> list[str]:
    """Split markdown text into paragraph-aligned chunks of ~*max_chars*."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if current and len(current) + len(para) + 2 > max_chars:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}".strip() if current else para
    if current:
        chunks.append(current)
    return chunks
