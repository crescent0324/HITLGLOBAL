# HITLGLOBAL — 護理之家照護協作台

供護理師、護理長、照服員與 IT 管理人員使用，處理住民看板、家屬服務詢問、人工接手、進度與交班。家屬及住民的預定入口為 LINE。

目前為虛構資料的本機體驗版，使用模擬聯絡身分與離線傳輸。2026-10-31 已確認 PR #1～#7 全數納入 main；合併順序、分支與測試結果見 [整合現況](docs/INTEGRATION_STATUS.md)。

## 從這裡開始

| 你要做什麼 | 閱讀入口 |
| --- | --- |
| 第一次接觸，想知道這是什麼、做到哪裡 | [一頁看懂 HITLGLOBAL](docs/OVERVIEW.md) |
| 啟動系統、看帳號權限與操作流程 | [操作說明](care_console/README.md) |
| 主持一場使用虛構資料的機構試用 | [UAT 試用套件](docs/uat/README.md) |
| 找規格、API、開發規劃或歷史證據 | [文件總覽](docs/README.md) |

## 啟動

需要 Python 3.12。Windows PowerShell：

```powershell
git clone https://github.com/crescent0324/HITLGLOBAL.git
cd HITLGLOBAL\care_console
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\start.cmd
```

瀏覽 `http://127.0.0.1:9465/`。體驗帳號為 `head_nurse`、`admin`、`nurse`、`nurse2`、`caregiver`，密碼為 `CareDemo2026!`；家屬及住民不能登入院內網頁。首次啟動會在 `care_console/runtime/` 建立獨立的虛構環境。

程式僅供 localhost 體驗，拒絕遠端 IP 與外部 Host。9465 若已被使用，先確認程序來源。正式 UAT 請依試用套件建立全新場次，保留前場資料。

## 開發與測試

在 `care_console/` 執行；前端測試需要 Node.js 20 以上：

```powershell
.\.venv\Scripts\python.exe -B -m unittest -v test_care_console test_case_monitor test_backup_hardening test_monitor_hardening
npm install
npm test
```

測試使用暫存虛構資料及離線替代服務，不需要 LINE 或 OpenAI 金鑰。開發規則見 [AGENTS.md](AGENTS.md)。

## 目錄

| 路徑 | 用途 |
| --- | --- |
| `care_console/` | 應用程式、核心依賴、介面、測試與啟停腳本 |
| `docs/` | 按用途查找的文件；舊驗收與匯入紀錄集中於 `docs/archive/` |
| `AGENTS.md` | 開發與檢查指引 |

目前已完成聯絡人對話隔離、穩定責任 ID、指定接受交班、護理長唯讀監控、IT 分離與床位範圍修正。真實 LINE、正式帳號、院內資料介接、常駐部署與真人驗收仍待完成，接續條件見 [開發規劃](docs/ROADMAP.md)。

本專案承接護理之家版本；原論文與研究資料保留在 `crescent0324/HITL`，維護界線見 [版本分離](docs/SEPARATION.md)。各輪歷史資料保留原日期與證據，不以功能測試推定照護成效或臨床安全。API 金鑰、實際對話、個資、執行資料庫與備份均須另行保存。
