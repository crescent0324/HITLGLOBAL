# HITLGLOBAL — 護理之家照護協作台

供護理師、照服員與管理者使用的照護協作系統，整合住民看板、服務訊息待辦、人工接手、處理進度與交班確認。家屬及住民的預定入口為 LINE，沒有院內網頁登入權限。

目前為虛構資料的本機體驗版，使用模擬 LINE 聯絡身分與離線傳輸。真實 LINE 配對、院內資料介接、護理長與 IT 權限分離、常駐部署及第一線試用仍待完成。

已完成本機聯絡人對話隔離：同一住民的不同聯絡人分別保存訊息、生成工作及人工案件；撤銷配對後停止新訊息與回覆。原先混合保存的對話保留為院內舊版紀錄，不指定對外收件者。實作與本輪測試見 [聯絡人對話驗證](docs/CONTACT_CONVERSATIONS.md)。

## 安全整合與 MVP

本輪另修正照服員讀取家屬訊息及案件資料的過度揭露，案件責任改用穩定帳號 ID。舊資料先備份再遷移，同名或無法確認的未結案責任會重新等待接手，不推測歸屬。實際負向測試、遷移、59 項回歸與第一版家屬訊息 MVP 規格見 [安全整合與 MVP 文件](docs/mvp/README.md)。新增獨立主管監控、正式角色與 LINE 仍未實作；本輪僅使用本機虛構資料。

## 與論文版本的關係

本儲存庫自 2026-10-20 起承接護理之家版本的後續開發。原始程式來自 `crescent0324/HITL` 的 `care_console/`；論文原型及研究資料繼續保存在原儲存庫與研究資料包。

本次沒有刪除或更動原儲存庫。新專案自帶必要核心，不依賴另一套系統的執行環境、資料庫或金鑰。詳見 [版本分離說明](docs/SEPARATION.md)。

## 啟動

需要 Python 3.12。Windows PowerShell：

```powershell
git clone https://github.com/crescent0324/HITLGLOBAL.git
cd HITLGLOBAL\care_console
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\start.cmd
```

瀏覽 `http://127.0.0.1:9465/`。體驗帳號為 `admin`、`nurse`、`nurse2`、`caregiver`，體驗密碼為 `CareDemo2026!`。帳號與住民資料均為本機示範用途。程式拒絕遠端來源，不要直接用公開通道開放這套體驗登入。

首次啟動會在 `care_console/runtime/` 建立獨立環境，沒有帶入舊版執行資料。如果 9465 已被其他副本使用，先確認執行來源，不要同時啟動多份，也不要直接終止所有 Python 程序。

詳細帳號權限、體驗流程、交班及備份操作見 [照護協作台說明](care_console/README.md)。

## 測試

在 `care_console/` 執行：

```powershell
.\.venv\Scripts\python.exe -B -m unittest -v test_care_console
```

測試使用暫存資料庫、虛構住民與離線替代服務，不需要 LINE 或 OpenAI 金鑰。本次分離的檢查方式與限制見 [匯入驗證紀錄](docs/IMPORT_VERIFICATION.md)。

## 目錄

| 路徑 | 用途 |
| --- | --- |
| `care_console/` | Flask 應用、SQLite 資料處理、流程測試與啟停腳本 |
| `care_console/core/` | 本版使用的風險、生成及 HITL 控制核心 |
| `care_console/static/`、`templates/` | 院內網頁 |
| `docs/` | 版本分離、驗證及後續開發規劃 |
| `AGENTS.md` | 程式開發與檢查指引 |

## 下一階段

以一家護理之家可受控試用為目標，在已完成的本機對話隔離上，接續設計真實 LINE 身分配對、收件者核對與傳送結果處理，並確認現場流程、員工帳號與職責，再準備院內資料介接及常駐環境。具體驗收條件見 [開發規劃](docs/ROADMAP.md)。

本儲存庫不包含 API 金鑰、LINE token、實際對話、住民個資、執行資料庫或備份。這些資料必須與程式分開保存，不得加入 Git。

風險規則不等同臨床分流標準；功能測試通過不代表已驗證照護成效或臨床安全。此版本尚未完成正式場域驗收。
