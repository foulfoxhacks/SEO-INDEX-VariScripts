[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [uri]$Url,
    [ValidateSet('google', 'bing', 'generic', 'all')]
    [string]$Engine = 'all',
    [uri]$Sitemap,
    [uri]$KeyLocation,
    [string]$JsonReport,
    [string]$MarkdownReport,
    [ValidateRange(0, 100)]
    [int]$FailBelow = 0,
    [switch]$NoSplash
)

$argsList = @('score', '--url', $Url.AbsoluteUri, '--engine', $Engine, '--fail-below', $FailBelow)
if ($Sitemap) { $argsList += @('--sitemap', $Sitemap.AbsoluteUri) }
if ($KeyLocation) { $argsList += @('--key-location', $KeyLocation.AbsoluteUri) }
if ($JsonReport) { $argsList += @('--json', $JsonReport) }
if ($MarkdownReport) { $argsList += @('--markdown', $MarkdownReport) }
if ($NoSplash) { $argsList = @('--no-splash') + $argsList }
& (Join-Path $PSScriptRoot 'Start-SEOIndexToolkit.ps1') @argsList
exit $LASTEXITCODE
