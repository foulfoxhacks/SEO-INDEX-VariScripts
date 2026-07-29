[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Url,
    [switch]$ShowJson,
    [string]$Json
)
$argsList = @('schema','--url',$Url)
if ($ShowJson) { $argsList += '--show-json' }
if ($Json) { $argsList += @('--json',$Json) }
& "$PSScriptRoot\Start-SEOIndexToolkit.ps1" @argsList
exit $LASTEXITCODE
