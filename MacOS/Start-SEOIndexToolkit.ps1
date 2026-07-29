<#
.SYNOPSIS
    Starts the SEO-INDEX VariScripts terminal toolkit.
.DESCRIPTION
    Locates Python 3 and forwards all remaining arguments to the shared
    cross-platform toolkit. With no arguments, an interactive terminal menu opens.
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

if (Get-Command py.exe -ErrorAction SilentlyContinue) {
    & py.exe -3 $script @ToolkitArguments
}
elseif (Get-Command python3.exe -ErrorAction SilentlyContinue) {
    & python3.exe $script @ToolkitArguments
}
elseif (Get-Command python.exe -ErrorAction SilentlyContinue) {
    & python.exe $script @ToolkitArguments
}
else {
    throw 'Python 3 was not found. Install Python 3, reopen the terminal, and retry.'
}
exit $LASTEXITCODE
