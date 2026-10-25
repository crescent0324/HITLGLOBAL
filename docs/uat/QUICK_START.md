# 快速開始

參與者只需閱讀「登入與基本操作」。前面的準備由主持人完成。只在自己的Windows電腦測試，所有住民、家屬及角色都是模擬身分；請勿填真實資料。

## 主持人：第一次準備

取得本UAT分支或交付包完整程式，保留資料夾結構；版本與PR依賴見 [整合檢查](INTEGRATION_CHECK.md)。請在檔案總管開啟其中的care_console資料夾，在位址列輸入powershell並按Enter。以下指令都在這個資料夾執行。

先安裝Python 3.12；在PowerShell輸入 `python --version`，應顯示Python 3.12.x。若找不到或版本不同，交由主持人／IT準備，參與者不必排除安裝問題。接著只需安裝一次：

```powershell
python -m venv .venv
if ($LASTEXITCODE -ne 0) { throw '虛擬環境建立失敗，請停止準備。' }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw '套件安裝失敗，請停止準備。' }
```

安裝套件需要連線取得Flask及Waitress；正式試用不使用外部模型或LINE。不必安裝Node.js即可操作網頁。若受管電腦的暫存資料夾禁止寫入，請IT設定可寫暫存位置後重試，不能改用既有營運環境。

## 主持人：每場建立全新環境

每次從頭執行整段，會產生新的場次碼。不要只重跑最後一行或改成既有runtime；不使用start.cmd的預設runtime。先關閉前場瀏覽器分頁並在前場啟動視窗按Ctrl+C。

```powershell
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath '.\run.py' -PathType Leaf)) { throw '請先進入本版 care_console 資料夾。' }
$uatPython = (Resolve-Path -LiteralPath '.\.venv\Scripts\python.exe').Path
& $uatPython -X utf8 -c "import sys,importlib.metadata as m; assert sys.version_info[:2]==(3,12), '需要Python3.12'; assert m.version('Flask')=='3.1.3'; assert m.version('waitress')=='3.0.2'; import flask,waitress; print('Python與依賴檢查通過')"
if ($LASTEXITCODE -ne 0) { throw '環境檢查失敗，請停止。' }
$uatBase = (Resolve-Path -LiteralPath '.').Path
if ((Get-Item -LiteralPath $uatBase).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw '請使用實際專案資料夾。' }
$uatRoot = Join-Path $uatBase 'runtime\uat'
foreach ($uatPart in @((Join-Path $uatBase 'runtime'), $uatRoot)) {
  if ((Test-Path -LiteralPath $uatPart) -and ((Get-Item -LiteralPath $uatPart).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw '資料路徑為連結，請IT確認。' }
}
$uatSession = 'S-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + ([guid]::NewGuid().ToString('N').Substring(0,8))
$uatData = Join-Path $uatRoot $uatSession
if (Test-Path -LiteralPath $uatData) { throw '場次已存在，請從整段重新開始。' }
$uatProbe = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,9468)
try { $uatProbe.Start() } catch { throw '無法使用9468，可能已被占用或被政策阻擋；請IT核對原測試視窗，勿停止其他服務。' } finally { $uatProbe.Stop() }
Write-Host "本場代碼：$uatSession"
Write-Host "資料位置：$uatData"
& $uatPython -B .\run.py --port 9468 --data-dir $uatData
```

看到 `Care console: http://127.0.0.1:9468/` 才開該網址。記下場次碼及資料位置；準備失敗沒有開始計時，不填參與者任務失敗。確認畫面標示本機體驗、模擬資料、使用既有服務摘要及未連接真實LINE。全新場次設定的模型與LINE均預設關閉，工作台沒有啟用模型的操作；不要求尋找不存在的「模型停用」按鈕。不提供API金鑰、不編輯設定檔、不使用tunnel或真實資料匯入。

若瀏覽器顯示前場帳號或資料，先關閉該場全部分頁、清除此localhost網站的舊登入或使用新的瀏覽器設定檔再登入；確認場次網址、住民R001～R006與沒有前場案件。初始有虛構照護觀察是種子資料，並非前場殘留。畫面不顯示場次碼，須以啟動視窗對照，不能只靠同一個網址判定新場已啟動。

## 參與者：登入與基本操作

1. 主持人開好本場網址後，在「院內帳號」選分配的護理師、接班護理師、護理長或照服員，輸入共用示範密碼 `CareDemo2026!`。登入後名稱標示體驗帳號；這些帳號不對應正式員工。
2. 護理師nurse可查看六位示範住民；nurse2扮演指定接班者；護理長head_nurse只看R001、R002案件監控；照服員caregiver只看R001、R002照護資料。
3. 主持人需要演示撤權時才使用admin。IT不能查看臨床或案件，不讓參與者用IT繞過其他角色限制。
4. 依 [情境腳本](TEST_SCENARIOS.md)逐項操作，卡住先說明看到什麼。沒有正確／錯誤個人評分；主持人會記錄需要提示及系統問題。
5. 一般編輯先保存才登出換帳號；但「保存進度並提出交班」已包含保存，提出後直接登出，不要再按「保存進度」，否則會取消待接受交班。尚未保存時，依視窗提示選繼續編輯或放棄。登出、關閉視窗與結案是不同動作。

若要保留接班者的舊畫面，主持人先準備兩個獨立瀏覽器設定檔，分別登入nurse與nurse2；一般同瀏覽器分頁共用登入，不能當成兩位獨立使用者。只有一個設定檔時用輪流登入，U03可能只能看到已失效而沒有可按的接受鈕，如實記錄展示方式。

## 停止、保留及下一位

保存必要紀錄，所有人登出，關閉該場分頁，在「本場」啟動視窗按Ctrl+C。等命令提示字元回來，再執行上面整段產生新場。這是切換到新資料夾的重設，不刪資料庫、不還原覆蓋、不複製前場資料。原場資料夾、錯誤及觀察表都保留供核對；依機構另定保存期限處置，不在試用時清空。

誤按後想再試：先保留失敗結果，記為新嘗試次數；需要從零開始時另開新場，不把重試改稱第一次成功。即使全是虛構資料，session.key與本機設定仍不能加入Git或公開分享。觀察表可能包含參與者意見，也不得直接提交儲存庫。
