# Research / Video Analyzer

以穩定的 Research 1.4.0 為基礎，整理為「Python CLI 核心 + Agent Skill」。目前版本為 `1.4.0`，原始碼已於 [GitHub](https://github.com/saunter-lin/research-video-analyzer) 公開；原創程式與專案文件已採用 MIT，第三方通知與散布邊界分開保存。

CLI 可獨立操作研究紀錄、來源快照、證據 ID、行號與時間定位、SQLite 快取、預算閘門、研究缺口，以及 Quick／Deep 報告。原有字幕、評論、網頁、影音、可選本機 VAD／ASR 與 Antigravity 驗證／接手機制均保留。內容判讀、來源獨立性與可比性仍由人或 Agent 核對。

## 安裝與離線範例

需要 Python 3.11+、macOS／Linux；本機驗證基準為 Python 3.12。原生 Windows 因 fcntl／resource 尚不支援；WSL 未實測。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/video-analyzer --help
.venv/bin/video-analyzer doctor
.venv/bin/python examples/offline_research.py --cli .venv/bin/video-analyzer
```

核心無第三方執行期依賴，不需要 Codex、付費 API 或模型下載。建置時需要 setuptools／wheel；安裝來源依 pip 設定，完全離線請參考[安裝文件](docs/install.md)。

```sh
video-analyzer --data ./data --cache ./cache create \
  --title '公開規格研究' --question '保存的原文支持哪些主張？'
video-analyzer --data ./data --cache ./cache list
video-analyzer --data ./data --cache ./cache research-status SESSION_ID
```

`--data`、`--cache` 須放在子指令前。完整可執行流程見[純合成離線範例](examples/offline_research.py)。選用功能使用 `pip install '.[video]'`、`'.[audio]'`、`'.[documents]'`、`'.[benchmark]'`，先閱讀[第三方授權](THIRD_PARTY.md)。安裝套件與取得模型須由操作者明確選擇。

## Skill 與資料

`video-analyzer skill-path` 顯示可獨立複製的 Skill 目錄。[Skill 安裝與 Agent 可攜性](docs/agents.md)說明 Codex 入口及其他 Agent 的限制；這次不會覆蓋現有 Skill。

預設資料 `~/.local/share/research-video-analyzer`，快取 `~/.cache/research-video-analyzer`，與原正式版分開。可設定 `RESEARCH_DATA_DIR`、`RESEARCH_CACHE_DIR`；模型設定用 `RESEARCH_RUNTIME`。不會自動讀取 `.env`。

正式研究資料、快取、歷史、帳密、Cookie、模型、第三方影音與歷史非商用素材均未納入。後續提交與散布內容依檔案清單及[安全規則](SECURITY.md)持續檢查。

## 文件與公開結論

- [開源準備評估與未解決問題](docs/open-source-assessment.zh-TW.md)
- [建議 Repository 結構與最小修改](docs/architecture.md)
- [安裝](docs/install.md)、[測試](docs/testing.md)、[安全邊界](SECURITY.md)

原創程式與專案文件採 [MIT](LICENSE)，四個已記錄 MIT 參考來源的完整通知保留於 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。[授權收尾紀錄](docs/license-closure.md)說明適用範圍；套件、二進位、模型與研究素材不因此被改授權。GitHub Repository 已公開，版本為 `1.4.0`；Repository 公開與 GitHub Release 分開管理，CI 保留手動啟動。英文文件見 [README](README.md)。
