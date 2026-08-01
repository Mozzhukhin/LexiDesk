#define AppName "LexiDesk"
#ifndef AppVersion
  #define AppVersion "dev"
#endif

[Setup]
AppId={{D32D1E10-24F5-4FF1-B82D-9628BCA9D46A}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=LexiDesk contributors
AppPublisherURL=https://github.com/Mozzhukhin/LexiDesk
DefaultDirName={autopf}\LexiDesk
DefaultGroupName=LexiDesk
DisableProgramGroupPage=yes
OutputDir=..\..\release
OutputBaseFilename=LexiDesk-Setup-Windows-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\LexiDesk.exe

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "autostart"; Description: "Start LexiDesk when I sign in"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
Source: "..\..\dist\LexiDesk\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\LexiDesk"; Filename: "{app}\LexiDesk.exe"
Name: "{autodesktop}\LexiDesk"; Filename: "{app}\LexiDesk.exe"; Tasks: desktopicon
Name: "{userstartup}\LexiDesk"; Filename: "{app}\LexiDesk.exe"; Tasks: autostart

[Run]
Filename: "{app}\LexiDesk.exe"; Description: "Launch LexiDesk"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{userstartup}\LexiDesk.cmd"
