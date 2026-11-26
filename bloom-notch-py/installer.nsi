; Crown Notch installer (NSIS, per-user — no admin required)
!define APPNAME "Crown Notch"
!define UNINSTKEY "CrownNotch"

Name "${APPNAME}"
OutFile "..\dist\CrownNotch-Setup.exe"
InstallDir "$LOCALAPPDATA\CrownNotch"
RequestExecutionLevel user
SetCompressor /SOLID lzma

Page directory
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

Section "install"
  SetShellVarContext current
  SetOutPath "$INSTDIR"
  File "dist\CrownNotch.exe"

  ; Start Menu shortcut
  CreateDirectory "$SMPROGRAMS\Crown Notch"
  CreateShortcut "$SMPROGRAMS\Crown Notch\Crown Notch.lnk" "$INSTDIR\CrownNotch.exe"
  CreateShortcut "$SMPROGRAMS\Crown Notch\Uninstall Crown Notch.lnk" "$INSTDIR\uninstall.exe"

  ; Uninstall entry (Settings > Apps)
  WriteUninstaller "$INSTDIR\uninstall.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${UNINSTKEY}" "DisplayName" "${APPNAME}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${UNINSTKEY}" "DisplayVersion" "0.3.0b1"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${UNINSTKEY}" "Publisher" "Crown Notch"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${UNINSTKEY}" "DisplayIcon" "$INSTDIR\CrownNotch.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${UNINSTKEY}" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${UNINSTKEY}" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${UNINSTKEY}" "NoRepair" 1

  ; launch right away so the notch appears immediately
  Exec "$INSTDIR\CrownNotch.exe"
SectionEnd

Section "uninstall"
  SetShellVarContext current
  ; kill a running instance so files can be removed
  nsExec::Exec 'taskkill /IM CrownNotch.exe /F'
  Sleep 500
  Delete "$SMPROGRAMS\Crown Notch\Crown Notch.lnk"
  Delete "$SMPROGRAMS\Crown Notch\Uninstall Crown Notch.lnk"
  RMDir "$SMPROGRAMS\Crown Notch"
  Delete "$INSTDIR\CrownNotch.exe"
  Delete "$INSTDIR\uninstall.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${UNINSTKEY}"
  ; keep %APPDATA%\CrownNotch settings — users may reinstall
SectionEnd
