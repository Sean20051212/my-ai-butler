# my-ai-butler 重構計畫 v2（已對照實際程式碼）

> 本文件給 Claude Code 在 `my-ai-butler` 專案內執行重構使用。所有方向已經拍板確認，**不需要再詢問是否要做，只需要詢問實作細節上的疑問**（例如某個函式命名、某個邊界情況怎麼處理）。
>
> v2 與 v1 的差異：v1 的方向完全保留，v2 額外把每項任務對照了**實際原始碼**，補上 v1 沒寫到的真實細節（介面回傳型別、殘留狀態欄位、啟動驗證、import 位置等），避免重構時踩到計畫與現況不一致的坑。

## 專案現狀（重構前，已實際核對）

```
backend/
├── app.py                  # FastAPI 入口；lifespan 第 9、17 行 import 並呼叫 start_vision_loop
├── config.py                # 環境變數讀取；結尾有 TTS_REF_AUDIO_PATH 啟動驗證警告
├── models/character.py       # CharacterState dataclass：trust/stress/energy + is_chatting + latest_vision
├── routes/chat.py            # /chat 端點，直接 `from backend.services import llm, tts`
├── services/
│   ├── llm.py               # OpenAI client 指向 Ollama；get_dynamic_system_prompt() + call_llm()
│   ├── tts.py                # get_audio()（hash 快取）+ _call_gptsovits()（寫死 GPT-SoVITS HTTP）
│   ├── vision.py             # start_vision_loop()：背景執行緒 8 秒輪詢隨機區域丟 llava
│   └── memory.py             # ChromaDB + Obsidian vault RAG（做得好，不動）
└── utils/text.py             # preprocess_for_tts() + converter（做得好，不動）
test_brain.py / test_vision.py   # 根目錄裸測試腳本，無斷言
requirements.txt / .env.example  # 待更新
CLAUDE.md                        # 含過時的 PyTorch Nightly 環境說明
```

### 對照實際程式碼後，務必注意的現況

- **LLM 不是「寫死呼叫 Ollama」的原生 client**：`llm.py` 用的是 `openai.OpenAI`，`base_url` 指到 `{OLLAMA_BASE_URL}/v1`、`api_key="ollama"`。
- **`call_llm()` 回傳的是 OpenAI completion 物件**，不是字串。實際的 JSON 解析、artefact 正則清洗（`<|im_start|>` 等）、`converter.convert()` 繁簡轉換，全部都在 `routes/chat.py` 第 39–55 行，**不在 llm.py 裡**。
- **`state.is_chatting`** 目前唯一用途是讓 vision 背景迴圈在對話時暫停（`vision.py` 第 36 行、`chat.py` 第 23/82 行）。移除背景迴圈後，這個欄位與 `character.py` 第 8 行「Shared between the vision background thread and the chat endpoint」的 docstring 都會變成殘留。
- **`config.py` 第 30–32 行**有針對 `TTS_REF_AUDIO_PATH` 的啟動驗證警告，屬於 GPT-SoVITS 專屬，移除 TTS 本地路線時要一併清掉。
- **`.env.example` 第 6–10 行**是 GPT-SoVITS TTS 段落（`TTS_API_URL` / `TTS_REF_AUDIO_PATH` / `TTS_PROMPT_TEXT` / `TTS_PROMPT_LANG`）。
- **`requirements.txt` 確認沒有** `torch` / `torchaudio` / `torchcodec`（符合 v1 假設）。
- **`CHAT_MODEL` 預設 `qwen2.5:7b`、`VISION_MODEL` 預設 `llava`**，皆為正規模型，符合「不得使用 uncensored/abliterated 版本」的約束。

## 已確認的六項決策（同 v1，不變）

1. **LLM**：先維持 Ollama 本地推論，但做成可切換 provider 架構，雲端先留擴充點、不實作。**模型只能用一般正規模型（如 `qwen2.5:7b`、`qwen3.5:9b`），不得使用任何 "uncensored"／"abliterated"／移除安全機制的版本。**
2. **視覺感知**：移除背景常駐 8 秒輪詢，改成按需觸發；採多層次優先序 DOM → 桌面無障礙樹 → VLM 截圖（VLM 為最後手段）。
3. **TTS**：放棄 GPT-SoVITS 本地路線，改接雲端語音克隆服務（廠商未定，先做抽象層 + 骨架）。
4. **本地推論環境**：移除 PyTorch Nightly 設定與踩坑紀錄。
5. **服務介面**：`services/` 全部拆成有明確抽象基底類別的設計，共用同一套模式。
6. **測試與 CI**：導入 pytest，根目錄裸腳本改寫成有斷言的測試；新增 GitHub Actions CI。

---

## 任務一：LLM Provider 抽象層

**目的**：把 `services/llm.py` 從「OpenAI-client 寫死指向 Ollama」改成「可切換的 provider 架構」。

1. 新增 `backend/services/llm/` 套件（取代現有的 `backend/services/llm.py` 單檔）：
   - `base.py` — 抽象基底類別 `BaseLLMProvider(abc.ABC)`，定義 `@abstractmethod chat(messages: list) -> str`。
     - **回傳契約（重要）**：`chat()` 回傳**原始回覆文字字串**，即現行 `response.choices[0].message.content` 的內容。**不要**在 provider 內做 JSON 解析或繁簡轉換——那些留在 `chat.py`。
   - `providers/ollama_provider.py` — 把現有 `llm.py` 的 OpenAI client 與 `call_llm()` 邏輯搬進來實作 `BaseLLMProvider`。注意把回傳從「completion 物件」改成「`.choices[0].message.content` 字串」，並保留 `response_format={"type":"json_object"}`、`temperature=0.4`、`model=CHAT_MODEL`。
   - `prompts.py` — `get_dynamic_system_prompt(state)` 與 provider 無關，整段（含角色卡 few-shot）搬到這裡獨立。
   - `providers/cloud_provider.py` — 骨架 `CloudLLMProvider(BaseLLMProvider)`，`chat()` 先 `raise NotImplementedError("雲端 provider 尚未實作，待後續決定要接哪家 API")`，留清楚 TODO。
   - `factory.py` — `get_llm_provider()` 依環境變數 `LLM_PROVIDER`（預設 `"ollama"`）回傳對應實例。
2. `config.py` 新增 `LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")`。
3. `.env.example` 新增 `LLM_PROVIDER=ollama` 與註解說明（含「cloud 尚未實作」字樣）。
4. `routes/chat.py`：
   - `from backend.services import llm` 改為透過 factory 取得 provider。
   - 第 28 行 `llm.get_dynamic_system_prompt(state)` 改為 import 自 `services.llm.prompts`。
   - 第 39 行 `response = llm.call_llm(messages)` + 第 40 行 `raw_content = response.choices[0].message.content` 兩步，合併成 `raw_content = llm_provider.chat(messages)`。
   - **第 43–55 行的 artefact 正則清洗、`converter.convert()`、`json.loads`、空 reply fallback 全部保留在 chat.py 不動。**
5. **驗收**：`LLM_PROVIDER` 設成不存在的值時，factory 丟出清楚錯誤（含可用清單），而非靜默失敗。

---

## 任務二：視覺感知改為按需觸發 + 多層次優先序

**目的**：移除常駐輪詢，改成「對話時才嘗試感知一次」，且優先用結構化資料而非螢幕截圖。

1. 新增 `backend/services/vision/` 套件：
   - `base.py` — 抽象基底類別 `VisionSource(abc.ABC)`，`@abstractmethod capture() -> str | None`（回傳場景描述，抓不到回 `None`）。
   - `dom_source.py` — Playwright 嘗試抓當前作用中瀏覽器分頁 DOM，摘要成一句話；抓不到回 `None`。
   - `accessibility_source.py` — `pywinauto` 讀當前作用中視窗無障礙樹組成簡短描述；失敗回 `None`。
   - `vlm_source.py` — 把現有 `vision.py` 的 `_vision_client` / `_VISION_PROMPT` 搬過來，並把 `_capture_random_region()` 改成「截取目前作用中視窗畫面」而非隨機區域，丟 `llava` 描述。最後手段。
   - `chain.py` — `VisionChain`，依序 `DomSource → AccessibilitySource → VlmSource`，回傳第一個非 `None` 結果；`get_vision_chain()` factory。
2. **移除** `start_vision_loop()` / `_loop()` 整段背景執行緒邏輯。`app.py` 第 9 行 import 與第 17 行呼叫一併刪除（lifespan 只保留 character、memory 初始化）。
3. **清理殘留狀態**：背景迴圈移除後，`state.is_chatting` 失去用途——
   - 移除 `chat.py` 第 23、82 行對 `is_chatting` 的設定，以及 `character.py` 的 `is_chatting` 欄位。
   - 更新 `character.py` 第 8 行 docstring，移除「Shared between the vision background thread」字樣。
   - （若擔心相容性風險，可保留欄位但加註 deprecated；預設做法是直接移除。**此處有疑問再問。**）
4. `CharacterState.latest_vision` 改成每次 `/chat` 即時呼叫 `VisionChain` 取得，不再背景更新。加一個簡單 TTL 快取（例如同一作用視窗 5 秒內重複問不重抓），避免每次對話都跑完整 fallback chain。
5. `routes/chat.py` 在組裝 system prompt 前呼叫 `vision_chain.capture()`，結果塞進 `state.latest_vision`（prompt 注入邏輯與第 36 行現況一致）。
6. **驗收**：模擬 DOM/無障礙樹都抓不到 → fallback 到 VLM；模擬 DOM 抓到 → 不會多打無障礙樹或 VLM。

---

## 任務三：TTS 改為雲端語音克隆服務

**目的**：移除本地 GPT-SoVITS 呼叫，改成可插拔雲端 provider，廠商未定先留擴充點。

1. 新增 `backend/services/tts/` 套件：
   - `base.py` — 抽象基底類別 `BaseTTSProvider(abc.ABC)`，`@abstractmethod synthesize(text: str) -> bytes | None`。
   - `providers/cloud_provider.py` — 骨架，`synthesize()` 先 `raise NotImplementedError`，註解列出常見可選方案（ElevenLabs / Azure Speech / PlayHT，皆支援聲音克隆與多語言）供之後決定。所需 API key 設定先寫進 `.env.example`，但用註解標「未啟用」。
   - `cache.py` — 把現有 `tts.py` `get_audio()` 第 25–39 行的 hash 快取邏輯（含 `preprocess_for_tts` 先處理、空字串回 `None`、`AUDIO_CACHE_DIR.mkdir`）抽成獨立、與 provider 解耦的快取層，任何 provider 共用。
   - `factory.py` — `get_tts_provider()` 依環境變數選 provider（預設先回 cloud 骨架）。
2. **移除**：
   - `tts.py` 的 `_call_gptsovits()` 整段（第 42–67 行）。
   - `config.py` 的 `TTS_API_URL` / `TTS_REF_AUDIO_PATH` / `TTS_PROMPT_TEXT` / `TTS_PROMPT_LANG`（第 15–19 行），以及第 30–32 行 `TTS_REF_AUDIO_PATH` 啟動驗證警告。
   - `.env.example` 第 6–10 行 GPT-SoVITS TTS 段落。
   - `requirements.txt` 若有僅供舊 TTS 用的依賴需檢查（目前 `requests` 仍被使用，視保留情況決定）。
3. **保留不動**：`utils/text.py` 的 `preprocess_for_tts()`——雲端 TTS 一樣需要乾淨中文輸入。
4. `routes/chat.py` 第 69 行 `tts.get_audio(reply_text)` 改成透過 `tts_provider`（經 `cache.py` 包裝）呼叫。
5. **驗收**：`synthesize()` 在 provider 未實作時，整條路徑要優雅回 `None`（對話繼續、只是沒語音），**不可讓 `/chat` 噴錯**。注意：cloud 骨架的 `NotImplementedError` 要被快取層或 chat 流程吞掉成 `None`，而非往上拋。**（此處的「在哪一層攔截 NotImplementedError」若有疑問再問。）**

---

## 任務四：清理 PyTorch Nightly 相關環境設定

**目的**：移除已不再需要的本地深度學習環境負擔。

1. 更新 `CLAUDE.md`：移除「硬體與底層環境」整段（PyTorch Nightly、Blackwell sm_120、torchaudio/torchcodec ABI 衝突），改寫成一句「本地端只需要 Ollama，不需額外管理 PyTorch/CUDA 環境」。
2. 檢查 `requirements.txt`：已確認沒有 `torch` / `torchaudio` / `torchcodec`，無需改動。
3. `CLAUDE.md`「已知問題與處理方式」段落：移除「音檔讀取」（torchaudio/torchcodec/soundfile 那段）、「TTS 訓練資料」中與 GPT-SoVITS 本地訓練直接相關的內容；「TTS 文字前處理」邏輯保留（雲端 TTS 一樣需要），改寫成不提 GPT-SoVITS 特定坑。
4. 連帶更新「系統架構 → 語音合成（本地）」與「待辦事項 → 階段一」中關於 GPT-SoVITS 本地訓練的描述，改成反映雲端 TTS 方向。

---

## 任務五：服務介面層統一重構

**目的**：讓任務一、二、三的 provider 抽象層風格一致，並統一 `services/` 呼叫方式。

1. 確認 LLM / Vision / TTS 三個抽象基底類別風格一致：同樣 `abc.ABC` + `@abstractmethod`，同樣有 factory 函式依環境變數選實作。
2. `routes/chat.py` 重構後在端點內（或模組層級）取得三個服務物件：
   ```python
   llm_provider = get_llm_provider()
   vision_chain = get_vision_chain()
   tts_provider = get_tts_provider()
   ```
   取代現行第 9 行 `from backend.services import llm, tts`。
3. `memory.py` 維持現狀不變——增量索引、優雅降級已完整，不套 provider 抽象層。
4. **驗收**：`routes/chat.py` 不再出現對 `services.llm`、`services.tts`、`services.vision` 模組層級函式的直接呼叫，全部透過 provider 物件。

---

## 任務六：測試框架與 CI

**目的**：補齊正式測試並設定自動化驗證。

1. `requirements.txt` 新增：`pytest`、`pytest-asyncio`、`httpx`（FastAPI `TestClient` 依賴）。
2. 新增 `tests/` 目錄：
   - `tests/test_chat.py` — 用 FastAPI `TestClient` 測 `/chat`，**mock 掉 LLM provider**（不真打 Ollama），同時 mock vision 與 tts provider，驗證：回 200、內容含 `reply` 欄位、LLM 回傳格式錯誤（非合法 JSON）時走 fallback 訊息（即 chat.py 第 78–80 行 except 分支或第 52–54 行空 reply fallback）。
   - `tests/test_llm_provider.py` — 測 factory 依 `LLM_PROVIDER` 正確選 provider；未知名稱丟明確錯誤。
   - `tests/test_vision_chain.py` — mock 三層 source，驗 fallback 順序（DOM 成功不呼叫無障礙樹/VLM；DOM 失敗、無障礙樹成功不呼叫 VLM）。
   - `tests/test_tts.py` — 驗快取命中（同段文字第二次不重複呼叫 provider）；驗 provider 未實作時優雅回 `None`。
3. 根目錄 `test_brain.py`、`test_vision.py` 整合進對應 `tests/` 檔後刪除。
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
   （`runs-on` 用 `windows-latest`；若 CI 跑 Linux 有問題再切換。註：`pywinauto` / `mss` 在 Linux runner 上會有相容性問題，測試需確保這些只在 mock 後使用、import 不在模組頂層硬性失敗。**此風險若浮現再決定是否改 Linux + skip。**）
5. **驗收**：本機 `pytest` 全綠；CI 設定檔語法正確，push 後 Actions 能觸發並跑完。

---

## 整體驗收清單

- [ ] `LLM_PROVIDER=ollama` 時行為跟重構前一致，可正常對話
- [ ] `LLM_PROVIDER=cloud` 時明確報錯（NotImplementedError），不靜默失敗
- [ ] 未知 `LLM_PROVIDER` 值時 factory 丟出含可用清單的清楚錯誤
- [ ] 對話時才觸發視覺感知一次，背景不再有 8 秒輪詢 print log
- [ ] `is_chatting` 殘留狀態已清理（或明確標記保留原因）
- [ ] 視覺感知優先序正確：DOM → 無障礙樹 → VLM，且具 TTL 快取
- [ ] TTS 呼叫雲端 provider 骨架（未實作）時對話不中斷，只是沒語音
- [ ] `config.py` / `.env.example` 不再有 GPT-SoVITS 專屬設定與啟動驗證
- [ ] `CLAUDE.md` 不再出現 PyTorch Nightly / Blackwell sm_120 相關內容
- [ ] `routes/chat.py` 只透過 provider 物件呼叫三服務，無直接 import 模組函式
- [ ] `pytest` 全部通過
- [ ] GitHub Actions CI 設定完成，且能成功觸發並跑完測試
