# my-ai-butler

個人化 AI 虛擬管家專案。具備即時語音互動、自訂人格、長期記憶，以及螢幕內容理解能力。

## 本地端環境

- 本地端只需要 Ollama（LLM 與 VLM 推論），不需要額外管理 PyTorch/CUDA 環境。
- TTS 已改為雲端語音克隆服務，語音合成不再佔用本地 VRAM。

## 系統架構

採用本地與雲端混合的微服務架構，`services/` 下的 LLM、TTS、Vision 各自為可插拔的 provider 抽象層（`abc.ABC` 基底類別 + factory 依環境變數選擇實作）。

### 語音合成（雲端）

- 改接雲端語音克隆服務（廠商未定，先以 `BaseTTSProvider` + `CloudTTSProvider` 骨架保留擴充點）。
- 候選方案：ElevenLabs / Azure Speech / PlayHT，皆支援聲音克隆與多語言。
- provider 未實作時，TTS 快取層會優雅回傳 `None`，對話流程不中斷、只是沒有語音。

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

LLM 輸出包含過長段落、英文或特殊符號時，會造成 TTS 漏字或中斷。文字進入 TTS 前須經過（`utils/text.py` 的 `preprocess_for_tts()`，雲端 TTS 同樣適用）：

- 英文轉中文拼音替換
- 生僻字過濾
- 依標點符號切分為短句（chunking）

## 開發慣例

- 上游函式庫不穩定時，於應用層撰寫 adapter 或 bypass 邏輯，不修改虛擬環境內的原始碼
- 視覺感知與文字處理優先使用純程式邏輯（DOM、文字解析），避免使用大型模型處理可結構化的資料
- LLM System Prompt 採用角色卡格式，包含 few-shot 對話範例
- LLM 輸出限制為口語化現代標準漢語，不使用排版符號與書面語，以利 TTS 處理

## 待辦事項

### 階段一：雲端 TTS 串接

- [ ] 決定雲端語音克隆廠商（ElevenLabs / Azure Speech / PlayHT）
- [ ] 在 `CloudTTSProvider.synthesize()` 實作 API 呼叫，API key 透過環境變數管理
- [ ] 準備聲音克隆所需的乾淨人聲樣本（不含歌唱、背景音樂或殘響）

### 階段二：LLM 邏輯與文字前處理

- [x] 實作文字前處理管線（切片、英文與符號過濾、拼音替換）
- [x] 串接 LLM provider，撰寫角色卡 System Prompt
- [x] 建置 ChromaDB，實作歷史對話向量化與 RAG 檢索

### 階段三：多模態整合

- [x] 實作 HTML DOM / 無障礙樹 / VLM 多層次擷取
- [ ] 將 LLM 串流輸出接入文字切片器，再送入雲端 TTS 進行即時語音合成
