# 驗收情境與虛構展示

> 版本說明：本文件保留 PR #2 的設計／驗證基準；2026-10-25 新增的護理長監控、IT 隔離、明確範圍與本輪測試，以 [監控工作台文件](../monitor/README.md) 為準。下列未實作狀態及 admin 描述屬當時版本，不能用來推定目前權限。

2026-10-25。下表區分本輪直接驗證與未來開發的驗收，不以規格存在代表功能完成。

## 已執行的安全及回歸情境

| 編號 | 前置／動作 | 必須成立的結果 | 證據 |
| --- | --- | --- | --- |
| SEC-01 | 護理師建立家屬訊息及進度，照服員讀看板與詳細資料 | 不含原文、聯絡人、案件風險／存在／責任／草稿／進度／稽核；照護資料仍可讀 | caregiver_cannot_read_family_conversations_or_case_metadata |
| SEC-02 | 照服員指定有效、院內舊紀錄或不存在的對話 | 一律 403；不能用猜對話 ID 擴大權限 | 同上 |
| SEC-03 | 照服員直接呼叫共用或模擬家屬訊息、人工操作 | 403，沒有寫入；仍可一般資訊查閱與觀察回報 | 同上及既有角色測試 |
| SEC-04 | 直接呼叫對話、作者、稽核與流程讀取方法 | 同樣拒絕照服員，不只在路由擋住 | caregiver_cannot_bypass_api_through_internal_read_helpers |
| ID-01 | 兩位護理師同名 | 非責任帳號不是 mine；不能回覆、改進度、交班、取消或結案 | same_display_name_cannot_impersonate_case_owner |
| ID-02 | 非責任同名者對目前對話的草稿做 approve／reject | 403，草稿不變、沒有模型呼叫 | same_name_colleague_cannot_review_real_conversation_draft；使用保留草稿 fixture，未驗證模型品質 |
| ID-03 | 原責任人更名，交班雙方再變成同名 | 原 ID 仍能處理；指定 ID 接受後才移轉，原 ID 隨後被拒 | owner_rename_keeps_identity_and_handoff_respects_ids |
| MIG-01 | 舊名稱唯一對應 | 備份原結構與原文字，再轉 ID，訊息／進度／交班保留；重啟不重做 | unique_legacy_owner_is_backed_up_and_migrated_once |
| MIG-02 | 舊責任同名 | 不猜身分，待接手、舊草稿與交班取消，原進度保留，重新接手才有責任 | ambiguous_legacy_owner_returns_to_pending_and_cancels_draft |
| MIG-03 | 舊帳號不存在、只有照服員或後來才出現同名 | 不指派、不提升角色、不因重啟復活舊身分 | missing_or_ineligible_legacy_owner_never_grants_authority／legacy_owner_matching_only_caregiver_is_not_migrated_as_owner |
| MIG-04 | 已結案但原身分不明 | 結案與原紀錄保留，不製造責任 ID | closed_legacy_case_keeps_history_without_inventing_owner_id |
| MIG-05 | 快照失敗／遷移中途故障 | 阻擋啟動或回復原結構與資料，不產生完成標記；可在修正原因後重試 | backup_failure_aborts_owner_upgrade／owner_migration_failure_rolls_back_schema_and_records |
| REG-01 | 新低風險訊息進入人工案件、交班後有新訊息、內容過時 | 人工狀態維持、舊交班拒收、進度不能過時覆寫 | 既有人工與交班回歸 |
| REG-02 | 聯絡人撤銷、生成中撤銷、重新配對、跨住民／對話 | 阻擋回覆、舊工作不復活、不同對話隔離 | 既有聯絡人與生成回歸 |
| REG-03 | 權限、照護評估、CSV、轉床、備份還原、重啟 | 原控制仍成立 | 完整 59 項測試通過 |

表中測試名稱省略 `test_`；完整名稱可在 `care_console/test_care_console.py` 查找。原本三個照服員測試的存取期待依新資料邊界調整，觀察評估、未授權操作與住民範圍的原有斷言保留。

## 已執行的瀏覽器情境

1. 護理師登入，工作台空待辦正常；開啟 R001 家屬對話，建立一件虛構轉人工詢問。
2. 接手，填寫進度與下一步，提出交班給 nurse2；畫面顯示原護理師繼續負責。
3. 登出切換照服員，只有 R001／R002 照護資料；對話選單的選項數為 0、舊訊息文字為空、人工頁籤不可見。
4. 照服員輸入觀察，關閉時收到未保存提醒；繼續編輯後可保存，未知數值仍為空，狀態尚未評估。
5. nurse2 從交班給我開啟案件，確認接受後才可回覆；回覆後案件持續人工，填結果才結案。
6. 展開歷史，看到原進度、結案結果與接班護理師；本輪未傳送真實 LINE。
7. 管理帳號可查閱既有結案歷史；再切回照服員，舊對話仍為空。停止服務後重新整理，顯示連線中斷並保留照護卡片。

截圖與執行結果交付於本輪輸出資料夾；沒有把執行資料庫、登入工作階段或設定金鑰加入 Git。瀏覽器驗證不包含手機／平板或實際護理師使用性研究。

## 可重跑的完全虛構展示

在 `care_console/` 使用專案 Python 與既有 requirements：

```powershell
python -B demo_family_case.py --output demo-evidence.json
```

程式每次建立全新的暫存虛構環境，完成後刪除。傳入既有非空資料目錄會拒絕；不讀取預設 `runtime/`、不接真實 LINE，也不呼叫模型。

展示順序：

1. 虛構家屬詢問形成待接手案件，operator_id=null。
2. nurse 接手，責任 ID 變為 nurse。
3. 同對話的一般新問題保持人工案件。
4. 保存進度、提出交班，原責任維持。
5. 照服員讀對話及回覆遭拒，照護資料仍可讀。
6. nurse2 接收後取得責任並回覆；nurse 不得再代為結案。
7. nurse2 結案，保留歷史；另一聯絡人仍無這些訊息。
8. 重新建立應用，案件仍已結案、歷史責任 ID 仍正確。

輸出 `result=passed`、`actual_line_sent=false`、`model_calls=0` 與逐步狀態。這是測試客戶端的可重現演示；也已另外實際操作瀏覽器的相同主要流程。

## 未來 MVP 實作時的驗收案例

| 編號 | 目標情境 | 尚需完成的可證明結果 |
| --- | --- | --- |
| MVP-01 | 正式主管與 IT 分離 | IT 不能因管理權限讀家庭原文；主管只見所轄範圍，既有工作階段亦重查 |
| MVP-02 | 到期／逾期與跨班代理 | 有經機構確認的 due_at 與分母；未設定不可當逾期；通知失敗有替代責任 |
| MVP-03 | 真實 LINE 事件 | 來源驗證、重送去重、住民／關係／收件者映射、撤銷及結果不明均通過；本輪禁止開通 |
| MVP-04 | 護理師與主管新頁面 | 空資料、載入失敗、長清單、搜尋／分頁、未保存、403／409 與同步過時均可操作 |
| MVP-05 | AI 草稿進入正式流程 | 來源支持、版本／設定／時間與授權更新、核准時序、錯誤及配額控制端到端驗收 |
| MVP-06 | 機構 SOP | 護理師、照服員、臨床主管實際走完日班／夜班、急迫／申訴及斷線情境，記錄責任與操作負擔 |

這些案例是待辦，不包含於本輪 59 項通過數。未完成前維持本機虛構模式；不得將研究者角色扮演說成已通過正式護理之家驗收。

[MVP 入口](README.md) · [頁面規格](PAGE_SPEC.md) · [驗證紀錄](VERIFICATION.md)
