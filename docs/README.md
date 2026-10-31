# 文件總覽

依眼前的工作選一個入口即可。各輪測試數字與設計提案都有固定日期；目前版本從 [整合現況](INTEGRATION_STATUS.md) 查起。

| 你要做什麼 | 先讀 | 需要時再查 |
| --- | --- | --- |
| 第一次接觸本專案 | [一頁看懂](OVERVIEW.md) | 本頁其他入口 |
| 啟動系統、查看角色或操作 | [操作說明](../care_console/README.md) | 同頁的交班、資料、備份與測試說明 |
| 主持第一場虛構資料試用 | [UAT 入口](uat/README.md) | [快速開始](uat/QUICK_START.md)、[U01～U20 任務](uat/TEST_SCENARIOS.md) |
| 確認 PR、分支與最新回歸 | [整合現況](INTEGRATION_STATUS.md) | [床位權限修正](BED_SCOPE_FIX.md) |
| 向機構確認職責與流程 | [機構流程訪談包](institution-workflow/README.md) | [角色權限候選](institution-workflow/ROLE_AND_PERMISSION_MATRIX.md)、[下一輪決策](institution-workflow/NEXT_MVP_DECISION.md) |
| 維護監控、API 或資料遷移 | [監控文件](monitor/README.md) | [API](monitor/API.md)、[遷移](monitor/MIGRATION.md)、[穩定性修正](monitor/HARDENING.md) |
| 安排後續開發 | [開發規劃](ROADMAP.md) | 先用 UAT 與機構 SOP 補齊決策證據 |

## 需要追查時才讀

| 材料 | 用途與版本 |
| --- | --- |
| [原始驗收與匯入紀錄](archive/README.md) | 2026-10-03～20 的七份原始檔，集中保存並列出搬移對照。 |
| [競品研究](competitive-research/README.md) | 2026-10-23 研究、固定程式 `18729be` 的來源與功能比較。 |
| [第一版 MVP 規格與驗證](mvp/README.md) | PR #2 的設計、安全修正與後續版本註記。 |
| [聯絡人對話隔離](CONTACT_CONVERSATIONS.md) | 2026-10-20 的變更與歷史驗證，保留後續權限修正說明。 |
| [版本分離](SEPARATION.md) | 護理之家版本、論文來源及資料維護界線。 |

## 文件怎麼放

```text
docs/
  README.md                 從這裡找文件
  INTEGRATION_STATUS.md     固定版本的整合核對
  ROADMAP.md                後續開發與驗收條件
  uat/                      主持人與參與者材料
  institution-workflow/     機構訪談與流程規格
  monitor/                  監控、API 與維護
  mvp/                      第一版設計與驗證
  competitive-research/     固定日期的研究快照
  archive/                  原始驗收與匯入紀錄
```

新增文件放入對應主題，並在該主題入口連結；同一份內容維護一個位置。日常操作指引放在 `care_console/README.md`，歷史測試與截圖說明放在 `docs/`，避免與可執行程式混在一起。程式依賴與測試檔保留既有路徑。
