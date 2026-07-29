<#
.SYNOPSIS
    Starts the localhost graphical SEO-INDEX workbench and live audit API.
#>
[CmdletBinding()]
param(
    [string]$HostAddress = '127.0.0.1',
    [ValidateRange(0, 65535)]
    [int]$Port = 8765,
    [ValidateRange(1, 10000)]
    [int]$ApiMaxPages = 500,
    [switch]$NoOpen,
    [switch]$AllowPrivateTargets,
    [switch]$VerboseRequests
)

$launcher = Join-Path $PSScriptRoot 'Start-SEOIndexToolkit.ps1'
$arguments = @('serve', '--host', $HostAddress, '--port', $Port, '--api-max-pages', $ApiMaxPages)
if ($NoOpen) { $arguments += '--no-open' }
if ($AllowPrivateTargets) { $arguments += '--allow-private-targets' }
if ($VerboseRequests) { $arguments += '--verbose' }
& $launcher @arguments
exit $LASTEXITCODE
