; ============================================================
; installer.iss — Inno Setup Script for Browser Forensics Pro
; ============================================================
; Requirements:
;   1. PyInstaller build must run first (creates dist\BrowserForensicsPro.exe)
;   2. Inno Setup 6 — https://jrsoftware.org/isinfo.php
;
; To compile:
;   ISCC.exe installer.iss
;   OR open in Inno Setup IDE and press F9

#define AppName        "Browser Forensics Pro"
#define AppExeName     "BrowserForensicsPro"
#define AppVersion     "1.0.0"
#define AppPublisher   "Sharath Chandra Karnati"
#define AppURL         "https://github.com/browserforensicspro/BFP"
#define AppExePath     "..\..\dist\BrowserForensicsPro.exe"
#define SetupOutDir    "..\..\release"
#define LicenseFile    "..\..\LICENSE.txt"

; ── Setup metadata ────────────────────────────────────────────────────────────
[Setup]
; App identity
AppId                     = {{A3F8B2C1-4D5E-4A6F-9B8C-1D2E3F4A5B6C}}
AppName                   = {#AppName}
AppVersion                = {#AppVersion}
AppPublisherURL           = {#AppURL}
AppSupportURL             = {#AppURL}
AppUpdatesURL             = {#AppURL}
AppPublisher              = {#AppPublisher}
AppCopyright              = Copyright 2025 {#AppPublisher}

; Install location
DefaultDirName            = {autopf}\{#AppName}
DefaultGroupName          = {#AppName}
DisableProgramGroupPage   = yes
AllowNoIcons              = yes

; Output
OutputDir                 = {#SetupOutDir}
OutputBaseFilename        = {#AppExeName}_v{#AppVersion}_Setup
SetupIconFile             = ..\..\assets\bfp_icon.ico

; Compression — LZMA2 with maximum compression level
Compression               = lzma2/ultra64
SolidCompression          = yes
LZMAUseSeparateProcess    = yes
LZMADictionarySize        = 1048576
LZMANumBlockThreads       = 4

; UI / Appearance
WizardStyle               = modern
WizardSizePercent         = 120
ShowLanguageDialog        = no

; Privileges
PrivilegesRequired        = admin
PrivilegesRequiredOverridesAllowed = dialog

; Windows version requirements
MinVersion                = 10.0.17763
ArchitecturesAllowed      = x64
ArchitecturesInstallIn64BitMode = x64

; Misc
DisableWelcomePage        = no
DisableDirPage            = no
DisableReadyPage          = no
AllowRootDirectory        = no
CreateUninstallRegKey     = yes
UninstallDisplayName      = {#AppName}
UninstallDisplayIcon      = {app}\{#AppExeName}.exe
Uninstallable             = yes
CloseApplications         = yes
RestartApplications       = yes
VersionInfoVersion        = {#AppVersion}
VersionInfoCompany        = {#AppPublisher}
VersionInfoDescription    = {#AppName} Installer
VersionInfoCopyright      = Copyright 2025 {#AppPublisher}

; ── Languages ─────────────────────────────────────────────────────────────────
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

; ── Installer pages ───────────────────────────────────────────────────────────
[Messages]
WelcomeLabel2=This will install [name/ver] on your computer.%n%nBrowser Forensics Pro is a read-only digital forensics tool for analyzing browser artifacts from Chrome, Edge, Brave, and Firefox.%n%nClick Next to continue, or Cancel to exit.

; ── Files to install ──────────────────────────────────────────────────────────
[Files]
; Main executable (built by PyInstaller)
Source: "{#AppExePath}";                  DestDir: "{app}"; DestName: "{#AppExeName}.exe"; Flags: ignoreversion

; App icon for shortcuts
Source: "..\..\assets\bfp_icon.ico";       DestDir: "{app}\assets"; Flags: ignoreversion

; License file
Source: "{#LicenseFile}";                  DestDir: "{app}"; Flags: ignoreversion isreadme

; README
Source: "..\..\README.md";                DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

; ── Shortcuts ────────────────────────────────────────────────────────────────
[Icons]
; Start Menu shortcut
Name: "{group}\{#AppName}";      Filename: "{app}\{#AppExeName}.exe"; IconFilename: "{app}\assets\bfp_icon.ico"; Comment: "Browser Forensics Pro — Digital Forensic Analysis Tool"
; Desktop shortcut
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}.exe"; IconFilename: "{app}\assets\bfp_icon.ico"; Tasks: desktopicon
; Uninstall shortcut in Start Menu
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"

; ── Optional tasks during install ─────────────────────────────────────────────
[Tasks]
Name: desktopicon; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

; ── Registry entries ─────────────────────────────────────────────────────────
[Registry]
; Optional metadata keys — HKA auto-selects HKLM (admin) or HKCU (non-admin)
; noerror flag ensures a permissions failure is silently skipped, not shown as an error
Root: HKA; Subkey: "Software\{#AppPublisher}\{#AppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey noerror
Root: HKA; Subkey: "Software\{#AppPublisher}\{#AppName}"; ValueType: string; ValueName: "Version"; ValueData: "{#AppVersion}"; Flags: noerror

; ── Run after install ─────────────────────────────────────────────────────────
[Run]
Filename: "{app}\{#AppExeName}.exe"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

; ── Uninstall cleanup ─────────────────────────────────────────────────────────
[UninstallDelete]
; Remove settings file created at runtime
Type: files; Name: "{localappdata}\BFP\bfp_settings.json"
Type: dirifempty; Name: "{localappdata}\BFP"

; ── Pascal script — auto-installs WebView2 if missing ────────────────────────
[Code]

// ─── Helper: check if WebView2 Evergreen Runtime is present ────────────────
function IsWebView2Installed(): Boolean;
var
  Version: String;
begin
  Result :=
    RegQueryStringValue(HKLM,
      'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
      'pv', Version) or
    RegQueryStringValue(HKCU,
      'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
      'pv', Version) or
    // Also check the fixed-version / machine-wide key Microsoft uses on newer machines
    RegQueryStringValue(HKLM,
      'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
      'pv', Version);
end;

// ─── Silent WebView2 download + install ────────────────────────────────────
function InstallWebView2(): Boolean;
var
  BootstrapperURL : String;
  BootstrapperPath: String;
  PsCmd           : String;
  ResultCode      : Integer;
begin
  Result := True;

  if IsWebView2Installed() then
    Exit;   // already present — nothing to do

  BootstrapperURL  := 'https://go.microsoft.com/fwlink/p/?LinkId=2124703';
  BootstrapperPath := ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe');

  // Build PowerShell one-liner to download the bootstrapper
  // Uses .NET WebClient — works on all Windows 10+ without elevation
  PsCmd := '-NoProfile -NonInteractive -Command "' +
    '(New-Object System.Net.WebClient).DownloadFile(' +
    '[string]''https://go.microsoft.com/fwlink/p/?LinkId=2124703'', ' +
    '[string]''' + BootstrapperPath + ''')"';

  WizardForm.StatusLabel.Caption := 'Downloading Microsoft WebView2 Runtime...';
  WizardForm.FilenameLabel.Caption := 'Connecting to Microsoft servers. Please wait...';

  // Run PowerShell download (wait until done)
  if not Exec('powershell.exe', PsCmd, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0) then
  begin
    WizardForm.StatusLabel.Caption := '';
    WizardForm.FilenameLabel.Caption := '';
    if MsgBox(
      'Could not download Microsoft WebView2 Runtime.' + #13#10 +
      'An internet connection is required on first install.' + #13#10 + #13#10 +
      'Click YES to continue anyway (app may not open),' + #13#10 +
      'or NO to cancel and install WebView2 manually from:' + #13#10 +
      'https://go.microsoft.com/fwlink/p/?LinkId=2124703',
      mbError, MB_YESNO) = IDNO then
      Result := False;
    Exit;
  end;

  // Run the bootstrapper silently — no user prompts
  WizardForm.StatusLabel.Caption := 'Installing Microsoft WebView2 Runtime...';
  WizardForm.FilenameLabel.Caption := 'This may take a moment. Please wait...';
  Exec(BootstrapperPath, '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  WizardForm.StatusLabel.Caption := '';
  WizardForm.FilenameLabel.Caption := '';
end;

// ─── Hook: called just before actual file installation begins ───────────────
function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';   // empty = no error, continue

  if not IsWebView2Installed() then
  begin
    if not InstallWebView2() then
      Result := 'Installation cancelled. Please install WebView2 manually and re-run Setup.';
  end;
end;

// ─── Always allow setup to proceed ─────────────────────────────────────────
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
