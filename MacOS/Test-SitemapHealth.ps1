[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [uri]$Sitemap,
    [ValidateRange(0, 1000000)]
    [int]$CheckPages = 0,
    [ValidateRange(1, 64)]
    [int]$Workers = 8,
    [string]$JsonReport,
    [switch]$NoSplash
)

$argsList = @('sitemap', '--sitemap', $Sitemap.AbsoluteUri, '--check-pages', $CheckPages, '--workers', $Workers)
if ($JsonReport) { $argsList += @('--json', $JsonReport) }
if ($NoSplash) { $argsList = @('--no-splash') + $argsList }
& (Join-Path $PSScriptRoot 'Start-SEOIndexToolkit.ps1') @argsList
exit $LASTEXITCODE
