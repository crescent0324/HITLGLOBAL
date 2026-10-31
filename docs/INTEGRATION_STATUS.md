# PR 與分支整合現況

核對日期：2026-10-31（台灣時間）。程式基準為 main [`1e1a5a517a31cb2967da064f240d468067597de8`](https://github.com/crescent0324/HITLGLOBAL/commit/1e1a5a517a31cb2967da064f240d468067597de8)，Git tree 為 `bfeb5567c61ccc902c8e288da42e1068221e2a64`。本文件的 PR、分支與測試結論限於這個固定版本；後續提交需另行核對。

PR #1～#7 都已合併；本輪盤點前沒有開放中的 PR 或 issue。七個既有遠端工作分支都已是 main 的祖先，沒有遺漏的獨有提交。後續開發從重新抓取的 main 建立分支即可。

## 實際合併順序

| 台灣時間 | PR 與內容 | 合併目的地／提交 |
| --- | --- | --- |
| 10-25 09:09 | [#2 照服員資料隔離、穩定責任 ID](https://github.com/crescent0324/HITLGLOBAL/pull/2) | main，`e7f3199` |
| 10-25 10:14 | [#3 護理長唯讀監控、IT 分離](https://github.com/crescent0324/HITLGLOBAL/pull/3) | main，`2d23e85` |
| 10-25 14:36 | [#4 監控競態、分頁、查詢與備份](https://github.com/crescent0324/HITLGLOBAL/pull/4) | main，`b7c771a` |
| 10-25 16:35 | [#6 UAT 套件、視窗通知修正](https://github.com/crescent0324/HITLGLOBAL/pull/6) | 先進入 #5 的機構流程分支，`1944754` |
| 10-25 16:51 | [#5 機構流程與權限訪談規格](https://github.com/crescent0324/HITLGLOBAL/pull/5) | 連同 #6 一起進入 main，`f3871b0` |
| 10-25 17:12 | [#1 固定版本競品研究](https://github.com/crescent0324/HITLGLOBAL/pull/1) | main，`34eb5d6` |
| 10-29 20:47 | [#7 床位對應資料範圍修正](https://github.com/crescent0324/HITLGLOBAL/pull/7) | main，`1e1a5a5` |

#6 的內容已隨 #5 納入 main，無須另行合併或挑選其提交。舊的 [UAT 合併檢查](uat/INTEGRATION_CHECK.md) 記錄的是發布前的建議；上表是 Git 歷史與 GitHub 狀態核對後的實際結果。

## 工作分支

| 既有遠端分支 | 核對 head | main 以外的提交 |
| --- | --- | --- |
| `docs/competitive-research-20261023` | `f6ee974` | 0 |
| `fix/caregiver-access-owner-identity-20261024` | `6a45c48` | 0 |
| `feature/head-nurse-monitor-20261025` | `362e049` | 0 |
| `fix/monitor-refresh-pagination-backup-20261025` | `b28dfc9` | 0 |
| `docs/institution-workflow-permissions-20261025` | `1944754` | 0 |
| `fix/uat-trial-kit-modal-feedback-20261025` | `b53d866` | 0 |
| `fix/bed-visibility-scope-20261029` | `fdd7a9c` | 0 |

這七個分支可列為完成後的清理候選。本輪保留分支及既有工作副本。另查到舊的本機 main 工作副本仍在 `18729be`，落後 origin/main 14 個提交；既有工作分支的本機副本也停在各輪版本。試用或後續修改前，先確認自己的 HEAD，避免從舊副本啟動。本輪另建固定於 `1e1a5a5` 的隔離工作副本執行驗證。

可在自己的 checkout 核對：

```powershell
git fetch origin
git status --short --branch
git log -1 --oneline origin/main
git rev-list --left-right --count origin/main...HEAD
git branch -r --merged origin/main
```

`rev-list` 的左欄是 main 獨有提交數，右欄是目前 HEAD 獨有提交數。這項檢查不會更新工作分支。

## 重複修改與保留情況

- 依七個實際 merge commit 的兩個父版本重算 `git merge-tree --write-tree`，7／7 與已合併的 tree 相同，沒有另加衝突解法的差異。
- 對七個原始工作提交計算 `git patch-id --stable`，沒有相同 patch。#5 以原始 `708e417` 計算自身變更，#6 以 `b53d866` 計算，避免把 #5 後來包含的 #6 再算一次。
- #2、#3、#4、#6 的 `app.js` 修改屬連續修正；#7 延續 `care_store.py` 與監控測試。檔案路徑重疊有相依關係，完整回歸另檢查目前組合的行為；patch 與 tree 相同本身不構成全面安全保證。
- 固定基準的 23 個核心檔仍未變更。競品研究 23 檔與 #1 相同；機構流程規格 9 檔與 #5 原始提交相同；基準 main 的 UAT 文件與 #6 相同。本次文件收尾只在 UAT 合併紀錄上方補現況連結，原始紀錄保留。
- GitHub 查詢的 #1～#7 討論與 review thread 均為空，沒有可追蹤的未解 review thread；這不能推定外部審查意見都已取得。

## 最新整合驗證

在基準 main 的隔離工作副本，使用 Python 3.12、Flask 3.1.3、Waitress 3.0.2，以及 Node.js 24、JSDOM 26.1.0 執行。測試使用新建暫存虛構資料與離線替代服務。

| 檢查 | 結果 |
| --- | --- |
| `test_care_console` | 59 項通過 |
| `test_case_monitor` | 22 項通過 |
| `test_backup_hardening` | 5 項通過 |
| `test_monitor_hardening` | 8 項通過 |
| 前端 `test_monitor_frontend.cjs` | 25 項通過 |
| 10-29 外部床位權限重現程式，原檔未修改 | 1 項通過 |

完整後端共 94 項，耗時 314.617 秒；前端 25 項，耗時 20.810 秒；外部原重現程式 1 項，耗時 3.809 秒。三組檢查均成功結束，外部重現另列，不灌入既有測試數。

完整命令在 `care_console/` 執行，套件安裝見 [程式說明](../care_console/README.md)：

```powershell
.\.venv\Scripts\python.exe -B -m unittest -v test_care_console test_case_monitor test_backup_hardening test_monitor_hardening
npm install
npm test
```

根 README 原指令只含前兩個後端模組，共 81 項，會漏掉 13 項穩定性與備份測試；AGENTS 原範例僅含 59 項。本次統一為四個後端模組，並補前端測試入口。各輪文件中的 47／59／77／90 項數字繼續表示當次歷史結果。

## 剩餘事項與接續方式

| 項目 | 本輪結論／接續條件 |
| --- | --- |
| #1～#7 的程式與文件整合 | 已完成，七個工作分支均無未合併提交。 |
| 10-29 床位資料揭露 | #7 已修正並合併；原外部重現程式在目前 main 通過。詳見 [床位修正](BED_SCOPE_FIX.md)。 |
| 現況入口與測試指令 | 本次純文件變更新增此頁、根 README 入口、完整指令及舊合併紀錄的現況連結。 |
| 自動化檢查 | 基準未包含 `.github/workflows/`；目前沒有儲存庫內定義的 GitHub Actions 測試流程。後續若需每次 PR 自動驗證，另立小範圍工作。 |
| 真人 UAT 與機構 SOP | 仍待執行，從 [UAT 入口](uat/README.md) 及 [決策表](uat/DECISION_TEMPLATE.md) 收集證據，M0～M3 尚未驗證。 |
| 正式帳號、真實 LINE、院內資料與部署 | 仍依 [試用規劃](ROADMAP.md) 確認；現有分支合併不代表這些能力已完成。 |

本輪工作聚焦合併完整性與既有整合回歸，沒有重做全面安全稽核或真人 UAT。應用程式、資料庫結構、角色能力及歷史研究資料均未修改。
