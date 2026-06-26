# my-ai-butler 重構計畫

> 本文件給 Claude Code 在 `my-ai-butler` 專案內執行重構使用。所有方向已經拍板確認，**不需要再詢問是否要做，只需要詢問實作細節上的疑問**（例如某個函式命名、某個邊界情況怎麼處理）。

## 專案現狀（重構前）

```
backend/
├── app.py                  # FastAPI 入口，lifespan 啟動 vision loop
├── config.py                # 環境變數讀取
├── models/character.py      # CharacterState：trust/stress/energy 狀態機
├── routes/chat.py           # /chat 端點，直接 import llm.py / tts.py
├── services/
│   ├── llm.py               # 寫死呼叫 Ollama（qwen2.5:7b）
│   ├── tts.py                # 寫死呼叫本地 GPT-SoVITS HTTP API
│   ├── vision.py             # 背景執行緒，8 秒輪詢隨機截圖丟 llava
│   └── memory.py             # ChromaDB + Obsidian vault RAG（這塊做得好，不動）
└── utils/text.py             # TTS 文字前處理（這塊做得好，不動）
test_brain.py / test_vision.py  # 根目錄裸測試腳本，無斷言
CLAUDE.md                      # 含過時的 PyTorch Nightly 環境說明
```

## 已確認的六項決策

1. **LLM**：先維持 Ollama 本地推論，但要做成可切換 provider 架構，雲端（Claude/Gemini 等）先留擴充點、不實作。**模型只能用一般正規模型（如 `qwen2.5:7b`、`qwen3.5:9b`），不要使用任何標榜 "uncensored"、"abliterated"、移除安全機制的模型版本。**
2. **視覺感知**：移除背景常駐 8 秒輪詢，改成按需觸發；採用多層次優先序：DOM 解析 → 桌面無障礙樹 → VLM 截圖（VLM 是最後手段）。
3. **TTS**：放棄 GPT-SoVITS 本地訓練路線，改接雲端語音克隆服務（廠商未定，先做抽象層 + 骨架）。
4. **本地推論環境**：移除 PyTorch Nightly 相關設定與踩坑紀錄——LLM/VLM 走 Ollama 不需要 PyTorch，TTS 改雲端後 GPT-SoVITS 整套移除，本地不再需要管理 PyTorch/CUDA 相容性。
5. **服務介面**：`services/` 全部拆成有明確介面（抽象基底類別）的設計，所有 provider 抽象層共用同一套設計模式。
6. **測試與 CI**：導入 pytest 正式測試，根目錄裸腳本全部改寫成有斷言的測試；新增 GitHub Actions CI，push/PR 時自動跑測試。

---

## 任務一：LLM Provider 抽象層

**目的**：把 `services/llm.py` 從「寫死呼叫 Ollama」改成「可切換的 provider 架構」。

1. 新增 `backend/services/llm/` 目錄（取代現有的 `backend/services/llm.py` 單檔案）：
   - `base.py` — 定義抽象基底類別 `BaseLLMProvider`，至少包含一個方法 `chat(messages: list) -> str`（回傳原始回覆文字，讓上層自己處理 JSON 解析）
   - `providers/ollama_provider.py` — 把現有 `llm.py` 的邏輯搬進來，實作 `BaseLLMProvider`。`get_dynamic_system_prompt()` 這個函式跟 provider 無關，搬到 `backend/services/llm/prompts.py` 獨立出來
   - `providers/cloud_provider.py` — 建立骨架類別 `CloudLLMProvider(BaseLLMProvider)`，`chat()` 方法先 `raise NotImplementedError("雲端 provider 尚未實作，待後續決定要接哪家 API")`，留清楚的 TODO 註解
   - `factory.py` — 依環境變數 `LLM_PROVIDER`（預設 `"ollama"`）回傳對應的 provider 實例
2. `config.py` 新增 `LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")`
3. `.env.example` 新增對應設定與註解說明
4. `routes/chat.py` 改成透過 factory 取得 provider，呼叫 `provider.chat(messages)`，不再直接 import 寫死的 client
5. **驗收**：`.env` 裡把 `LLM_PROVIDER` 改成不存在的值時，factory 應該丟出清楚的錯誤訊息，而不是靜默失敗

---

## 任務二：視覺感知改為按需觸發 + 多層次優先序

**目的**：移除常駐輪詢，改成「對話時才嘗試感知一次」，且優先用結構化資料而非螢幕截圖。

1. 新增 `backend/services/vision/` 目錄：
   - `base.py` — 抽象基底類別 `VisionSource`，方法 `capture() -> str | None`（回傳場景描述文字，抓不到回傳 `None`）
   - `dom_source.py` — 用 Playwright 嘗試抓取當前作用中瀏覽器分頁的 DOM 內容並摘要成一句話描述；抓不到（沒有瀏覽器作用中視窗）回傳 `None`
   - `accessibility_source.py` — 用 `pywinauto` 讀取當前作用中視窗的無障礙樹，組成簡短描述；失敗回傳 `None`
   - `vlm_source.py` — 把現有 `_capture_random_region()` 改成「截取目前作用中視窗的畫面」而非隨機區域，丟給 `llava` 做描述。這是最後手段
   - `chain.py` — `VisionChain` 類別，依序嘗試 `DomSource → AccessibilitySource → VlmSource`，回傳第一個成功的結果
2. **移除** `start_vision_loop()` 背景執行緒整段邏輯，`app.py` 的 `lifespan` 不再呼叫它
3. `CharacterState.latest_vision` 改成「每次 `/chat` 請求時即時呼叫 `VisionChain` 取得」，不再是背景更新的快取值。可以視情況加一個簡單的 TTL 快取（例如同一個視窗 5 秒內重複問不用重新抓），避免每次對話都觸發一次完整 fallback chain
4. `routes/chat.py` 在組裝 system prompt 前呼叫 `vision_chain.capture()`，結果跟現有邏輯一樣塞進 prompt
5. **驗收**：模擬 DOM/無障礙樹都抓不到的情況，確認會 fallback 到 VLM；模擬 DOM 抓到的情況，確認不會多打一次無障礙樹或 VLM 的呼叫

---

## 任務三：TTS 改為雲端語音克隆服務

**目的**：移除本地 GPT-SoVITS 呼叫，改成可插拔的雲端 provider，廠商未定先留擴充點。

1. 新增 `backend/services/tts/` 目錄：
   - `base.py` — 抽象基底類別 `BaseTTSProvider`，方法 `synthesize(text: str) -> bytes | None`
   - `providers/cloud_provider.py` — 骨架類別，`synthesize()` 先 `raise NotImplementedError`，註解列出常見可選方案供之後決定時參考（ElevenLabs / Azure Speech / PlayHT，皆支援聲音克隆與多語言），需要的 API key 設定先留在 `.env.example` 但用註解標記「未啟用」
   - `cache.py` — 把現有 `get_audio()` 裡的 hash-based 快取邏輯（這塊做得好）抽出來獨立，跟具體 provider 解耦，任何 provider 都共用同一套快取
2. **移除**：`_call_gptsovits()` 函式整段、`TTS_API_URL`、`TTS_REF_AUDIO_PATH`、`TTS_PROMPT_TEXT`、`TTS_PROMPT_LANG` 這些 GPT-SoVITS 專屬設定（連同 `.env.example` 裡對應的段落）
3. **保留不動**：`utils/text.py` 的 `preprocess_for_tts()`——雲端 TTS 一樣需要乾淨的中文輸入，這段邏輯繼續適用
4. `routes/chat.py` 改成透過 TTS provider 介面呼叫，不直接 import 寫死的函式
5. **驗收**：`synthesize()` 被呼叫但 provider 未實作時，應該優雅地回傳 `None`（讓對話流程繼續、只是沒有語音），不應該讓整個 `/chat` 請求噴錯

---

## 任務四：清理 PyTorch Nightly 相關環境設定

**目的**：移除已經不再需要的本地深度學習環境負擔。

1. 更新 `CLAUDE.md`：移除「硬體與底層環境」整段（PyTorch Nightly、Blackwell sm_120、torchaudio/torchcodec ABI 衝突等內容），改寫成簡短一句說明「本地端只需要 Ollama，不需要額外管理 PyTorch/CUDA 環境」
2. 檢查 `requirements.txt`：確認沒有列出 `torch`、`torchaudio`、`torchcodec`（目前看起來沒有，因為這些原本是另外手動裝在 venv 裡，不在 `requirements.txt` 內）
3. `CLAUDE.md` 的「已知問題與處理方式」段落裡，移除「音檔讀取」「TTS 訓練資料」「TTS 文字前處理」中跟 GPT-SoVITS 本地訓練直接相關的內容；「TTS 文字前處理」這塊邏輯本身保留（因為雲端 TTS 一樣需要），只是改寫成不提 GPT-SoVITS 特定坑

---

## 任務五：服務介面層統一重構

**目的**：讓任務一、二、三的 provider 抽象層風格一致，並把整個 `services/` 目錄的呼叫方式統一。

1. 確認 LLM / Vision / TTS 三個 provider 的抽象基底類別風格一致（同樣用 `abc.ABC` + `abstractmethod`，同樣有 factory 函式依環境變數選擇實作）
2. `routes/chat.py` 重構後應該長這樣（示意，不是逐字要求）：
   ```python
   llm_provider = get_llm_provider()
   vision_chain = get_vision_chain()
   tts_provider = get_tts_provider()
   ```
   而不是像現在一樣直接 `from backend.services import llm, tts`
3. `memory.py` 維持現狀不變——這塊原本的增量索引、優雅降級設計已經很完整，不需要套用 provider 抽象層
4. **驗收**：`routes/chat.py` 裡不應該再出現任何對 `services.llm`、`services.tts`、`services.vision` 模組層級函式的直接呼叫，全部透過 provider 物件

---

## 任務六：測試框架與 CI

**目的**：補齊正式測試，並設定自動化驗證。

1. `requirements.txt` 新增：`pytest`、`pytest-asyncio`、`httpx`（FastAPI `TestClient` 依賴）
2. 新增 `tests/` 目錄：
   - `tests/test_chat.py` — 用 FastAPI `TestClient` 測試 `/chat` 端點，**mock 掉 LLM provider**（不要真的打 Ollama），驗證：回傳 200、回傳內容包含 `reply` 欄位、LLM 回傳格式錯誤時有 fallback 訊息
   - `tests/test_llm_provider.py` — 測試 factory 依 `LLM_PROVIDER` 環境變數正確選擇 provider；測試未知 provider 名稱會丟出明確錯誤
   - `tests/test_vision_chain.py` — mock 三層 source，驗證 fallback 順序正確（DOM 成功時不會呼叫無障礙樹和 VLM；DOM 失敗、無障礙樹成功時不會呼叫 VLM）
   - `tests/test_tts.py` — 驗證快取機制（同一段文字第二次呼叫應該命中快取、不重複呼叫 provider）；驗證 provider 未實作時優雅回傳 `None`
3. 原本根目錄的 `test_brain.py`、`test_vision.py` 整合進對應的 `tests/` 檔案後可以刪除
4. 新增 `.github/workflows/test.yml`：
   ```yaml
   name: Test
   on: [push, pull_request]
   jobs:
     test:
       runs-on: windows-latest
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-python@v5
           with:
             python-version: '3.11'
         - run: pip install -r requirements.txt
         - run: pytest
   ```
   （`runs-on` 用 `windows-latest` 是因為專案路徑/環境是 Windows 為主；若 CI 跑 Linux 有問題再切換）
5. **驗收**：本機跑 `pytest` 全部通過；確認 CI 設定檔語法正確（可以先用 `act` 工具本機驗證，或直接 push 上 GitHub 看 Actions 頁面）

---

## 整體驗收清單

- [ ] `LLM_PROVIDER=ollama` 時行為跟重構前一致，可正常對話
- [ ] `LLM_PROVIDER=cloud` 時會明確報錯（NotImplementedError），不會靜默失敗
- [ ] 對話時才觸發視覺感知一次，背景不再有 8 秒輪詢的 print log
- [ ] 視覺感知優先序正確：DOM → 無障礙樹 → VLM
- [ ] TTS 呼叫雲端 provider 骨架（未實作）時，對話流程不中斷，只是沒有語音
- [ ] `CLAUDE.md` 不再出現 PyTorch Nightly / Blackwell sm_120 相關內容
- [ ] `routes/chat.py` 只透過 provider 物件呼叫三個服務，沒有直接 import 模組函式
- [ ] `pytest` 全部測試通過
- [ ] GitHub Actions CI 設定完成，且能成功觸發並跑完測試
