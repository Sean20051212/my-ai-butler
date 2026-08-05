"""my-ai-butler 專用的 CosyVoice2 常駐推論服務。

在 WSL2 的 conda `cosyvoice` 環境內執行，載入一次微調完成的
`CosyVoice2-0.5B-fukalos-final` 模型，透過 HTTP 對 Windows 端的 FastAPI 後端
提供語音合成。刻意只用 Python 標準庫的 http.server，不在這個脆弱的環境裡
新增任何依賴（torch / soundfile / numpy 都是 CosyVoice 既有的）。

本檔版控在 my-ai-butler 專案內，但實際跑在 WSL 的 CosyVoice 環境；透過
`COSYVOICE_HOME` 環境變數指向 CosyVoice repo 根目錄（預設 /home/sean/CosyVoice），
不需要放進 CosyVoice repo。

端點：
  POST /tts    body: {"text": "要合成的（簡體）文字"}  → 200 audio/wav bytes
                                                       → 204 文字為空 / 無輸出
  GET  /health → 200 application/json  回報模型狀態與實際 VRAM 佔用

注意：繁→簡轉換由 Windows 端 provider 負責（這個環境沒有 opencc），
      本服務假設收到的已是模型慣用的簡體中文，但非簡體也能運作。
"""

import io
import os
import sys
import json
import threading
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# CosyVoice repo 根目錄：模型、prompt、third_party 都在這底下（WSL 原生檔案系統）
COSYVOICE_HOME = os.getenv("COSYVOICE_HOME", "/home/sean/CosyVoice")
if not os.path.isdir(COSYVOICE_HOME):
    raise SystemExit(f"COSYVOICE_HOME 不存在：{COSYVOICE_HOME}")
os.chdir(COSYVOICE_HOME)
sys.path.insert(0, COSYVOICE_HOME)
sys.path.insert(0, os.path.join(COSYVOICE_HOME, "third_party/Matcha-TTS"))

import numpy as np
import soundfile as sf
import torch
from cosyvoice.cli.cosyvoice import CosyVoice2

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ── 設定 ────────────────────────────────────────────────────────────────────
HOST = "0.0.0.0"
PORT = int(os.getenv("BUTLER_TTS_PORT", "9880"))
MODEL_DIR = "pretrained_models/CosyVoice2-0.5B-fukalos-final"
# zero-shot 參考音檔與其對應文本（HANDOFF 指定，簡體）
PROMPT_TEXT = "放心，你要做的，不是让自己变成真正的神明的样子，你只要扮演人类想象中神明的样子就好了。"
PROMPT_WAV = "./asset/fukalos_prompt.wav"

# 推論非執行緒安全、GPU 也只有一張，序列化所有合成請求
_infer_lock = threading.Lock()
cosyvoice = None  # 於 main() 啟動時載入一次


def _synthesize(text: str) -> bytes | None:
    """把文字合成為 WAV bytes；無有效輸出時回傳 None。"""
    text = (text or "").strip()
    if not text:
        return None
    chunks = []
    with _infer_lock:
        # frontend 內部已依標點把長文本切句，這裡把各段串接成一段完整語音
        for out in cosyvoice.inference_zero_shot(text, PROMPT_TEXT, PROMPT_WAV, stream=False):
            chunks.append(out["tts_speech"].squeeze(0).cpu().numpy())
    if not chunks:
        return None
    audio = np.concatenate(chunks)
    buf = io.BytesIO()
    sf.write(buf, audio, cosyvoice.sample_rate, format="WAV")
    return buf.getvalue()


def _vram_report() -> dict:
    if not torch.cuda.is_available():
        return {"cuda": False}
    free, total = torch.cuda.mem_get_info()
    return {
        "cuda": True,
        "device": torch.cuda.get_device_name(0),
        "allocated_mb": round(torch.cuda.memory_allocated() / 1024**2, 1),
        "reserved_mb": round(torch.cuda.memory_reserved() / 1024**2, 1),
        "free_mb": round(free / 1024**2, 1),
        "total_mb": round(total / 1024**2, 1),
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # 導向 logging，避免 stderr 雜訊
        logging.info("%s - %s", self.address_string(), fmt % args)

    def _send_json(self, code: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.rstrip("/") == "/health":
            self._send_json(200, {
                "model_loaded": cosyvoice is not None,
                "sample_rate": getattr(cosyvoice, "sample_rate", None),
                "vram": _vram_report(),
            })
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path.rstrip("/") != "/tts":
            self._send_json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b""
            text = json.loads(raw.decode("utf-8")).get("text", "") if raw else ""
        except Exception as exc:
            self._send_json(400, {"error": f"bad request: {exc}"})
            return

        try:
            audio = _synthesize(text)
        except Exception as exc:
            logging.exception("synthesis failed")
            self._send_json(500, {"error": f"synthesis failed: {exc}"})
            return

        if audio is None:
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(audio)))
        self.end_headers()
        self.wfile.write(audio)


def main():
    global cosyvoice
    logging.info("COSYVOICE_HOME=%s", COSYVOICE_HOME)
    logging.info("Loading CosyVoice2 model from %s ...", MODEL_DIR)
    cosyvoice = CosyVoice2(MODEL_DIR, load_jit=False, load_trt=False, fp16=False)
    logging.info("Model loaded. sample_rate=%s. VRAM=%s", cosyvoice.sample_rate, _vram_report())
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    logging.info("Butler TTS server listening on http://%s:%d", HOST, PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("Shutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
