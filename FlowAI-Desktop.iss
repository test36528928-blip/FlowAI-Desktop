; FlowAI Desktop v2 Inno Setup script
#define MyAppName "FlowAI Desktop"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "FlowAI"
#define MyAppExeName "FlowAI.exe"

[Setup]
AppId={{A47E90AA-45CF-4F5D-8B38-DAE3B6A0C91D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\FlowAI Desktop
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=FlowAI-Desktop-Setup-v{#MyAppVersion}
SetupIconFile=flowai.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaüstü kısayolu oluştur"; GroupDescription: "Ek kısayollar:"; Flags: unchecked

[Files]
Source: "dist\FlowAI.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "FlowAI Desktop'ı başlat"; Flags: postinstall nowait skipifsilent
