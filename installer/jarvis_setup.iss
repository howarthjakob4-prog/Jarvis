[Setup]
AppId={{A8F32D1C-48C9-4F43-9C8E-4A4C28E8C1A7}
AppName=JARVIS
AppVersion=1.0.1
AppPublisher=MrClipperz
AppPublisherURL=https://github.com/howarthjakob4-prog/Jarvis
AppSupportURL=https://github.com/howarthjakob4-prog/Jarvis/issues
AppUpdatesURL=https://github.com/howarthjakob4-prog/Jarvis/releases
DefaultDirName={autopf}\JARVIS
UsePreviousAppDir=yes
DefaultGroupName=JARVIS
UsePreviousGroup=yes
AllowNoIcons=yes
LicenseFile=..\LICENSE
OutputDir=.
OutputBaseFilename=JARVIS-Setup-v1
SetupIconFile=..\jarvis.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UninstallDisplayIcon={app}\jarvis.ico
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"
Name: "startupentry"; Description: "Start JARVIS &automatically with Windows (runs minimized)"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
; Patch the existing program files in place. User profile/configuration lives outside
; {app} in %APPDATA%\JARVIS and is deliberately not touched by this installer.
Source: "..\dist\JARVIS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\jarvis.ico"; DestDir: "{app}"; DestName: "jarvis.ico"; Flags: ignoreversion

[Icons]
Name: "{group}\JARVIS"; Filename: "{app}\JARVIS.exe"; IconFilename: "{app}\jarvis.ico"; IconIndex: 0
Name: "{group}\Uninstall JARVIS"; Filename: "{uninstallexe}"; IconFilename: "{app}\jarvis.ico"; IconIndex: 0
Name: "{commondesktop}\JARVIS"; Filename: "{app}\JARVIS.exe"; IconFilename: "{app}\jarvis.ico"; IconIndex: 0; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "JARVIS"; ValueData: """{app}\JARVIS.exe"" --minimized"; Flags: uninsdeletevalue; Tasks: startupentry

[Run]
Filename: "{app}\JARVIS.exe"; Description: "Launch updated JARVIS now"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then begin
    // This is an in-place patch. Do not reset or recreate the JARVIS user profile.
  end;
end;
