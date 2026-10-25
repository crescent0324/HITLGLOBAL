# UAT 試用入口

套件版本：Loop Engineering v0.3／2026-10-25。這套材料供實際工作人員使用虛構資料試用；真人驗收尚未執行，M0～M3均尚未驗證。程式沿用目前 care_console；僅修正實測被modal遮住的通知及其清理，沒有增加角色、代理、改派或 AI 權力。

## 第一場怎麼開始

1. 機構窗口與主持人依 [訪談指引](INTERVIEW_GUIDE.md)確認同意、記錄保管及停止條件，核定 [量測版本](MEASUREMENT.md)。
2. 主持人先照 [快速開始](QUICK_START.md)安裝及檢查環境，試跑後停止；正式場次重新建立全新資料夾。參與者只操作瀏覽器。
3. 複製 [空白觀察表](OBSERVATION_TEMPLATE.csv)到機構核定的保管位置。每位參與者使用匿名代碼，保留U01～U20的未執行列，勿填姓名或真實個案。
4. 先完成 [U01～U08](TEST_SCENARIOS.md)連續系統任務，再用U09～U20紙卡。多角色同場可演練一次完整交班，但分別記錄每位人員的操作與提示；下一位獨立受試者另開新場。
5. 使用 [HITL理解觀察](HITL_EVALUATION.md)記錄回答，再以 [決策表](DECISION_TEMPLATE.md)整理證據與下一輪需求。

## 材料用途

| 文件 | 使用人與用途 |
| --- | --- |
| QUICK_START.md | 主持人的安裝、每場開關、全新場次及參與者登入操作。 |
| TEST_SCENARIOS.md | U01～U08逐步操作、U09～U20可列印情境卡與每項空白結果欄。 |
| OBSERVATION_TEMPLATE.csv、MEASUREMENT.md | 每人每項每次一列，記時間、提示、錯誤、感受及證據；定義分析分母。 |
| INTERVIEW_GUIDE.md | 簡短主持詞、院內實際做法、SOP確認及同意。 |
| HITL_EVALUATION.md | 八個理解問題的展示方式、提問及判讀。 |
| DECISION_TEMPLATE.md | M0～M3同一張證據與依賴表，不預選產品方向。 |
| INTEGRATION_CHECK.md | PR #1／#5與main的版本、衝突及合併順序。 |
| VALIDATION.md、REVIEW.md | 本輪實際驗證與獨立審查；不能代替真人使用經驗。 |

本包沿用 [機構流程規格](../institution-workflow/README.md)的U／S編號、四層權限及H0～H3，詳細法規與產品來源仍以該包的 [來源登錄](../institution-workflow/SOURCES.md)為準。本輪不重新宣稱產品現況或法律適用。PR #1是另一份歷史競品研究；沒有合併到本包，也不改寫原研究數字。

## 完成的不同層次

環境與開發者演練是否可重現，見VALIDATION；參與者是否能獨立完成，必須實際試用後回填。機構SOP核定、正式產品驗收與學位論文研究另有各自的同意及審查程序。文件交付不表示已取得上述證據。
