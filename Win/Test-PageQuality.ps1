[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Url,
    [string]$Json,
    [string]$Markdown,
    [ValidateSet('critical', 'warning', 'never')][string]$FailOn = 'critical'
)
$argsList = @('page', '--url', $Url, '--fail-on', $FailOn)
if ($Json) { $argsList += @('--json', $Json) }
if ($Markdown) { $argsList += @('--markdown', $Markdown) }
& "$PSScriptRoot\Start-SEOIndexToolkit.ps1" @argsList
exit $LASTEXITCODE
