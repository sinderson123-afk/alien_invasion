# Deploy this checkout over SSH without copying local secrets or databases.
$ErrorActionPreference = 'Stop'
$webRoot = Split-Path $PSScriptRoot -Parent
$archive = Join-Path ([IO.Path]::GetTempPath()) ('alien-web-' + [guid]::NewGuid().ToString('N') + '.tar.gz')
try {
    tar -czf $archive -C $webRoot server.py storage.py requirements.txt backup.py migrate_firestore.py index.html version.json static deploy DEPLOYMENT.md
    if ($LASTEXITCODE) { throw 'Archive failed' }
    scp -q $archive la-vps:/opt/alien-invasion/update.tar.gz
    if ($LASTEXITCODE) { throw 'Upload failed' }
    ssh la-vps 'set -eu; systemctl start alien-invasion-backup.service; tar -xzf /opt/alien-invasion/update.tar.gz -C /opt/alien-invasion/web --no-same-owner --no-same-permissions; sh /opt/alien-invasion/web/deploy/install.sh; sleep 2; curl -fsS http://127.0.0.1:8080/health'
    if ($LASTEXITCODE) { throw 'Deployment failed; inspect journalctl -u alien-invasion' }
} finally {
    if (Test-Path -LiteralPath $archive) { Remove-Item -LiteralPath $archive }
}
