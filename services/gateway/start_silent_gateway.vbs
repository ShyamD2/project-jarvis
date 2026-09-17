Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "d:\Project J.A.R.V.I.S"
WshShell.Run "cmd.exe /c """ & "d:\Project J.A.R.V.I.S\run_telegram_gateway.bat" & """", 0, False
