[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Url,
    [string[]]$Agent,
    [string]$Json
)
$argsList = @('robots','--url',$Url)
foreach ($item in $Agent) { $argsList += @('--agent',$item) }
if ($Json) { $argsList += @('--json',$Json) }
& "$PSScriptRoot\Start-SEOIndexToolkit.ps1" @argsList
exit $LASTEXITCODE
