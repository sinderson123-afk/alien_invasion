# Uses the current gcloud login. Store the output outside the repository.
param([Parameter(Mandatory=$true)][string]$OutputPath)
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $OutputPath) { throw 'Refusing to overwrite an export' }
$token = gcloud auth print-access-token
if ($LASTEXITCODE) { throw 'gcloud authentication failed' }
$headers = @{Authorization="Bearer $token"}
$root = 'https://firestore.googleapis.com/v1/projects/my-server-502313/databases/(default)/documents'
function Convert-FirestoreValue($value) {
    switch ($value.Keys | Select-Object -First 1) {
        'stringValue' { return $value.stringValue }
        'integerValue' { return [long]$value.integerValue }
        'doubleValue' { return [double]$value.doubleValue }
        'booleanValue' { return [bool]$value.booleanValue }
        'nullValue' { return $null }
        'timestampValue' {
            if ($value.timestampValue -is [datetime]) { return $value.timestampValue.ToUniversalTime().ToString('o') }
            return [string]$value.timestampValue
        }
        'arrayValue' {
            $items = @($value.arrayValue.values | ForEach-Object { Convert-FirestoreValue $_ })
            return ,$items
        }
        'mapValue' {
            $map = @{}
            foreach ($key in $value.mapValue.fields.Keys) { $map[$key] = Convert-FirestoreValue $value.mapValue.fields[$key] }
            return $map
        }
        default { throw 'Unsupported Firestore value type' }
    }
}
function Get-CollectionIds($uri) {
    $ids = @()
    $page = ''
    do {
        $body = @{pageSize=1000;pageToken=$page} | ConvertTo-Json
        $response = Invoke-RestMethod -Method Post -Uri "${uri}:listCollectionIds" -Headers $headers -ContentType 'application/json' -Body $body
        if ($response.collectionIds) { $ids += $response.collectionIds }
        $page = $response.nextPageToken
    } while ($page)
    return $ids
}
$names = Get-CollectionIds $root
$collections = @{}
foreach ($name in $names) {
    if ($name -notin @('users','codes','leaderboard')) { throw "Unexpected collection: $name" }
    $documents = @{}
    $page = ''
    do {
        $uri = "$root/${name}?pageSize=1000"
        if ($page) { $uri += '&pageToken=' + [uri]::EscapeDataString($page) }
        $response = Invoke-WebRequest -Uri $uri -Headers $headers
        $result = $response.Content | ConvertFrom-Json -AsHashtable
        foreach ($document in $result.documents) {
            $children = @(Get-CollectionIds ('https://firestore.googleapis.com/v1/' + $document.name))
            if ($children.Count) { throw 'Subcollections found; refusing incomplete export' }
            $fields = @{}
            foreach ($key in $document.fields.Keys) { $fields[$key] = Convert-FirestoreValue $document.fields[$key] }
            $documents[($document.name -split '/')[-1]] = $fields
        }
        $page = $result.nextPageToken
    } while ($page)
    $collections[$name] = $documents
}
@{version=1;collections=$collections} | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $OutputPath -Encoding utf8NoBOM
$collections.Keys | ForEach-Object { [PSCustomObject]@{Collection=$_;Count=$collections[$_].Count} }
