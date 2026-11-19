# 可選音訊基礎流程

功能預設關閉：`runtime.json` 的 `audio_analysis.enabled=false`。本版只接受 `audio-analyze --enable` 作單次明確啟用；修改 runtime 的旗標本身不會自動啟動工作。原有搜尋、擷取、轉錄及報告指令不呼叫新模組。不要批次重跑全部影片。

## 使用

使用正式專案 `.venv/bin/python scripts/va.py audio-analyze SESSION SOURCE --artifact-key 已納入來源的素材key --source-offset 原片偏移秒 --clip-start 素材內起秒 --clip-end 素材內迄秒 --enable --config 選用設定.json`。

`--source-offset` 必填，即使為0；用擷取紀錄／manifest確認，不能只由檔名猜。完整原片為0；例如原片699–773的素材，offset=699、clip-start=38、clip-end=45，對應原片737–744。CLI不取得新媒體；非已納入來源或非該來源所屬artifact即拒絕。省略clip-end代表素材結尾。範圍以數字秒處理，解碼後樣本數為長度依據，取樣誤差最多約一個16kHz樣本。

設定範例：
```json
{"asr_enabled":true,"vad_fallback":true,"vad":{"threshold":0.5,"window_seconds":60,"overlap_seconds":2},"asr":{"backend":"whisper.cpp","model":"base","language":"auto","max_segment_seconds":30}}
```

不給設定時採Silero原封裝門檻、60秒視窗／2秒重疊、Whisper.cpp base、中文、30秒ASR上限。VAD視窗可調1–300秒、ASR分塊1–120秒；禁止不明參數。VAD長段視窗獨立推論，邊界效果仍需人工檢查。

## 模組介面

- `audio_analysis.preprocess.prepare_audio(path, store)`：現有FFmpeg解碼為16kHz單聲道PCM16衍生檔；不降噪、不正規化。支援FFmpeg能解碼的音訊／影片格式，原檔唯讀。
- `audio_analysis.vad.detect_speech_segments(path, config)`：回傳status、segments與原始每視窗sample區間。非標準WAV時傳`config['store']=既有Store`，重用前處理快取。每段含start_seconds、end_seconds、duration_seconds、confidence=null、model_name、model_version。Silero封裝沒有可校準的區段信心，不能補造分數。
- `audio_analysis.asr.transcribe_speech_segments(path, speech_segments, config)`：config須有store、runtime；可加backend、model、language、max_segment_seconds。空陣列跳過ASR；None代表VAD失敗，回退既有worker，按上限切完整輸入。數位全零仍獨立跳過ASR。ASR本身失敗會記failed，不悄悄改後端或重抓模型。
- `audio_analysis.alignment`：合併VAD重疊、裁界、依實際PCM取樣偏移轉換ASR時間。ASR字串不參與推算；被裁界或丟棄的區段有warning，raw不變。
- `audio_analysis.pipeline.analyze`：只處理明確啟用的已納入來源，建立VAD／ASR各自的sidecar。`asr_enabled=false`仍可獨立驗證VAD。

## 證據與Session

正式契約為 [audio-evidence.schema.json](audio-evidence.schema.json)。沿用Round4命名，避免重複別名：record_id對應evidence_id、session_id對應research_session_id、audio_clip.id對應audio_clip_id；audio_clip.source_start_s/end_s為原片範圍；model.name/version、result、known_limitations、human_confirmation.confirmed分別對應模型、normalized_result、limitations、human_verified。另增created_at。機器預設confirmed=false、support=undetermined，不自動晉升為報告主張。

VAD result是clip-relative區間，ASR result是原片秒數；raw保留各ASR小段相對時間、語言判讀、可取得的信心欄位、完整Whisper JSON與執行日誌。`language=auto`為請求值；真正模型判斷另從raw保存／彙總，不假裝已人工確認。Whisper.cpp非full JSON模式未提供的token機率不另捏造。

Session只追加`audio_analyses`關聯（artifact_key、source_id、parent_artifact_key、record_ids、created_at），不修改legacy `evidence`、transcript鍵或原報告。依artifact_key從現有Store讀取sidecar；raw、衍生輸入、ASR子結果都pin到Session。若要讓報告引用主張，需核對後經既有evidence流程提交，不能把sidecar ID直接當作舊`[E:...]` ID。

快取沿用既有SQLite artifacts／recipes／pins，不遷移資料表。鍵含音訊SHA、模型權重SHA、後端版本、前處理、門檻、ASR設定、程式雜湊與時間映射。相同輸入／設定重用成功結果；改設定失效，子段ASR仍可重用。失敗結果保留但不當永久成功快取；VAD有語音而ASR空白為needs_review，可以重用原始結果。暫存目錄自動清除，已pin證據不刪除。

## 限制與驗證

VAD不是收音品質評分，ASR成功不是人聲清晰度證明，轉錄中談到風聲不構成獨立風噪量測。無語音結果只代表此模型在此設定的預測。尚未包含事件分類、干擾量尺或音質估計；未人工聆聽不得標已確認。

執行`.venv/bin/python -m unittest discover -s tests -v`。實際Metal推論需有GPU裝置存取權；若出現Metal配置失敗，保留錯誤並檢查執行環境，不將它誤報為VAD或語音品質問題。不自動下載模型、不使用付費API。

資產授權：現有Silero封裝與程式MIT，來源[Silero](https://github.com/snakers4/silero-vad)／[faster-whisper](https://github.com/SYSTRAN/faster-whisper)；Whisper／whisper.cpp MIT。沿用已安裝資產及其授權聲明，不重新散布權重。封裝V6的精確上游訓練revision未知，以完整檔案hash追蹤。
