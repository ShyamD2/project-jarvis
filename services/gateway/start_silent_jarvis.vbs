Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "D:\Project J.A.R.V.I.S"
localAppData = WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%")
cmd = Chr(34) & localAppData & "\Programs\Python\Python313\pythonw.exe" & Chr(34) & " " & Chr(34) & "D:\Project J.A.R.V.I.S\services\jarvis_background_service.py" & Chr(34)
WshShell.Run cmd, 0, False
