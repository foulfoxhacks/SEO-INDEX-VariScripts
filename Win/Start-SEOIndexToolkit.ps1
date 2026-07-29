<#
.SYNOPSIS
    Starts the SEO-INDEX VariScripts terminal toolkit.
.DESCRIPTION
    Locates Python 3 from PATH or common per-user/system install locations and
    forwards all remaining arguments to the shared cross-platform toolkit.
    With no arguments, an interactive terminal menu opens.
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$ToolkitArguments
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $root 'Py+Linux\Scripts\seo_index_toolkit.py'
if (-not (Test-Path -LiteralPath $script)) {
    throw "Toolkit core not found: $script"
}

function Test-RealPythonCommand {
    param([System.Management.Automation.CommandInfo]$Command)
    if (-not $Command) { return $false }
    $path = $Command.Source
    if (-not $path) { $path = $Command.Path }
    if ($path -and $path -like '*\Microsoft\WindowsApps\python*.exe') { return $false }
    return $true
}

$py = Get-Command py.exe -ErrorAction SilentlyContinue
if (Test-RealPythonCommand $py) {
    & $py.Source -3 $script @ToolkitArguments
    exit $LASTEXITCODE
}

foreach ($name in @('python3.exe', 'python.exe')) {
    $command = Get-Command $name -ErrorAction SilentlyContinue
    if (Test-RealPythonCommand $command) {
        & $command.Source $script @ToolkitArguments
        exit $LASTEXITCODE
    }
}

$patterns = @(
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python*\python.exe'),
    (Join-Path $env:LOCALAPPDATA 'Python\**\python.exe'),
    (Join-Path $env:ProgramFiles 'Python*\python.exe')
)
if (${env:ProgramFiles(x86)}) {
    $patterns += (Join-Path ${env:ProgramFiles(x86)} 'Python*\python.exe')
}

$candidates = foreach ($pattern in $patterns) {
    Get-ChildItem -Path $pattern -File -ErrorAction SilentlyContinue
}
$python = $candidates | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($python) {
    & $python.FullName $script @ToolkitArguments
    exit $LASTEXITCODE
}

throw @'
Python 3 was not found.
Install it with:
  winget install --exact --id Python.Python.3.14 --source winget
Then reopen the terminal. App Installer aliases named python.exe/python3.exe are not real interpreters.
'@
