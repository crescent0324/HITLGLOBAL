# HITLGLOBAL 程式核對與差距分析

核對固定版本：[18729be4178e431418cbcbce010ca409f0b30fa9](https://github.com/crescent0324/HITLGLOBAL/tree/18729be4178e431418cbcbce010ca409f0b30fa9)。2026-10-24 已 fetch 確認當時 origin/main 為此版本。本輪只新增研究文件，沒有更動程式、資料庫、既有測試或原論文資料。

## 核對方法與證據範圍

本輪讀取根目錄與子專案 README、ROADMAP、對話隔離文件，並檢查應用入口、所有路由、資料表、觀察與授權、交班、生成生命週期、來源版本、前端及既有測試。完整固定版本共有 53 個追蹤檔案，逐檔路徑及 SHA-256 列於 [CODE_INVENTORY.csv](CODE_INVENTORY.csv)。

本機重新執行既有 `python -B -m unittest -v test_care_console`，47 項通過，138.847 秒。使用 Python 3.12 系列、Flask 3.1.3、Waitress 3.0.2、暫存資料與離線替代服務；未呼叫付費模型或真實 LINE。第一次執行因沙箱暫存目錄權限失敗，改將 TEMP／TMP 指向研究工作目錄後成功，沒有改測試以取得通過。命令及結果見 [驗證紀錄](VALIDATION.md)。

現有測試不是所有治理控制的完整驗收。[TEST_EVIDENCE.csv](TEST_EVIDENCE.csv)列出實際執行的 47 個測試、程式行號與核對組。[HITLGLOBAL_FEATURE_AUDIT.csv](HITLGLOBAL_FEATURE_AUDIT.csv)將矩陣全部功能逐列映射至程式及測試，而非只讀 README。

## A～D 的判定

| 類別 | 本研究定義 | 已找到的代表項目 |
| --- | --- | --- |
| A：已有實作且有測試 | 相應實作與具體斷言存在，本輪測試通過；只宣稱斷言涵蓋的行為 | 住民範圍、照服員不能設定評估狀態、多聯絡人隔離、撤銷阻擋、交班確認、CSV 原子匯入與還原 |
| B：已有實作但未充分驗證 | 有程式或介面，缺少直接覆蓋完整語意／失敗條件的測試與場域驗收 | 全套 AI 草稿核准、設定／知識／時間失效控制、線上模型、前端使用性 |
| C：只有文件或設計 | ROADMAP 提出目標，應用尚不可完成該端到端工作 | 真實 LINE 配對收發、正式員工生命週期、護理長／IT 分離、院內介接、常駐與場域試用 |
| D：完全尚未開發 | 固定版本的完整功能、資料模型與操作入口均未提供此工作；不是僅搜尋不到字串 | 標準護理計畫、傷口／管路／給藥、感染管理、人資薪資、財務、營養餐食、完整評鑑與不可竄改稽核 |

同一主題可拆成不同層次，例如：聯絡人隔離是 A，真實 LINE 身分驗證是 C，既有底層傳輸類別存在也不能把端到端功能改判成 A。矩陣的「部分支援」與 A／B／C／D 是不同維度。

## 現有能力與成熟 ERP 的差距

| 領域 | 當前程式行為 | 與競品研究所指工作之差距 |
| --- | --- | --- |
| 住民與床位 | 有住民、床位配置與轉床；換床不改住民身分 | 沒有完整入退住、契約、住民病史與行政流程 |
| 前線照護 | 五項量測、觀察時間／入庫時間／來源、自由文字與四種狀態 | 不是 NANDA、ADL 等完整評估，沒有護理問題—措施—評值、給藥、傷口及管路模組 |
| 照服員 | 依授權只見特定住民，可寫觀察，評估狀態固定尚未評估 | 沒有服務排班、每日任務派工與所有照顧項目表單 |
| 人工協作 | 待辦、接手者、已處理內容、下一步、待確認、指定交班及結案 | 交的是服務案件；尚缺正式值班表、逾時責任與現場通知驗收 |
| 家屬資訊 | 模擬聯絡人與住民分開，對話、案件與生成隔離；撤銷擋回覆 | 真實身分、LINE Webhook、實際收件者、查詢揭露範圍與送達結果尚未接通 |
| 主管監督 | 可看訊息待辦與最近已評估追蹤狀態 | 沒有臨床品質指標分子分母、異常事件趨勢、工作負荷及財務儀表 |
| 匯入備份 | 虛構量測 CSV 有去重與整批回復，兩個 SQLite 可快照及新目錄還原 | 未形成實際 ERP／IoT 連接器、異地備援、排程及離場資料格式 |
| AI | 受限服務資訊生成核心、版本與來源資料、人工草稿 API 存在 | 正式臨床資料摘要與真實模型驗收未完成；合法來源 ID 不保證逐句正確 |
| 權限及安全 | 後端角色／住民檢查、CSRF、localhost、部分稽核 | admin 合併護理長與 IT；沒有完整企業身分生命週期、TLS 正式入口、靜態資料加密及不可竄改封存 |

程式依據依下方核對組及 [CODE_EVIDENCE.csv](CODE_EVIDENCE.csv)逐項定位。`core/web.py` 等底層或另一入口的能力，沒有據此推定已經接入 `care_console/run.py` 使用的應用。

## 八個產品與研究問題

### 1. 哪些成熟功能不宜先重做

護理紀錄、專業表單、照護計畫、品質統計、人事薪資、財會、耗材及核銷已是競品產品的重要範圍。HITLGLOBAL 短期若全面重建，還需處理專業分類授權、表單版本、申報規範及多年資料移轉。研究者建議優先讓既有 ERP 維持照護與行政主檔，HITLGLOBAL 專注訊息協作與治理。[J02](SOURCES_AND_EVIDENCE.md#j02)、[C01](SOURCES_AND_EVIDENCE.md#c01)、[U11](SOURCES_AND_EVIDENCE.md#u11)

### 2. 哪些可以合法 API 整合

已知三家各有某些既有介接，但本輪沒有找到可讓 HITLGLOBAL 直接使用的公開 API 契約。可行路徑是機構與廠商書面確認的唯讀 API，或經授權、格式明確的匯出檔；不能把政府支審／健保的專屬介接權利當成一般第三方權利。完整所需條件見[產品策略](PRODUCT_STRATEGY.md)。[J12](SOURCES_AND_EVIDENCE.md#j12)、[C01](SOURCES_AND_EVIDENCE.md#c01)、[U11](SOURCES_AND_EVIDENCE.md#u11)

### 3. HITL 控制有什麼可證實的價值

目前已測的是：低風險新訊息不解除同對話人工案件、只有目前接手者能處理、指定接班者確認才移轉、授權撤銷後停止回覆及生成結果、同住民不同聯絡人不混對話。這些控制把「收到、待處理、已有人負責、可對誰送出」分開，具體降低已測情境中的錯誤操作空間。未量測到場域事故下降、臨床效果或跨分散式併發的保證。

### 4. 哪些差異競品也已提供

角色權限、操作稽核、行動照護與資料整合已有競品證據；Jubo 另明示 AI 由專業人員主導，Amy 提供來源與既有權限，並有線上簽核。因而「有人工、有引用、有權限、有交班」均不能當獨家賣點。[J05](SOURCES_AND_EVIDENCE.md#j05)、[J06](SOURCES_AND_EVIDENCE.md#j06)、[J10](SOURCES_AND_EVIDENCE.md#j10)、[J15](SOURCES_AND_EVIDENCE.md#j15)、[C02](SOURCES_AND_EVIDENCE.md#c02)、[U11](SOURCES_AND_EVIDENCE.md#u11)

### 5. 哪些是可驗證的競爭機會

可提出的假設是「將訊息收件權限、責任移轉與生成有效性做成可檢查的一條鏈」，並以撤銷、交班期間新訊息、模型延遲及資料更正等情境比較。競品公開資料不足以確定其內部沒有同等控制，現階段沒有已實證的獨家或市場優越性。需要同題 Demo 與場域資料，才能確認比較優勢。

### 6. ERP 整合的障礙

住民唯一識別與床位不同；家屬關係也不能直接化為收件權。其餘障礙包括資料授權、欄位與單位、觀察及同步時間、補登更正、刪除撤銷、連線中斷、事件去重、來源版本、API 限額與成本。更大的流程問題是誰維護主檔、誰對 AI 輸出負責，以及資料更新後已審草稿能否繼續發送。這些均須在整合契約與驗收案例中具體定義。

### 7. 最適合試點的三項增量

| 優先項目 | 已有基礎 | 試點還要完成 |
| --- | --- | --- |
| 真實 LINE 家屬授權與收件核對 | 本機 CONTACT、REVOKE | 真實綁定、Webhook 去重、收件者映射、撤銷與結果不明處理 |
| 跨班人工案件責任與逾時追蹤 | CASE、HANDOFF | 機構值班責任、到期定義、提醒與接收／代理驗收 |
| 可追溯照護來源與草稿過時阻擋 | IMPORT、GEN、CONTEXT | 經授權唯讀資料、臨床內容範圍、審閱確認、更新失效與端到端測試 |

這是研究者建議的試點順序，完整假設、指標及停止條件見 [PRODUCT_STRATEGY.md](PRODUCT_STRATEGY.md)。

### 8. 哪些超出原 HITL 論文範圍

薪資、財會、庫存、餐食、完整護理紀錄、保險核銷及機構 ERP 替換，偏離原 LINE 聊天機器人治理核心。真實身分、臨床資料、跨班責任及正式場域試用雖與治理相連，也新增倫理、資料與現場流程條件，應另訂研究／產品驗收，不將新試用結果回填原論文樣本或凍結成果。依儲存庫 [分離文件](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/docs/SEPARATION.md)維持界線。

## 工程證據與市場假設分開

| 結論類型 | 目前能說的話 | 目前不能證明 |
| --- | --- | --- |
| 已實證工程能力 | 47 項測試中的隔離、撤銷、交班、來源時間與還原行為 | 競品都沒有、機構願意付費、臨床事故已下降 |
| 尚未充分驗證的實作 | 生成前後與審閱時的部分有效性檢查可讀 | 所有競態、模型錯誤、多人部署與真實傳輸都已涵蓋 |
| 市場假設 | 現場可能需要可追蹤的家屬訊息責任與內容有效性 | 問題頻率、付費意願、導入成本與淨效益 |
| 待比較機會 | 可以設計同題情境讓競品與 H 演示 | 公開資料不足不能當成競品失敗結果 |

## 程式與測試核對組

以下各組是功能矩陣與逐項稽核 CSV 的查核索引。每個連結固定至本輪讀取的 commit；行號只定位實作，不表示整個方法都已測試。A／B 或 A／D 表示同組的不同子能力，逐項分類仍以矩陣及 CSV 為準。

### BASE — 本機體驗環境與可讀程式架構

實作分類：A／B。

程式依據：[care_console/app.py:27](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/app.py#L27)、[care_console/run.py:8](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/run.py#L8)、[care_console/requirements.txt:1](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/requirements.txt#L1)。

對應測試：

- [test_restart_keeps_existing_data_and_does_not_reseed](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L237)
- [test_unauthenticated_and_remote_access_denied](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L80)

適用界線：A 為本機行為；B 為未做正式部署、負載及架構可用性驗收。

### AUTH — 院內角色、住民範圍及工作階段

實作分類：A。

程式依據：[care_console/app.py:69](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/app.py#L69)、[care_console/app.py:83](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/app.py#L83)、[care_console/care_store.py:129](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/care_store.py#L129)。

對應測試：

- [test_roles_have_distinct_resident_scopes](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L99)
- [test_family_and_resident_cannot_log_in_to_web](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L107)
- [test_access_revocation_takes_effect_on_current_session](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L207)
- [test_csrf_and_cross_origin_login_rejected](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L85)
- [test_password_and_login_rate_limit](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L89)

適用界線：固定示範角色；沒有完整帳號生命週期及護理長／IT 分離。

### BOARD — 住民看板與訊息待辦

實作分類：A／B。

程式依據：[care_console/app.py:165](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/app.py#L165)、[care_console/workflow.py:106](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/workflow.py#L106)、[care_console/static/app.js:95](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/static/app.js#L95)。

對應測試：

- [test_work_queue_orders_message_risk_and_explains_origin](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L262)
- [test_caregiver_queue_stays_within_assigned_residents](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L285)
- [test_board_lists_each_contact_case_and_cross_thread_handoff_is_rejected](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L460)

適用界線：A 為 API／排序與範圍；B 為未量測的前端便利性及完成率語意。

### OBS — 觀察回報、量測來源及評估狀態限制

實作分類：A。

程式依據：[care_console/care_store.py:149](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/care_store.py#L149)、[care_console/care_store.py:155](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/care_store.py#L155)、[care_console/care_store.py:172](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/care_store.py#L172)、[care_console/care_store.py:209](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/care_store.py#L209)。

對應測試：

- [test_caregiver_observation_cannot_set_assessment](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L115)
- [test_missing_values_remain_unknown_and_old_record_is_not_latest](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L187)
- [test_unassessed_reports_do_not_clear_recorded_followup](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L381)
- [test_assessment_uses_observed_time_and_keeps_unknown_separate](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L402)
- [test_tracking_status_requires_reason](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L357)

適用界線：五項量測加自由文字；不是標準護理評估、護理計畫或臨床判斷。

### BED — 轉床與住民識別保留

實作分類：A。

程式依據：[care_console/care_store.py:253](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/care_store.py#L253)、[care_console/app.py:333](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/app.py#L333)。

對應測試：

- [test_transfer_keeps_resident_records_and_grants](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L196)

適用界線：只證明既有住民轉床，沒有完整入退住行政流程。

### IMPORT — 虛構量測 CSV 原子匯入

實作分類：A。

程式依據：[care_console/care_store.py:227](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/care_store.py#L227)、[care_console/app.py:358](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/app.py#L358)。

對應測試：

- [test_atomic_csv_rejects_invalid_row_without_partial_insert](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L164)
- [test_csv_duplicate_idempotency_and_conflict_roll_back](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L170)
- [test_csv_requires_synthetic_confirmation_and_known_resident](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L179)

適用界線：1～500 筆、虛構確認與指定欄位，不是實際 ERP 或 IoT 連接器。

### CONTACT — 同住民多聯絡人對話隔離

實作分類：A。

程式依據：[care_console/conversations.py:41](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/conversations.py#L41)、[care_console/conversations.py:61](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/conversations.py#L61)、[care_console/app.py:225](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/app.py#L225)。

對應測試：

- [test_contacts_have_separate_messages_cases_and_reply_recipients](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L426)
- [test_two_family_contacts_do_not_share_context](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L444)
- [test_cross_resident_conversation_read_and_action_are_rejected](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L481)
- [test_message_source_must_match_selected_conversation](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L537)
- [test_legacy_shared_records_are_not_assigned_to_contacts](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L546)

適用界線：聯絡身分與傳輸皆為本機模擬；未完成真實 LINE 身分驗證。

### REVOKE — 配對撤銷及生成期間撤銷

實作分類：A。

程式依據：[care_console/app.py:372](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/app.py#L372)、[care_console/conversations.py:119](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/conversations.py#L119)、[care_console/conversations.py:122](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/conversations.py#L122)。

對應測試：

- [test_contact_revoke_blocks_reply_and_keeps_history](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L504)
- [test_contact_revoke_during_generation_cancels_old_result](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L518)
- [test_live_transport_cannot_use_a_logical_thread_as_recipient](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L566)

適用界線：只在已測本機流程成立；未證實分散式競態或 LINE 已收件。

### CASE — 人工接手、進度、回覆與結案

實作分類：A。

程式依據：[care_console/core/service.py:163](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/core/service.py#L163)、[care_console/core/service.py:184](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/core/service.py#L184)、[care_console/app.py:273](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/app.py#L273)。

對應測試：

- [test_same_contact_conversation_keeps_manual_state](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L132)
- [test_only_current_case_owner_can_reply_and_resolve](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L143)
- [test_stale_case_id_cannot_target_a_new_case](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L493)

適用界線：人工所有權仍依現有體驗帳號，未完成正式員工帳號治理。

### HANDOFF — 指定人員確認交班及防過時接收

實作分類：A。

程式依據：[care_console/workflow.py:132](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/workflow.py#L132)、[care_console/workflow.py:150](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/workflow.py#L150)、[care_console/workflow.py:165](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/workflow.py#L165)。

對應測試：

- [test_progress_requires_owner_and_resists_stale_overwrite](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L291)
- [test_handoff_requires_summary_next_action_and_valid_recipient](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L298)
- [test_handoff_changes_owner_only_after_recipient_accepts](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L305)
- [test_new_message_invalidates_pending_handoff_acceptance](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L321)
- [test_progress_update_cancels_old_handoff_and_new_request_can_be_accepted](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L330)
- [test_resolve_cancels_handoff_and_keeps_history](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L341)
- [test_handoff_and_progress_survive_restart](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L417)

適用界線：交的是服務案件責任，未含完整護理交班表與人力排班。

### RISK — 規則分級與高風險停止一般生成

實作分類：A。

程式依據：[care_console/core/live.py:117](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/core/live.py#L117)、[care_console/core/service.py:184](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/core/service.py#L184)、[care_console/core/research.py:52](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/core/research.py#L52)。

對應測試：

- [test_high_risk_has_no_general_generation](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L158)
- [test_same_contact_conversation_keeps_manual_state](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L132)

適用界線：本輪只測既有功能情境；未重做原論文分類效度、臨床分流或敏感度研究。

### GEN — 生成生命週期與人工草稿審閱

實作分類：B。

程式依據：[care_console/core/research.py:42](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/core/research.py#L42)、[care_console/core/research.py:115](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/core/research.py#L115)、[care_console/core/research.py:179](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/core/research.py#L179)、[care_console/core/research.py:210](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/core/research.py#L210)、[care_console/core/generation.py:86](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/core/generation.py#L86)。

對應測試：

- [test_contact_revoke_during_generation_cancels_old_result](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L518)

適用界線：該測試只直接覆蓋撤銷過程，未充分驗證中風險核准、所有失效原因、真實模型及傳輸失敗。

### CONTEXT — 受限歷史、來源及版本有效性

實作分類：B。

程式依據：[care_console/core/model_context.py:32](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/core/model_context.py#L32)、[care_console/core/model_context.py:95](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/core/model_context.py#L95)、[care_console/core/model_context.py:129](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/core/model_context.py#L129)。

對應測試：

- [test_context_includes_existing_service_reply_without_generated_summary](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L350)
- [test_two_family_contacts_do_not_share_context](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L444)

適用界線：直接測到固定摘要與隔離；未充分測知識／提示／時間界線，來源 ID 合法不代表逐句正確。

### AUDIT — 人員事件稽核與不可竄改界線

實作分類：A／D。

程式依據：[care_console/care_store.py:168](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/care_store.py#L168)、[care_console/core/service.py:148](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/core/service.py#L148)、[care_console/workflow.py:42](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/workflow.py#L42)。

對應測試：

- [test_same_contact_conversation_keeps_manual_state](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L132)
- [test_only_current_case_owner_can_reply_and_resolve](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L143)
- [test_resolve_cancels_handoff_and_keeps_history](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L341)

適用界線：A 為已測事件留存；D 為不可竄改儲存、外部封存與完整稽核產品尚未實作。

### BACKUP — SQLite 快照及新目錄還原

實作分類：A。

程式依據：[care_console/app.py:388](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/app.py#L388)、[care_console/conversations.py:17](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/conversations.py#L17)。

對應測試：

- [test_backup_restores_into_new_directory_without_secrets](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L218)
- [test_restart_keeps_existing_data_and_does_not_reseed](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L237)
- [test_legacy_shared_records_are_not_assigned_to_contacts](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L546)

適用界線：人工備份，不是每日異地備援、正式 DR 演練或資料離場格式。

### UI — 未保存內容、草稿介面及行動版行為

實作分類：B。

程式依據：[care_console/static/app.js:13](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/static/app.js#L13)、[care_console/static/app.js:218](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/static/app.js#L218)、[care_console/templates/index.html:50](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/templates/index.html#L50)。

本輪沒有足以驗證此項完整行為的對應測試。

適用界線：可讀實作與既有記錄，本輪未重跑瀏覽器、平板或實際護理師使用性測試。

### DEPLOY — 真實 LINE、院內介接、帳號分工與常駐規劃

實作分類：C。

程式依據：[docs/ROADMAP.md:1](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/docs/ROADMAP.md#L1)、[care_console/app.py:83](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/app.py#L83)、[care_console/conversations.py:122](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/conversations.py#L122)。

對應測試：

- [test_unauthenticated_and_remote_access_denied](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L80)
- [test_live_transport_cannot_use_a_logical_thread_as_recipient](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/test_care_console.py#L566)

適用界線：測試證明現版阻擋對外通道，並不代表 ROADMAP 的部署功能完成。

### ERP — 完整臨床及行政 ERP 功能尚未開發

實作分類：D。

程式依據：[care_console/app.py:118](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/app.py#L118)、[care_console/care_store.py:38](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/care_store.py#L38)、[care_console/templates/index.html:1](https://github.com/crescent0324/HITLGLOBAL/blob/18729be4178e431418cbcbce010ca409f0b30fa9/care_console/templates/index.html#L1)。

本輪沒有足以驗證此項完整行為的對應測試。

適用界線：以完整追蹤檔案清單、路由、資料表、頁面及業務文件核對；未見護理計畫、給藥、傷口、感染、人資薪資、財會等可用模組。


[返回研究入口](README.md) · [工作流程](WORKFLOW_COMPARISON.md) · [策略](PRODUCT_STRATEGY.md)
