import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Absolute path of the project root (stable across --reload restarts)
PROJECT_DIR = Path(__file__).parent.parent.resolve()

# --- LLM provider selection ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")

# --- Ollama ---
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
CHAT_MODEL      = os.getenv("CHAT_MODEL",      "qwen2.5:7b")
VISION_MODEL    = os.getenv("VISION_MODEL",    "llava")

# --- TTS ---
TTS_API_URL        = os.getenv("TTS_API_URL",        "http://127.0.0.1:9880")
TTS_REF_AUDIO_PATH = os.getenv("TTS_REF_AUDIO_PATH", "")
TTS_PROMPT_TEXT    = os.getenv("TTS_PROMPT_TEXT",    "触れたらあったかいかなっていつも思うんだ")
TTS_PROMPT_LANG    = os.getenv("TTS_PROMPT_LANG",    "ja")

# --- Audio cache ---
AUDIO_CACHE_DIR = Path(os.getenv("AUDIO_CACHE_DIR", str(PROJECT_DIR / "cache" / "audio")))

# --- Memory / Obsidian ---
OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH", "")
EMBED_MODEL         = os.getenv("EMBED_MODEL",         "nomic-embed-text")
CHROMA_DB_PATH      = Path(os.getenv("CHROMA_DB_PATH", str(PROJECT_DIR / "data" / "chroma")))

# --- Startup validation ---
if not TTS_REF_AUDIO_PATH:
    print("Warning: TTS_REF_AUDIO_PATH not set — voice synthesis will be unavailable.")
    print("         Copy .env.example to .env and fill in the path.")
