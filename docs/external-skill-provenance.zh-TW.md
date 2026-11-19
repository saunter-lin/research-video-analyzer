# 外部 Skill 來源追溯與授權審查

> 2026-11-19 授權收尾更新：原創程式／專案文件已採 MIT，四項 MIT 參考來源完整通知已保留，來源限定為不含套件／模型／二進位／歷史素材的原始碼候選。已具備建立私有 Repository 的授權管理條件；下文的 LICENSE 待定／NO-GO 為前兩輪歷史結論，不代表目前尚未放置 LICENSE。詳見[授權收尾](license-closure.md)。原先不確定的作者歷史與提示詞衍生限制仍如實保留，沒有改成「完全原創」證明。


查核日期：2026-11-19（Asia/Taipei）。對象：Research / Video Analyzer 1.4.0 的 `1.4.0.dev1` GitHub 開源候選。優先查讀 Obsidian，再循其連結核對開發報告、PoC、正式整合與上游原文；正式 Research、Vault、其他個人專案均只讀。

## 來源追溯結論（保留當輪紀錄，授權決策見上方更新）

**MIT 仍是原創部分的可行建議，但本次沒有足夠證據將候選整體認定為「完全原創／權利已清空」。公開發布維持 NO-GO。**

目前可支持的分類是：video-digest-skill 的設計參考；10/23 字幕 Skill 的測試切分／錯誤處理借鑑後本地實作；Local Deep Research 的缺口／查詢歷程概念轉成本地帳本；Download Anything 的收件需求啟發後使用不同專用工具實作。未確認把這些上游的實質程式或文件直接收錄至候選。也未確認候選有特定上游提示詞的翻譯／衍生改寫；此項是**證據不足**，不是「已證明沒有」。

Humanizer 的固定版本直接收錄可在 **Courseware／Storyboard** 核實，不能移算為 Research 整合。AnySearch 的 Research 紀錄明示延後／非必要且當輪沒有安裝或呼叫；未找到候選中的 API client、安裝器或對應提示詞，但歷史指涉沒有固定 Repository／revision，不能以今天同名倉庫倒推當時版本。

沒有證據要求 Research 僅因本次查到的外部 Skill 而改用 GPL／AGPL；仍須完成原創權利人確認與原評估列出的套件／binary／素材問題。若後續找到實質複製／衍生內容，須重新判斷適用通知與授權，不能用重寫幾個句子取代來源審查。

## 方法與證據強度

1. Vault 先行：完整搜尋 Markdown 的 Research／video-analyzer／AnySearch／Humanizer，讀取五份 video-analyzer 專案筆記、六專案決策筆記及相關整理入口；Humanizer 命中另按所屬專案分流。
2. 可定位歷程：2026-10-18 初始規劃 → 10/19 字幕／報告 → 10/23 外部 Skill 評估與 F1/F2 → 10/24 混合來源 → 11/1 PoC／正式 1.4.0 → 11/3 後端 → 11/13 文件收件 → 本次候選。Vault 是索引而非完整逐回合紀錄；缺失的初始聊天、未保存外部快照、沒有 Git 作者歷史，均限制「完整」的可證明程度。
3. 候選掃描覆蓋 **37 個 Python、33 份 Markdown**（在本次審查文件加入前），包括核心、測試、根 SKILL、獨立 Skill、references 及文件。與 **63 個上游保存檔**中的 42 個 Python、14 份 Markdown 比較；其餘為 LICENSE／NOTICE。上游文字僅供比對，未執行、安裝或收錄進公開候選。
4. Python 逐字門檻：連續 40 個非註解／非排版 token；Markdown 門檻：移除空白、case-fold 後連續 100 字元。**兩類均零命中。** 另人工對照功能、流程、prompt 結構及本地決策。這是線索篩選，不能偵測所有翻譯、變數改名、短段重組，也不是法律上的「實質相似」判決。
5. 歷史版本交叉驗證：取回的 imlewc 14 檔（含五份測試）與 10/23 manifest SHA-256 全數一致；LDR 三份關鍵程式與 11/1 source-register 全數一致。Humanizer 上游 SKILL 與另外兩個專案的 vendor 檔案逐位元組一致；Research 沒有相應 vendor 檔。

可重核的來源與 hash、比對方法／結果見 [JSON](external-skill-provenance.json)。私有原始路徑、Vault 行號與證據索引另存交付根目錄 `verification/`，不放進建議 GitHub root；本報告只保留筆記名稱、證據 ID 與上游連結。

## 來源清單與實際用法

| 來源、Repository／著作權人 | 實際用途／分類 | 候選對應與證據 | 授權、必要處理 |
|---|---|---|---|
| [video-digest-skill](https://github.com/coocA-Alex/video-digest-skill)，coocA-Alex；LICENSE：2026 coocA-Alex | **參考設計理念**：字幕與畫面核對、事實／作者意見分流；不是其外部模型、B站追更或摘要管線整套導入 | E02 初始規劃明示參考、不整套引入；候選 `references/audio-review.md`、Skill `references/orchestration.md`、`scripts/va.py` 的 claim_type／verification；不同於上游摘要模板與 API pipeline | [MIT 固定來源](https://github.com/coocA-Alex/video-digest-skill/blob/798c92f017008280959d7d9faeee00ded37407a4/LICENSE)。目前未確認需攜帶其 LICENSE 的複製範圍；建議設計致謝。若找到實質 prompt／文件／程式衍生，保留其完整通知。初期實際閱讀 revision 未保存，本次比對 revision 不等於當時採用證明 |
| [video-analyser-skill](https://github.com/LDJ-creat/video-analyser-skill)，LDJ-creat（提交作者 LDJ；權利人未確認） | **曾評估、紀錄為不採用程式碼**：video-helper 服務依賴與 Mac 部署不符現有方案 | E02；上游採後端 submit/poll/chunks，候選採 Store／Evidence／本機取得；未見 VIDEO_HELPER client、安裝服務或該 job protocol | 固定 `e1b3e49…` root tree 無 LICENSE，GitHub license=null，**授權未確認**。不能視為可自由商用；如後續發現直接或衍生複製，先阻擋該部分，取得授權或真正獨立替代 |
| [video-to-subtitle-summary-skill](https://github.com/imlewc/video-to-subtitle-summary-skill)，Repository imlewc；LICENSE：2025 **ultrasev** | **參考測試切分／錯誤說明後本地重新實作（支持性證據）**；不是整套 Skill／代理 API 的採用 | E03 評估 → E04 F1/F2 報告與 diff；候選 `scripts/va.py:436–492`、`tests/test_acquisition.py`、`references/workflow.md`。本地依型別／status 保守分類並丟棄原 logger，與上游有限 URL fallback／逐 URL 訊息處理不同 | [MIT 固定來源](https://github.com/imlewc/video-to-subtitle-summary-skill/blob/50598e25e9962b3f7fef3c7d73c066c00d3ecb87/LICENSE)。14 檔歷史 hash 一致，未命中長片段逐字相同；可保留設計來源記錄。若收錄實質內容，著作權聲明應為 **ultrasev**，不能改成只寫 imlewc |
| [Local Deep Research](https://github.com/LearningCircuit/local-deep-research)，LICENSE：2025 LearningCircuit | **設計理念 → 本地重新實作（支持性證據）**：缺口查詢、iteration history、狀態／取消；停止價值沿用既有 Research 規則 | E06 明列 R-A/R-B 來源；E07 隔離 PoC → E08 正式整合；候選 `scripts/research_ledger.py:129–349`、`references/research-ledger.md`。上游 BaseQuestionGenerator／LLM questions_by_iteration 與本地 reservation／有效 Evidence receipt／來源預算資料結構不同 | [MIT 固定來源](https://github.com/LearningCircuit/local-deep-research/blob/5294f7d0a0e4e60f0496587ca8739d540eab5a14/LICENSE)。本次比較 atomic_fact、source_based、cache 三個歷史檔，未證明逐行移植；不是獨立 clean-room 認證。若收錄或改寫實質程式／prompt，須攜帶對應通知 |
| [Download Anything](https://github.com/nengong/download-anything)，LICENSE：2026 Download Anything Contributors | **參考收件能力與檔案契約後本地重新實作（支持性證據）**，未導入整套下載器／Skill | E09 評估＋後續驗證；候選 `scripts/document_intake.py`、兩處 `references/web-research.md`。上游為 BaseDriver／AssetPackage、requests＋BeautifulSoup；本地為受限 HTTPS＋Trafilatura／pypdf、allowlisted images／hash manifest | [MIT 固定來源](https://github.com/nengong/download-anything/blob/f3db92847c14245ee9afae881ecb307e27d8d829/LICENSE)。相同 arXiv PDF／BibTeX endpoint 是介面重合，不能單憑它判為程式複製；未找到需攜帶其通知的實質複製證據。所用 library 授權另見 THIRD_PARTY |
| [AnySearch Skill](https://github.com/anysearch-ai/anysearch-skill)，NOTICE：2026 AnySearch | **延後／未導入的搜尋供應者候選**。歷史名稱無確定 Repository／revision；此官方同名 repo 僅為本次可識別比對對象 | E05 10/24 正式決策明示未安裝／呼叫；候選 `references/web-research.md:9` 及 Skill orchestration 第 7 行明示非必要；未見 API client／API domain／安裝器／專用 prompt | [Apache-2.0 LICENSE](https://github.com/anysearch-ai/anysearch-skill/blob/e70355ba9957cf69923f49ae8ffb224ccc3ae7f0/LICENSE)＋[NOTICE](https://github.com/anysearch-ai/anysearch-skill/blob/e70355ba9957cf69923f49ae8ffb224ccc3ae7f0/NOTICE)。目前無已確認的 Apache 內容散布義務；若未來收錄／衍生，保留 LICENSE、適用 NOTICE／著作權及修改註記，原創部分仍可另採 MIT，不能將該部分單改標 MIT |
| [Humanizer](https://github.com/blader/humanizer)，LICENSE：2025 Siqi Chen | **Research 整合／特定提示詞改寫：證據不足；其他專案直接文件複製已確認** | E10 Vault 筆記屬 Courseware；另外兩專案 vendor SKILL 與固定上游完全一致，附 LICENSE／provenance；候選無 Humanizer vendor、import、自然度處理器或對應 receipt。不能因同一使用者／宿主載入多個 Skill 就轉算成 Research 依賴 | [MIT 固定來源](https://github.com/blader/humanizer/blob/8c307f367c91bd974002f10f2be2965d642c13df/LICENSE)。Research 現階段沒有已確認需補帶其 LICENSE 的收錄範圍。若找到實質文件／prompt 衍生，MIT 相容但須保留 **Siqi Chen** 通知；不能從「沒搜到名稱」推導完全沒借鑑 |

對「獨立重新實作」的判定僅表示開發報告、介面與實作差異共同支持本地實作路徑，不表示從未閱讀上游，亦不否認可追溯的概念借鑑。所有列為「未確認複製」的項目，均不能改寫成「已證明完全原創」。

## 提示詞與文件的專項判斷

| 類型 | 本次確認範圍 | 仍未知 |
|---|---|---|
| 設計理念 | 字幕／畫面與主張分類、缺口查詢／歷程、文件成套收件等有明示開發來源 | 初始每句規則的最早寫作來源未完整保存 |
| 本地重新實作 | F1/F2、R-A/R-B、document_intake 的本地報告／差異及不同結構可互證 | 沒有全程作者／commit 歷史，不能給予 clean-room 保證 |
| 改寫提示詞 | 未找到可定位至上述上游的特定衍生段落；Research 有自己的研究／Evidence 契約 | 翻譯、拆句、短段重組不一定命中比對；須標「證據不足」 |
| 直接複製程式／文件 | 本次上游樣本與 Research 候選未見門檻命中；候選自身沿用正式 Research 的 SKILL／references，屬本地歷史延續 | 最早 Research 文件的來源權利仍需權利人確認；直接複製 Humanizer 是別的兩專案，不能歸入 Research |

## 其他評估來源與專案邊界

- **Open Deep Research（langchain-ai/open_deep_research）**：E02 記載只參考設計、不導入框架；候選未見 LangChain／該專案 import。歷史記載 MIT，本次未重核該 revision 的 LICENSE；無特定實質相似段落，列「設計參考；精確版本與來源範圍證據不足」。
- **DigUp、Kokoro、Short Video Factory、AI YouTube Shorts Generator、Podcastfy**：E06 的六專案報告與 Vault 決策表橫跨研究、TTS 與影片製作；不能把所有提案都歸為 Research 已整合。Research 本次可追到正式落地的是 LDR 的 R-A/R-B；其餘未見在候選中的對應 provider／索引器／renderer／TTS 程式。歷史報告記載的 SVF AGPL 風險不能自動變成 Research 的 AGPL 義務，若日後找到移植則須另審。
- **yt-dlp、Whisper、Trafilatura、pypdf 等**為實際程式依賴／工具，不因它們也被其他 Skill 使用，就等於 Research 複製了該 Skill；完整套件／binary／模型授權仍依 [THIRD_PARTY.md](../THIRD_PARTY.md) 個別處理。
- **宿主提供的技能與文件**不是自動隨 Research 散布的內容；應以候選實際收錄、執行依賴與可定位衍生段落判定。本次未將宿主 Skill 清單或別的專案的 Humanizer receipt 當成 Research 的使用證據。

## 歷程證據索引

下列本機來源已實際讀取；完整私有路徑、檔案 hash 與定位保存於交付根目錄 `verification/external-skill-evidence.local.json`。不把 Vault 內文或整份上游原文搬入 GitHub 候選。

| ID | 本機紀錄 | 能支持的結論 |
|---|---|---|
| E01 | Vault `video-analyzer.md`、`video-analyzer 近期開發與驗證.md`、`多來源證據與評論整合 2026-10-28.md`、`Research 1.4.0 查詢帳本正式整合.md`、`Research 後端委派與收件 2026-11-13.md` | 版本演進與原始報告定位；舊 1.3.0／未整合 PoC 不能代表後續 1.4.0 |
| E02 | `docs/archive/baseline/規劃結論.md`，第 17–37 行 | 初期 video-digest／video-analyser／LDR／Open Deep Research 的選型與不導入邊界 |
| E03 | `research-ab/external-skill-review-20261023/研究報告.md`，第 3–15、48–78、119–127 行；external-source-manifest | 外部字幕 Skill 是唯讀評估；功能／測試差異與固定上游 |
| E04 | `research-ab/f1-f2-implementation-20261023/實作與驗收報告.md`，第 1–28 行及 `va.diff` | 後續只落地 acquisition 測試與錯誤分類，沿用本地核心 |
| E05 | `docs/maintenance/multisource-20261024.md`，第 3–9 行；現行 web-research 契約 | AnySearch 延後，當輪無安裝／呼叫，混合來源另行本地實作 |
| E06 | Vault `開源架構選擇性借鑑 2026-11-01.md`，第 9–24 行；six-projects-architecture-review／source-register；PoC requirements-baseline 第 250–270 行 | 六專案評估範圍；R-A/R-B 明示 LDR 借鑑，其他專案並非自動採用 |
| E07 | `research-ab/ra-rb-poc-20261101/README.md`、query_ledger.py | 隔離 PoC、原 Evidence／預算／停止語意與本地契約；PoC 當時未啟用，不否認後續整合 |
| E08 | `ra-rb-integration/REPORT.md`；Vault 正式整合筆記第 9–25 行 | 後續 1.4.0 真正落地；不是停在提案 |
| E09 | download-anything-feasibility、document-intake-verification；Vault 後端／收件筆記第 9–17 行 | DA 評估後採有限文件收件；Research 與 Courseware 驗證範圍須分開 |
| E10 | Vault Courseware 專案筆記第 19–23 行；兩專案 vendor Humanizer SKILL／LICENSE／provenance | Humanizer 的直接文件收錄屬另兩專案；固定上游 byte match 已確認 |

補充歷史摘要可協助找到決策，但本次 AnySearch 結論也由 E05 的實際 owning source 獨立核實。摘要指向的原聊天檔目前不存在，不能宣稱已回讀完整對話。

## 授權處理與 MIT 決策

1. **本次即可完成的修正**：撤回過度概括的「未複製外部 Skill」權利推論，改成以上逐來源、逐範圍與不確定性結論；在 THIRD_PARTY 與總評估加入本審查入口。不要為沒有收錄的 Humanizer／AnySearch 盲目添加錯誤依賴聲明。
2. **原創部分可建議 MIT**：已核實的四項活躍參考來源為 MIT；尚未證明收錄它們的實質表達。不因設計參考就禁止原創部分 MIT，也不因其 MIT 就免除收錄時的通知。Repo owner 與 copyright holder 分開記錄。
3. **若確認 MIT 程式／文件／prompt 衍生**：固定來源與受影響路徑、保留原著作權及完整 MIT 許可文字，並將本地修改清楚標示；不得只放首頁超連結替代應有通知。
4. **若確認 Apache AnySearch 衍生**：按 LICENSE 第 4 節保留適用 LICENSE／NOTICE、著作權與修改說明；MIT 可用於自己的部分，不能抹除 Apache 部分的條件。
5. **若確認 LDJ 授權不明內容或其他 AGPL 來源移植**：先停止發布受影響內容，取得明確授權或替代，完成範圍／相容性審查後再決定。不從 repository 可讀、名稱相似或 Star 數推導採用許可。
6. **權利人仍須確認的缺口**：早期來源有無未記錄抄錄／翻譯，哪些人／單位持有原創程式及文件權利，以及先前整體依賴／素材審查。沒有相關證據時保留「證據不足」，不簽發「完全原創」結論。

本次為文件審查，Python、SKILL 與操作 references 均未修改，不重跑上一輪功能測試，也不把先前 158/158 結果當作授權證明。舊 wheel／source archive 是本次審查前的文件快照；可繼續作舊版本驗證證據，但不能宣稱包含本次報告。發布前需依最後核准內容重新建置並檢查封裝。
