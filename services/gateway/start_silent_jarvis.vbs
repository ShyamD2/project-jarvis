Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "D:\Project J.A.R.V.I.S"
cmd = Chr(34) & "C:\Users\dines\AppData\Local\Programs\Python\Python313\pythonw.exe" & Chr(34) & " " & Chr(34) & "D:\Project J.A.R.V.I.S\services\jarvis_background_service.py" & Chr(34)
WshShell.Run cmd, 0, False
