# Bilibili DevTools 字幕自動操作

此流程供 Codex 在研究中操作現有瀏覽器 UI，銜接既有離線匯入器；沒有新增瀏覽器驅動、CDP 連接器或背景服務。搜尋詞：DevTools、Network、aisubtitle、複製回應、CID、import-subtitles。

## 入口與停止條件

- 已納入的 Bilibili 影片，沒有滿足本次語言／範圍需求的有效字幕快取，且 CLI 字幕取得受阻，或使用者指定瀏覽器取得時啟動。人工字幕優先；目前原生 JSON 匯入格式只支援 AI 軌，人工軌不可偽裝成 AI。
- 先讀 `show` 與 `transcript`，確認 source ID、分 P、選取及已用預算。沿用同一 Session；切換取得路徑不新增來源名額，也不刷新有效素材。離線重編報告不啟動此流程。
- 沿用已開啟的瀏覽器與登入狀態。必要登入／權限阻擋依 [登入續接](workflow.md#computer-use-存取登入與續接)保存中斷點並交由使用者登入；不操作憑證。
- 每來源每輪先作一次字幕載入／擷取。若確定只是未觸發請求，可在同頁重新切換該字幕軌一次；仍失敗即記錄原因、繼續其他來源。一般 UI 定位修正不算重新下載；不持續重載頁面或循環重試，不自動提高研究預算。

## 工具與 UI 編排

1. 讀取當前 Computer Use 工具文件及瀏覽器／應用程式 inventory。若瀏覽器整合未提供既有 Edge 分頁，使用原生 Edge app 操作。不要猜測工具存在網路攔截、剪貼簿讀取、匯出或檔案寫入 API；只用實際提供的能力。不為取得字幕另啟遠端除錯埠、安裝擴充功能或改瀏覽器設定。
2. 核對標準影片 URL、標題、分 P 與播放器片長。用當前可見的頁面／DevTools 資訊確認該分 P 的 CID；無法可靠核對就停止正式匯入。不要把 BV 號當 CID，也不要以另一分 P 的回應代替。
3. 透過瀏覽器選單或工具文件支援的快捷鍵開啟 DevTools，選「網路／Network」。每組 UI 動作後取得最新可及性樹，必要時看截圖，再選擇下一個元素；不硬編碼歷史座標或跨觀察沿用元素索引。
4. 先以已觀察到的字幕資源關鍵字篩選（既有成功案例為 `aisubtitle`），再在播放器選取原語言 AI 字幕以觸發載入。核對字幕軌切換及實際文字，不把選項存在當作已取得字幕。頁面載入舊請求不能單憑排序當作本次目標。
5. 在篩選結果中核對目標 CID、狀態 200 與 Response／回應的 JSON 本體。字幕資源路徑改變時可從本次可見 UI 重新辨識，不能猜測平台端點或重播簽名 URL。核對回應含 `type=AIsubtitle`、`lang`、`body[].from/to/content/sid`，並與播放器可見原文抽查對應。
6. 使用選中請求的「複製回應／Copy response」。不複製 URL、cURL、fetch、要求標頭或 HAR。以工具實際支援的 UI 貼上／儲存能力把回應本體保存為 UTF-8 純文字 `subtitles.raw.json`；例如經文字編輯器的純文字文件存檔。不可經過模型重述、重新拼接或修字來製造原始檔。工具無法無損存檔時，標記 `response_save_unavailable` 並停止正式匯入，不能以截斷的 AX 文字補成完整檔。
7. 儲存使用本輪獨立目錄，例如 `data/research_runs/<本輪名稱>/<來源名稱>/`，不覆寫既有回應。確認檔案存在、UTF-8 可解碼、JSON 可解析並計算 SHA-256。只保存字幕本體和非機密 provenance；請求網址與敏感要求資訊不進入檔案或操作紀錄。避免擷取未篩選的 Network 面板或登入頁截圖。

工具不支援必要 UI 操作時，據實標記 `tool_unavailable`；只有局部字幕可讀時標記局部觀察，不走完整回應匯入入口。繼續其他可用來源，ASR 仍依原授權、可用音訊與預算判斷。

## 保存、匯入與讀回

依 [Bilibili JSON 契約](workflow.md#computer-use-外部字幕明確啟用離線)產生 manifest，填入本次實際核對的 source_id、標準 URL、CID、語言、AI 來源、取得時間、片長及 `capture_method=browser_network_response`。只有保存完整回應本體才能宣告 `coverage=full_response`；首尾 cue 接近片長不能單獨證明完整性。

循序執行，僅在上一步成功後續作；SESSION_ID 與路徑必須換成真實值：

```sh
.venv/bin/python scripts/va.py import-subtitles SESSION_ID /absolute/path/manifest.json
.venv/bin/python scripts/va.py transcript SESSION_ID SOURCE_ID
```

檢查匯入回傳 `status=ok` 及該來源的 `imported`／`reused`／`duplicate` 狀態，取得 artifact key。`transcript` 可能同時回傳多軌，須依 key、來源、語言確認本次軌，而非一律採第一軌。對照原檔與保存 raw artifact 的 SHA-256，逐段比對 `from/to/content` 與讀回 `start/end/text`、cue 數及涵蓋範圍。CLI 匯入驗證失敗就保留原檔與錯誤，不直接寫 SQLite、不修改原文來通過檢查。

字幕取得成功後，由 Codex 判讀本題相關區間，另走既有 `evidence` 及 Quick／Deep 報告流程。JSON 匯入不等於已完成內容分析，也不代表平台轉錄正確或已核對動態畫面／原音。

## 狀態與驗證邊界

在本輪 acquisition 紀錄中分列 CLI error_code、瀏覽器字幕選項、切換／文字可讀、影片／分 P／CID 核對、回應保存、coverage、cue 數／首尾、原檔 hash、匯入狀態及 artifact key、讀回驗證、阻擋原因與下一步。既有狀態採追加更新，保留先前失敗；不新增 Session schema。需中斷續接時，讀取並合併既有 context 後使用 `update`，不清空其他情境。

既有 2026-10-24 驗證案例（歷史驗證資料未隨公開候選散布）已驗證一片 AI 軌的 UI 取得與正式匯入。此處將其操作納入預設備援編排；其他影片、介面變動及無人值守可靠性仍須實測，不以文件更新宣稱完成新一輪端到端驗收。
