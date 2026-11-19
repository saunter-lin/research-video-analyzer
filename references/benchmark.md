# Whisper 基準測試

已整合 whisper.cpp Metal 與 faster-whisper CPU/int8；預設後端尚未決定，呼叫時明確指定。runtime.json 指向本機已下載模型，模型不存在即報錯，不隱式下載。

```sh
.venv/bin/python scripts/benchmark.py /absolute/path/16k-mono.wav --reference /absolute/path/corrected.txt --repeats 2 --output data/benchmarks/real-review
```

使用同一份 16kHz／mono／PCM16 WAV、同級多語言 base 模型、語言 zh、beam=1、best_of=1、temperature=0、VAD 關閉、四執行緒、不沿用前文。後端實作與精度不同，不能宣稱完全等價設定。Core ML 未建置／未測。

記錄 wall time、RTF、load time、RSS、加速日誌、原始 CER 和 OpenCC 繁簡正規化 CER。首次／後續都重新開程序載入模型，後續僅可能受 OS 快取影響；不是模型常駐暖機測試。首次也不保證清空磁碟快取。RSS 不包含可準確歸屬的共享 GPU 配置。

有 reference 才算 CER；不把網路字幕直接當人工標準答案。型號、數字、中英混雜、靜音幻覺及時間戳偏差需另人工校對。benchmark JSON 保留逐字稿和片段時間供核對。

附帶合成語音測試只驗證執行與初步效能，不能決定真實評測素材上的中文品質。正式選預設後端前，應用使用者提供或合法取得的真實短片＋長片，核對參考稿並觀察持續負載。沒有真實測試來源時保留此限制，不擅自下載未選候選作測試。
