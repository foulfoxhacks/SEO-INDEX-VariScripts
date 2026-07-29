[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$Url,[string]$Json)
$argsList = @('geo','--url',$Url)
if ($Json) { $argsList += @('--json',$Json) }
& "$PSScriptRoot\Start-SEOIndexToolkit.ps1" @argsList
exit $LASTEXITCODE
