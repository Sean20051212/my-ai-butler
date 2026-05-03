# my-ai-butler

個人化 AI 虛擬管家專案。具備即時語音互動、自訂人格、長期記憶，以及螢幕內容理解能力。

## 硬體與底層環境

- GPU：NVIDIA RTX 5070 Ti（Blackwell 架構，`sm_120`）
- PyTorch：須使用 Nightly 版本（例如 `2.12.0.dev20260320+cu128`），以支援 50 系列顯卡
- 不可降回 PyTorch Stable 版本，否則無法使用 GPU 算力
- Nightly 版本的 API 可能有破壞性變更，需留意 `torchaudio` 與 `torchcodec` 的 C++ ABI 相容性

## 系統架構

採用本地與雲端混合的微服務架構，將 VRAM 優先保留給語音合成。

### 語音合成（本地）

- 使用 GPT-SoVITS（VITS 架構）
- 不採用 Fish Speech：自迴歸模型在 zero-shot 跨語言與少樣本場景下穩定度不足，曾出現聲碼器崩潰
- GPT-SoVITS 適用於 10–30 分鐘的小型資料集微調

### LLM 與記憶（混合）

- 推理任務透過雲端 API 處理（Claude、Gemini 等），不佔用本地 VRAM
- 長期記憶使用本地向量資料庫（ChromaDB 或 FAISS），以 RAG 機制注入歷史對話

### 視覺與情境感知

優先順序：

1. 擷取網頁 HTML DOM（BeautifulSoup、Playwright）
2. 讀取桌面無障礙樹（`pywinauto`）
3. 上述皆無法使用時，才以 VLM 進行截圖辨識

VLM 延遲與資源開銷較高，僅作為備用方案。

## 已知問題與處理方式

### 音檔讀取

`torchaudio` 與 `torchcodec` 綁定，並與 Windows 的 FFmpeg DLL 發生 ABI 衝突。處理方式：

- 改用 `soundfile` 搭配 numpy 讀取音檔
- 轉為 PyTorch Tensor 前呼叫 `.copy()` 確保記憶體連續
- 注意單聲道與雙聲道的維度對齊：`[channels, time]`

### TTS 訓練資料

- 訓練資料不可包含歌唱、背景音樂或殘響
- 5 分鐘乾淨人聲的訓練效果優於 30 分鐘含雜訊資料

### TTS 文字前處理

LLM 輸出包含過長段落、英文或特殊符號時，會造成 TTS 漏字或中斷。文字進入 TTS 前須經過：

- 英文轉中文拼音替換
- 生僻字過濾
- 依標點符號切分為短句（chunking）

## 開發慣例

- 上游函式庫不穩定時，於應用層撰寫 adapter 或 bypass 邏輯，不修改虛擬環境內的原始碼
- 視覺感知與文字處理優先使用純程式邏輯（DOM、文字解析），避免使用大型模型處理可結構化的資料
- LLM System Prompt 採用角色卡格式，包含 few-shot 對話範例
- LLM 輸出限制為口語化現代標準漢語，不使用排版符號與書面語，以利 TTS 處理

## 待辦事項

### 階段一：語音資料準備與訓練

- [ ] 使用 `pyannote.audio` 對長篇音檔進行語者分離，擷取目標角色片段
- [ ] 使用 UVR5（MDX-Net 或 VR Architecture）分離人聲與背景音樂
- [ ] 將音檔切分為 2–10 秒的短句
- [ ] 使用 FunASR 或 Whisper 進行文字標註，並人工校對
- [ ] 執行 GPT-SoVITS 的 SoVITS 與 GPT 權重微調

### 階段二：LLM 邏輯與文字前處理

- [ ] 實作文字前處理管線（切片、英文與符號過濾、拼音替換）
- [ ] 串接 LLM API，撰寫角色卡 System Prompt
- [ ] 建置 ChromaDB 或 FAISS，實作歷史對話向量化與 RAG 檢索

### 階段三：多模態整合

- [ ] 實作 HTML DOM 擷取腳本
- [ ] 將 LLM 串流輸出接入文字切片器，再送入 GPT-SoVITS 進行即時語音合成