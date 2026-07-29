[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Url,
    [ValidateRange(1,50)][int]$MaxHops = 10,
    [string]$Json
)
$argsList = @('redirect','--url',$Url,'--max-hops',$MaxHops)
if ($Json) { $argsList += @('--json',$Json) }
& "$PSScriptRoot\Start-SEOIndexToolkit.ps1" @argsList
exit $LASTEXITCODE
