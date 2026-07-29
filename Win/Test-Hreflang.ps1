[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Url,
    [switch]$CheckAlternates,
    [ValidateRange(0,1000)][int]$Limit = 20,
    [string]$Json
)
$argsList = @('hreflang','--url',$Url,'--limit',$Limit)
if ($CheckAlternates) { $argsList += '--check-alternates' }
if ($Json) { $argsList += @('--json',$Json) }
& "$PSScriptRoot\Start-SEOIndexToolkit.ps1" @argsList
exit $LASTEXITCODE
