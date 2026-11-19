# Research / Video Analyzer 1.4.0 開源準備評估

> 2026-11-19 授權收尾更新：原創程式／專案文件已採 MIT，四項 MIT 參考來源完整通知已保留，版本為 `1.4.0`，GitHub Repository 已公開；散布範圍為不含套件／模型／二進位／歷史素材的原始碼。下文的 LICENSE 待定／NO-GO 為前兩輪歷史結論，不代表目前尚未放置 LICENSE。詳見[授權收尾](license-closure.md)。原先不確定的作者歷史與提示詞衍生限制仍如實保留，沒有改成「完全原創」證明。


查核日期：2026-11-19（Asia/Taipei）。範圍為既有穩定工具的獨立公開候選整理，採 Python CLI 核心 + Agent Skill，不啟動新研究工具專案，也不改正式安裝。依專案規則，本次屬既有專案維護，不重做 3～5 個替代方案的完整新專案預研。

## 前兩輪結論（歷史紀錄，現況見上方更新）

**當時結論：授權尚未收尾，判定 NO-GO；其後已完成 MIT 與來源通知整理，Repository 現已公開。**

獨立候選可安裝、可不用 Codex 執行，具備合成離線範例、雙語文件、Skill、CI 定義與回歸驗證。原創程式權利歸屬、最終 LICENSE、精確版本第三方授權／通知與依賴發行策略仍待確認，故未放置 LICENSE，不能宣稱已取得整套環境的自由商用／散布許可。沒有建立 GitHub Repository、Push、Release 或呼叫付費 API。

2026-11-19 第二輪已完成[外部 Skill 來源追溯與授權審查](external-skill-provenance.zh-TW.md)：Humanizer 的直接收錄屬 Courseware／Storyboard；AnySearch 的 Research owning source 明示延後與當輪未呼叫；其餘分成設計參考與有支持性證據的本地重新實作。比對未見設定門檻的長片段相同，仍無法排除翻譯／短段衍生，不能認定完全原創。MIT 仍屬有條件建議；授權未確認的 LDJ 來源若日後確認有實質複製，須先處理。此輪僅更新文件，既有封裝檔不含新增審查報告。

建議原創程式採 **MIT**，理由是 CLI／Agent 整合採用門檻低、授權通知簡單；若重視明確專利授權，可選 Apache-2.0。選擇須由權利人確認。這項建議不覆蓋第三方套件、FFmpeg build、模型或研究來源素材的權利。

## 一、架構與功能盤點

| 層／模組 | 保留能力 | 公開版邊界 |
|---|---|---|
| `scripts/va.py` | CLI、Session revision/history、SQLite、hash、pin、cache、選片、Evidence、Quick/Deep、JSON/附錄 | 演算法未重寫；只有封裝、runtime、預設資料路徑與 Node 發現方式的小幅調整 |
| `research_ledger.py` | gap、query-plan、搜尋前 reservation、有效增量、獨立來源與停止帳本、取消 | 原樣保留；外部 Agent 搜尋仍須遵守契約，CLI 無法全域攔截外部工具 |
| `web_sources.py`／`video_comments.py`／`external_subtitles.py` | 離線快照、原文引句、行號／時間戳、已選來源閘門 | 原樣保留；來源內容權利與個資由操作者處理 |
| `audio_analysis/`、ASR worker／metrics | 可選本機 VAD、ASR、時間映射、hash 與快取 | 預設關閉；不下載模型，不將工具輸出當作音質真值 |
| `antigravity_backend.py`／entry | Schema／引用驗證、配額不足才一次 fallback、付費限制、host 接手與審核 | 保留；啟動請求增加目前 interpreter 與獨立 Store 路徑傳遞；macOS guard 仍必要 |
| `document_intake.py`／benchmark | 公開 HTTPS／arXiv 選擇性收件、本機後端比較 | 原樣保留，選配依賴；缺專用回歸覆蓋 |
| Skill | 研究編排、證據分類、預算、研究深度、瀏覽器字幕備援與模型審核 | 自含 SKILL.md + references，可單獨複製；CLI 不依賴 Skill loader |

核心來源約 3,200 行 Python，現有正式測試 152 項。詳細目錄與最小變更見 [architecture.md](architecture.md)。沒有加入服務、付費 SDK 或新應用框架；標準 setuptools／wheel 僅用於 Python 封裝。保留 legacy modules 匯入方式，尚不承諾穩定 in-process SDK。

## 二、安全與隱私審查

- 原正式 launcher、runtime 與文件含個人絕對路徑，runtime 也指向正式模型／工具。公開版已改為通用入口、私有設定及相對設定解析。
- 正式 `data/`、歷史研究、報告、快取、SQLite、`.backups`、`research-ab`、歸檔、環境、模型與工具二進位均未複製到公開候選；不用把 `.gitignore` 當成已清除歷史的證明。
- 對正式來源／文件／歷史的限定文字掃描檢查了 **2,084 個檔案、66,306,237 bytes**，另有 259 個不符文字／大小條件的檔案略過；853 個檔案出現個人家目錄樣式，2 個檔案出現 token／簽名 query 樣式，2 個檔案出現已知 Token 外形，沒有 private-key header 命中。遮罩檢視後，token／簽名 query 命中來自合成測試；Token 外形來自歸檔 Google／Kaggle 網頁內嵌設定，並非已確認的個人金鑰。未驗證其有效性，仍整批排除歸檔，不複製值。掃描不輸出憑證值；詳細數量見 [摘要](production-risk-summary.json)。未進行全面姓名／電話／個資辨識，二進位與外部 cache 亦非完整掃描範圍。
- 公開候選、wheel 與 source archive 均完成 forbidden-file／private-path／常見金鑰樣式掃描，結果零命中；source archive 亦成功重建 wheel，並通過零選配套件測試組。原正式來源 50 個盤點檔案以 SHA-256 比對，內容未變。
- 原專案根目錄沒有 `.git`；候選也沒有攜入 Git 歷史。未來若匯入其他既有 Git 歷史，須另掃完整 objects/history；本次無法為未提供的歷史背書。
- 本機 manifest 可指定檔案，不是可直接對外開放的上傳 API。來源文字是不可信資料；保留已選來源與內容審核規則，不把 prompt injection 內容當指令。

## 三、第三方授權與相依

原環境 lock 有 36 筆、可選文件 intake lock 有 18 筆，重疊保留共 **54 筆**；已逐筆查讀現有套件 metadata，54 筆版本均與 lock 一致，並記錄宣告授權與 notice 檔名。這是本機 metadata 核對，不是完整原始碼、wheel 內容或安全弱點稽核。完整表見 [THIRD_PARTY.md](../THIRD_PARTY.md) 與 [JSON](dependency-inventory.json)。

| 風險 | 判定與處理 | 後續使用／散布仍須確認 |
|---|---|---|
| 原創程式權利／貢獻 | 未看到可沿用的專案 LICENSE；第二輪逐來源追溯確認設計借鑑，未證實直接收錄；特定提示詞衍生仍證據不足，不能認定完全原創 | 權利人、貢獻與任何未標註引用，決定 MIT／Apache-2.0 後再加入 LICENSE |
| GPL／MPL 相依 | mutagen GPL-2.0-or-later；certifi MPL-2.0；tld 含 MPL/GPL/LGPL 選項；不隨原始碼候選散布套件 | 最終 dependency route、選定授權、必要通知及未來 bundled distribution 義務 |
| FFmpeg／PyAV／wrapper | wrapper BSD 不代表 FFmpeg BSD；正式環境紀錄為 GPL-enabled build | 精確 binary build／link 組合與散布義務；本候選不附任何 binary |
| 模型／歸檔素材 | 歷史模型與 ESC-50 非商用素材全部排除 | 未來如重新加入，逐一核對精確版本、來源、通知及商用範圍 |
| 文字／字幕／評論／影音 | 研究取得權不等於再散布權 | 實際來源權利／條款／個資，公開範例限自寫合成內容 |

上游查核來源：[yt-dlp 發行形式授權差異](https://github.com/yt-dlp/yt-dlp#licensing)、[faster-whisper MIT](https://github.com/SYSTRAN/faster-whisper/blob/master/LICENSE)、[FFmpeg 官方授權](https://ffmpeg.org/legal.html)、[Trafilatura Apache-2.0](https://raw.githubusercontent.com/adbar/trafilatura/master/LICENSE)。來源為當日可取得頁面，未全數固定到每個 pinned release 的 commit。

## 四、最小分離修改與安裝

1. 新增 `pyproject.toml`、console adapter、wheel／sdist file manifest；公開套件與內部核心版本統一為 `1.4.0`。
2. 核心執行期依賴為標準庫；影片、音訊、文件與 benchmark 改成選配 extra。原 lock 保留為歷史清單，避免誤稱為跨平台可解析的公共 lock。
3. 預設 Store 與 cache 為 `~/.local/share/research-video-analyzer`／`~/.cache/research-video-analyzer`，可用 CLI 或環境變數指定；不寫 site-packages，不重用正式 Store。
4. 私有 `RESEARCH_RUNTIME` 設定模型；移除個人 shebang 與 Codex 內建 Node 路徑，Node 只讀 PATH；預設 analysis provenance 改成 Human or Agent，不假稱來自 Codex；doctor 不安裝、不下載、不呼叫模型。
5. Skill 獨立在 `skills/research-video-analyzer`，保留完整研究契約並說明 legacy 指令映射；沒有改動目前已啟用的 Skill。
6. 測試只調整依賴正式路徑／歸檔的假設，增加隔離、設定與引用報告整合驗證；Evidence、預算與模型驗證邏輯不改。

安裝、實際 CLI 範例與 Skill 安裝見 [英文 README](../README.md)、[繁中 README](../README.zh-TW.md)、[安裝文件](install.md)、[Agent 文件](agents.md)。Codex 本機 Skill 搜尋路徑以 [官方文件](https://learn.chatgpt.com/docs/build-skills) 核對。其他 Agent 的 shell 呼叫具可攜性，但尚未在其 Skill loader／權限系統完成端到端驗收。

## 五、測試與未解決問題

| 驗證 | 結果 | 限制 |
|---|---|---|
| 原版隔離基線 | 152/152 通過 | 既有本機 dependencies/models 只讀；不代表線上取得或真實媒體驗收 |
| 公開候選完整回歸 | 158/158 通過、0 skip | 151 個保留契約 + 歸檔排除契約 + 6 個可攜整合測試；選配環境使用原 interpreter 只讀 |
| 零選配套件核心組 | 71 項，67 通過、4 明確 skip | 4 個 yt-dlp mocking 測項由完整回歸覆蓋 |
| 乾淨 venv + wheel | `--no-index --no-deps` 安裝成功，help／doctor／Skill 路徑與合成流程成功 | 核心無 runtime dependencies；沒有從 package index 全新安裝所有 extras |
| 真實 CLI 合成流程 | 建 Session、選來源、import-web、原文 Evidence、引用報告讀回成功 | example.com 自寫文字，沒有外部取得、真實產品／語音結論 |
| 覆蓋率 | stdlib trace 敘述行 1,934/2,726 = 70.95% | 僅目前 process、沒有 branch／subprocess coverage；intake／benchmark 缺專用測試 |
| Skill 格式 | skill-creator quick validator 通過 | 不代表 Agent 真實決策與 host 整合驗收 |
| CI | Linux/macOS、Python 3.11/3.12/3.13 core matrix + 3.12 完整回歸定義完成 | 尚未上傳 GitHub，因此沒有遠端 CI 執行結果 |

未解決事項依優先順序：

- **發布阻擋：**原創權利／最終 LICENSE 未確認；精確第三方授權、依賴散布路線與通知需維護者確認。
- **功能相容性：**原生 Windows 不支援 fcntl／resource；Linux core 與 CI 定義尚未遠端執行；Antigravity 仍限 macOS guard，其他 Agent 的 host 操作與 legacy provenance 名稱需適配。
- **外部可用性：**既有模型 ID／免費基礎配額並非永久承諾；這次不呼叫 agy、不查帳號額度、不試付費 API；CLI 保留失敗接手與驗證閘門。
- **驗證缺口：**全新 extras 安裝、套件索引可用性、各平台 native wheel、線上影片取得、瀏覽器字幕、真實 ASR／聽感、文件 intake 與 benchmark 專用測試尚未完成。
- **資料可搬移性：**既有 Session 可含絕對 artifact 路徑；本階段不遷移正式資料、不宣稱歷史 Session 可直接搬機。

完整執行與覆蓋率說明見 [testing.md](testing.md)。現階段適合審閱獨立候選並處理授權，不應直接公開宣稱完整跨平台、所有 Agent 原生相容或所有選配功能已在乾淨環境驗收。
