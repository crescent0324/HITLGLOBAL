# 第二輪獨立 Code Review

初次審查時間：2026-10-25 11:05–11:09（Asia/Taipei）。

審查目錄：`本分支工作目錄`。
基準：`2d23e85ad76bfe87644f8e5926f6b3ccbfacfbae`；分支：`fix/monitor-refresh-pagination-backup-20261025`。包含對基準的已追蹤差異與本輪新檔。Reviewer 未修改 production code、未 commit／push、未發 GitHub 評論。

## 結果

初次發現 1 項 P2；實作者修正後已經獨立複查通過，目前沒有未結案 findings。其餘已檢查範圍未發現可重現且有實際影響的新問題；這不表示不存在其他缺陷。

### 初次 P2（已修正並複查）：未解決的案件歷程錯誤仍會被背景輪詢清除並自動重查

- 位置：`care_console/static/app.js:286–296`（歷程錯誤處理），相關路徑為 `:204` 的背景輪詢阻擋條件與 `:213` 的視窗內容重設。
- 觸發條件：護理長已取得案件清單，開啟任一案件歷程；歷程 GET 回傳 400、403 且重新核對後仍為同一護理長、500 或網路失敗。保持案件視窗開啟且不再操作，等下一次 15 秒輪詢。
- 實際結果：歷程分支僅顯示錯誤，未建立會阻擋輪詢的 error 狀態。下一次 `refreshMonitor(...,{background:true})` 仍發出清單 GET，立即將錯誤改成「正在重新核對案件權限…」；清單成功後還會自動重讀歷程。未處理的錯誤被覆蓋，也使 400／403 這類應等待使用者處理的失敗被背景反覆重試。
- 影響：錯誤語意與保留規則只有清單受到保護，案件歷程不受保護；使用者尚未處理的失敗可能消失。與本輪 A 的錯誤保留要求及 HARDENING.md 的敘述不一致。此問題未證實會造成未授權讀取或資料寫入，因此列 P2。
- 修正方向：為歷程建立可辨識的未解決錯誤狀態，納入背景輪詢的阻擋條件；只有明確手動查詢／重試、關閉或切換案件／工作階段等適當操作才清除。保留 403 的角色重驗與既有 404 清單失效保護。

### 原始獨立重現證據

腳本：`交付包內 independent-timeline-error-repro.cjs`。腳本重用既有 JSDOM boot/fetch 控制框架並執行實際 app.js，沒有改寫 production code，也沒有先完成背景清單回應才檢查。

原始斷言：

```javascript
h.polls[0]();await tick();await tick();
assert.equal(h.requests.length,2,
  'background must not silently clear/retry unresolved timeline errors');
assert.match(h.document.querySelector('#monitor-events').textContent,/synthetic/);
```

初次結果：400、403（角色不變）、500、network 四個情境均失敗；每個情境都是 `actual: 3`、`expected: 2`，確認背景輪詢在未解決歷程錯誤後又發出請求。4 tests、0 pass、4 fail，約 0.853 秒。失敗是此次獨立重現的預期結果，不能列為產品通過證據。

初次檢查 app.js SHA-256：`D7815E19006421FDD576B12AAFD2E4BA5EA75949C5F7B2FF70386051EE6778AF`。

## 已核對範圍

- 前端：requestId、AbortController、epoch／角色檢查，手動讀取繞過全域寫入 busy，清單／歷程 409 的一次回第一頁，延遲 401、登出／IT 切換／撤權，篩選草稿與清單錯誤保留、輪詢去重。
- 後端：SQL 授權 JOIN、SQL 聚合與原 item／DTO 的有效交班語意、owners GROUP BY、逐列 JSON SHA-256 的原雜湊相容性、keyset、清單／歷程 BEGIN 讀取交易、索引備份與一次性遷移。
- 備份：新 snapshots.py、離線 ZIP 與各升級快照，密碼雜湊／業務資料敏感性聲明、SQLite 完整性檢查、SHA-256、同檔案系統完成更名、失敗殘留與舊備份保留、還原說明與 Git 忽略規則。
- 文件與證據：PERFORMANCE.md 及六份 raw benchmark JSON、HARDENING.md、MIGRATION.md、NEXT_PHASE.md、既有 90 項 Python 日誌、18 項前端日誌、OpenAPI 實際回應檢查結果、localhost browser-qa.json。NEXT_PHASE 維持設計草案，未賦予護理長新操作權限或自訂 SOP／醫療急迫門檻。

## 本次實際執行

- 原有 Node/JSDOM 前端測試：18／18 通過，約 1.710 秒。
- 針對性 Python：test_backup_hardening 的 5 項，加上 SQL 統計語意、stream fingerprint、索引重啟保留三項，共 8／8 通過，8.932 秒。
- 獨立歷程錯誤重現：4／4 成功重現問題（測試斷言為 4 fail，詳上）。
- `git check-ignore` 確認 runtime SQLite、backups ZIP、.incomplete 殘留路徑均被忽略。
- 六份 benchmark JSON 的 before／after invariant_sha256、案件總數及每項三筆樣本中位數另外以 Python 小腳本核對，100／1,000／10,000 三組全相符。
- `git diff --check` 另回報 README 新增行的尾端空白／CRLF；屬格式訊息，未升列功能 finding。

未重跑整套 90 項測試，未重跑全部 benchmark，未另外操作真實瀏覽器；這三類證據為閱讀既有交付產物。沒有使用真實住民資料、LINE 或模型。

## 修正後複查

複查時間：2026-10-25 11:11（Asia/Taipei）。

實作者以獨立的 `historyError`／`historyLoading` 保存歷程狀態；`refreshMonitor` 的背景 guard 同時檢查清單與歷程的錯誤／載入，歷程錯誤分支設定 `historyError`，finally 依 epoch＋sequence 回收 loading。關閉歷程只清歷程旗標，保留清單 `error`。關鍵位置為修正後 app.js 的 `:204`、`:289`、`:300`、`:478`。

獨立重跑原始四個斷言：4／4 通過（約 0.864 秒）。保留四個原斷言，另增加下列三個邊界情境後，共 7／7 通過（1.047 秒）：

1. 帶 cursor 的歷程 409 自動回第一頁後，第二次 409 不再重試且錯誤跨輪詢保留。
2. 清單讀取失敗時關閉歷程，清單錯誤仍保留，輪詢不另發請求。
3. 歷程 GET 尚未完成時連續觸發背景輪詢，不新增 GET，也不 abort 正在執行的歷程。

另外重跑當前全部前端測試：21／21 通過（1.946 秒）。production Python 未因本次修正再變動，沒有重跑 90 項全套。複查 app.js SHA-256：`6DCD6EEE74FA021AC8A3E9EFDEE10C833E2AEAC9A5ECD027D34FD75B5B285F1E`。

初次 P2 已解決；此次複查沒有新增 findings。Reviewer 仍未修改 production code、commit／push 或發 GitHub 評論。


## 交付格式核對

依儲存庫保留精確換行位元組的規則，實作者使用 `git -c core.whitespace=cr-at-eol diff --check` 核對通過，沒有為消除 CRLF 訊息而批次重排既有文件。公開文件中的本機絕對路徑已改為相對描述；原始獨立報告及重現腳本保留於本機交付包。
