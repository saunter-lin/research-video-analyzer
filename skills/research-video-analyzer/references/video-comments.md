# 影片評論取得與證據契約

公開評論可補充使用情境、長期回報、不同觀點、作者留言補充與待查問題。評論者自述有購買／實測經驗仍是自述；沒有原始素材與可比條件，就不提升成片中實測或官方規格。影片作者留言也必須與影片正文分開標示。

## 取得與取樣

先重用已保存評論快照；只處理已納入影片，不為評論另建正式研究。以現有瀏覽器／可用工具讀取公開評論，沿用登入規則，不讀 Cookie、不安裝外掛。Bilibili 評論可能延遲載入：捲到評論區後再讀可及性樹／DOM，初次「正在玩命加载」不代表沒有評論。頁面只顯示部分內容或受阻就保留缺口，不影響其他來源。

預設為輕量補充：每支至多查看 20 則熱門、10 則最新頂層評論，必要回覆僅展開與問題相關者，合計至多 50 則；已有較小範圍優先，不需湊滿。兩種排序都無法取得時明示限制。需要超出此輪取樣預算再詢問；使用者指定全量時另評估可行性，不宣稱一次載入即為全部。選入正式引用的理由須針對研究問題，保留支持、反對與矛盾內容，記錄已查看與實際保存範圍，不能只挑認同既有結論的評論。

記錄影片身分、取得時間、排序、取樣範圍、原文、公開暱稱、網站顯示發布時間、按讚數與回覆關聯。未知值用 null；縮寫讚數不能猜精確值。只保留研究所需公開資料，不擷取個人聯絡資料或無關私人資訊。圖片／影片附件未核對就說明僅擷取文字，不能由評論圖片標籤推論內容。

平台評論 ID／永久連結必須由實際頁面或合法可用工具取得，不能從帳號 ID 或 UI 元素索引推測。若沒有平台 ID，使用穩定的快照本地 ID，例如 `local:` 加影片 ID／暱稱／日期／原文的內容 hash，標為 `id_kind=snapshot_local`；不冒充平台評論 ID，permalink 留 null。回覆保留 parent_id；缺父留言時明示上下文未取得，不把回覆誤當獨立評論。

## 離線匯入

`import-comments` 不連線、不搜尋、不發文。綁定現有已選取影片，不新增候選或消耗另一支影片的自動選片名額；評論數與快照數不等於獨立來源數。若評論指向新的原始測試或外部來源，另走候選／選取與剩餘預算，不自動納入。

保存實際取得的文字為 `comments.raw.json`（正規化後的觀察紀錄，不冒稱平台原生 JSON）：

```json
[{"comment_id":"local:實際計算的hash","id_kind":"snapshot_local","author":"實際公開暱稱","text":"逐字原文","published_at":"網站顯示的日期原文","likes":null,"parent_id":null,"author_role":"unknown","permalink":null}]
```

`author_role` 只接受 unknown，或經網站 UP／作者標誌核對的 video_author；暱稱相同不足以認定。平台 ID 則填 `id_kind=platform`。permalink 可省略或填實際觀察到的同影片標準 URL 加錨點；目前不支援跳往另一頁型態的評論連結，不為滿足欄位而編造。原文保持不動，摘要寫在分析裡。

建立 manifest（source_id／url 以 CLI identity 為準，Bilibili 各分 P 分開；網站評論若共用整片頁面需在 sampling_scope 說明，不能推定特定分 P）：

```json
{"source_id":"bilibili:BV1Wogf6vEPj:p1","url":"https://www.bilibili.com/video/BV1Wogf6vEPj?p=1","file":"comments.raw.json","retrieved_at":"2026-10-24T15:00:00+08:00","capture_method":"Edge native accessibility text","sort_order":"hot","coverage":"partial","sampling_scope":"熱門已載入列表中保存的相關頂層評論；未展開回覆；未核對圖片"}
```

sort_order 為 hot／new／unknown；coverage 只接受 partial／unknown，不以 UI 取樣宣稱全量。單檔 5MiB、1～1000 則為匯入器上限，不代表自動取得預算。

```sh
.venv/bin/python scripts/va.py import-comments SESSION_ID manifest.json
.venv/bin/python scripts/va.py comments SESSION_ID bilibili:BV1Wogf6vEPj:p1
```

回傳 artifact_key。原始 JSON bytes、解析快照、取得方式與取樣條件一併保存，hash 去重；新日期／文字另存快照，不覆寫已引用資料。完整驗證後才寫入；未知欄位、錯誤影片、重複 ID、無原文、錯誤按讚值或時間格式會阻擋。這是結構驗證，不能驗證留言誠信。

## 評論 Evidence 與報告

```json
{"source_id":"bilibili:BV1Wogf6vEPj:p1","source_type":"comment","artifact_key":"實際key","locator":{"comment_id":"快照中實際ID"},"excerpt":"該評論中逐字存在的原文","claim":"某評論者回報的使用情境／意見","claim_type":"reviewer_opinion","support":"low","reason":"只支持該評論者如此表述；未驗證購買或測試","conditions":"依留言描述；版本未知","limitations":"局部樣本、身分與獨立性未知","product_version":"未確認","verification":"保存評論原文與頁面核對"}
```

excerpt 必須逐字存在於指定評論，不能只在另一則找到。評論不用 start/end；不能以發文日期、評論排序或內文提到的秒數偽造影片時間定位。claim_type 可為 reviewer_opinion、unverified、inference；原始性能測試／官方說明須取得相應來源後另建 Evidence。support 應針對主張：評論能支持「此人提出這個看法」，不代表能支持產品性能。

沿用既有 `evidence`、Quick／Deep／Legacy 報告與 `[E:ID]`。引用呈現「影片評論」、ID 類型、暱稱、發布時間、取得日期及局部取樣標記，不生成影片秒數連結。Deep 顯示評論證據性質與取樣方式，與同影片字幕／實測各自引用。

分析時辨識反串、疑問、轉述、廣告、抽獎、重貼與同一討論串；熱門排序、讚數與多個帳號都不等於獨立驗證或母體比例。重複引用影片說法的評論仍按同源理解；自述不同經驗者的獨立性保持未知，不能一律視為影片轉載，也不能一律視為獨立實測。不用少量負評估算故障率、不用沒人提及推導不存在。與官方文件或影片相衝突時保留兩方條件，標記待查，不硬選贏家。
