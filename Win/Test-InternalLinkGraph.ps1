<#
.SYNOPSIS
    Crawls a site and builds an internal-link graph report.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Url,
    [string]$Sitemap,
    [ValidateRange(1, 10000)]
    [int]$MaxPages = 250,
    [ValidateRange(0, 50)]
    [int]$MaxDepth = 6,
    [ValidateRange(0, 60000)]
    [int]$DelayMs = 75,
    [string]$Json,
    [string]$Html,
    [switch]$IncludeSubdomains,
    [switch]$DropQuery,
    [switch]$Progress
)

$launcher = Join-Path $PSScriptRoot 'Start-SEOIndexToolkit.ps1'
$arguments = @('links', '--url', $Url, '--max-pages', $MaxPages, '--max-depth', $MaxDepth, '--delay-ms', $DelayMs)
if ($Sitemap) { $arguments += @('--sitemap', $Sitemap) }
if ($Json) { $arguments += @('--json', $Json) }
if ($Html) { $arguments += @('--html', $Html) }
if ($IncludeSubdomains) { $arguments += '--include-subdomains' }
if ($DropQuery) { $arguments += '--drop-query' }
if ($Progress) { $arguments += '--progress' }
& $launcher @arguments
exit $LASTEXITCODE
