# 本輪實際驗證

2026-10-25（台灣時間），基準為已合併 PR #2 的 main `e7f319973806c89fc49eb3be0e1c59dc4cbf6034`。所有程式修改在獨立分支，未自行合併 main。

## 自動化測試

```text
python -B -m unittest -v test_care_console test_case_monitor

Ran 77 tests in 206.660s
OK
```

77 項包含原有 59 個測試名稱及新增 18 項監控、權限、遷移與工作階段測試。四個舊測試依新政策調整：院內角色及 IT 看板期待、角色清單、完整備份改由離線工具呼叫，以及生成中撤銷情境改由護理師建立訊息、IT 撤權；保留其原本要驗證的拒絕、撤銷、備份內容及還原斷言。

先跑四項重點檢查，通過後完整 75 項通過（203.245 秒）。瀏覽器發現背景回應干擾登入／登出，修正工作階段 cookie 與前端過期回應後，完整 76 項通過（207.120 秒）；最後補上既有護理長 ID 衝突的中止保護及測試，重新完整執行上述 77 項並通過。沒有把前一次通過數當成後續修改已驗證的證據。

環境為 Windows、Python 3.12.14、Flask 3.1.3／Waitress 3.0.2，依賴與暫存目錄獨立。測試使用暫存虛構資料、OfflineProvider，阻擋外部 socket。新增案例的 API 權限、資料內容及故障回復斷言均已執行。

| 驗收要求 | 實際測試／證據 |
| --- | --- |
| 護理長只看授權案件 | scope_is_applied_to_rows_statistics_owner_options_and_timeline；清單、統計與單案均排除 R003 |
| IT 無家屬／臨床原文 | it_cannot_read_or_write_clinical_content_or_download_backup；含原 API、內部讀取、自己授權及完整備份拒絕 |
| 照服員與護理師無主管 API | monitor_is_head_nurse_only_and_anonymous_is_rejected；原照服員資料允許清單回歸亦通過 |
| 主管唯讀且不能擴權 | head_nurse_is_read_only_and_cannot_extend_own_scope；案件所有寫入、匯入、移床及授權均拒絕 |
| 重疊統計不加總 | overlap_statistics_and_unset_deadlines_are_not_invented；三件未結案中的一件同時已接手／待接受 |
| 時限未知不當逾期 | 同上；極舊建立時間仍是 due_at=null、overdue=null，沒有假造到期 |
| 篩選、分頁及竄改 | filter_status_owner_and_timezone_aware_created_time、signed_pagination_cannot_change_scope_filter_or_viewer、invalid_filters_are_rejected_without_returning_cases |
| 新訊息與過時交班 | new_message_invalidates_cursor_and_handoff_without_transferring_owner，加上既有交班版本、人工狀態及草稿失效回歸 |
| 撤權影響既有工作階段 | scope_and_role_revocation_affect_existing_sessions_and_internal_reader、revoked_nurse_scope_blocks_old_owner_and_invalid_handoff，加上生成中聯絡人撤銷 |
| 進度歷史及唯讀無副作用 | timeline_retains_progress_revisions_and_pages_only_this_case、monitor_reads_do_not_change_case_messages_drafts_or_audit |
| 舊資料升級安全 | upgrade_preserves_passwords_history_and_old_nurse_scope_once、upgrade_failure_rolls_back_role_scope_deadline_and_marker、monitor_upgrade_snapshot_failure_aborts_before_mutation、upgrade_refuses_head_account_id_collision_without_privilege_promotion |
| 登出競態 | background_reads_do_not_reissue_auth_cookie_after_logout_race；另以瀏覽器實際在背景請求中登出並登入 IT |

表中省略 test_。完整 77 項清單見 [TEST_RESULTS.csv](TEST_RESULTS.csv)，機器可讀結果見 [VERIFICATION_RESULTS.json](VERIFICATION_RESULTS.json)。

## API 契約與研究

監控 OpenAPI 3.1 通過 openapi-spec-validator 0.7.2；2 個路徑／2 項 GET 操作均對應實際 Flask 路由。15 個 schema 的 13 組實際回應檢查通過，涵蓋空清單、待接手、責任與交班、進度事件、簽章分頁、三種角色拒絕、404、錯誤投影及結案；亦確認清單 schema 拒絕額外原文欄位。契約是監控子集，不聲稱涵蓋全站或未實作通知端點。

PR #1 研究重新驗證及最新 main 差異見 [RESEARCH_REVIEW](RESEARCH_REVIEW.md)。保留 18729be 的固定研究雜湊，沒有為新功能改寫原研究結果或補寫未知的競品能力。

文件另檢查 15 份 Markdown、81 個連結及 30 個表格，無本地目標、錨點或欄數錯誤；10 份新增／修改 Python 通過語法解析，前端通過 Node.js 語法檢查。Mermaid 12.2.0 成功解析原有兩張流程圖。23 個 core 檔案與 main 基準逐位元組一致。十張截圖已依實際 JPEG 格式保存並驗證，沒有更動影像內容。

## 實際瀏覽器操作

在 127.0.0.1:9666 與全新虛構資料目錄，以獨立測試服務操作。測試服務將監控回應延遲 0.6 秒，用於觀察載入與在途請求，未改正式應用路由或授權。

1. 護理長登入，空資料、載入提示、兩位住民範圍及四張零統計可讀。
2. 護理師在 R001 的獨立家屬對話建立詢問、接手、保存進度與提出 nurse2 交班；保存後可離開。
3. 護理長看見同一件案件已接手 1、交班待接受 1，下一步及原責任人正確；歷程唯讀，沒有回覆或改派操作。前一角色訊息已清空。
4. 透過本機 API 建立分頁虛構案例：護理長範圍內 14 件、R003 另 1 件。第一頁 10、下一頁 4，不包含 R003；最後頁的下一頁按鈕停用。
5. 狀態、責任 ID 及台灣時間篩選取得預期案件；反向時間回應錯誤並清除資料，輸入保留，可清除篩選重查。
6. 照服員只見兩張照護卡片；監控、歷程及前一角色訊息清空。未保存提醒可繼續編輯，保存後為尚未評估，未知量測仍空。
7. 指定 nurse2 接受交班、回覆並結案；原進度保留。護理長以結案及 nurse2 篩選取得該案，可讀提出、接受、回覆及結案歷程。
8. IT 撤銷 R001 後，護理長既有歷程重新查詢得到 404，案件內容清空，範圍只剩 R002。之後恢復本機示範授權。
9. IT 只見服務資訊及人員授權導覽，無照護工作台／監控；完整備份按鈕停用，前一角色內容為空。
10. 實際重現並修正背景 cookie 覆寫登出；在監控載入中登出並立即登入 IT 後，沒有舊角色或 CSRF 錯誤。
11. 停止測試服務後重新整理，顯示讀取失敗，清除案件列、統計及歷程。確認 9666 沒有監聽，關閉測試分頁。

已交付十張虛構畫面。沒有宣稱手機、平板、長期效能或第一線護理師使用性研究已完成。

## 可重現的三角色展示

`python -B demo_monitor.py --output monitor-demo.json` 已實際執行，result=passed、model_calls=0、actual_line_sent=false。護理師、護理長與照服員走完各自授權流程；另包括指定接班者、IT 拒絕、撤權及重新載入歷史。展示使用新的暫存資料，沒有讀寫使用者既有 runtime。

## 剩餘限制

沒有真實機構 SOP、正式帳號、住民資料、LINE 或模型品質驗收。時限、升級、改派、主管匯出及跨機構未實作。舊版未保存的進度歷史不會被回填成已知內容；本機 SQLite 與單程序鎖定不等於多程序一致性或不可竄改封存。正式授權核准、作業系統管理權、備份保管／加密、工作階段全面撤銷及機構現場驗收仍待完成。
