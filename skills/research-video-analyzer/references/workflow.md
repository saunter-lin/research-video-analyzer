# 操作與資料契約

所有命令從專案根目錄執行：`.venv/bin/python scripts/va.py ...`。可在子命令前加 `--data /absolute/path --cache /absolute/path` 做隔離測試。預設 data 為專案 `data/`。僅支援單一寫入者，避免同時對同一研究執行修改命令。

## 研究模式與預算

新 Session 預設 `automatic`；既有無模式 Session 沿用互動，明確切換才遷移。模式切換不重設已用自動來源預算、選片或素材。快速／深度與選片模式獨立。

```sh
.venv/bin/python scripts/va.py research-policy SESSION_ID --mode automatic --max-auto-sources 3
.venv/bin/python scripts/va.py select SESSION_ID SOURCE_ID --actor automatic --reason '新增戶外麥克風測試線索；裝置仍待核對'
.venv/bin/python scripts/va.py research-policy SESSION_ID --mode interactive
```

自動模式由 Codex 搜尋、判讀、呼叫 CLI，並非常駐自主排程器。CLI 強制自動納入來源的累計上限；排除／切換模式不退還預算。預設每輪最多 4 組新查詢；依[缺口查詢與停止帳本](research-ledger.md)先計畫與保留額度，再搜尋、判讀及結算，CLI 與外部工具共用 Session.research_rounds。CLI 自動 discover 強制 reservation；外部工具須由 Codex 遵守先 reserve 的編排，不能宣稱全域硬攔截。每個新來源至多先取一次字幕；無測試線索不做全片 ASR。影片片段及影格沿用使用者的更小範圍與既有容量限制。有效快取優先，不為本輪刷新；來源選片額度與實際下載成本分開記錄。額外付費上限為 0，不讀取登入憑證。提高預算／額外費用先詢問；登入依下方 Computer Use 流程交由使用者手動完成，公開功能足夠時不要求登入。達上限可結案並列缺口，不必為用完額度再搜尋。

`--actor user` 僅記錄真正的使用者選擇；自動納入／排除用 `--actor automatic`，附實際理由。互動模式阻擋 automatic 選片。兩模式中未納入來源都無法取得字幕／影音。排除紀錄也保留 actor、時間與原因。

## 基本操作

```sh
.venv/bin/python scripts/doctor.py
.venv/bin/python scripts/va.py list
.venv/bin/python scripts/va.py create --title '耳機戶外通話' --question '現有耳機是否值得升級？' --seed 'https://www.youtube.com/watch?v=VIDEO_ID_11'
.venv/bin/python scripts/va.py show SESSION_ID
.venv/bin/python scripts/va.py inspect SESSION_ID SOURCE_ID
# 先依 research-ledger.md 建立計畫並逐筆 query-reserve，再使用回傳的精確 query
.venv/bin/python scripts/va.py discover SESSION_ID --reservation TOKEN --query '產品型號 戶外通話實測' --limit 15
.venv/bin/python scripts/va.py candidates SESSION_ID
.venv/bin/python scripts/va.py select SESSION_ID SOURCE_ID --reason '使用者訊息：選第 2、4 支'
.venv/bin/python scripts/va.py select SESSION_ID SOURCE_ID --exclude --reason '使用者排除搬運影片'
.venv/bin/python scripts/va.py acquire SESSION_ID SOURCE_ID --kind subtitles
.venv/bin/python scripts/va.py transcript SESSION_ID SOURCE_ID
.venv/bin/python scripts/va.py transcribe SESSION_ID SOURCE_ID --backend whisper.cpp --model base --language zh
.venv/bin/python scripts/va.py extract SESSION_ID SOURCE_ID --kind clip --start 62 --end 90
.venv/bin/python scripts/va.py extract SESSION_ID SOURCE_ID --kind frames --start 62 --end 90 --count 6
.venv/bin/python scripts/va.py cache-status
```

上例 ID 為佔位表示，須使用命令回傳的實際值。YouTube ID 格式 `youtube:影片ID`；Bilibili 格式 `bilibili:BV號:p1`。完整網址中的時間參數不產生新影片，Bilibili 各分 P 分開。BV／av 別名目前不保證自動歸併；短網址先展開完整連結。所有 CLI JSON 輸出供 Codex 讀取，不是內容分析的自動結論。

新增使用者提供影片：`import-candidates` 匯入後，依模式使用真實使用者指示或 AI 證據價值理由執行 `select`。同影片跨研究重用素材，但選片狀態不跨研究自動繼承。`update SESSION_ID changes.json` 可更新 question、products、context、conflicts、gaps，不會重下載或修改舊報告。

## 候選匯入

`import-candidates SESSION_ID candidates.json` 接受 JSON 陣列，供 B 站／外部搜尋結果使用。僅匯入實際查到的網址，不創造假來源：

```json
[{"url":"https://www.bilibili.com/video/BV123456?p=1","metadata":{"title":"實際標題","uploader":"作者","upload_date":null},"relevance":"針對指定測項","expected_value":"可能含戶外測試，尚未驗證","independence":"贊助與搬運未確認","source_group":null,"product_version":"未確認","recommended":true}]
```

完整候選表還應由 Codex 補充平台、發布日期、查詢與查核日期、來源連結、相關性、預期分析價值、推薦／排除理由及限制。腳本輸出的資料缺項標為未確認；不可把搜尋結果當已看過的實測。YouTube 搜尋結果亦可能缺日期，`inspect` 可做輕量補查，不下載媒體。

## 證據

`evidence SESSION_ID evidence.json` 一次匯入一項，回傳 evidence ID：

```json
{"source_id":"youtube:abcdefghijk","claim":"作者表示室內通話清楚，戶外尚無證據","claim_type":"reviewer_opinion","support":"low","reason":"只有講評，未核對測試錄音","conditions":"室內；距離未知","limitations":"未聆聽戶外收音","product_version":"未確認","verification":"字幕核對","artifact_key":"由 acquire／transcribe／extract 回傳的素材雜湊","start":62.5,"end":70.0,"excerpt":"實際原文摘錄"}
```

claim_type：`test_presented`、`reviewer_opinion`、`official_spec`、`official_marketing`、`unverified`、`inference`。
support：`high`、`medium`、`low`、`undetermined`，必附理由。`test_presented` 仍須在 verification 說明是作者報告結果或本次直接核對。支援／反駁關係可記 `supports`／`refutes`，在研究 conflicts 中明確保留。

素材綁定所屬來源；起訖採原影片秒數。`clip` 保存 offset；整片 ASR offset 為 0。外部分段逐字稿需先把時間加回原始偏移，不能直接匯入為整片時間。原有轉錄指令維持原行為；明確啟用的新音訊基礎流程另支援VAD區段與時間對齊，見audio-analysis.md。

## 報告

`report SESSION_ID analysis.json`：

```json
{"summary":"作者講評偏正面，但只有字幕支持 [E:實際證據ID]","topics":"戶外風噪待確認。","comparison":"條件不同，無法排序。","limitations":"缺少同場原音。","conclusion":"證據不足","evidence_ids":["實際證據ID"]}
```

四個文字欄位須為完成分析；重要主張用 `[E:12位證據ID]` 引用。evidence_ids 必須與文字引用集合一致。可輸出 Markdown 比較表。結論允許：建議購買／有條件購買／保留現有設備／不建議購買／證據不足／一般影片分析。缺現有設備與預算時不可假裝完成個人化評估。

Session 內 products 為產品／版本記錄、context 保存設備／預算／地區／幣別等，未指定時留空；未來網頁來源契約至少包含 role、URL、snapshot_hash、retrieved_at、verified_at、product_version。價格另含 currency、region、tax、shipping、promotion_conditions、checked_at。網頁快照與正式 Evidence 現由 [網頁與混合來源契約](web-research.md) 支援；上述自動擷取與價格驗證仍未實作。

## 快取與故障

SQLite 索引在 data，快取素材依種類存放；recipe key 含工具／模型／參數或內容雜湊，指向不可變的 artifact key。搜尋／metadata 預設 24 小時；`--refresh` 可指定刷新。字幕／ASR 不自動重取，來源字幕修訂須 `acquire --kind subtitles --refresh`。媒體取得最多 2GiB 單檔，整體快取 20GiB；平台實際下載大小不能只依 metadata 保證。

所有實際取得素材即保留 Session 副本，確保報告可追溯；data 因此可能增長，沒有自動清理。模型存 `.models/`，不計入快取。失敗作業不登記成功；下載暫存失敗會清除，重跑可重用已完成階段，但不保證網路下載位元級續傳。平台受阻時回報缺口，不自動讀 Cookie 或無限重試。requests-cache 非必要依賴；可選 document_intake.py 取得公開文件後仍須正式 import-web。

`acquire` 的取得錯誤維持 stderr JSON `status=blocked`、安全的 `error` 說明及 exit code 2，另附 `error_code`：

- `no_subtitles`：人工與自動兩輪皆成功完成，但均無繁簡英 VTT；不表示影片完全無任何語言字幕。
- `transient_network`：具型別的 timeout／連線／傳輸例外，或 HTTP 408、429、500、502、503、504；不代表沒有字幕，也不額外自動重試。
- `access_restricted`：HTTP 401、403、451 或明確地區限制例外；不推斷必須登入，依既有 Computer Use 流程確認。
- `unknown_failure`：其他取得失敗，包含只有文字訊息、TLS／憑證或代理錯誤；不憑訊息猜測原因。

上述分類僅包裝 yt-dlp 取得呼叫；選片、容量、快取與檔案保存驗證仍沿用原錯誤。原始 extractor 訊息不輸出至 CLI，避免簽名網址或憑證外洩。成功仍回傳原 artifact key；CLI 本身不自動啟動 Browser Use／ASR。Codex 研究流程應依下方瀏覽器字幕備援檢查已選取來源，不改人工字幕優先政策或既有字幕匯入契約。

## Quick／Deep 報告與完整附錄

研究深度與 automatic／interactive 選片模式獨立，不增加來源／搜尋預算。`report SESSION_ID analysis.json --mode quick|deep` 明確指定深度。預設 `auto` 依序讀 analysis.research_mode、context.research_mode，再判斷題目；要求至少五支影片比較、交叉驗證、完整研究預設 Deep，其餘 Quick。Codex 應將本輪意圖明確傳入 --mode，以涵蓋未寫進原 Session 的續作要求。使用者明確指定 Quick 優先。

Quick 回傳 `.decision.md` 精簡決策主報告。Deep 回傳 `.full.md` 完整研究主報告，涵蓋背景、產品比較、影片清單、逐片方法／條件、觀察結果、交叉驗證、使用情境、限制及最終建議。主報告的每個 `[E:ID]` 會展開為影片來源及時間戳連結，讀者不必打開附錄才能理解主要證據。來源與時間戳代表紀錄支持範圍，不代表全片已觀看；完整逐字稿不放主報告。

兩模式都另存 `.appendix.md`、原七節 `.md`（Legacy）和 `.json`，同一 revision／analysis_key，JSON 保存 mode、layout、context 與證據快照；新檔不覆寫舊報告。`--layout legacy` 保留舊輸出相容性。

Quick 可提供 decision：recommendation、comparison、confidence、key_limitations（一至三項）、next_step，總長最多 2400 字元（建議400–800中文字）。這個上限僅限精簡摘要，不限制 Deep 主報告。舊分析缺 decision 時沿用 summary／comparison／limitations，不宣稱自動精簡。

Deep 在原 summary、topics、comparison、limitations、conclusion、evidence_ids 外，必須提供：

```json
{"research_mode":"deep","deep":{"background":"研究需求、產品版本及範圍","cross_validation":"哪些影片一致、哪裡衝突、測試條件與獨立性如何影響解讀 [E:實際證據ID]","scenarios":"需求情境、維護取捨及不可外推之處 [E:實際證據ID]","recommendation":"有條件的最終建議與理由 [E:實際證據ID]"}}
```

逐片內容由本次 evidence 的 claim、conditions、verification、reason、limitations 產生；不得新增未記錄的方法、數值或觀察。已納入但無本次證據的來源明示缺口，不計為性能驗證。deep 不齊全時拒絕產生，不能默默降級成摘要。原四個文字欄位引用集合仍須與 evidence_ids 一致；deep 引用限本次 evidence_ids，交叉驗證、情境與建議需有引用。語意支持仍需 Codex 核對，不能把多支意見當成多組獨立實測。

Deep 排版補充（向後相容的可選欄位）：

- `report_context` 依主題補充情境，允許 current_device、budget、region、needs、phone。每欄為 `{"value":"RV30Plus","question_quote":"延續RV30Plus換機評估"}`；value 必須逐字出現在引句，引句必須逐字存在 Session 研究問題。程式驗證可核對性，Codex 仍須判斷語意是否確實為使用者提供的條件。不得把期望當產品實際能力，也不得以引句省略「待確認」等原有限定。原 context 不回寫，報告欄位與引句保存在 JSON analysis；context 有不同值時明列記錄差異，不擅自宣告最新值。缺值不固定顯示「未確認」；phone 僅在手機／耳機／通話主題呈現。其他主題可沿用相關的已記錄欄位，不印出原始 context JSON。
- `deep.comparison_table` 可提供帶證據引用的 Markdown 表格；未提供時沿用 comparison。原 comparison 留在 Legacy／appendix／JSON。
- `topics_in_cross_validation: true` 僅在主題內容已完整融入交叉驗證時使用，以免重複章節；未提供則保留補充主題。這是 Codex 的內容審核責任，不能只為縮短報告設為 true。
- `data_basis` 明示本輪取得與核對範圍；離線重編須寫明沿用何時保存的資料，以及沒有重新觀看、搜尋或下載。
- Deep 主報告採八節順序：背景、結論摘要、比較、逐片證據、交叉驗證、使用情境、限制、最終建議。結論摘要回答研究問題，交叉驗證解釋差異與可比性，建議說明選擇條件與待確認事項，避免逐節複述。
- 主報告不輸出 revision／analysis_key、Session conflicts／gaps JSON、快取路徑或分析窗口 bookkeeping。原始欄位、完整 reason、分析窗口註記與原情境保留在既有技術附錄／JSON；保留有實質意義的版本、翻譯、來源利益與測試限制。已知的 end 分析窗口註記僅在呈現時移除，原證據不變。

完成後用 Codex Desktop 開啟回傳的主報告，最終回覆附絕對路徑 Markdown 連結並只摘要結果。不要只提供 appendix 或 decision 連結代替 Deep。

context 中歷史提供但未再確認的設備／預算應記錄來源與確認狀態，不改成「未提供」。用 update 合併完整 context 建立新 revision；不回改舊報告。預算幣別不等於售價已查核。

## Computer Use 存取、登入與續接

本節由 Codex 透過 Computer Use 執行，不新增 CLI 登入器、不變更 Session schema 或字幕匯入契約。

1. 先查既有 Session、選片與有效快取，再使用 Computer Use 現有瀏覽器／分頁開啟目標 YouTube 或 Bilibili 影片。沿用該瀏覽器的登入狀態，不登出、不清除網站資料、不另建隔離瀏覽器。登入狀態只由網站可見 UI 判斷，不讀取瀏覽器設定檔或憑證。瀏覽器工具不可用時明示限制，不宣稱已驗證。
2. 在取得新資料前，實際確認影片身分、頁面及本次必要功能（例如逐字稿、字幕或指定片段播放）可正常存取。未登入但公開功能足夠就直接繼續；不因看見「登入」按鈕而要求登入。候選階段仍僅檢查 metadata／簡介／章節，未選取來源不得取得字幕或影音。
3. 若必要資料因未登入、登入過期或權限不足被阻擋，先記錄中斷點：Session ID、source ID、無敏感參數的影片標準網址、所需功能、阻擋原因、最後完成步驟、下一個未完成步驟，以及已完成素材／匯入結果的識別碼。使用既有 `show`／`update`，將非機密檢查點保存至 `context.computer_use_checkpoint`；更新時先讀取並合併完整 context，保留所有其他欄位。多個待處理來源以 source ID 分別保存。不得存登入網址中的授權參數、帳號資訊、頁面登入截圖或憑證。
4. 使用同一瀏覽器開啟對應網站官方登入頁（YouTube 使用網站「登入」入口至 Google 帳號頁；Bilibili 使用官方登入入口／登入頁）。驗證網域，避免搜尋廣告或第三方登入入口。隨即暫停 Computer Use 操作並通知使用者：「此來源的〔必要功能〕受登入／權限限制；已開啟官方登入頁，請在瀏覽器手動完成後告知。也可選擇跳過此來源或改用其他來源。」不要要求先授權開啟登入頁，也不要代填、提交或觀察登入過程。不得索取密碼、驗證碼、Cookie、Token，不匯出或另存登入憑證，不把瀏覽器憑證轉交 CLI／下載工具。
5. 使用者回覆登入完成後，讀回原 Session 與檢查點，返回原影片重新檢查必要功能；不能只憑使用者回覆或頭像判定可用。確認可用後從下一個未完成步驟續接，完成後標記該檢查點已解決。沿用既有選片、預算、素材與快取，不重建 Session、不重跑搜尋或已完成取得／匯入；不自動 `--refresh`。登入頁開啟失敗或不具自動續傳能力時，如實說明並保留檢查點。
6. 登入失敗、使用者取消、登入後仍缺權限，或原因其實是下架／地區限制／無字幕／網路錯誤時，不反覆要求登入或無限重試。說明可觀察到的限制，提供「跳過此來源」與「改用其他來源」選項；替代來源依原選片模式與剩餘預算處理，互動模式仍等待使用者選片。保留既有選片與證據，依選擇更新檢查點及 gaps，不把受阻作業登記為成功，也不將缺失資料當作證據。需要購買或額外授權時另詢問，不自行付費或繞過限制。

## Browser Use 字幕備援

適用於已選取影片的 CLI 字幕取得失敗，或使用者明確要求以瀏覽器檢查字幕。沿用上節的 Session、快取、登入與續接規則；切換取得方式不另建研究 Session、不重跑產品報告。CLI 失敗、影片播放、字幕取得與內容判讀各自記錄，不因其中一項受阻就放棄其他可用來源。

自動接續：Codex 收到上述失敗後，在既有授權與預算內直接執行本節，不把「請使用者手動打開 DevTools／複製字幕」當作預設下一步。Bilibili 的 UI 操作、回應保存及匯入讀回依 [DevTools 自動操作流程](devtools-subtitles.md)；工具缺失或登入阻擋時保留中斷點。這項自動化由目前 Codex 工作階段執行，`acquire` 原有 exit code／錯誤契約不變，單獨執行 CLI 不會啟動 UI。

1. 使用目前可用的 Browser Use／Computer Use 工具，優先連接現有瀏覽器及目標分頁。若瀏覽器整合未暴露 Edge 分頁，但原生應用程式操作可用，可改由該工具操作現有 Edge；不要因此另開未登入的瀏覽器，也不要宣稱有工具未提供的網路攔截或匯出能力。依實際工具文件操作，不臆造 API。
2. 核對影片 URL／ID、分 P 及標題。YouTube 檢查逐字稿入口與工具實際提供的字幕匯出功能；Bilibili 開啟播放器「字幕」，優先人工原語言軌，其次原語言 AI 軌。看到「中文 AI」等選項只證明有該選項，選取後須確認切換成功，並檢查實際字幕文字。翻譯軌另標記，不能當原語言逐字稿。
3. 優先取得帶時間戳的完整逐字稿或網站／工具實際支援的字幕匯出；驗證原文、時間排序、影片身分與涵蓋範圍後保存。沒有匯出能力時，可讀取可及性樹／DOM 的當前字幕；若只能截圖辨讀，標記為畫面人工轉錄並核對文字。畫面內嵌字幕與可切換的平台 AI 字幕要分開，不能混成同一軌。
4. 只有當前字幕可讀時，可依研究問題查看必要片段，保存播放器所示時間、原文、語言、AI／人工／未知來源、取得方式及日期，標記「局部字幕觀察，非完整轉錄」。取樣時刻不等於字幕 cue 起點；未知起訖保留未知，不以取樣時刻偽造 cue 時間。不得把跳看、稀疏截圖或局部片段宣稱為全片字幕，也不以摘要補齊漏段。需要逐段擷取全片時，先評估既有時間／來源預算，無法驗證連續性就保留缺口。
5. Bilibili 完整字幕可透過現有瀏覽器的 DevTools「網路」面板取得：先以字幕資源網域／路徑篩選（本次 AI 軌為 `aisubtitle`），再切換中文 AI 觸發請求。核對目標分 P 的 CID 與字幕請求身分，檢查 200 回應的「回應」分頁，使用「複製回應」保存 JSON 原文。不要複製 URL、cURL、fetch、要求標頭或整份 HAR；它們可能包含簽名參數／登入資料。只有本體字幕 JSON 及不敏感的影片 URL、CID、語言、取得時間與方法進入匯入清單。工具不支援這些 UI 操作時，據實保留限制，不能改讀憑證或臆造端點。
6. 正式匯入使用下節的 YouTube TXT 或 Bilibili 原生 AI JSON 契約，不得偽裝平台、直接寫 SQLite／artifact slot 或將字幕冒充網頁快照。局部 UI 觀察不是完整 JSON，不套用本入口。字幕 artifact 保存後，主張仍須另外建立 Evidence，不把「匯入成功」當作內容已分析。
7. 若瀏覽器也無法取得完整字幕，記錄各階段結果及具體限制，再依既有授權與預算考慮 ASR／人工核對；不自動啟用原本停用的 ASR、不讀取 Cookie、不無限重試、不因必要功能未受阻而要求登入。繼續分析其他可用來源。

對外狀態應分列：CLI 錯誤碼；瀏覽器字幕選項；切換及當前文字是否成功；取得範圍；完整字幕檔是否保存；正式匯入狀態。`unknown_failure` 只描述 CLI 取得路徑，不能寫成「影片沒有字幕」。產品結論不得由字幕取得狀態推導；另有系統驗收報告時，將取得與匯入限制寫在驗收報告，產品報告保留與結論相關的證據缺口。

實測（2026-10-24）：現有 Edge 的 Bilibili `BV1Wogf6vEPj:p1` 中文 AI 回應 34,389 bytes，共 210 段，sid 1～210 連續，範圍 0～512.02 秒，播放器片長 513 秒；片頭 00:02、片中 04:19、片尾 08:29 的 UI 文字均對應 JSON。正式 CLI 在隔離 data/cache 完成匯入、210 段起訖／文字逐項比對、原檔 SHA-256 比對及重複匯入去重。詳見驗證報告（歷史驗證資料未隨公開候選散布）。這是整條平台字幕軌擷取成功，不代表每個語音皆被平台辨識、全片人工校對或其他影片必定成功；末尾 0.98 秒沒有 cue，未補造。

## Computer Use 外部字幕（明確啟用、離線）

`import-subtitles SESSION_ID manifest.json` 僅處理已選取來源，沿用 create、import-candidates、select 入口；不探索、不下載。JSON 清單中的 file 相對於清單目錄：

```json
[{"video_id":"abcdefghijk","url":"https://www.youtube.com/watch?v=abcdefghijk","subtitle_source":"YouTube auto-generated via Computer Use","file":"transcript.txt"}]
```

省略 format 或指定 `youtube-txt-v1` 時，沿用 Computer Use YouTube TXT：`YouTube transcript`、`Video ID: ...`、`Language: en`（可缺）、`Captions: auto-generated` 標頭，接著 `[m:ss] 原文` 或 `[h:mm:ss] 原文`。不接受摘要替代。每段保存 source_line、raw_timestamp、start、text，end=null、end_status=unknown；不推算 cue end。Evidence 仍須選取有效主張範圍並揭露推算依據，未知末段不得補造終點。

Bilibili 原生 AI JSON 指定 `format=bilibili-json-v1`；直接匯入瀏覽器取得的完整 JSON 本體，不改字、不四捨五入、不轉成 YouTube TXT。清單範例（日期／CID／片長依實際觀察填寫）：

```json
[{"format":"bilibili-json-v1","source_id":"bilibili:BV1Wogf6vEPj:p1","url":"https://www.bilibili.com/video/BV1Wogf6vEPj?p=1","subtitle_source":"Bilibili 中文 AI via Edge Network response","file":"subtitles.raw.json","cid":"40346979438","language":"zh","caption_type":"auto-generated","captured_at":"2026-10-24T14:53:00+08:00","capture_method":"browser_network_response","coverage":"full_response","video_duration":513}]
```

支援觀察到的 `type=AIsubtitle`、`lang`、`body[].from/to/content/sid` 結構。source_id 必須符合 URL 的 BV／av 及分 P；CID 為正整數字串，取得時間須含時區，語言及 AI 來源須相符。JSON 本體不含影片 ID／CID，清單綁定仍依瀏覽器核對，不能宣稱匯入器獨立證明影片身分。只允許字幕本體欄位與上述清單欄位；不接受額外標頭／Cookie／簽名網址欄位。SRT／VTT、人工軌及截圖轉錄尚未納入此格式。

保留原始浮點 from/to 為 start/end、end_status=provided，以及 source_json_path／sid；檢查有限非負數值、end>start、時間排序、cue 不超過已觀察片長與非空原文。非連續 sid、重複段落保留並警告。coverage.declared 保存 full_response／partial／unknown，並記錄首尾時間與 cue 數；full_response 是完整回應本體的取得聲明，不能由首尾時間自動升級成全片語音無漏字／人工驗收。partial／unknown 不與 full_response 混用快取版本。

整批驗證後才匯入；錯誤回傳 blocked 與原始檔定位，不刪原文、不修正文字。相同時間／相同段落保留並警告；其他未知行、無文字、負數或非數時間、倒序、ID/URL不符、缺來源、UTF-8損壞會阻擋整批。來源不明需人工確認後再送。

來源ID＋字幕來源＋內容hash去重；YouTube 內容hash包含語言及逐段開始／原文，Bilibili 另含原始結束時間、caption_type，去重身分另含 CID／coverage／片長。原始bytes另存SHA-256，匯入時間、清單hash、原始檔案路徑與原檔artifact均保存。首次成功匯入的來源記錄保持不變；跨Session重用同一內容；相同內容重新匯出但bytes不同不新增字幕版本，第二次提交的檔案仍由呼叫端保存。新版本／語言用獨立artifact slot，不覆寫既有字幕或ASR。`transcript` 回傳既有優先軌及全部外部字幕軌，消費端依origin/language選用。

不呼叫 import-subtitles 即停用取得功能；移除外部模組時也需移除CLI分派，已匯入JSON仍可由transcript讀取。不需新增依賴、修改Evidence Schema或執行資料遷移。

## 多來源研究

已納入影片的公開評論可作補充，依[影片評論契約](video-comments.md)取樣。`import-comments SESSION_ID manifest.json` 離線保存，`comments SESSION_ID SOURCE_ID` 讀回所有已保存版本；Evidence 使用 source_type=comment 與 locator.comment_id，報告與字幕／片中實測分開標示，不接受影片秒數定位。

網頁與影片共用 Session、來源選取及 Evidence；網頁以 `source_type=web` 匯入候選，再以 `import-web` 保存已擷取文字，流程及範例見 [網頁研究](web-research.md)。`一般研究分析` 為新增中性結論，舊 `一般影片分析` 仍有效。

## 預設語意分析後端

使用者提出研究問題時，依 [Antigravity 委派、免費配額與 Codex 接手契約](antigravity-backend.md) 自動安排 `analyze`、語意審核及 `backend-finish`；保留本文件全部取得、預算、Evidence、Quick／Deep 與報告契約。不得把 CLI 回傳接手要求當作研究已完成。
