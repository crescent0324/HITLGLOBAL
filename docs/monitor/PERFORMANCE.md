# 案件監控效能實測

基準為 main `2d23e85ad76bfe87644f8e5926f6b3ccbfacfbae`。全為程式建立的虛構資料；外部網路被測試替代阻擋，真實 LINE 傳送與模型呼叫均為 0。

## 環境與方法

Windows-11-10.0.26300-SP0；Python 3.12.14；SQLite 3.53.1；CPU Intel64 Family 6 Model 186 Stepping 2, GenuineIntel；20 個邏輯處理器。Flask 3.1.3，與 before 相同的 Python 與相依套件。

資料建立與量測分開。before 使用已核對與基準 care_console 相同的獨立工作目錄；after 使用本分支。每個規模、每個階段用新程序啟動相同資料的副本；啟動、建立虛構資料、索引升級與快照時間不計入查詢耗時。每項三次暖快取循序實測取中位數，原始三筆數值完整保存。另跑第四次 tracemalloc，避免把量測記憶體的額外成本混入計時。這是本機應用層查詢測試，沒有多使用者負載、網路延遲、冷快取或正式服務 SLA 保證。

六位住民輪流分配，護理長只授權 R001、R002。每個聯絡人對話五個案件（四個已結案與一個未結案），約 80% 已結案、10% 已接手、10% 待接手；每案一筆進度及三筆歷程、每個對話四筆訊息。部分已接手案件有待接受交班，其中一半刻意使訊息版本過時。實際案件總數與狀態分布、授權件數均在原始 JSON。

清單與翻頁均包含統計、範圍驗證及簽章版本。獨立統計 before 重現原先載入各列及 DTO 計算，after 呼叫相同查詢的 SQL 聚合；這是內部階段量測，沒有新增統計 API。歷程每頁兩筆以實際觸發分頁。

## 耗時（毫秒，中位數）

| 全部／授權案件 | 作業 | before | after |
| --- | --- | ---: | ---: |
| 100／40 | 清單含統計 | 3.913 | 3.686 |
| 100／40 | 獨立統計階段 | 2.790 | 1.593 |
| 100／40 | 下一頁含統計 | 3.793 | 4.033 |
| 100／40 | 單案歷程 | 1.884 | 1.518 |
| 1,000／340 | 清單含統計 | 16.705 | 12.458 |
| 1,000／340 | 獨立統計階段 | 11.831 | 3.359 |
| 1,000／340 | 下一頁含統計 | 16.829 | 12.690 |
| 1,000／340 | 單案歷程 | 2.113 | 1.685 |
| 10,000／3,340 | 清單含統計 | 505.456 | 128.687 |
| 10,000／3,340 | 獨立統計階段 | 467.390 | 15.668 |
| 10,000／3,340 | 下一頁含統計 | 510.665 | 137.168 |
| 10,000／3,340 | 單案歷程 | 4.239 | 3.674 |

## 記憶體

| 全部案件 | 清單 Python 尖峰 before／after（MiB） | 程序尖峰 RSS before／after（MiB） |
| --- | ---: | ---: |
| 100 | 0.473／0.335 | 46.086／46.242 |
| 1,000 | 2.842／0.336 | 47.234／46.426 |
| 10,000 | 27.950／0.336 | 83.543／49.023 |

tracemalloc 只涵蓋 Python 配置，不涵蓋 SQLite 的全部 C 記憶體。RSS 為整個新程序的尖峰，包含啟動與所有查詢，不能視為單項查詢增量，也不能把 Python 降幅直接套用到總 RSS。各作業的 Python 尖峰與保留量另見 JSON。

## 修改與查詢計畫

統計改為同一份授權 SQL 的 COUNT／SUM，責任選項使用 GROUP BY；Python 只建立單頁 DTO。新增 cases(conversation_id,id) 與 messages(conversation_id,id)，避免每個案件的最新訊息查詢掃描整張訊息表。case_activity(case_id,id) 沿用原索引。keyset 仍依 id < after，沒有改成 OFFSET。

完整 EXPLAIN QUERY PLAN 已保存於各 JSON。10,000 件 after 的 scoped_rows 與 keyset_page 會使用 monitor_cases_by_thread、monitor_messages_by_thread；before 的最新訊息子查詢只有 SEARCH messages，沒有這個覆蓋索引。排序仍可能使用暫存 B-tree，並未宣稱所有步驟皆是常數時間。

資料版本保留原本每個授權列的完整 JSON 欄位與排序，逐列輸入 SHA-256，測試確認與原本整份陣列雜湊相同。沒有改用可能碰撞的 MAX(timestamp) 或單純 COUNT，亦未導入需要監測所有寫入來源的版本觸發器。指紋仍需 O(授權案件數) 掃描；這是保留現有失效規則的明確成本。

三個規模的清單 ID、下一頁 ID、統計、責任人選項、授權範圍與歷程內容雜湊均相同。小規模的數毫秒差異會受暖快取及本機排程影響；先前探索樣本曾觀察到 100 件清單變慢，不能由本次小幅差距推定穩定收益。10,000 件的主要改善來自避免重複掃描訊息及累積全量 Python DTO。

## 重跑

在兩個獨立 checkout 使用相同 Python 環境，先為三個規模各建立一次 before 資料，再複製成 after 資料。執行測試時須使用全新、明確指定的虛構目錄，勿指向既有 runtime。

```powershell
python -B care_console/benchmark_monitor.py --source ../HITLGLOBAL-baseline/care_console --data-dir ../bench/before-100 --prepare 100 --stage before --output ../bench/before-100.json
# 複製該虛構資料目錄為 ../bench/after-100；其後在新程序量測，省略 --prepare。
python -B care_console/benchmark_monitor.py --source ../HITLGLOBAL-baseline/care_console --data-dir ../bench/before-100 --stage before --output ../bench/before-100.json
python -B care_console/benchmark_monitor.py --source care_console --data-dir ../bench/after-100 --stage after --output ../bench/after-100.json
```

將 100 替換為 1000、10000。--prepare 只用於全新虛構目錄；重複匯入會因唯一識別碼衝突中止。比較時先確認 invariant_sha256 相同，再解讀效能。

原始紀錄：[before-100.json](benchmark/before-100.json)、[after-100.json](benchmark/after-100.json)、[before-1000.json](benchmark/before-1000.json)、[after-1000.json](benchmark/after-1000.json)、[before-10000.json](benchmark/before-10000.json)、[after-10000.json](benchmark/after-10000.json)。
