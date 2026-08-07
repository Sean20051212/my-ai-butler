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

# --- Vision (on-demand perception) ---
# CDP endpoint of the user's browser for DOM-based perception (highest
# priority). Requires the browser launched with --remote-debugging-port.
VISION_CDP_URL   = os.getenv("VISION_CDP_URL", "http://localhost:9222")
# Seconds a capture stays cached while the same window is in focus.
VISION_CACHE_TTL = float(os.getenv("VISION_CACHE_TTL", "5"))

# --- TTS ---
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "cloud")
# CosyVoice2 fukalos inference server (runs in WSL cosyvoice conda env).
COSYVOICE_TTS_URL = os.getenv("COSYVOICE_TTS_URL", "http://localhost:9880/tts")

# --- STT (speech-to-text, voice input) ---
STT_PROVIDER = os.getenv("STT_PROVIDER", "whisper")
# faster-whisper runs on the CPU by default to stay off the already-tight GPU
# (CosyVoice2 + Ollama). int8 keeps the small model fast enough for short clips.
WHISPER_MODEL_SIZE   = os.getenv("WHISPER_MODEL_SIZE",   "small")
WHISPER_DEVICE       = os.getenv("WHISPER_DEVICE",       "cpu")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
# Transcription language. "zh" for the Chinese-primary butler; "" = auto-detect.
WHISPER_LANGUAGE     = os.getenv("WHISPER_LANGUAGE",     "zh")

# --- Audio cache ---
AUDIO_CACHE_DIR = Path(os.getenv("AUDIO_CACHE_DIR", str(PROJECT_DIR / "cache" / "audio")))

# --- Memory / Obsidian ---
OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH", "")
EMBED_MODEL         = os.getenv("EMBED_MODEL",         "nomic-embed-text")
CHROMA_DB_PATH      = Path(os.getenv("CHROMA_DB_PATH", str(PROJECT_DIR / "data" / "chroma")))
