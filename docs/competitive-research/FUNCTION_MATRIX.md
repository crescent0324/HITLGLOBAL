# 功能比較矩陣

固定程式基準：`18729be4178e431418cbcbce010ca409f0b30fa9`；公開資料查閱：2026-10-24。

比較狀態限定為「已確認支援、已確認不支援、部分支援、規劃中、公開資料不足」。支援指有明確產品宣告或原始碼證據；未代表同等功能深度、現場效益或已登入操作。模組存在不能推論其子功能全部存在。

HITLGLOBAL 的「已確認不支援」只針對固定版本：完整追蹤檔案、路由、資料表及文件均已核對，沒有相應可用實作。競品未找到的項目一律不判定不支援。H 的部分支援常表示本機模擬、範圍有限或只有程式尚缺驗收。

證據欄 J／C／U 分別對應三家來源；H 的代碼連到 [程式與測試核對組](HITLGLOBAL_GAP_ANALYSIS.md#程式與測試核對組)。A～D 分類另存於 CSV，與功能支援狀態分開。

共 125 個具體項目。機器可讀版本：[FUNCTION_MATRIX.csv](FUNCTION_MATRIX.csv)。未確認格逐列展開於 [PUBLIC_GAPS.csv](PUBLIC_GAPS.csv)。

## 產品範圍

| 編號與功能 | Jubo | CareOne | uCare | HITLGLOBAL | 證據／備註 |
| --- | --- | --- | --- | --- | --- |
| P01 住宿型照護系統 | 已確認支援 | 已確認支援 | 已確認支援 | 部分支援 | J：[J02](SOURCES_AND_EVIDENCE.md#j02)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)、[U11](SOURCES_AND_EVIDENCE.md#u11)；H：BASE/A。H 僅本機協作體驗，缺少完整護理 ERP。 |
| P02 日照中心管理 | 已確認支援 | 已確認支援 | 已確認支援 | 已確認不支援 | J：[J03](SOURCES_AND_EVIDENCE.md#j03)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)；H：ERP/D。日照模組不能全部延伸為住宿型標配。 |
| P03 居家服務管理 | 已確認支援 | 已確認支援 | 已確認支援 | 已確認不支援 | J：[J04](SOURCES_AND_EVIDENCE.md#j04)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)；H：ERP/D。居服派班、服務執行及核銷，與居家護理分開。 |
| P04 居家護理管理場域 | 公開資料不足 | 已確認支援 | 已確認支援 | 已確認不支援 | J：[J04](SOURCES_AND_EVIDENCE.md#j04)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)、[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。Jubo 本輪主系統為居服，未證實居家護理版；C 的健保申報細節另見 T10。 |
| P05 跨專業電子紀錄 | 已確認支援 | 已確認支援 | 已確認支援 | 部分支援 | J：[J02](SOURCES_AND_EVIDENCE.md#j02)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)、[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)、[U11](SOURCES_AND_EVIDENCE.md#u11)；H：OBS/A。H 為共同觀察與訊息，沒有各專業專屬表單。 |
| P06 正式雲端軟體服務 | 已確認支援 | 已確認支援 | 已確認支援 | 規劃中 | J：[J01](SOURCES_AND_EVIDENCE.md#j01)、[J06](SOURCES_AND_EVIDENCE.md#j06)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：DEPLOY/C。H 目前只接受 localhost，常駐環境見 ROADMAP。 |
| P07 機構地端正式部署方案 | 公開資料不足 | 公開資料不足 | 公開資料不足 | 公開資料不足 | J：[J01](SOURCES_AND_EVIDENCE.md#j01)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：DEPLOY/C。本機體驗不能視為已可正式部署的地端方案。 |

## 護理師

| 編號與功能 | Jubo | CareOne | uCare | HITLGLOBAL | 證據／備註 |
| --- | --- | --- | --- | --- | --- |
| N01 院內帳號登入 | 已確認支援 | 已確認支援 | 已確認支援 | 已確認支援 | J：[J06](SOURCES_AND_EVIDENCE.md#j06)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)、[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：AUTH/A。登入存在不代表權限配置及身分驗證強度相同。 |
| N02 每日工作台與提醒總覽 | 已確認支援 | 公開資料不足 | 部分支援 | 已確認支援 | J：[J07](SOURCES_AND_EVIDENCE.md#j07)、[J38](SOURCES_AND_EVIDENCE.md#j38)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)、[C05](SOURCES_AND_EVIDENCE.md#c05)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)、[U17](SOURCES_AND_EVIDENCE.md#u17)；H：BOARD/A。uCare 有 2021 住宿示例及短片居護工作台；CareOne 未取得當前工作台。 |
| N03 跨班照護紀錄查閱 | 已確認支援 | 公開資料不足 | 公開資料不足 | 部分支援 | J：[J11](SOURCES_AND_EVIDENCE.md#j11)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)、[C05](SOURCES_AND_EVIDENCE.md#c05)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)、[U11](SOURCES_AND_EVIDENCE.md#u11)；H：HANDOFF/A。H 已測人工服務案件交班，非完整護理臨床交班單。 |
| N04 指定接班者確認後才轉移案件責任 | 公開資料不足 | 公開資料不足 | 公開資料不足 | 已確認支援 | J：[J11](SOURCES_AND_EVIDENCE.md#j11)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)、[C05](SOURCES_AND_EVIDENCE.md#c05)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)、[U11](SOURCES_AND_EVIDENCE.md#u11)；H：HANDOFF/A。三家公開資料未揭露相同責任轉移語意。 |
| N05 住民名冊與床位資料查看 | 已確認支援 | 已確認支援 | 部分支援 | 已確認支援 | J：[J07](SOURCES_AND_EVIDENCE.md#j07)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)；H：BED/A。uCare 畫面有住民與床位欄位；2026 完整操作未實測。 |
| N06 住民照護歷程集中查閱 | 已確認支援 | 已確認支援 | 已確認支援 | 已確認支援 | J：[J02](SOURCES_AND_EVIDENCE.md#j02)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：OBS/A。H 保存觀察、對話、案件及來源時間。 |
| N07 新增護理／照護紀錄 | 已確認支援 | 已確認支援 | 已確認支援 | 部分支援 | J：[J02](SOURCES_AND_EVIDENCE.md#j02)、[J36](SOURCES_AND_EVIDENCE.md#j36)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：OBS/A。J36 可核對單人／多人紀錄、存檔與列印；H 為自由文字觀察，缺完整護理格式。 |
| N08 紀錄修改或追加更正 | 部分支援 | 公開資料不足 | 公開資料不足 | 部分支援 | J：[J09](SOURCES_AND_EVIDENCE.md#j09)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)、[C05](SOURCES_AND_EVIDENCE.md#c05)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：OBS/A。J 畫面有修改；H 以新來源碼追加更正，沒有原筆覆寫。 |
| N09 護理紀錄專業簽核 | 部分支援 | 公開資料不足 | 公開資料不足 | 已確認不支援 | J：[J10](SOURCES_AND_EVIDENCE.md#j10)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)、[C05](SOURCES_AND_EVIDENCE.md#c05)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。J 支援表單簽核，護理特定文件適用與鎖定規則未全公開。 |
| N10 手動輸入生命徵象 | 已確認支援 | 部分支援 | 已確認支援 | 已確認支援 | J：[J37](SOURCES_AND_EVIDENCE.md#j37)、[J16](SOURCES_AND_EVIDENCE.md#j16)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：OBS/A。J37 有可見量測時間、數值與存檔；C 生理資訊服務與護家紀錄整合程度待確認。 |
| N11 生命徵象歷史趨勢圖 | 部分支援 | 部分支援 | 公開資料不足 | 已確認不支援 | J：[J16](SOURCES_AND_EVIDENCE.md#j16)、[J18](SOURCES_AND_EVIDENCE.md#j18)、[J19](SOURCES_AND_EVIDENCE.md#j19)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)、[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。C 明示體重曲線；J 有健康與異常回顧，但全項趨勢未實測；H 只有紀錄列表。 |
| N12 入住護理評估 | 部分支援 | 公開資料不足 | 部分支援 | 已確認不支援 | J：[J05](SOURCES_AND_EVIDENCE.md#j05)、[J09](SOURCES_AND_EVIDENCE.md#j09)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)、[C05](SOURCES_AND_EVIDENCE.md#c05)；U：[U00](SOURCES_AND_EVIDENCE.md#u00)、[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。一般評估表存在，不等於已確認全部入住表單與簽核。 |
| N13 定期護理評估與到期檢核 | 已確認支援 | 公開資料不足 | 部分支援 | 已確認不支援 | J：[J09](SOURCES_AND_EVIDENCE.md#j09)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)、[C05](SOURCES_AND_EVIDENCE.md#c05)；U：[U00](SOURCES_AND_EVIDENCE.md#u00)、[U11](SOURCES_AND_EVIDENCE.md#u11)、[U17](SOURCES_AND_EVIDENCE.md#u17)；H：ERP/D。U17 有日照定期評估到期表，住宿全套規則仍待查；H 非臨床量表。 |
| N14 標準護理問題與診斷 | 公開資料不足 | 部分支援 | 部分支援 | 已確認不支援 | J：[J02](SOURCES_AND_EVIDENCE.md#j02)、[J05](SOURCES_AND_EVIDENCE.md#j05)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)、[C05](SOURCES_AND_EVIDENCE.md#c05)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)；H：ERP/D。C 的 NANDA 授權年份較舊；U 公司授權需確認產品與版本。 |
| N15 照護計畫建立 | 已確認支援 | 已確認支援 | 部分支援 | 已確認不支援 | J：[J02](SOURCES_AND_EVIDENCE.md#j02)、[J09](SOURCES_AND_EVIDENCE.md#j09)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U00](SOURCES_AND_EVIDENCE.md#u00)、[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。U 已揭露服務計畫匯入，護理計畫的各步驟未公開。 |
| N16 措施執行與照護評值 | 部分支援 | 公開資料不足 | 公開資料不足 | 已確認不支援 | J：[J09](SOURCES_AND_EVIDENCE.md#j09)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)、[C05](SOURCES_AND_EVIDENCE.md#c05)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。J 有評值元件；無法驗證完整問題、措施、評值的資料鏈。 |
| N17 跌倒與意外事件紀錄／提醒 | 已確認支援 | 公開資料不足 | 部分支援 | 已確認不支援 | J：[J11](SOURCES_AND_EVIDENCE.md#j11)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)、[C05](SOURCES_AND_EVIDENCE.md#c05)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)；H：ERP/D。uCare 舊示例有異常事件區；H 文字回報不算獨立事件模組。 |
| N18 壓傷分級與追蹤 | 部分支援 | 公開資料不足 | 公開資料不足 | 已確認不支援 | J：[J02](SOURCES_AND_EVIDENCE.md#j02)、[J11](SOURCES_AND_EVIDENCE.md#j11)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)、[C05](SOURCES_AND_EVIDENCE.md#c05)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。J 傷口功能已宣告，壓傷專屬分級與歷程未完整公開。 |
| N19 感染事件監測 | 部分支援 | 公開資料不足 | 公開資料不足 | 已確認不支援 | J：[J08](SOURCES_AND_EVIDENCE.md#j08)、[J32](SOURCES_AND_EVIDENCE.md#j32)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)、[C05](SOURCES_AND_EVIDENCE.md#c05)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。J32 日照教材列感染事件；未逐段查閱，住宿版、定義、分母與處理鏈仍未知。 |
| N20 傷口紀錄與換藥追蹤 | 已確認支援 | 公開資料不足 | 公開資料不足 | 已確認不支援 | J：[J02](SOURCES_AND_EVIDENCE.md#j02)、[J11](SOURCES_AND_EVIDENCE.md#j11)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)、[C05](SOURCES_AND_EVIDENCE.md#c05)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。傷口大小部位可見於 J App 說明；其他家缺少產品特定細節。 |
| N21 管路照護紀錄 | 已確認支援 | 公開資料不足 | 公開資料不足 | 已確認不支援 | J：[J02](SOURCES_AND_EVIDENCE.md#j02)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)、[C05](SOURCES_AND_EVIDENCE.md#c05)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。一般護理模組不推定已含所有管路種類。 |
| N22 藥品與處方資料管理 | 已確認支援 | 已確認支援 | 部分支援 | 已確認不支援 | J：[J02](SOURCES_AND_EVIDENCE.md#j02)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)；H：ERP/D。U 圖有藥品入口；開方、停藥、交互作用檢查未確認。 |
| N23 逐次給藥執行紀錄 | 公開資料不足 | 公開資料不足 | 公開資料不足 | 已確認不支援 | J：[J02](SOURCES_AND_EVIDENCE.md#j02)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)、[C05](SOURCES_AND_EVIDENCE.md#c05)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。CareOne 歷史索引有給藥表，原檔未可讀，不據此確認現版 eMAR。 |
| N24 特殊處置紀錄 | 已確認支援 | 公開資料不足 | 公開資料不足 | 已確認不支援 | J：[J02](SOURCES_AND_EVIDENCE.md#j02)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)、[C05](SOURCES_AND_EVIDENCE.md#c05)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。醫囑存在不等於完整處置核對工作流。 |
| N25 就醫回診與轉診資訊 | 已確認支援 | 已確認支援 | 部分支援 | 已確認不支援 | J：[J02](SOURCES_AND_EVIDENCE.md#j02)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)；H：ERP/D。U 有醫療入口示例，完整回診排程未確認。 |
| N26 跨專業照會及回覆追蹤 | 部分支援 | 公開資料不足 | 部分支援 | 已確認不支援 | J：[J02](SOURCES_AND_EVIDENCE.md#j02)、[J32](SOURCES_AND_EVIDENCE.md#j32)、[J36](SOURCES_AND_EVIDENCE.md#j36)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)、[C05](SOURCES_AND_EVIDENCE.md#c05)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)、[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。J36 多人照護紀錄可選照會人員，J32 另有日照／居服照會教材；回覆時限與結案未確認。 |
| N27 逾期評估／紀錄提醒 | 已確認支援 | 公開資料不足 | 部分支援 | 已確認不支援 | J：[J09](SOURCES_AND_EVIDENCE.md#j09)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)、[C05](SOURCES_AND_EVIDENCE.md#c05)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)；H：ERP/D。H 的人工訊息等候時間不等於臨床評估到期提醒。 |
| N28 手機或平板操作 | 已確認支援 | 公開資料不足 | 已確認支援 | 部分支援 | J：[J02](SOURCES_AND_EVIDENCE.md#j02)、[J11](SOURCES_AND_EVIDENCE.md#j11)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)；H：UI/B。H 是瀏覽器介面，本輪未執行行動裝置使用性驗收。 |
| N29 語音輸入照護文字 | 已確認支援 | 已確認支援 | 已確認支援 | 已確認不支援 | J：[J02](SOURCES_AND_EVIDENCE.md#j02)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。C 語音辨識未足以證實生成式 AI。 |
| N30 斷線暫存及恢復同步 | 部分支援 | 公開資料不足 | 部分支援 | 已確認不支援 | J：[J16](SOURCES_AND_EVIDENCE.md#j16)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U00](SOURCES_AND_EVIDENCE.md#u00)；H：ERP/D。J16 為量測暫存同步；U00 為居服離線打卡；均不擴張為護理表單全功能離線。 |

## 照服員

| 編號與功能 | Jubo | CareOne | uCare | HITLGLOBAL | 證據／備註 |
| --- | --- | --- | --- | --- | --- |
| C01 當日服務清單 | 已確認支援 | 已確認支援 | 已確認支援 | 部分支援 | J：[J20](SOURCES_AND_EVIDENCE.md#j20)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)；H：BOARD/A。三家主要證據為居服；H 目前是住民與訊息待辦。 |
| C02 服務項目與時間查閱 | 已確認支援 | 已確認支援 | 已確認支援 | 部分支援 | J：[J20](SOURCES_AND_EVIDENCE.md#j20)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)；H：BOARD/A。H 有觀察及案件時間，沒有完整服務排程。 |
| C03 照護任務完成回報 | 已確認支援 | 已確認支援 | 已確認支援 | 部分支援 | J：[J27](SOURCES_AND_EVIDENCE.md#j27)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)、[U13](SOURCES_AND_EVIDENCE.md#u13)、[U14](SOURCES_AND_EVIDENCE.md#u14)；H：OBS/A。U 開發者說明及導入單位均明列勾選服務後簽退；H 可報觀察，未建立任務實體。 |
| C04 特殊狀況回報 | 已確認支援 | 公開資料不足 | 部分支援 | 已確認支援 | J：[J20](SOURCES_AND_EVIDENCE.md#j20)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)；H：OBS/A。U 只有異常列表元件，提交細節未知；H 回報不自動判斷臨床風險。 |
| C05 日常照顧紀錄 | 已確認支援 | 已確認支援 | 已確認支援 | 已確認支援 | J：[J02](SOURCES_AND_EVIDENCE.md#j02)、[J27](SOURCES_AND_EVIDENCE.md#j27)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：OBS/A。H 為自由文字及五項量測，無 ADL 全套照護表。 |
| C06 工作派案與指派 | 已確認支援 | 已確認支援 | 已確認支援 | 已確認不支援 | J：[J04](SOURCES_AND_EVIDENCE.md#j04)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U00](SOURCES_AND_EVIDENCE.md#u00)、[U01](SOURCES_AND_EVIDENCE.md#u01)；H：ERP/D。H 的住民查看授權不是照護任務派工。 |
| C07 與護理師交換照護資訊 | 已確認支援 | 部分支援 | 已確認支援 | 已確認支援 | J：[J02](SOURCES_AND_EVIDENCE.md#j02)、[J11](SOURCES_AND_EVIDENCE.md#j11)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)、[U11](SOURCES_AND_EVIDENCE.md#u11)；H：OBS/A。C 有共同資料模組；是否有定向提醒與已讀未知。 |
| C08 依角色與住民限制資料範圍 | 已確認支援 | 已確認支援 | 已確認支援 | 已確認支援 | J：[J06](SOURCES_AND_EVIDENCE.md#j06)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：AUTH/A。廠商宣告權限功能；各欄位及預設職責矩陣未公開。 |
| C09 後端阻止照服員設定護理評估狀態 | 公開資料不足 | 公開資料不足 | 公開資料不足 | 已確認支援 | J：[J06](SOURCES_AND_EVIDENCE.md#j06)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：OBS/A。其他產品沒有足以證實相同規則的公開細節。 |

## 主管

| 編號與功能 | Jubo | CareOne | uCare | HITLGLOBAL | 證據／備註 |
| --- | --- | --- | --- | --- | --- |
| S01 入住／入院管理 | 已確認支援 | 已確認支援 | 部分支援 | 已確認不支援 | J：[J11](SOURCES_AND_EVIDENCE.md#j11)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)；H：ERP/D。H 已有住民種子與 active 欄位，沒有完整入住操作。 |
| S02 退住／出院／結案管理 | 已確認支援 | 已確認支援 | 部分支援 | 已確認不支援 | J：[J11](SOURCES_AND_EVIDENCE.md#j11)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)；H：ERP/D。H 的人工案件結案與住民退住分開，不可混稱。 |
| S03 轉床及空床衝突檢查 | 公開資料不足 | 公開資料不足 | 公開資料不足 | 已確認支援 | J：[J02](SOURCES_AND_EVIDENCE.md#j02)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)；H：BED/A。三家資料不足不表示無轉床功能。 |
| S04 員工基本資料維護 | 已確認支援 | 已確認支援 | 已確認支援 | 部分支援 | J：[J02](SOURCES_AND_EVIDENCE.md#j02)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：AUTH/B。H 有預建使用者及授權；未有完整員工建檔生命週期。 |
| S05 職務群組權限管理 | 已確認支援 | 已確認支援 | 已確認支援 | 已確認支援 | J：[J06](SOURCES_AND_EVIDENCE.md#j06)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：AUTH/A。H 院內角色固定，不等於任意自訂角色設計器。 |
| S06 護理長與 IT 職責隔離 | 公開資料不足 | 公開資料不足 | 公開資料不足 | 規劃中 | J：[J06](SOURCES_AND_EVIDENCE.md#j06)、[J10](SOURCES_AND_EVIDENCE.md#j10)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：DEPLOY/C。H 目前 admin 合併二者，ROADMAP 列為待辦。 |
| S07 護理師與照服員排班 | 已確認支援 | 已確認支援 | 部分支援 | 已確認不支援 | J：[J02](SOURCES_AND_EVIDENCE.md#j02)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U00](SOURCES_AND_EVIDENCE.md#u00)、[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。U 居服班表可見，住宿護理師排班細節未公開。 |
| S08 出勤與考勤統計 | 已確認支援 | 公開資料不足 | 已確認支援 | 已確認不支援 | J：[J02](SOURCES_AND_EVIDENCE.md#j02)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U00](SOURCES_AND_EVIDENCE.md#u00)、[U01](SOURCES_AND_EVIDENCE.md#u01)；H：ERP/D。C 人員管理不直接證明實際出勤資料流程。 |
| S09 人力比與工作負荷計算 | 部分支援 | 公開資料不足 | 公開資料不足 | 已確認不支援 | J：[J26](SOURCES_AND_EVIDENCE.md#j26)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)；H：ERP/D。J 只確認日照核銷人力比檢核；TLCA 工時成本不算 uCare。 |
| S10 工作完成率與紀錄覆蓋統計 | 已確認支援 | 公開資料不足 | 部分支援 | 部分支援 | J：[J09](SOURCES_AND_EVIDENCE.md#j09)、[J19](SOURCES_AND_EVIDENCE.md#j19)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U00](SOURCES_AND_EVIDENCE.md#u00)、[U11](SOURCES_AND_EVIDENCE.md#u11)；H：BOARD/B。H 有待辦／追蹤數量，未形成班別工作完成率與分母。 |
| S11 逾期工作檢核 | 已確認支援 | 公開資料不足 | 部分支援 | 部分支援 | J：[J09](SOURCES_AND_EVIDENCE.md#j09)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)；H：BOARD/A。H 有人工案件等候時間與排序，未有臨床時限配置。 |
| S12 照護品質指標統計 | 已確認支援 | 公開資料不足 | 已確認支援 | 已確認不支援 | J：[J08](SOURCES_AND_EVIDENCE.md#j08)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)、[C05](SOURCES_AND_EVIDENCE.md#c05)；U：[U00](SOURCES_AND_EVIDENCE.md#u00)、[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。C 歷史六大指標資料不足以確定現版完整模組。 |
| S13 跌倒壓傷感染趨勢整合 | 部分支援 | 公開資料不足 | 公開資料不足 | 已確認不支援 | J：[J08](SOURCES_AND_EVIDENCE.md#j08)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)、[C05](SOURCES_AND_EVIDENCE.md#c05)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。須逐指標確認公式，不能由品質模組總名推定全部支援。 |
| S14 教育訓練紀錄與時數 | 已確認支援 | 已確認支援 | 公開資料不足 | 已確認不支援 | J：[J09](SOURCES_AND_EVIDENCE.md#j09)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。U 導入教育訓練服務不等於員工受訓管理模組。 |
| S15 證照到期提醒 | 已確認支援 | 公開資料不足 | 公開資料不足 | 已確認不支援 | J：[J07](SOURCES_AND_EVIDENCE.md#j07)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。J 圖示員工證書即將到期；發證資格與查核另議。 |
| S16 人員操作稽核查詢 | 已確認支援 | 公開資料不足 | 已確認支援 | 已確認支援 | J：[J06](SOURCES_AND_EVIDENCE.md#j06)、[J10](SOURCES_AND_EVIDENCE.md#j10)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：AUDIT/A。H 保存本機事件，未提供不可竄改保證。 |
| S17 耗材倉儲與進銷存 | 已確認支援 | 已確認支援 | 已確認支援 | 已確認不支援 | J：[J02](SOURCES_AND_EVIDENCE.md#j02)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。硬體與耗材供應事業不自動算軟體功能，U 依 U11 確認。 |
| S18 成本與耗材使用管理 | 部分支援 | 已確認支援 | 已確認支援 | 已確認不支援 | J：[J02](SOURCES_AND_EVIDENCE.md#j02)、[J33](SOURCES_AND_EVIDENCE.md#j33)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。J 案例提及用量追蹤，精確成本核算方法未知。 |
| S19 財會與薪資管理 | 已確認支援 | 已確認支援 | 已確認支援 | 已確認不支援 | J：[J02](SOURCES_AND_EVIDENCE.md#j02)、[J04](SOURCES_AND_EVIDENCE.md#j04)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。完整會計科目、關帳及稅務申報未逐項驗證。 |
| S20 住民帳單與收據 | 已確認支援 | 部分支援 | 部分支援 | 已確認不支援 | J：[J02](SOURCES_AND_EVIDENCE.md#j02)、[J18](SOURCES_AND_EVIDENCE.md#j18)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。C／U 財務模組範圍已知，住民帳單欄位與核銷過程未公開。 |
| S21 社工服務紀錄與計畫 | 已確認支援 | 公開資料不足 | 部分支援 | 已確認不支援 | J：[J02](SOURCES_AND_EVIDENCE.md#j02)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)、[C05](SOURCES_AND_EVIDENCE.md#c05)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)；H：ERP/D。C 歷史有社工表單但現版未知；U 圖有社工入口。 |
| S22 營養評估與餐食管理 | 部分支援 | 已確認支援 | 部分支援 | 已確認不支援 | J：[J02](SOURCES_AND_EVIDENCE.md#j02)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)；H：ERP/D。J 明示營養建議整合，未證實完整餐食排程；U 圖有營養入口。 |
| S23 評鑑表單與資料檢核 | 已確認支援 | 已確認支援 | 已確認支援 | 已確認不支援 | J：[J09](SOURCES_AND_EVIDENCE.md#j09)、[J25](SOURCES_AND_EVIDENCE.md#j25)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。場域及年度基準仍須依 G04、G05 核對。 |
| S24 機構營運儀表板 | 已確認支援 | 公開資料不足 | 部分支援 | 已確認支援 | J：[J07](SOURCES_AND_EVIDENCE.md#j07)、[J19](SOURCES_AND_EVIDENCE.md#j19)、[J22](SOURCES_AND_EVIDENCE.md#j22)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)、[C05](SOURCES_AND_EVIDENCE.md#c05)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)；H：BOARD/A。uCare 住宿首頁可見人數與異常，但 OIC 不算內建。 |
| S25 第一線紀錄自動轉品質統計 | 已確認支援 | 公開資料不足 | 已確認支援 | 已確認不支援 | J：[J08](SOURCES_AND_EVIDENCE.md#j08)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)、[C05](SOURCES_AND_EVIDENCE.md#c05)；U：[U00](SOURCES_AND_EVIDENCE.md#u00)、[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。U11 支持跨表單與指標連動，公式和重算規則仍未知。 |

## 家屬

| 編號與功能 | Jubo | CareOne | uCare | HITLGLOBAL | 證據／備註 |
| --- | --- | --- | --- | --- | --- |
| F01 家屬與服務對象關係驗證 | 已確認支援 | 公開資料不足 | 公開資料不足 | 部分支援 | J：[J18](SOURCES_AND_EVIDENCE.md#j18)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)；H：CONTACT/A。H 為模擬配對；真實身分確認待開發。 |
| F02 家屬查詢照護資訊 | 已確認支援 | 公開資料不足 | 已確認支援 | 規劃中 | J：[J18](SOURCES_AND_EVIDENCE.md#j18)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)；H：DEPLOY/C。H 沒有家屬網頁入口，真實 LINE 查詢待驗證。 |
| F03 LINE 家屬入口 | 已確認支援 | 公開資料不足 | 公開資料不足 | 規劃中 | J：[J18](SOURCES_AND_EVIDENCE.md#j18)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)、[U11](SOURCES_AND_EVIDENCE.md#u11)；H：DEPLOY/C。U 客服 Line 群不是家屬產品入口。 |
| F04 家屬 App 入口 | 部分支援 | 公開資料不足 | 已確認支援 | 已確認不支援 | J：[J13](SOURCES_AND_EVIDENCE.md#j13)、[J18](SOURCES_AND_EVIDENCE.md#j18)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)；H：ERP/D。J 安心寶 2.0 是 LINE 入口；舊 App 稱法不混版本。 |
| F05 家屬獨立網頁登入 | 公開資料不足 | 公開資料不足 | 公開資料不足 | 已確認不支援 | J：[J18](SOURCES_AND_EVIDENCE.md#j18)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)；H：AUTH/D。H 設計只開放院內人員網頁，家屬登入已明確拒絕。 |
| F06 家庭聯絡簿 | 已確認支援 | 公開資料不足 | 已確認支援 | 已確認不支援 | J：[J13](SOURCES_AND_EVIDENCE.md#j13)、[J18](SOURCES_AND_EVIDENCE.md#j18)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)；H：ERP/D。U 只確認日照家屬聯絡簿；住宿是否同規格未知。 |
| F07 工作人員留言回覆 | 已確認支援 | 公開資料不足 | 公開資料不足 | 部分支援 | J：[J18](SOURCES_AND_EVIDENCE.md#j18)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)；H：CONTACT/A。H 人工回覆僅離線模擬，不代表真實 LINE 已送出。 |
| F08 照護及活動通知 | 已確認支援 | 公開資料不足 | 公開資料不足 | 部分支援 | J：[J18](SOURCES_AND_EVIDENCE.md#j18)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)；H：CONTACT/A。H 有模擬訊息送出，沒有家屬手機推播驗收。 |
| F09 同住民多聯絡人對話隔離 | 公開資料不足 | 公開資料不足 | 公開資料不足 | 部分支援 | J：[J18](SOURCES_AND_EVIDENCE.md#j18)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)、[U11](SOURCES_AND_EVIDENCE.md#u11)；H：CONTACT/A。H 本機測試可證，不主張其他產品沒有；真實 LINE 未接入。 |
| F10 撤銷授權後阻擋回覆及舊生成 | 公開資料不足 | 公開資料不足 | 公開資料不足 | 部分支援 | J：[J18](SOURCES_AND_EVIDENCE.md#j18)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：REVOKE/A。H 已測生成期間撤銷，範圍限本機及離線傳輸。 |
| F11 生成式 AI 自動回覆照護問答 | 公開資料不足 | 公開資料不足 | 公開資料不足 | 部分支援 | J：[J05](SOURCES_AND_EVIDENCE.md#j05)、[J18](SOURCES_AND_EVIDENCE.md#j18)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U09](SOURCES_AND_EVIDENCE.md#u09)、[U11](SOURCES_AND_EVIDENCE.md#u11)；H：GEN/B。J 聯絡簿生成不等於任意家屬問答；H 只有受限核心及離線能力。 |
| F12 轉人工與案件接手 | 公開資料不足 | 公開資料不足 | 公開資料不足 | 部分支援 | J：[J18](SOURCES_AND_EVIDENCE.md#j18)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：CASE/A。廠商宣告溝通不代表同一個人工案件狀態機。 |
| F13 案件進度與跨班處理 | 公開資料不足 | 公開資料不足 | 公開資料不足 | 部分支援 | J：[J11](SOURCES_AND_EVIDENCE.md#j11)、[J18](SOURCES_AND_EVIDENCE.md#j18)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：HANDOFF/A。H 服務訊息有進度、下一步及接收確認；對外通道仍離線。 |
| F14 聯絡簿回覆與歷史紀錄 | 已確認支援 | 公開資料不足 | 公開資料不足 | 部分支援 | J：[J18](SOURCES_AND_EVIDENCE.md#j18)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)；H：CONTACT/A。H 有隔離對話歷程，沒有正式家庭聯絡簿資料模型。 |
| F15 家庭聯絡簿 AI 文字生成 | 已確認支援 | 公開資料不足 | 公開資料不足 | 已確認不支援 | J：[J13](SOURCES_AND_EVIDENCE.md#j13)、[J18](SOURCES_AND_EVIDENCE.md#j18)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。U AI 語音不是家屬聯絡簿生成證據。 |

## AI 與治理

| 編號與功能 | Jubo | CareOne | uCare | HITLGLOBAL | 證據／備註 |
| --- | --- | --- | --- | --- | --- |
| A01 照護及交班自動摘要 | 已確認支援 | 公開資料不足 | 公開資料不足 | 已確認不支援 | J：[J05](SOURCES_AND_EVIDENCE.md#j05)、[J11](SOURCES_AND_EVIDENCE.md#j11)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U09](SOURCES_AND_EVIDENCE.md#u09)、[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。H 的固定服務摘要不是依住民照護紀錄生成交班摘要。 |
| A02 AI 語音照護紀錄 | 已確認支援 | 部分支援 | 已確認支援 | 已確認不支援 | J：[J05](SOURCES_AND_EVIDENCE.md#j05)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。C 只證實語音輸入，生成及專業結構化程度未知。 |
| A03 AI 照護計畫草稿 | 部分支援 | 公開資料不足 | 公開資料不足 | 已確認不支援 | J：[J05](SOURCES_AND_EVIDENCE.md#j05)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)、[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U10](SOURCES_AND_EVIDENCE.md#u10)、[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。J N-Copilot 主情境為 A 個管，非證實住宿護理計畫全自動。 |
| A04 以自然語言查詢系統資料 | 已確認支援 | 公開資料不足 | 公開資料不足 | 部分支援 | J：[J05](SOURCES_AND_EVIDENCE.md#j05)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U09](SOURCES_AND_EVIDENCE.md#u09)、[U11](SOURCES_AND_EVIDENCE.md#u11)；H：GEN/B。H 只在長照服務資訊範圍回答，沒有住民臨床資料問答。 |
| A05 獨立規則判定對話風險 | 公開資料不足 | 公開資料不足 | 公開資料不足 | 已確認支援 | J：[J05](SOURCES_AND_EVIDENCE.md#j05)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：RISK/A。J 生理異常提醒不等於聊天風險分級；H 規則非臨床分流標準。 |
| A06 中風險草稿須人工核准 | 公開資料不足 | 公開資料不足 | 公開資料不足 | 部分支援 | J：[J05](SOURCES_AND_EVIDENCE.md#j05)、[J10](SOURCES_AND_EVIDENCE.md#j10)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：GEN/B。H 有核心與 API 實作，本輪未全面覆蓋草稿核准情境。 |
| A07 高風險停止一般生成 | 公開資料不足 | 公開資料不足 | 公開資料不足 | 已確認支援 | J：[J05](SOURCES_AND_EVIDENCE.md#j05)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：RISK/A。H 有對應測試；不能推論臨床危急偵測有效率。 |
| A08 低風險新訊息不解除人工案件 | 公開資料不足 | 公開資料不足 | 公開資料不足 | 已確認支援 | J：[J05](SOURCES_AND_EVIDENCE.md#j05)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：CASE/A。H 同聯絡人對話測試成立，未擴張為任意分散式部署。 |
| A09 新訊息使舊草稿失效 | 公開資料不足 | 公開資料不足 | 公開資料不足 | 部分支援 | J：[J05](SOURCES_AND_EVIDENCE.md#j05)、[J15](SOURCES_AND_EVIDENCE.md#j15)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：GEN/B。J Amy 同日沿用結果；公開資訊不能判斷其他 AI 工作的失效規則。 |
| A10 模型設定版本變更使舊工作失效 | 公開資料不足 | 公開資料不足 | 公開資料不足 | 部分支援 | J：[J05](SOURCES_AND_EVIDENCE.md#j05)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：GEN/B。H 有 config_revision 與取消流程，相關測試覆蓋不足。 |
| A11 知識版本與有效時間核對 | 部分支援 | 公開資料不足 | 公開資料不足 | 部分支援 | J：[J05](SOURCES_AND_EVIDENCE.md#j05)、[J15](SOURCES_AND_EVIDENCE.md#j15)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：CONTEXT/B。J 有來源及原權限說明，版本與有效時間實作未公開；H 核對雜湊與 600 秒界線。 |
| A12 人工核准與操作責任稽核 | 已確認支援 | 公開資料不足 | 已確認支援 | 部分支援 | J：[J06](SOURCES_AND_EVIDENCE.md#j06)、[J10](SOURCES_AND_EVIDENCE.md#j10)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：AUDIT/A。H 案件操作有測試，AI 全程決策鏈仍需更完整驗收。 |
| A13 生成來源與處理版本追溯 | 部分支援 | 公開資料不足 | 公開資料不足 | 部分支援 | J：[J05](SOURCES_AND_EVIDENCE.md#j05)、[J15](SOURCES_AND_EVIDENCE.md#j15)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：CONTEXT/B。H 保存來源編號與版本，不保證每句內容真實。 |
| A14 模型錯誤配額不足時停止並留狀態 | 公開資料不足 | 公開資料不足 | 公開資料不足 | 部分支援 | J：[J05](SOURCES_AND_EVIDENCE.md#j05)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：GEN/B。H 有錯誤／配額處理，未完成真實供應商失敗驗收。 |
| A15 AI 對照護成效的獨立場域驗證 | 公開資料不足 | 公開資料不足 | 公開資料不足 | 公開資料不足 | J：[J40](SOURCES_AND_EVIDENCE.md#j40)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：BASE/D。三家公開效益文案及本機測試都不能替代獨立臨床或使用性研究。 |

## 技術與安全

| 編號與功能 | Jubo | CareOne | uCare | HITLGLOBAL | 證據／備註 |
| --- | --- | --- | --- | --- | --- |
| T01 網頁操作介面 | 已確認支援 | 已確認支援 | 已確認支援 | 已確認支援 | J：[J01](SOURCES_AND_EVIDENCE.md#j01)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：BASE/A。公開網頁支援不等於已測所有裝置。 |
| T02 原生／獨立工作人員 App | 已確認支援 | 公開資料不足 | 已確認支援 | 已確認不支援 | J：[J11](SOURCES_AND_EVIDENCE.md#j11)、[J20](SOURCES_AND_EVIDENCE.md#j20)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)；H：ERP/D。H 的響應式網頁不能列為 App。 |
| T03 角色與資料範圍控制 | 已確認支援 | 已確認支援 | 已確認支援 | 已確認支援 | J：[J06](SOURCES_AND_EVIDENCE.md#j06)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：AUTH/A。廠商未公開全部後端授權檢查規則。 |
| T04 公開第三方開發者 API 契約 | 公開資料不足 | 公開資料不足 | 公開資料不足 | 已確認不支援 | J：[J12](SOURCES_AND_EVIDENCE.md#j12)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。有整合不等於對 HITLGLOBAL 開放 API；H 有院內 API，沒有正式第三方契約。 |
| T05 依專案第三方系統介接 | 已確認支援 | 部分支援 | 已確認支援 | 規劃中 | J：[J01](SOURCES_AND_EVIDENCE.md#j01)、[J12](SOURCES_AND_EVIDENCE.md#j12)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)、[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：DEPLOY/C。C 生理資訊服務與護家介接範圍需確認；H 真實院內介接在規劃。 |
| T06 個案或服務資料匯入 | 部分支援 | 已確認支援 | 已確認支援 | 部分支援 | J：[J26](SOURCES_AND_EVIDENCE.md#j26)、[J30](SOURCES_AND_EVIDENCE.md#j30)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：IMPORT/A。H 只接受 1～500 筆虛構量測 CSV，非完整個案匯入。 |
| T07 資料匯出與離場取回 | 已確認支援 | 公開資料不足 | 公開資料不足 | 部分支援 | J：[J06](SOURCES_AND_EVIDENCE.md#j06)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)、[C05](SOURCES_AND_EVIDENCE.md#c05)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)、[U12](SOURCES_AND_EVIDENCE.md#u12)；H：BACKUP/A。H 可下載 SQLite 備份，沒有標準跨系統完整匯出。 |
| T08 生命徵象 IoT 自動介接 | 已確認支援 | 部分支援 | 已確認支援 | 規劃中 | J：[J12](SOURCES_AND_EVIDENCE.md#j12)、[J16](SOURCES_AND_EVIDENCE.md#j16)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)、[U11](SOURCES_AND_EVIDENCE.md#u11)；H：DEPLOY/C。C 已有量測服務，但護家自動回填需展示；H CSV 不能算設備整合。 |
| T09 政府支審核銷介接 | 已確認支援 | 部分支援 | 已確認支援 | 已確認不支援 | J：[J26](SOURCES_AND_EVIDENCE.md#j26)、[J30](SOURCES_AND_EVIDENCE.md#j30)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。C 只確認中衛評鑑上傳，與支審核銷不同。 |
| T10 居家護理健保讀卡申報 | 公開資料不足 | 公開資料不足 | 已確認支援 | 已確認不支援 | J：[J04](SOURCES_AND_EVIDENCE.md#j04)；C：[C01](SOURCES_AND_EVIDENCE.md#c01)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。J、C 本輪缺少該特定功能證據。 |
| T11 公開 HL7 FHIR 介接規格 | 公開資料不足 | 公開資料不足 | 公開資料不足 | 已確認不支援 | J：[J12](SOURCES_AND_EVIDENCE.md#j12)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：ERP/D。未找到不能說廠商不支援；H 固定版本無 FHIR 介接。 |
| T12 可查詢人員操作紀錄 | 已確認支援 | 公開資料不足 | 已確認支援 | 已確認支援 | J：[J06](SOURCES_AND_EVIDENCE.md#j06)、[J10](SOURCES_AND_EVIDENCE.md#j10)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：AUDIT/A。稽核存在不等於所有查閱均可匯出或完整長期保存。 |
| T13 不可竄改稽核儲存 | 公開資料不足 | 公開資料不足 | 公開資料不足 | 已確認不支援 | J：[J06](SOURCES_AND_EVIDENCE.md#j06)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：AUDIT/D。H SQLite 事件表沒有不可竄改或外部封存機制。 |
| T14 網際網路傳輸加密 | 已確認支援 | 公開資料不足 | 部分支援 | 規劃中 | J：[J06](SOURCES_AND_EVIDENCE.md#j06)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)、[U13](SOURCES_AND_EVIDENCE.md#u13)；H：DEPLOY/C。U13 居服 App 商店寫資料未加密，與 U11 傳輸加密宣告待釐清；H 預設 localhost HTTP。 |
| T15 資料庫靜態資料加密 | 公開資料不足 | 公開資料不足 | 公開資料不足 | 已確認不支援 | J：[J06](SOURCES_AND_EVIDENCE.md#j06)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：BASE/D。傳輸加密不直接證明靜態加密；H 本版 SQLite 未有加密層。 |
| T16 資料備份機制 | 已確認支援 | 公開資料不足 | 已確認支援 | 已確認支援 | J：[J06](SOURCES_AND_EVIDENCE.md#j06)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：BACKUP/A。H 為管理者手動快照；沒有每日異地排程。 |
| T17 還原演練或備份還原驗證 | 已確認支援 | 公開資料不足 | 公開資料不足 | 部分支援 | J：[J06](SOURCES_AND_EVIDENCE.md#j06)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：BACKUP/A。H 已測新目錄還原；場域災難演練與復原目標未驗證。 |
| T18 有數值的服務可用性 SLA | 公開資料不足 | 公開資料不足 | 公開資料不足 | 公開資料不足 | J：[J06](SOURCES_AND_EVIDENCE.md#j06)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：DEPLOY/C。U11 說有 SLA，未公開百分比、排除條款與賠償條件。 |
| T19 公開復原時間與資料復原點目標 | 公開資料不足 | 公開資料不足 | 公開資料不足 | 規劃中 | J：[J06](SOURCES_AND_EVIDENCE.md#j06)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：DEPLOY/C。H 復原規劃存在，RTO／RPO 未決定及測試。 |
| T20 正式服務的台灣境內資料存放 | 已確認支援 | 公開資料不足 | 公開資料不足 | 公開資料不足 | J：[J06](SOURCES_AND_EVIDENCE.md#j06)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：DEPLOY/C。H 只有本機檔案；檔案路徑不能證明地理位置，正式託管及 AI 出境契約未確認。 |
| T21 契約終止後保存與刪除機制 | 已確認支援 | 公開資料不足 | 公開資料不足 | 規劃中 | J：[J06](SOURCES_AND_EVIDENCE.md#j06)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U12](SOURCES_AND_EVIDENCE.md#u12)；H：DEPLOY/C。U12 主要為網站／帳號政策，未證實 ERP 住民紀錄離場規格。 |
| T22 撤銷權限影響既有工作階段 | 公開資料不足 | 公開資料不足 | 公開資料不足 | 已確認支援 | J：[J06](SOURCES_AND_EVIDENCE.md#j06)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：AUTH/A。H 每次後端重查；廠商權限設定宣告不足以證實同一時序。 |
| T23 公開資安驗證宣告 | 已確認支援 | 公開資料不足 | 部分支援 | 已確認不支援 | J：[J06](SOURCES_AND_EVIDENCE.md#j06)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U01](SOURCES_AND_EVIDENCE.md#u01)、[U07](SOURCES_AND_EVIDENCE.md#u07)、[U11](SOURCES_AND_EVIDENCE.md#u11)；H：BASE/D。J 為官方宣告；U 新舊 ISO 說法待核證；H 無已取得認證證據。 |
| T24 可核實私有後端技術與資料庫 | 公開資料不足 | 公開資料不足 | 公開資料不足 | 已確認支援 | J：[J06](SOURCES_AND_EVIDENCE.md#j06)；C：[C02](SOURCES_AND_EVIDENCE.md#c02)；U：[U11](SOURCES_AND_EVIDENCE.md#u11)；H：BASE/B。H 可由原始碼確認 Flask／SQLite；三家未公開技術不以官網前端推測。 |

## 十二項產品決策比較

| 面向 | 可支持的差異 | 評估限制／下一步 |
| --- | --- | --- |
| 功能完整度 | 三家已有護理或長照管理模組；H 為協作與治理原型 | 依逐項功能及場域比較，未計算總分 |
| 第一線便利性 | J 有勾選、語音、行動交班；C 有語音及動態表單；U 有 DITTO 與行動服務 | 都未有同題任務計時，不能排速度名次 |
| 重複登打 | J 有 IoT／聯絡簿帶入；U 有跨表單與政府資料匯入；C 有個案匯入及動態表單 | 須量測同一筆資料出現幾次、何時需確認及如何更正 |
| 家屬溝通 | J 安心寶 2.0 LINE 與聯絡簿資訊最明確；U 日照有家屬 App；C 資料不足 | H 真實 LINE 尚未完成，不能算已領先 |
| AI 應用 | J 有交班、聯絡簿、A 個管與居督摘要；U 有 AI 語音；C 只有語音明示 | 不把單一生成畫面當全套自動回覆 |
| HITL 治理 | H 可查規則、失效、接手與責任控制；J 已有專業人員主導、權限及簽核 | 競品私有時序未知；H 的獨家性尚無法證明 |
| 主管監督 | J／U 有臨床到品質統計；C 有評鑑與統計模組 | H 目前待辦看板不能當品質管理平台 |
| 介接能力 | J 有設備及支審，U 有全人評估／健保／支審，C 有中衛上傳 | 介接許可、欄位規格及費用未公開 |
| 導入負擔 | J 線上循環教學；U 宣告盤點、匯入、訓練與客服 | 未量測歷史轉檔、平行期及上線天數；C 服務條件待報價 |
| 產品成熟度 | J／U 具名案例及多場域產品；C 有長期公開產品資訊與歷史簡報 | 沒有可比活躍客戶、留存、故障或版本數據，未排名 |
| 定價透明度 | J 部分公開起價及 Amy 點數；C／U 金額未公開 | 詳見三家介紹；未估算成官方機構報價 |
| 擴充性 | J 專案整合、U 模組與客製、C 動態表單 | 擴充成本與第三方 API 契約未知，開源程式不自動等於正式擴充能力 |

[工作流程](WORKFLOW_COMPARISON.md) · [技術與資安](TECHNOLOGY_AND_SECURITY.md) · [返回入口](README.md)
