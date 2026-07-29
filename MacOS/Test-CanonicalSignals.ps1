[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [uri]$Sitemap,
    [string]$ExpectedHost,
    [ValidateRange(0, 1000000)]
    [int]$Limit = 100,
    [ValidateRange(1, 64)]
    [int]$Workers = 8,
    [string]$JsonReport,
    [switch]$NoSplash
)

$argsList = @('canonical', '--sitemap', $Sitemap.AbsoluteUri, '--limit', $Limit, '--workers', $Workers)
if ($ExpectedHost) { $argsList += @('--expected-host', $ExpectedHost) }
if ($JsonReport) { $argsList += @('--json', $JsonReport) }
if ($NoSplash) { $argsList = @('--no-splash') + $argsList }
& (Join-Path $PSScriptRoot 'Start-SEOIndexToolkit.ps1') @argsList
exit $LASTEXITCODE
