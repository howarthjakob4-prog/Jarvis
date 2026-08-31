[Setup]
AppName=JARVIS
AppVersion=1
AppPublisher=MrClipperz
AppPublisherURL=https://github.com/howarthjakob4-prog/Jarvis
AppSupportURL=https://github.com/howarthjakob4-prog/Jarvis/issues
AppUpdatesURL=https://github.com/howarthjakob4-prog/Jarvis/releases
DefaultDirName={autopf}\JARVIS
DefaultGroupName=JARVIS
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
UninstallDisplayIcon={app}\JARVIS.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"
Name: "startupentry"; Description: "Start JARVIS &automatically with Windows (runs minimized)"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
Source: "..\dist\JARVIS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\JARVIS"; Filename: "{app}\JARVIS.exe"; IconFilename: "{app}\JARVIS.exe"
Name: "{group}\Uninstall JARVIS"; Filename: "{uninstallexe}"
Name: "{commondesktop}\JARVIS"; Filename: "{app}\JARVIS.exe"; IconFilename: "{app}\JARVIS.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "JARVIS"; ValueData: """{app}\JARVIS.exe"" --minimized"; Flags: uninsdeletevalue; Tasks: startupentry

[Run]
Filename: "{app}\JARVIS.exe"; Description: "Launch JARVIS now"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then begin
    // Keep setup lightweight. Optional browser automation can be installed later on demand.
  end;
end;
