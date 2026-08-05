#!/usr/bin/env bash
# 由 start.bat 透過 WSL 呼叫：啟用 cosyvoice conda 環境並啟動 CosyVoice TTS 服務。
# 抽成獨立腳本是為了避開在 .bat 裡巢狀引號 conda/python 指令的麻煩。
set -e

source /home/sean/miniconda3/etc/profile.d/conda.sh
conda activate cosyvoice

# CosyVoice repo 根目錄（模型與 third_party 所在），可用環境變數覆寫
export COSYVOICE_HOME="${COSYVOICE_HOME:-/home/sean/CosyVoice}"

# 若已有舊服務佔用 9880，先收掉避免重複
fuser -k 9880/tcp 2>/dev/null || true
sleep 1

# 以本腳本所在目錄定位 server，不受呼叫時 cwd 影響
DIR="$(cd "$(dirname "$0")" && pwd)"

# 同時輸出到終端機與 log 檔，方便服務若中途死掉時回頭查原因
LOG="/tmp/butler_tts.log"
echo "=== butler TTS server start $(date) ===" >> "$LOG"
python "$DIR/butler_tts_server.py" 2>&1 | tee -a "$LOG"
