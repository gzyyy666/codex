Option Explicit

Dim shell, fso, baseDir, pythonw, launcher
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

baseDir = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = shell.ExpandEnvironmentStrings("%LocalAppData%") & "\Python\pythoncore-3.14-64\pythonw.exe"
If Not fso.FileExists(pythonw) Then pythonw = "pythonw.exe"
launcher = fso.BuildPath(baseDir, "launcher.pyw")

shell.CurrentDirectory = baseDir
shell.Run """" & pythonw & """ """ & launcher & """", 0, False
