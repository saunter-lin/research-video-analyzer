# Antigravity 分析後端（Research 1.4.0）

使用者仍只需說「研究 XXX」。Codex 是主控、排程者及最終報告負責者；Python CLI 不會自行召喚另一個 Codex 或呼叫模型 API。既有來源、Evidence、Session、SQLite、搜尋前 query-reserve、預算與停止條件繼續有效。

## Codex 編排

1. 沿用 list/show/research-status、查詢計畫、來源選取與素材取得。每個外部搜尋仍須先 query-reserve；後端不搜尋、不提高預算。先以正式 evidence 入口保存已核對的證據，保留 ID。
2. 有待處理的大量字幕、跨來源比較、Evidence 分析或報告草稿時，優先 `./video-analyzer backend-launch SESSION_ID`，取得固定入口的 host tool_request；目前 Codex 用 `exec_command` 的 `require_escalated` 發起該命令，並以回傳 prefix_rule 建議窄範圍可重用授權。這只是請求，不代表已授權。Python 不自行提權；若平台沒有此工具、拒絕或無法取得必要授權，記錄 `backend-handoff SESSION_ID --reason authorization_denied|authorized_execution_unavailable` 後由當前 Codex 接手，不用其他執行通道繞過。`analyze` 保留原入口供具適當權限的執行環境使用。Python 自行打包已選取來源的既有字幕、Evidence、情境與缺口；不必由 Codex 先重讀完整字幕。CLI 預設每次模型呼叫最多 600 秒（`--timeout 1..1800`），模型清單預檢最多 20 秒。
3. `awaiting_codex_review`：優先讀 `validated_analysis` 和 receipt，再核對引用 Evidence 的主張、分類、條件、核對方式與限制。只有爭議、遺漏或關鍵結論才回讀相關原文／字幕區間；不能以 Schema 通過代替語意審核。
4. `codex_required`：當前 Codex 立即接手，沿用正式 Evidence 與先前通過驗證的分析；讀 `resume_input`、state、research-status。不得讀取或採信未驗證輸出，不重新呼叫 agy，不另開付費 API。依原查詢帳本與停止契約補足尚未完成的研究，或保留缺口結案。Codex 也無法執行時，保留 state 與輸入，明示未完成。
5. Codex 寫最終 analysis JSON（沿用 `schemas/antigravity-analysis.json`）與下列具體 review JSON，執行 `backend-finish`。以 `backend-status` 回傳的最新 fingerprint 綁定本次 Session；analysis_hash 是 `va.digest(analysis)`，即 UTF-8、ensure_ascii=False、sort_keys=True 的 JSON SHA-256。研究資料或分析變更後須重新審核、重算雜湊。

```sh
./video-analyzer backend-status SESSION_ID
./video-analyzer backend-finish SESSION_ID final-analysis.json codex-review.json --mode deep
```

```json
{
  "actor": "current_codex_session",
  "analysis_hash": "最終 analysis 的 va.digest",
  "session_fingerprint": "backend-status 的 current_session_fingerprint",
  "complete": true,
  "source_support": "具體說明哪些引用支持哪些主張，以及修正或無法支持之處",
  "opinion_inference": "說明來源事實、作者意見、模型推論與未驗證資訊如何區分",
  "comparability": "說明型號、條件、測項及來源獨立性的可比性與衝突",
  "limitations": "說明未觀看、未聆聽、缺乏直接測試及不可外推範圍",
  "remaining_work": "說明剩餘工作如何完成，或依何種停止條件保留哪些缺口"
}
```

review 是目前 Codex 的可追溯審核紀錄；欄位檢查只能證明紀錄完整，不能證明語意正確。不得機械填寫「已通過」。`backend-finish` 只做驗證、保存 review、沿用原 `report` 產生器；無模型呼叫。尚有待審／接手工作時，直接 `report` 會要求改走 backend-finish，避免草稿繞過審核。未使用後端的舊 Session 與原分析檔仍可照原入口產生報告。無 Evidence 時直接交 Codex，結論須為證據不足／一般分析；若無法滿足原 Deep 引用要求，用 Quick 明示缺口，不捏造引用。

完成後依原契約開啟 `.full.md`／`.decision.md`，回傳絕對路徑。主報告與 Legacy 均註明是否 Antigravity → Codex 接手及安全原因代碼，JSON 保留模型事件與用量。

## 免費配額與有限切換

查核日期：2026-11-03。正式 CLI 支援 `--model`、`--settings`、`-p`、`--json-schema`；當前 `agy models` 列出 Gemini 3.8 Flash、Claude Sonnet 4.6 與 GPT-OSS 120B。固定先選 `gemini-3.8-flash-high`；僅在明確 quota_exhausted 時，從可用模型清單選一個第二組模型（優先 `claude-sonnet-4-6`，否則 `gpt-oss-120b-medium`），至多再呼叫一次。不依次輪試 Sonnet 和 GPT-OSS。模型清單不能證明剩餘配額，帳號當下餘額未知，配額分組是本編排政策；不宣稱已獨立量測後端計費桶。

每次以單次 `--settings` 強制 `useG1Credits=false`、`modelProvider=""`，不允許用點數補足、不使用直接 Gemini API provider，移除子程序環境中的 API_KEY／ACCESS_TOKEN／SECRET。依[官方點數說明](https://antigravity.google/docs/cli/credits)，關閉 useG1Credits 會限制超額點數扣款；[官方設定](https://antigravity.google/docs/settings?tab=cli) 說明單次設定與 direct API provider。這是現有方案內基礎額度，不代表所有模型對所有帳號皆永久免費，也不代表已查到帳號餘額。

兩組配額都不可用，或遇到限流、登入失效、服務失敗、CLI 失敗、互動要求、付費要求、逾時或驗證失敗，立即寫 codex_required；disabled_scope=delegation，僅停用本次未完成委派。同一工作重啟或補 Evidence 不自動重試；Codex 完成接手後，若有不同研究輸入（fingerprint 改變）的新委派，可正常優先使用後端；不影響其他 Session，也不修改全域設定。原失敗 receipt 保留，不直接清除或重跑失敗工作。切換、所選模型、服務端回傳的模型（若有）、每次 usage、接手原因都保存在每次 attempt receipt 與 state。`usage` 未回傳則記 null；不以 0 冒充實際 Token，也不加總 thinking 與 total 造成重複。paid_api_calls=0 指本 Adapter 沒有外部付費 API 呼叫，不是帳單稽核證明。

## 非互動與隔離邊界

Python 預先備妥輸入；以 `agy -p --output-format json --json-schema ...` 單次呼叫，禁止 slash／skill 展開。不用 continue、不開危險全域權限，Antigravity 內部不請使用者點擊工具許可。Codex 啟動層可能需要一次性／可重用命令授權，見下節；不能因此宣稱整體永遠無人值守。stdin=DEVNULL；所有 read_file/write_file/command/unsandboxed/read_url/execute_url/mcp 操作以單次 deny 規則拒絕（[官方權限規則](https://antigravity.google/docs/permissions?tab=cli)）。以作業系統 sandbox-exec 再阻擋正式專案、Store data 與 cache 的寫入；後端 cwd 為獨立暫存目錄，不交付正式資料的寫入管道。CLI 本身仍可保存其帳號會話與用量紀錄。

Python wall-clock timeout 與 CLI `--print-timeout 600s` 雙層限制；超時／中斷終止整個子程序群組。回報互動需求立即失敗；若 CLI 無輸出地等待，最遲於 wall timeout 接手。OS 保護不可用時安全接手，不移除保護重跑。Codex 的受限執行環境若禁止 sandbox-exec 或 CLI 必要本機埠，依既有工具權限執行；不把權限失敗偽裝為配額不足。

## 產物與恢復

`data/sessions/ID/backend/state.json` 保存最新進度；每次 attempt 的 input.json、receipt.json、validated_analysis.json（僅通過時）保留。失敗不保存未驗證分析或含憑證風險的原始 stderr。後端不寫 Session／Evidence／SQLite；只有 Python 的原有 Store 讀取與報告保存流程運作。原 Ledger 不因委派重設或新增查詢。程序中斷後再次 analyze 只轉 codex_required，不重送請求。

CLI 啟動失敗另保存 cli_diagnostic：失敗階段、解析出的 CLI 路徑、cwd、stdin=DEVNULL、exit_code、stdout/stderr 位元組數，以及允許清單內的安全 stderr 摘要。未識別的原始錯誤以遮蔽標記代替；不保存 prompt、原始 stdout、憑證或任意 stderr。models_preflight 遭本機 bind／sandbox 限制時記 cli_environment_blocked，直接 Codex 接手，不誤認為免費額度耗盡，也不在 Python 內自行提權。

## Codex 命令授權層

固定入口為 `scripts/antigravity_entry.py`，只接受 `probe`（模型目錄，無推論）或 `analyze SESSION_ID --timeout SECONDS`。嚴格驗證 12 碼 Session ID 與 1..1800 秒；拒絕任意命令、程式碼、模型、provider、data/cache 路徑及額外 CLI 旗標。使用專案既有 Python，重用原 analyze／Store／Evidence／驗證流程。正式資料仍由 Python 管理，agy 子程序仍有 OS 禁寫與禁工具規則；授權入口內的可信 Python 管理程式本身在沙盒外運作，故該程式與匯入模組修改後須重新檢視授權風險。

Codex 先用同一固定入口 `probe` 做最小啟動驗證，再執行 backend-launch 的分析命令。對 probe／analyze 分別使用 `[入口絕對路徑, "probe"]`／`[入口絕對路徑, "analyze"]` 作 prefix_rule；不授權任意 Python、Shell 或通用 agy。Codex 的 tool 呼叫由當前工作階段發起，Python 沒有能直接申請該授權的工具連線；不使用新的 Codex／Agents API 來取得授權。

[官方命令規則](https://learn.chatgpt.com/docs/agent-configuration/rules) 支援限定命令前綴；是否批准、保存與套用由 Codex host／組織政策決定。本機附帶經 execpolicy check 驗證的[候選規則](https://learn.chatgpt.com/docs/agent-configuration/rules)，沒有自行安裝到全域設定。prefix_rule 請求獲准不等於永久規則已保存；若保存狀態未確認，須明示未知。

可能需要人工確認的時機：首次命令升權；host 沒有保存規則或選擇只准本次；規則／程式路徑變更；組織政策要求逐次批准。登入失效交回 Codex／使用者處理，不在 agy 子程序等候；Antigravity 的任何內部互動提示仍視為失敗。沒有批准便不執行，拒絕後只記錄接手，不換通道或重試。
