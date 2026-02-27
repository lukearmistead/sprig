$ErrorActionPreference = "Stop"

$repo = "lukearmistead/sprig"
$installDir = "$HOME\.local\bin"

if (-not (Test-Path $installDir)) {
    New-Item -ItemType Directory -Path $installDir -Force | Out-Null
}

Write-Host "Downloading Sprig for Windows..."
$url = "https://github.com/$repo/releases/latest/download/sprig-windows.exe"
Invoke-WebRequest -Uri $url -OutFile "$installDir\sprig.exe" -UseBasicParsing

Write-Host "Installed to $installDir\sprig.exe"

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$installDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$installDir", "User")
    Write-Host "Added $installDir to your PATH (restart your terminal to use 'sprig' directly)."
}

Write-Host "Run 'sprig sync' to get started."
