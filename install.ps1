<#
.SYNOPSIS
    Installs SEO-INDEX VariScripts for the current Windows user.
.DESCRIPTION
    Downloads the public GitHub repository, installs it under LocalAppData,
    creates a seo-index command shim, and optionally adds the shim directory
    to the current user's PATH.
.EXAMPLE
    irm https://raw.githubusercontent.com/foulfoxhacks/SEO-INDEX-VariScripts/main/install.ps1 | iex
#>
[CmdletBinding()]
param(
    [string]$Repository = 'foulfoxhacks/SEO-INDEX-VariScripts',
    [string]$Ref = 'main',
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'SEO-INDEX-VariScripts'),
    [string]$BinDir = (Join-Path $HOME 'bin'),
    [switch]$NoPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
try {
    [Net.ServicePointManager]::SecurityProtocol =
        [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
}
catch {}

$temp = Join-Path ([IO.Path]::GetTempPath()) ('seo-index-' + [Guid]::NewGuid().ToString('N'))
$archive = Join-Path $temp 'repo.zip'
$extract = Join-Path $temp 'extract'
$download = "https://github.com/$Repository/archive/refs/heads/$Ref.zip"

try {
    New-Item -ItemType Directory -Path $temp, $extract -Force | Out-Null
    Write-Host "Downloading $Repository ($Ref)..."
    Invoke-WebRequest -Uri $download -OutFile $archive -UseBasicParsing
    Expand-Archive -LiteralPath $archive -DestinationPath $extract -Force
    $source = Get-ChildItem -LiteralPath $extract -Directory | Select-Object -First 1
    if (-not $source) { throw 'Downloaded archive did not contain a repository directory.' }

    if (Test-Path -LiteralPath $InstallDir) {
        Remove-Item -LiteralPath $InstallDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    Copy-Item -Path (Join-Path $source.FullName '*') -Destination $InstallDir -Recurse -Force

    New-Item -ItemType Directory -Path $BinDir -Force | Out-Null
    $cmdPath = Join-Path $BinDir 'seo-index.cmd'
    $launcher = Join-Path $InstallDir 'Win\Start-SEOIndexToolkit.ps1'
    @"
@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$launcher" %*
"@ | Set-Content -LiteralPath $cmdPath -Encoding ASCII

    if (-not $NoPath) {
        $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
        $parts = @($userPath -split ';' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
        if ($parts -notcontains $BinDir) {
            $newPath = (@($parts) + $BinDir) -join ';'
            [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
            Write-Host "Added $BinDir to your user PATH. Open a new terminal before using seo-index."
        }
    }

    Write-Host ''
    Write-Host 'SEO-INDEX VariScripts installed.' -ForegroundColor Green
    Write-Host "Install directory: $InstallDir"
    Write-Host "Command shim:      $cmdPath"
    Write-Host 'Run: seo-index'
}
finally {
    Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
}
