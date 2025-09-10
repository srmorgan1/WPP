[Setup]
AppName=WPP Web Application
AppVersion=1.0.0
AppPublisher=WPP Development Team
DefaultDirName={autopf}\WPP
DefaultGroupName=WPP
OutputDir=installer
OutputBaseFilename=WPP-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
WizardStyle=modern
SetupIconFile=
UninstallDisplayIcon={app}\wpp-web-app.exe
VersionInfoVersion=1.0.0
AppSupportURL=https://github.com/srmorgan1/WPP
AppUpdatesURL=https://github.com/srmorgan1/WPP

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main executables at root level
Source: "dist\wpp\wpp-web-app.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\wpp\run-reports.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\wpp\update-database.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\wpp\wpp-web-api.exe"; DestDir: "{app}"; Flags: ignoreversion; Check: FileExists(ExpandConstant('{src}\dist\wpp\wpp-web-api.exe'))

; Dependencies directory
Source: "dist\wpp\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

; Wheel files at top level
Source: "dist\*.whl"; DestDir: "{app}"; Flags: ignoreversion

; Optional: Include any additional files like README, LICENSE
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion; Check: FileExists(ExpandConstant('{src}\README.md'))
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion; Check: FileExists(ExpandConstant('{src}\LICENSE'))

[Icons]
; Start Menu shortcuts
Name: "{group}\WPP Web Application"; Filename: "{app}\wpp-web-app.exe"; WorkingDir: "{app}"; Comment: "Launch WPP Web Application"
Name: "{group}\Run Reports"; Filename: "{app}\run-reports.exe"; WorkingDir: "{app}"; Comment: "Run WPP Reports"
Name: "{group}\Update Database"; Filename: "{app}\update-database.exe"; WorkingDir: "{app}"; Comment: "Update WPP Database"
Name: "{group}\{cm:UninstallProgram,WPP}"; Filename: "{uninstallexe}"

; Desktop shortcut (optional)
Name: "{autodesktop}\WPP Web Application"; Filename: "{app}\wpp-web-app.exe"; WorkingDir: "{app}"; Tasks: desktopicon; Comment: "Launch WPP Web Application"

[Registry]
; Add to Windows PATH (optional)
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Check: NeedsAddPath('{app}')

[Code]
function NeedsAddPath(Param: string): boolean;
var
  OrigPath: string;
begin
  if not RegQueryStringValue(HKEY_LOCAL_MACHINE,
    'SYSTEM\CurrentControlSet\Control\Session Manager\Environment',
    'Path', OrigPath)
  then begin
    Result := True;
    exit;
  end;
  { look for the path with leading and trailing semicolon }
  { Pos() returns 0 if not found }
  Result := Pos(';' + Param + ';', ';' + OrigPath + ';') = 0;
end;

function FileExists(FileName: string): Boolean;
begin
  Result := FileOrDirExists(FileName);
end;

[Run]
Filename: "{app}\wpp-web-app.exe"; Description: "{cm:LaunchProgram,WPP Web Application}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"
Type: files; Name: "{app}\*.whl"