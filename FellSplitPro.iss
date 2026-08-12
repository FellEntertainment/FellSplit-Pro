#define MyAppName "FellSplit Pro"
#define MyAppVersion "1.3.0"
#define MyAppPublisher "Fell Entertainment & Co."
#define MyAppExeName "FellSplitPro.exe"

[Setup]
AppId={{F93D5D7D-2B2A-4CC5-A4B9-7410FBE18122}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
; Intentionally shared with 1.2.2 builds from before the product rename.
AppMutex=Local\SplitLock-Fell-Entertainment-v1
DefaultDirName={autopf}\FellSplit Pro
DefaultGroupName=FellSplit Pro
DisableDirPage=no
DisableProgramGroupPage=yes
OutputDir=installer
OutputBaseFilename=FellSplit-Pro-Setup-{#MyAppVersion}
SetupIconFile=assets\FellSplitPro.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} {#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
CloseApplications=yes
RestartApplications=no
CloseApplicationsFilter=FellSplitPro.exe
SetupLogging=yes
UsePreviousAppDir=yes
VersionInfoVersion=1.3.0.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=Installer fuer {#MyAppName}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "Desktop-Verknuepfung erstellen"; GroupDescription: "Zusaetzliche Verknuepfungen:"; Flags: unchecked

[Files]
Source: "dist\FellSplitPro.exe"; DestDir: "{app}"; Flags: ignoreversion

[InstallDelete]
; Removes only files left by the older OneDir package. User files are untouched.
Type: filesandordirs; Name: "{app}\_internal"
Type: files; Name: "{app}\README.md"
Type: files; Name: "{app}\CHANGELOG.md"
Type: files; Name: "{app}\emergency_unlock.ps1"
Type: files; Name: "{app}\FellSplitPro_Notfall.bat"

[Icons]
Name: "{autoprograms}\FellSplit Pro"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autoprograms}\FellSplit Pro Notfall-Freigabe"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--emergency-unlock"; WorkingDir: "{app}"
Name: "{autodesktop}\FellSplit Pro"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "FellSplit Pro"; Flags: uninsdeletevalue dontcreatekey
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "SplitLock"; Flags: uninsdeletevalue dontcreatekey

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "FellSplit Pro jetzt starten"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent
