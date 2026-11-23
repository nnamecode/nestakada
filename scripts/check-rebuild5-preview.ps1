[CmdletBinding()]
param(
    [string]$BaseUrl = 'http://127.0.0.1:18085',
    [string]$RouteMap = (Join-Path $PSScriptRoot '..\docs\analytics-route-map.csv'),
    [ValidateSet('All', 'Services')]
    [string]$Scope = 'All'
)

$ErrorActionPreference = 'Stop'
$rows = @(Import-Csv -LiteralPath $RouteMap)
$expectedIds = @(1..115 | ForEach-Object { 'MAP-{0:D3}' -f $_ })
$actualIds = @($rows.map_id | Sort-Object)
$targets = @($rows.requested_path)
if (
    $rows.Count -ne 115 -or
    (Compare-Object $expectedIds $actualIds) -or
    @($targets | Sort-Object -Unique).Count -ne 115 -or
    @($rows | Where-Object { $_.requested_path -notmatch '^/' }).Count
) {
    throw 'RB5_ACCEPTANCE_ROUTE_AUTHORITY_INVALID'
}
$selectedRows = $rows
if ($Scope -ceq 'Services') {
    $serviceTypes = @(
        'services_master_catalog',
        'service_catalog',
        'service_section_overview',
        'service_detail',
        'service_wash_legacy_alias'
    )
    $selectedRows = @($rows | Where-Object { $_.proposed_type -in $serviceTypes })
    if ($selectedRows.Count -ne 62) {
        throw 'RB5_ACCEPTANCE_SERVICE_AUTHORITY_INVALID'
    }
}

$handler = [Net.Http.HttpClientHandler]::new()
$handler.AllowAutoRedirect = $false
$client = [Net.Http.HttpClient]::new($handler)
$client.Timeout = [TimeSpan]::FromSeconds(10)
$origin = [Uri]::new($BaseUrl.TrimEnd('/') + '/')
$results = [Collections.Generic.List[object]]::new()

function Get-HeaderValue([Net.Http.HttpResponseMessage]$Response, [string]$Name) {
    $values = $null
    if ($Response.Headers.TryGetValues($Name, [ref]$values)) {
        return ($values -join ', ')
    }
    if ($Response.Content.Headers.TryGetValues($Name, [ref]$values)) {
        return ($values -join ', ')
    }
    return $null
}

function Assert-Response(
    [string]$Method,
    [pscustomobject]$Row
) {
    $response = $null
    $request = [Net.Http.HttpRequestMessage]::new(
        [Net.Http.HttpMethod]::new($Method),
        [Uri]::new($origin, $Row.requested_path.TrimStart('/'))
    )
    try {
        $response = $client.SendAsync($request).GetAwaiter().GetResult()
        $body = $response.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult()
        $status = [int]$response.StatusCode
        $isPageOneRedirect = $Row.requested_path -ceq '/gallery-of-works/?page=1'
        $expectedStatus = if ($isPageOneRedirect) { 302 } else { 200 }
        if ($status -ne $expectedStatus) {
            throw "RB5_ACCEPTANCE_STATUS:$($Row.map_id):${Method}:$status"
        }
        if ($Method -ceq 'HEAD' -and $body.Length -ne 0) {
            throw "RB5_ACCEPTANCE_HEAD_BODY:$($Row.map_id)"
        }
        if (Get-HeaderValue $response 'Set-Cookie') {
            throw "RB5_ACCEPTANCE_COOKIE:$($Row.map_id):$Method"
        }
        $vary = Get-HeaderValue $response 'Vary'
        if ($vary -and $vary -match '(?i)(?:^|,)\s*Cookie\s*(?:,|$)') {
            throw "RB5_ACCEPTANCE_VARY_COOKIE:$($Row.map_id):$Method"
        }
        if ($isPageOneRedirect) {
            $location = $response.Headers.Location
            if ($null -eq $location -or $location.OriginalString -cne '/gallery-of-works/') {
                throw "RB5_ACCEPTANCE_REDIRECT:$($Row.map_id):$Method"
            }
            return [pscustomobject]@{ map = $Row.map_id; method = $Method; status = $status; bytes = $body.Length }
        }
        $cache = Get-HeaderValue $response 'Cache-Control'
        $cacheDirectives = @(($cache -split ',') | ForEach-Object { $_.Trim().ToLowerInvariant() } | Sort-Object)
        if (($cacheDirectives -join ',') -cne 'max-age=0,must-revalidate,public') {
            throw "RB5_ACCEPTANCE_CACHE:$($Row.map_id):$Method"
        }
        if ($Method -ceq 'GET') {
            if ($body.Length -eq 0) {
                throw "RB5_ACCEPTANCE_EMPTY_HTML:$($Row.map_id)"
            }
            $html = [Text.Encoding]::UTF8.GetString($body)
            $canonical = [regex]::Match($html, '<link rel="canonical" href="([^"]+)">').Groups[1].Value
            $expectedCanonical = if ($Row.map_id -ceq 'MAP-018') {
                '/gallery-of-works/'
            } elseif ($Row.map_id -ceq 'MAP-088') {
                '/services/avtomojka'
            } else {
                $Row.requested_path
            }
            if ($canonical -cne $expectedCanonical) {
                throw "RB5_ACCEPTANCE_CANONICAL:$($Row.map_id):$canonical"
            }
            if (
                $html -match '(?i)<iframe\b' -or
                $html -match '(?i)\s(?:src|poster)=["'']https?://' -or
                $html -match '(?i)<link\b[^>]*\shref=["'']https?://'
            ) {
                throw "RB5_ACCEPTANCE_EXTERNAL_RESOURCE:$($Row.map_id)"
            }
        }
        return [pscustomobject]@{ map = $Row.map_id; method = $Method; status = $status; bytes = $body.Length }
    }
    finally {
        if ($null -ne $response) { $response.Dispose() }
        $request.Dispose()
    }
}

try {
    foreach ($row in $selectedRows) {
        $results.Add((Assert-Response -Method 'GET' -Row $row))
        $results.Add((Assert-Response -Method 'HEAD' -Row $row))
    }
}
finally {
    $client.Dispose()
    $handler.Dispose()
}

[pscustomobject]@{
    schema = 'estakada.rb5-public-acceptance-v1'
    scope = $Scope
    routes = $selectedRows.Count
    pages = if ($Scope -ceq 'Services') { 61 } else { $null }
    requests = $results.Count
    get200 = @($results | Where-Object { $_.method -ceq 'GET' -and $_.status -eq 200 }).Count
    head200 = @($results | Where-Object { $_.method -ceq 'HEAD' -and $_.status -eq 200 }).Count
    redirects = @($results | Where-Object { $_.status -ge 300 -and $_.status -lt 400 }).Count
} | ConvertTo-Json -Compress
