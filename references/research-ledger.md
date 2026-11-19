# 缺口查詢計畫與停止帳本（1.4.0）

自動研究的 CLI discover 與外部搜尋共用 Session.research_rounds；來源、Evidence、歷史與 artifact cache 仍由既有 Store 保存。先 list／show／research-status，沿用研究、預算與快取，不為用完額度而搜尋。

## 計畫與搜尋前保留

```sh
./video-analyzer research-status SESSION_ID
./video-analyzer research-plan SESSION_ID query-plan.json
./video-analyzer query-reserve SESSION_ID QUERY_ID
```

status 只讀回 gap IDs、目前輪次、已用來源與 cache。已有 gaps 時沿用原文；沒有 gaps 時以原研究問題建立虛擬缺口，不改寫 Session.gaps。只規劃本題需要的查詢，不必湊四組。

計畫例子（gap_id 換成 status 實際回傳值）：

```json
{"max_new_queries":4,"queries":[{"gap_id":"gap-實際ID","provider":"yt-dlp YouTube","query":"指定產品 同場實測 測試條件","purpose":"尋找同裝置、環境與方法的原始對照","expected_value":"可能補足同條件測試；取得前不代表支持主張","budget":{"query_groups":1,"max_new_sources":1,"max_new_candidates":10,"cache_bytes":1048576,"paid_api_calls":0}}]}
```

計畫自動綁定既有 Evidence IDs。purpose 與 expected_value 是搜尋理由，不是證據。max_new_sources 是本查詢最多自動納入數，max_new_candidates 是最多新增候選；重用來源可設 0。cache_bytes 是搜尋結果快取寫入預算；影音取得仍受原選片規則、單檔限制與全域 20GiB admission 約束，不因查詢而擴大下載。

計畫回傳 query_id；reserve 回傳 reservation、精確 query、provider、預算與已用量。每個 query 字串算一組；三個字串不能算成一次批量呼叫。本版只允許一筆待完成 reservation，因此逐筆執行、判讀再續搜。CLI discover 的 provider 固定為 `yt-dlp YouTube`；外部工具名稱須如實填寫。

reserve 在搜尋前檢查：至多四組及更小既有上限、歷史累計自動來源、候選池 30、cache 20GiB 與零付費。provider／query 完全相同（NFKC、大小寫與空白正規化）以 fingerprint 攔截，不自動合併同義或跨語言句。失敗、取消與中斷不自動退還已用查詢，不自動重試或提高上限。

## 執行與搜尋結果

CLI YouTube：

```sh
./video-analyzer discover SESSION_ID --reservation TOKEN --query 'reservation 回傳的原查詢' --limit 10
```

自動模式未傳 reservation 會在網路前被拒絕。同一 reservation 不可換 provider、換查詢、塞多組或重送。成功到 awaiting_evidence；metadata 不算 Evidence，也不在內容判讀前立即視為零價值。

外部搜尋先 reserve，成功後才用回傳的精確字串呼叫工具，不能先搜尋後補帳。之後：

```sh
./video-analyzer query-search-result SESSION_ID TOKEN search-result.json
./video-analyzer import-candidates SESSION_ID candidates.json --reservation TOKEN
```

結果檔：`{"status":"completed","result_count":3,"reason":"公開搜尋完成，內容待核對"}`。工具受阻／失敗用 status=blocked|failed 與安全原因，停止本輪；不保存簽名 URL、登入資訊或敏感錯誤。候選仍依原流程選片；select --actor automatic --reason 同時檢查歷史來源上限與本查詢增量。

外部工具不是此 CLI 子程序；CLI 無法攔截直接繞過 reservation 的外部呼叫，必須由本 Skill 編排遵守。不得宣稱已全域攔截所有工具，也不能以新 Session、新計畫檔名規避預算。

## 內容判讀與有效增量

沿用原字幕／快照／影音取得、hash 與分類；判讀來源內容後，以本次 token 匯入 Evidence：

```sh
./video-analyzer evidence SESSION_ID evidence.json --reservation TOKEN
./video-analyzer query-complete SESSION_ID TOKEN review.json
```

review 例子：

```json
{"reviews":[{"evidence_id":"正式匯入回傳的ID","gap_id":"原計畫gap-ID","basis":"source_content_review","addresses_gap":true,"relevance_reason":"原文或實測如何補足此缺口，保留方法與限制","independence_basis":"reviewed_original_content","independence_reason":"已核對原始發布者與素材來源，非轉載；未知不能這樣填"}]}
```

無符合項目用 `{"reviews":[]}`。只可引用本 token 匯入且非 baseline 的 Evidence。舊證據、相同內容／定位／主張以新 ID 複製、錯 gap、LLM confidence、inference、unverified、undetermined 均不能計有效增量。未知獨立性填 unknown；不能捏造判讀理由。舊 Evidence 永不覆寫、gap 不自動關閉。

帳本分開記搜尋回傳數、觀察到的 Evidence、有效增量、獨立來源增量、來源／cache 用量與 stop_reason。origin_source_id 共同根來源不重複算；轉載自稱 original 仍不算新增獨立來源；缺 origin 也不證明獨立。字幕、評論與作者意見保留原有證據限制，不以數量判斷產品勝負或關閉 gap。

零有效增量留下 zero_new_value 並停止。前筆待判讀時不得 reserve 下一筆。Session 歷史保留計畫與事件，重啟不清空額度或自動重搜。中斷在 reserved／searching 時先 status：外部既有結果可依原 token 補錄，或取消；不重送 discover、自動開新輪次。

## 取消、舊研究與新輪次

```sh
./video-analyzer query-cancel SESSION_ID TOKEN --reason '使用者取消或必要資料受阻'
```

取消 token marker 原子保存，不等待網路作業持有的 writer lock。CLI 回應後及提交候選／搜尋快取前再查取消，Evidence 提交與取消共用短鎖。取消後拒絕遲到候選、Evidence 與完成 receipt。取消前已提交的 Evidence／素材保留，不刪除或回滾；也不能撤銷已送出的外部請求。marker 在 status 即可見，下次寫入帳本時同步到 Session 歷史。

首次 research-plan 將最新舊 round 的 queries、queries_used 與較小 max_new_queries 保守遷移，原 round 不變。沒有舊 round 但有 searches 時計入既有查詢。格式無法核對則停止，不假定額度未用。升版不批次寫入舊 Session，只在明確對該 Session 執行 plan 時建立帳本。

已有計畫時 plan 只補候選，不重設已用額度、不改寫原查詢或其預算；較小上限不自動提高。本輪停止就保留缺口結案。只有真正使用者明確要求新研究輪次，才使用：

```sh
./video-analyzer research-plan SESSION_ID new-plan.json --new-round --actor user --reason '引用使用者本次明確續作要求'
```

新輪次保留歷史與來源消耗、沿用較小查詢上限，不代表同意付費、增加來源或擴大研究；不得將 AI 自行決定記作 user。模式切換、重啟、改檔名與排除來源都不退還額度。
