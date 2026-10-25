# 角色分離、舊資料與備份

本輪只升級本機虛構體驗環境。啟動前先停止舊服務；沒有操作真實住民資料或原論文資料庫。

## 升級順序

1. 在既有資料庫變動前，建立 `backups/before-staff-scope-monitor-v2-隨機碼/`，保存兩個 SQLite、環境識別與 manifest，不複製設定檔及工作階段金鑰。快照失敗中止啟動。
2. 沿用 PR #2 的穩定責任 ID 遷移；新增活動資料表及角色轉換紀錄。
3. 在明確交易中新增 nullable `cases.due_at`，為原先具有全住民隱含權限的護理師保存一次明確 access。此後重啟不會重授已撤銷範圍。
4. 原 admin 帳號保留 ID、帳號及密碼雜湊，改為 IT 能力；原示範顯示名稱才更新為 IT 名稱，自訂名稱不重設。舊合法評估透過轉換時間保留來源，不因今天角色改變就清除歷史。
5. 新增獨立 head_nurse 示範身分，預設只授權 R001、R002；既有同名 ID 不會被提升或覆寫，帳號名稱衝突會中止待確認。
6. 保留原稽核事件與最新進度為舊版快照。仍由原合併管理身分接手的案件回待接手、取消舊草稿及交班，不自動指派護理長；已結案歷史不捏造新的責任人。
7. 寫入 `meta.staff_scope_monitor_v2`，之後不重新灌入種子、重設密碼或反覆匯入歷史。
8. 本輪增加 `case_monitor_indexes_v3`：既有環境先建立 `before-case-monitor-indexes-v3-*` 快照，再於交易內新增 `cases(conversation_id,id)` 與 `messages(conversation_id,id)` 索引及完成標記。只新增索引，不改案件、帳號、責任、進度或授權；重啟不重複備份與遷移。全新環境初始化時直接建立索引。

交易故障會回復角色、授權、期限欄位、案件與完成標記；既有資料表初始化可能留下空的新表，這不表示遷移已完成。完成標記缺少時可在修正原因後重試。測試包含故障注入、原快照、密碼／內容保留及重啟不重授。

## 完整備份離開網頁入口

完整 SQLite 包含所有住民、家屬訊息及帳號資料，不能用 IT 的系統管理身分下載，也不開給只有部分範圍的護理長。

保留相同 SQLite backup 與還原能力，移到持有作業系統資料目錄權限的人員手動操作。在 `care_console/`、停止原服務後：

```powershell
python -B backup_local.py --data-dir runtime
```

工具核對既有虛構環境與資料庫，取得與 run.py 相容的程序鎖，再建立 ZIP；不建立新住民、不啟動應用或順便進行遷移。服務仍使用同目錄時會拒絕。備份不含 API 設定或 session.key，但包含敏感的資料庫內容及帳號雜湊，不能公開交付。

還原仍使用全新目錄：facility.sqlite3 放根目錄；core.sqlite3 放到 core/research.sqlite3；environment.json 放根目錄；core-environment.json 放到 core/integration-environment.json。保留原備份，不覆蓋運作中的資料庫；使用新工作階段，核對虛構內容、授權與歷史後再操作。

## Manifest 與失敗產物

新備份使用 `format_version: 2`。`credentials_included: true` 表示包含可被離線攻擊的密碼雜湊；先前的 false 標記不精確，舊備份檔不會被自動改寫或刪除。即使舊 manifest 寫 false，也應視為敏感資料。

| 欄位 | 新備份值 | 意義 |
| --- | --- | --- |
| plaintext_passwords_included | false | 應用的密碼儲存欄位只保存雜湊；沒有複製明文密碼檔。這不保證任意業務自由文字從未被人填入密碼。 |
| password_hashes_included | true | facility.users 的 password_hash 在 SQLite 中。 |
| session_keys_included | false | session.key 不在備份中；還原使用新工作階段金鑰。 |
| api_configuration_included | false | 不複製 config.local.json、API 金鑰或 LINE token 設定檔。 |
| business_data_included | true | 案件、進度、歷史、訊息、住民、配對與授權均可能在資料庫中。 |

先在同一 backups 檔案系統的 `.incomplete-*` 目錄製作 SQLite backup，驗證每個副本的 integrity_check，記錄檔案大小與 SHA-256。升級快照完成 manifest 後才原子更名為 `before-*`；離線工具完成 ZIP CRC 檢查後才更名為 `care-demo-*.zip`。成功 ZIP 的本次暫存副本會清除；既有備份與來源資料不變。

失敗留下 `.incomplete-*` 和可寫入時的 failure.json（只有錯誤類型，不含敏感錯誤字串），不發布成功名稱。磁碟已滿時可能連診斷檔也寫不出，仍以 `.incomplete-*` 名稱判定不可還原。作業中斷也可能留下該目錄；不得只看到其中某個資料庫或 manifest 就當成完整備份。維運人員須確認失敗原因後，依機構政策處理這些敏感殘留。現有 `.gitignore` 排除任意層的 backups/、runtime/、SQLite、金鑰與記錄檔；提交前仍檢查實際追蹤清單。

還原前確認成功名稱、status=complete、兩個資料庫及環境識別檔齊全，核對 manifest 的大小與 SHA-256，檢查 ZIP CRC 與 SQLite integrity_check。升級目錄中的 integration-environment.json 對應 core/integration-environment.json；ZIP 內則使用 core-environment.json。使用新目錄完成角色、授權、案件責任、交班、歷史與登出驗證；保留原服務與備份直到驗收。

## 正式部署前的備份設計

機構須指定獨立的資料保管人、最小 OS 存取權限及讀取稽核；不得透過 IT 網頁角色下載完整資料庫。正式備份應採經核准的靜態加密，金鑰與備份分開保存，建立金鑰輪替、失竊處理及復原授權程序。本輪沒有實作備份加密或雲端服務。

保存期限、輪替數量、刪除核准、異地副本、可接受資料損失與復原時間由機構及適用規範確認，不在示範程式中硬設天數或自動刪除。備份工作與還原演練須可稽核；定期在隔離環境驗證完整性、版本相容、金鑰取得與業務流程，記錄失敗與改善。複製兩個資料庫前仍須停止服務或持有相同服務鎖及維運程序，SQLite backup 本身不構成跨服務的一致性保證。

## 工作階段與範圍

每次 API 都重讀目前帳號角色與 access。護理長撤權後的清單、統計、游標及單案歷程都必須重驗；護理師撤權後不能繼續寫入，舊責任無效時接班亦須重新確認。

背景 GET 不再每次重新簽發登入 cookie，避免較慢的舊回應在登出後覆寫登入狀態；前端也會忽略先前工作階段的回應。登入仍更新 CSRF，工作階段最長一小時。這項修正已用背景監控請求途中登出、隨即登入 IT 的瀏覽器情境驗證。

正式停權、憑證失竊後的全面工作階段撤銷、OS 管理權、備份加密與多人維運仍未完成，不將 localhost 示範登入描述成正式身分服務。
