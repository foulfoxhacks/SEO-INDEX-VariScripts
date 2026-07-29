<#
.SYNOPSIS
    Reads one or more XML sitemaps and submits their URLs to IndexNow.

.DESCRIPTION
    A public, site-agnostic IndexNow runner for Windows PowerShell 5.1 and
    PowerShell 7+. It supports sitemap indexes, GZip-compressed sitemaps,
    exact host validation, optional host rewriting, duplicate removal,
    batches of up to 10,000 URLs, and dry-run mode.

.PARAMETER SitemapUrl
    One or more absolute sitemap or sitemap-index URLs.

.PARAMETER KeyLocation
    Public URL of the hosted IndexNow key file.

.PARAMETER CanonicalHost
    Hostname used in the IndexNow payload and required for submitted URLs.
    Defaults to the hostname in KeyLocation.

.PARAMETER RewriteHostFrom
    Optional exact alternate hostname to rewrite to CanonicalHost. This is
    useful while fixing a sitemap that contains the wrong apex/www variant.

.PARAMETER Endpoint
    IndexNow POST endpoint. Defaults to the global IndexNow endpoint.

.PARAMETER BatchSize
    URLs per request. IndexNow permits no more than 10,000.

.PARAMETER DelaySeconds
    Delay between batches during a live submission.

.PARAMETER TimeoutSeconds
    HTTP timeout for sitemap, key, and API requests.

.PARAMETER MaxSitemaps
    Maximum number of sitemap files followed recursively.

.PARAMETER ShowUrls
    Prints every normalized URL instead of only the first five.

.PARAMETER DryRun
    Validates and displays the planned batches without sending a POST.

.EXAMPLE
    .\Submit-IndexNow.ps1 `
      -SitemapUrl 'https://www.example.com/sitemap.xml' `
      -KeyLocation 'https://www.example.com/your-key.txt' `
      -DryRun

.EXAMPLE
    .\Submit-IndexNow.ps1 `
      -SitemapUrl 'https://example.com/sitemap.xml' `
      -KeyLocation 'https://example.com/your-key.txt'

.EXAMPLE
    .\Submit-IndexNow.ps1 `
      -SitemapUrl 'https://www.example.com/sitemap.xml' `
      -KeyLocation 'https://example.com/your-key.txt' `
      -CanonicalHost 'example.com' `
      -RewriteHostFrom 'www.example.com' `
      -DryRun
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [uri[]]$SitemapUrl,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [uri]$KeyLocation,

    [ValidateNotNullOrEmpty()]
    [string]$CanonicalHost,

    [string]$RewriteHostFrom,

    [ValidateNotNullOrEmpty()]
    [uri]$Endpoint = 'https://api.indexnow.org/indexnow',

    [ValidateRange(1, 10000)]
    [int]$BatchSize = 10000,

    [ValidateRange(0, 300)]
    [int]$DelaySeconds = 1,

    [ValidateRange(1, 600)]
    [int]$TimeoutSeconds = 30,

    [ValidateRange(1, 10000)]
    [int]$MaxSitemaps = 1000,

    [ValidateNotNullOrEmpty()]
    [string]$UserAgent = 'IndexNow-Public-Runner/1.0',

    [switch]$ShowUrls,

    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

try {
    [Net.ServicePointManager]::SecurityProtocol =
        [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
}
catch {
    # PowerShell 7+ normally negotiates TLS without this compatibility setting.
}

function Normalize-HostName {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$HostName
    )

    $value = $HostName.Trim().TrimEnd('.').ToLowerInvariant()

    if ([string]::IsNullOrWhiteSpace($value)) {
        throw 'A hostname cannot be empty.'
    }

    if ($value.Contains('://') -or $value.Contains('/') -or $value.Contains(':')) {
        throw ("Use a hostname without a scheme, path, or port: '{0}'" -f $HostName)
    }

    return $value
}

function Get-RemoteBytes {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [uri]$Uri
    )

    $temporaryFile = [IO.Path]::GetTempFileName()

    try {
        Invoke-WebRequest `
            -Uri $Uri.AbsoluteUri `
            -OutFile $temporaryFile `
            -Headers @{ 'User-Agent' = $UserAgent } `
            -TimeoutSec $TimeoutSeconds `
            -UseBasicParsing `
            -ErrorAction Stop | Out-Null

        return [IO.File]::ReadAllBytes($temporaryFile)
    }
    finally {
        Remove-Item -LiteralPath $temporaryFile -Force -ErrorAction SilentlyContinue
    }
}

function Convert-BytesToText {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [byte[]]$Bytes
    )

    $inputStream = New-Object IO.MemoryStream(, $Bytes)
    $contentStream = $inputStream
    $gzipStream = $null
    $reader = $null

    try {
        if (
            $Bytes.Length -ge 2 -and
            $Bytes[0] -eq 0x1F -and
            $Bytes[1] -eq 0x8B
        ) {
            $gzipStream = New-Object IO.Compression.GZipStream(
                $inputStream,
                [IO.Compression.CompressionMode]::Decompress
            )
            $contentStream = $gzipStream
        }

        $reader = New-Object IO.StreamReader(
            $contentStream,
            [Text.Encoding]::UTF8,
            $true
        )

        return $reader.ReadToEnd()
    }
    finally {
        if ($null -ne $reader) {
            $reader.Dispose()
        }
        elseif ($null -ne $gzipStream) {
            $gzipStream.Dispose()
        }
        else {
            $inputStream.Dispose()
        }
    }
}

function Get-RemoteText {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [uri]$Uri
    )

    return Convert-BytesToText -Bytes (Get-RemoteBytes -Uri $Uri)
}

function Get-SitemapUrls {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [uri]$Uri,

        [Parameter(Mandatory = $true)]
        [hashtable]$Visited
    )

    $visitKey = $Uri.AbsoluteUri.ToLowerInvariant()

    if ($Visited.ContainsKey($visitKey)) {
        return
    }

    if ($Visited.Count -ge $MaxSitemaps) {
        throw ("The sitemap traversal exceeded MaxSitemaps ({0})." -f $MaxSitemaps)
    }

    $Visited[$visitKey] = $true
    Write-Host ("Reading sitemap: {0}" -f $Uri.AbsoluteUri)

    $text = Get-RemoteText -Uri $Uri

    try {
        [xml]$xml = $text
    }
    catch {
        throw ("Could not parse sitemap XML at '{0}'. {1}" -f $Uri.AbsoluteUri, $_.Exception.Message)
    }

    if ($null -eq $xml.DocumentElement) {
        throw ("The sitemap at '{0}' has no XML document element." -f $Uri.AbsoluteUri)
    }

    $rootName = $xml.DocumentElement.LocalName

    if ($rootName -eq 'sitemapindex') {
        $nodes = $xml.SelectNodes(
            "/*[local-name()='sitemapindex']/*[local-name()='sitemap']/*[local-name()='loc']"
        )

        foreach ($node in $nodes) {
            $value = $node.InnerText.Trim()

            if ([string]::IsNullOrWhiteSpace($value)) {
                continue
            }

            try {
                $childUri = [uri]$value
            }
            catch {
                throw ("Invalid child sitemap URL: {0}" -f $value)
            }

            if ($childUri.Scheme -notin @('http', 'https')) {
                throw ("Unsupported child sitemap URL scheme: {0}" -f $value)
            }

            Get-SitemapUrls -Uri $childUri -Visited $Visited
        }

        return
    }

    if ($rootName -eq 'urlset') {
        $nodes = $xml.SelectNodes(
            "/*[local-name()='urlset']/*[local-name()='url']/*[local-name()='loc']"
        )

        foreach ($node in $nodes) {
            $value = $node.InnerText.Trim()

            if (-not [string]::IsNullOrWhiteSpace($value)) {
                $value
            }
        }

        return
    }

    throw (
        "Unsupported sitemap root element '{0}' at '{1}'. Expected urlset or sitemapindex." -f
        $rootName,
        $Uri.AbsoluteUri
    )
}

function Get-IndexNowStatusMeaning {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [int]$StatusCode
    )

    switch ($StatusCode) {
        200 { return 'OK: request received successfully.' }
        202 { return 'Accepted: request received; key validation may still be pending.' }
        400 { return 'Bad Request: invalid request format.' }
        403 { return 'Forbidden: key validation failed.' }
        422 { return 'Unprocessable Entity: URL, host, key, or protocol validation failed.' }
        429 { return 'Too Many Requests: rate limited.' }
        default { return 'Unexpected HTTP response.' }
    }
}

function Invoke-IndexNowBatch {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [string[]]$Urls,

        [Parameter(Mandatory = $true)]
        [string]$HostName,

        [Parameter(Mandatory = $true)]
        [string]$Key,

        [Parameter(Mandatory = $true)]
        [uri]$KeyFileUri,

        [Parameter(Mandatory = $true)]
        [uri]$ApiEndpoint,

        [Parameter(Mandatory = $true)]
        [int]$BatchNumber,

        [switch]$WhatIfOnly
    )

    if ($Urls.Count -eq 0) {
        throw 'Refusing to submit an empty IndexNow batch.'
    }

    $payload = [ordered]@{
        host        = $HostName
        key         = $Key
        keyLocation = $KeyFileUri.AbsoluteUri
        urlList     = @($Urls)
    }

    $json = $payload | ConvertTo-Json -Depth 4 -Compress

    if ($WhatIfOnly) {
        Write-Host (
            "[Dry run] Batch {0} would submit {1} URL(s) to {2}" -f
            $BatchNumber,
            $Urls.Count,
            $ApiEndpoint.AbsoluteUri
        )

        return [pscustomobject]@{
            Batch      = $BatchNumber
            UrlCount   = $Urls.Count
            StatusCode = $null
            Status     = 'Dry run'
        }
    }

    try {
        $response = Invoke-WebRequest `
            -Uri $ApiEndpoint.AbsoluteUri `
            -Method Post `
            -ContentType 'application/json; charset=utf-8' `
            -Body ([Text.Encoding]::UTF8.GetBytes($json)) `
            -Headers @{ 'User-Agent' = $UserAgent } `
            -TimeoutSec $TimeoutSeconds `
            -UseBasicParsing `
            -ErrorAction Stop

        $statusCode = [int]$response.StatusCode
        $meaning = Get-IndexNowStatusMeaning -StatusCode $statusCode

        Write-Host (
            "Batch {0}: HTTP {1} - {2}" -f
            $BatchNumber,
            $statusCode,
            $meaning
        )

        return [pscustomobject]@{
            Batch      = $BatchNumber
            UrlCount   = $Urls.Count
            StatusCode = $statusCode
            Status     = $meaning
        }
    }
    catch {
        $statusCode = 0
        $details = $_.Exception.Message

        if ($null -ne $_.Exception.Response) {
            try {
                $statusCode = [int]$_.Exception.Response.StatusCode
            }
            catch {
                $statusCode = 0
            }
        }

        if (
            $null -ne $_.ErrorDetails -and
            -not [string]::IsNullOrWhiteSpace($_.ErrorDetails.Message)
        ) {
            $details = $_.ErrorDetails.Message
        }

        $meaning = if ($statusCode -gt 0) {
            Get-IndexNowStatusMeaning -StatusCode $statusCode
        }
        else {
            'No valid HTTP response was received.'
        }

        throw (
            "Batch {0} failed. HTTP {1} - {2} Details: {3}" -f
            $BatchNumber,
            $statusCode,
            $meaning,
            $details
        )
    }
}

foreach ($uriToCheck in @($SitemapUrl) + @($KeyLocation, $Endpoint)) {
    if ($uriToCheck.Scheme -notin @('http', 'https')) {
        throw ("Only HTTP and HTTPS URLs are supported: {0}" -f $uriToCheck.AbsoluteUri)
    }
}

if ([string]::IsNullOrWhiteSpace($CanonicalHost)) {
    $CanonicalHost = $KeyLocation.Host
}

$CanonicalHost = Normalize-HostName -HostName $CanonicalHost

if (-not [string]::IsNullOrWhiteSpace($RewriteHostFrom)) {
    $RewriteHostFrom = Normalize-HostName -HostName $RewriteHostFrom

    if ($RewriteHostFrom -eq $CanonicalHost) {
        throw 'RewriteHostFrom must be different from CanonicalHost.'
    }
}

$keyHost = Normalize-HostName -HostName $KeyLocation.Host

if ($keyHost -ne $CanonicalHost) {
    throw (
        "The key file host '{0}' does not match CanonicalHost '{1}'." -f
        $keyHost,
        $CanonicalHost
    )
}

Write-Host ''
Write-Host 'IndexNow Public Runner 1.0'
Write-Host '=========================='
Write-Host ("Canonical host: {0}" -f $CanonicalHost)
Write-Host ("Key file:      {0}" -f $KeyLocation.AbsoluteUri)
Write-Host ("Endpoint:      {0}" -f $Endpoint.AbsoluteUri)
Write-Host ("Sitemaps:      {0}" -f $SitemapUrl.Count)

if (-not [string]::IsNullOrWhiteSpace($RewriteHostFrom)) {
    Write-Host ("Host rewrite:  {0} -> {1}" -f $RewriteHostFrom, $CanonicalHost)
}
else {
    Write-Host 'Host rewrite:  disabled'
}

Write-Host ("Mode:          {0}" -f $(if ($DryRun) { 'DRY RUN' } else { 'LIVE SUBMISSION' }))
Write-Host ''

Write-Host ("Checking hosted IndexNow key: {0}" -f $KeyLocation.AbsoluteUri)
$key = (Get-RemoteText -Uri $KeyLocation).Trim().TrimStart([char]0xFEFF)

if ($key -notmatch '^[A-Za-z0-9-]{8,128}$') {
    throw 'The hosted key must be 8-128 letters, numbers, or hyphens.'
}

$keyDirectory = [IO.Path]::GetDirectoryName($KeyLocation.AbsolutePath)

if ([string]::IsNullOrWhiteSpace($keyDirectory)) {
    $keyDirectory = '/'
}

$keyDirectory = $keyDirectory.Replace('\', '/')

if (-not $keyDirectory.EndsWith('/')) {
    $keyDirectory += '/'
}

$visited = @{}
$rawUrls = New-Object 'System.Collections.Generic.List[string]'

foreach ($sitemap in $SitemapUrl) {
    foreach ($value in @(Get-SitemapUrls -Uri $sitemap -Visited $visited)) {
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            $rawUrls.Add($value)
        }
    }
}

if ($rawUrls.Count -eq 0) {
    throw 'No page URLs were found in the supplied sitemap files.'
}

$normalizedUrls = New-Object 'System.Collections.Generic.List[string]'
$invalidUrls = New-Object 'System.Collections.Generic.List[string]'
$rewrittenCount = 0

foreach ($rawUrl in $rawUrls) {
    try {
        $pageUri = [uri]$rawUrl
    }
    catch {
        $invalidUrls.Add($rawUrl)
        continue
    }

    if ($pageUri.Scheme -notin @('http', 'https')) {
        $invalidUrls.Add($rawUrl)
        continue
    }

    if (-not [string]::IsNullOrWhiteSpace($pageUri.Fragment)) {
        $invalidUrls.Add($rawUrl)
        continue
    }

    $pageHost = Normalize-HostName -HostName $pageUri.Host

    if ($pageHost -eq $CanonicalHost) {
        $canonicalUri = $pageUri
    }
    elseif (
        -not [string]::IsNullOrWhiteSpace($RewriteHostFrom) -and
        $pageHost -eq $RewriteHostFrom
    ) {
        $builder = New-Object System.UriBuilder($pageUri)
        $builder.Host = $CanonicalHost
        $canonicalUri = $builder.Uri
        $rewrittenCount++
    }
    else {
        $invalidUrls.Add($rawUrl)
        continue
    }

    if (
        $keyDirectory -ne '/' -and
        -not $canonicalUri.AbsolutePath.StartsWith(
            $keyDirectory,
            [StringComparison]::OrdinalIgnoreCase
        )
    ) {
        $invalidUrls.Add($rawUrl)
        continue
    }

    $normalizedUrls.Add($canonicalUri.AbsoluteUri)
}

if ($invalidUrls.Count -gt 0) {
    $examples = ($invalidUrls | Select-Object -First 5) -join "`n  "

    throw (
        "Found {0} invalid, out-of-scope, or non-canonical URL(s). " +
        "Expected host '{1}'. Examples:`n  {2}" -f
        $invalidUrls.Count,
        $CanonicalHost,
        $examples
    )
}

$uniqueUrls = @($normalizedUrls | Sort-Object -Unique)

Write-Host (
    "Found {0} sitemap URL(s); {1} unique canonical URL(s) are ready." -f
    $rawUrls.Count,
    $uniqueUrls.Count
)

if ($rewrittenCount -gt 0) {
    Write-Warning (
        "Rewrote {0} URL(s) from '{1}' to '{2}'. Fix the sitemap when practical." -f
        $rewrittenCount,
        $RewriteHostFrom,
        $CanonicalHost
    )
}

Write-Host ''
Write-Host $(if ($ShowUrls) { 'Canonical URLs:' } else { 'First canonical URLs:' })

$urlsToShow = if ($ShowUrls) { $uniqueUrls } else { @($uniqueUrls | Select-Object -First 5) }
$urlsToShow | ForEach-Object { Write-Host ("  {0}" -f $_) }
Write-Host ''

$results = @()
$batchNumber = 0

for ($offset = 0; $offset -lt $uniqueUrls.Count; $offset += $BatchSize) {
    $batchNumber++
    $lastIndex = [Math]::Min($offset + $BatchSize - 1, $uniqueUrls.Count - 1)
    $batch = @($uniqueUrls[$offset..$lastIndex])

    $result = Invoke-IndexNowBatch `
        -Urls $batch `
        -HostName $CanonicalHost `
        -Key $key `
        -KeyFileUri $KeyLocation `
        -ApiEndpoint $Endpoint `
        -BatchNumber $batchNumber `
        -WhatIfOnly:$DryRun

    $results += $result

    if (
        -not $DryRun -and
        $DelaySeconds -gt 0 -and
        $lastIndex -lt ($uniqueUrls.Count - 1)
    ) {
        Start-Sleep -Seconds $DelaySeconds
    }
}

Write-Host ''
Write-Host (
    "Completed {0} batch(es), covering {1} unique canonical URL(s)." -f
    $batchNumber,
    $uniqueUrls.Count
)

$results
