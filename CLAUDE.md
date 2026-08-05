# my-ai-butler

個人化 AI 虛擬管家專案。具備即時語音互動、自訂人格、長期記憶，以及螢幕內容理解能力。

## 本地端環境

- 本地端需要 Ollama（LLM 與 VLM 推論），不需要額外管理 PyTorch/CUDA 環境。
- TTS 採本地 CosyVoice2 微調語音（芙卡洛斯／芙寧娜聲線），跑在 WSL2 的 `cosyvoice` conda 環境，透過常駐 HTTP 服務對外提供；佔用約 2.4GB VRAM，與 Ollama `qwen2.5:7b` 可同時共用 16GB 顯卡。

## 系統架構

採用本地與雲端混合的微服務架構，`services/` 下的 LLM、TTS、Vision 各自為可插拔的 provider 抽象層（`abc.ABC` 基底類別 + factory 依環境變數選擇實作）。

### 前端與 Live2D（Electron 桌寵）

- 前端為 Electron 視窗（`main.js` + `index.html`），透過 HTTP 呼叫後端 `/chat`。
- Live2D 角色為芙寧娜，模型在 `model/Furina/`（VTS 版、檔名已 ASCII 正規化，`model3.json` 接了 happy/sad/surprised 三個表情）。
- 渲染 runtime 是 **PixiJS v8 + `untitled-pixi-live2d-engine`（`live2d-engine.min.js`，底層為官方 Cubism 5 SDK）**。**不可換回 guansss 的 `pixi-live2d-display`**：芙寧娜模型有網格用到 20+ 個裁切遮罩，超過該庫寫死的 16 上限會渲染崩潰（`not supported mask count`）；此引擎會自動啟用 high-precision mask 才能顯示。
- 對嘴用引擎的 `model.speak(blobURL)`（需 `pixi-sound.min.js`），會在正確時機驅動 `ParamMouthOpenY`；不要用自寫的每幀 `setParameterValueById`，會被 update 蓋掉。
- 鏡頭與凝視是可即時調的參數：Console 可呼叫 `frameModel({zoom,x,y})` 與 `lookAt(nx,ny)`（凝視走 `focusController` 正規化座標，與視窗大小無關）。預設鏡頭為上半身特寫、凝視 (0,0) 正前方。

### 語音合成（本地 CosyVoice2）

- 使用微調完成的 `CosyVoice2-0.5B-fukalos-final` 模型（芙卡洛斯／芙寧娜聲線），以 zero-shot 方式合成。
- 模型跑在 WSL2 的 `cosyvoice` conda 環境（PyTorch nightly，配合 RTX 5070 Ti），由 `tts_service/butler_tts_server.py`（純標準庫 `http.server`）常駐載入一次、對外提供 `POST /tts` 與 `GET /health`。
- Windows 後端的 `CosyVoiceTTSProvider`（`TTS_PROVIDER=cosyvoice`）負責把回覆文字繁→簡（`tw2sp`）後 HTTP 呼叫該服務取回 WAV；`start.bat` 會自動先把 WSL 服務帶起來並健康檢查。
- `CloudTTSProvider` 骨架保留，未實作時 TTS 快取層優雅回傳 `None`，對話流程不中斷、只是沒有語音；WSL 服務未啟動時亦同（provider 連線失敗回 `None`）。

### LLM 與記憶（混合）

- LLM 走可切換 provider：目前預設 Ollama 本地推論（`qwen2.5:7b`），雲端 provider 留擴充點。
- 模型只能用一般正規模型，不得使用任何標榜 "uncensored"、"abliterated"、移除安全機制的版本。
- 長期記憶使用本地向量資料庫（ChromaDB），以 RAG 機制注入歷史對話。

### 視覺與情境感知

按需觸發（對話時感知一次），依優先序嘗試，回傳第一個成功的結果：

1. 擷取網頁 HTML DOM（Playwright，需瀏覽器開啟 remote debugging port）
2. 讀取桌面無障礙樹（`pywinauto`）
3. 上述皆無法使用時，才以 VLM 截取作用中視窗辨識

VLM 延遲與資源開銷較高，僅作為最後手段。

## 已知問題與處理方式

### TTS 文字前處理

LLM 輸出包含過長段落、英文或特殊符號時，會造成 TTS 漏字或中斷。文字進入 TTS 前須經過（`utils/text.py` 的 `preprocess_for_tts()`）：

- 英文轉中文拼音替換
- 生僻字過濾
- 依標點符號切分為短句（chunking）

## 開發慣例

- 上游函式庫不穩定時，於應用層撰寫 adapter 或 bypass 邏輯，不修改虛擬環境內的原始碼
- 視覺感知與文字處理優先使用純程式邏輯（DOM、文字解析），避免使用大型模型處理可結構化的資料
- LLM System Prompt 採用角色卡格式，包含 few-shot 對話範例
- LLM 輸出限制為口語化現代標準漢語，不使用排版符號與書面語，以利 TTS 處理

## 待辦事項

### 階段一：本地 CosyVoice2 TTS 串接

- [x] 微調 `CosyVoice2-0.5B-fukalos-final` 芙卡洛斯／芙寧娜聲線（詳見 `HANDOFF.md`）
- [x] WSL 常駐推論服務 `tts_service/butler_tts_server.py`（載入模型一次、`/tts` + `/health`）
- [x] Windows 後端 `CosyVoiceTTSProvider`（繁→簡 + HTTP）串接、`start.bat` 自動啟動 WSL 服務
- [ ] 延遲優化：用 `add_zero_shot_spk` 預先快取 prompt 音檔，縮短單句合成時間（目前約 13-15s）

### 階段二：LLM 邏輯與文字前處理

- [x] 實作文字前處理管線（切片、英文與符號過濾、拼音替換）
- [x] 串接 LLM provider，撰寫角色卡 System Prompt
- [x] 建置 ChromaDB，實作歷史對話向量化與 RAG 檢索

### 階段三：多模態整合

- [x] 實作 HTML DOM / 無障礙樹 / VLM 多層次擷取
- [ ] 將 LLM 串流輸出接入文字切片器，再送入 CosyVoice TTS 進行即時語音合成
