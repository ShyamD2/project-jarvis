Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "D:\Project J.A.R.V.I.S"
WshShell.Run """C:\Users\dines\AppData\Local\Programs\Python\Python313\python.exe""" """D:\Project J.A.R.V.I.S\services\gateway\telegram_bot.py""", 0, False
