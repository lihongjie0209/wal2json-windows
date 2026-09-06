param(
    [Parameter(Mandatory)][ValidatePattern('^wal2json_\d+_\d+(_\d+)?$')][string]$Tag,
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$Commit,
    [Parameter(Mandatory)][ValidateSet('9.4.26','9.5.2','9.5.25','9.6.24')][string]$PgVersion,
    [Parameter(Mandatory)][ValidateSet('x86','x64')][string]$Arch
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = Split-Path $PSScriptRoot -Parent
$work = Join-Path $root ('work/' + [guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $work
$dist = Join-Path $root 'dist'
$null = New-Item -ItemType Directory -Path $dist -Force
$data = Join-Path $work 'data'
$pg = Join-Path $work 'pgsql'
$started = $false
function Check([string]$What) { if ($LASTEXITCODE -ne 0) { throw "$What failed (exit $LASTEXITCODE)" } }
function Sql([string]$Statement) {
    $result = & "$pg/bin/psql.exe" -X -h 127.0.0.1 -p 55495 -U postgres -d postgres -w -A -t -v ON_ERROR_STOP=1 -c $Statement
    Check 'SQL'
    return $result
}
try {
    $platform = if ($Arch -eq 'x86') { 'windows' } else { 'windows-x64' }
    $dep = @{ url = "https://get.enterprisedb.com/postgresql/postgresql-$PgVersion-1-$platform-binaries.zip" }
    $archive = Join-Path $work 'postgres.zip'
    & curl.exe --fail --location --retry 4 --output $archive $dep.url
    Check 'PostgreSQL download'
    $dep.sha256 = (Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    Write-Output "PostgreSQL dependency SHA256: $($dep.sha256)"
    & 7z.exe x $archive "-o$work" -y | Out-Null
    Check 'PostgreSQL extraction'
    & git clone --quiet --no-checkout https://github.com/eulerto/wal2json.git (Join-Path $work 'source')
    Check 'Source clone'
    $source = Join-Path $work 'source'
    $resolved = & git -C $source rev-parse "refs/tags/$Tag^{commit}"
    Check 'Tag resolution'
    if ($resolved -ne $Commit) { throw 'Upstream tag moved after discovery' }
    & git -C $source checkout --quiet --detach $Commit
    Check 'Source checkout'
    $vswhere = "${env:ProgramFiles(x86)}/Microsoft Visual Studio/Installer/vswhere.exe"
    $vs = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if (-not $vs) { throw 'MSVC C++ tools not installed' }
    Import-Module (Join-Path $vs 'Common7/Tools/Microsoft.VisualStudio.DevShell.dll')
    Enter-VsDevShell -VsInstallPath $vs -SkipAutomaticLocation -DevCmdArguments "-arch=$Arch -host_arch=x64"
    Push-Location $work
    try {
        & cl.exe /nologo /LD /O2 /MT /DWIN32 /D_WINDOWS /D__WINDOWS__ /D__WIN32__ /DWIN32_STACK_RLIMIT=4194304 /D_CRT_SECURE_NO_WARNINGS /D_CRT_NONSTDC_NO_DEPRECATE "/I$pg/include/server/port/win32_msvc" "/I$pg/include/server/port/win32" "/I$pg/include/server" "/I$pg/include" "$source/wal2json.c" /link "/LIBPATH:$pg/lib" postgres.lib /OUT:wal2json.dll "/MACHINE:$Arch"
        Check 'DLL compilation'
    } finally { Pop-Location }
    Copy-Item "$work/wal2json.dll" "$pg/lib/wal2json.dll"
    & "$pg/bin/initdb.exe" -D $data -U postgres -A trust --encoding=UTF8 --locale=C
    Check 'initdb'
    & "$pg/bin/pg_ctl.exe" -D $data -l "$work/server.log" -o '-h 127.0.0.1 -p 55495 -c wal_level=logical -c max_replication_slots=2 -c max_wal_senders=2' -w start
    Check 'PostgreSQL start'
    $started = $true
    $version = Sql 'SELECT version()'
    $version | Write-Output
    if ($version -notmatch [regex]::Escape("PostgreSQL $PgVersion,")) { throw 'Unexpected server version' }
    $bits = if ($Arch -eq 'x86') { '32-bit' } else { '64-bit' }
    if ($version -notmatch $bits) { throw 'Unexpected server architecture' }
    Sql "LOAD 'wal2json'"
    Sql "SELECT * FROM pg_create_logical_replication_slot('smoke', 'wal2json')"
    Sql 'CREATE TABLE probe (id integer PRIMARY KEY, value text);'
    Sql "INSERT INTO probe VALUES (1, 'before')"
    Sql "UPDATE probe SET value = 'after' WHERE id = 1"
    Sql 'DELETE FROM probe WHERE id = 1'
    $json = @(Sql "SELECT data FROM pg_logical_slot_get_changes('smoke', NULL, NULL, 'include-lsn', 'true')")
    foreach ($line in $json) {
        $txn = $line | ConvertFrom-Json
        if (-not $txn.nextlsn -or $txn.nextlsn -eq '0/0') { throw 'Invalid transaction end LSN' }
    }
    $changes = @($json | ForEach-Object { ($_ | ConvertFrom-Json).change } | Where-Object { $_.table -eq 'probe' })
    if ($changes.Count -ne 3 -or ($changes.kind -join ',') -ne 'insert,update,delete') { throw 'Incorrect decoded changes' }
    if ($changes[0].columnvalues[1] -ne 'before' -or $changes[1].columnvalues[1] -ne 'after' -or $changes[2].oldkeys.keyvalues[0] -ne 1) { throw 'Incorrect decoded values' }
    $tagParts = $Tag.Split('_')
    if ([int]$tagParts[1] -gt 2 -or ([int]$tagParts[1] -eq 2 -and [int]$tagParts[2] -ge 6)) {
        Sql "INSERT INTO probe VALUES (2, 'format2')"
        $format2 = @(Sql "SELECT data FROM pg_logical_slot_get_changes('smoke', NULL, NULL, 'format-version', '2', 'include-lsn', 'true')")
        $records = @($format2 | ForEach-Object { $_ | ConvertFrom-Json })
        if (($records.action -join ',') -ne 'B,I,C') { throw 'Incorrect format 2 boundaries' }
        $begin = $records[0]; $end = $records[2]
        if (-not $end.nextlsn -or $end.nextlsn -eq '0/0' -or $begin.nextlsn -ne $end.nextlsn -or $begin.lsn -ne $end.lsn) { throw 'Incorrect format 2 transaction LSNs' }
        $valid = Sql "SELECT '$($end.nextlsn)'::pg_lsn > '$($end.lsn)'::pg_lsn"
        if ($valid -ne 't') { throw 'Transaction end must follow commit LSN' }
        $json += $format2
    }
    Sql "SELECT pg_drop_replication_slot('smoke')"
    $package = Join-Path $work 'package'
    $null = New-Item -ItemType Directory -Path $package
    Copy-Item "$work/wal2json.dll" $package
    Copy-Item "$source/wal2json.c" $package
    Copy-Item "$source/LICENSE" (Join-Path $package 'LICENSE.wal2json')
    Copy-Item (Join-Path $root 'README.md') $package
    $json | Set-Content (Join-Path $package 'smoke-test.jsonl') -Encoding utf8
    $dependencies = & dumpbin.exe /dependents "$work/wal2json.dll"
    Check 'DLL dependency inspection'
    $dependencies | Set-Content (Join-Path $package 'dependencies.txt')
    $manifest = [ordered]@{
        upstream_tag = $Tag; upstream_commit = $Commit; postgresql_version = $PgVersion
        architecture = $Arch; postgres_url = $dep.url; postgres_sha256 = $dep.sha256
        dll_sha256 = (Get-FileHash "$work/wal2json.dll" -Algorithm SHA256).Hash.ToLowerInvariant()
        packaging_commit = $env:GITHUB_SHA; runner_image = $env:ImageVersion
        compiler = (Get-Item (Get-Command cl.exe).Source).VersionInfo.FileVersion
        runtime_linkage = 'static /MT'; smoke_test = 'passed'; server_version = "$version"
    }
    $manifest | ConvertTo-Json | Set-Content (Join-Path $package 'manifest.json') -Encoding utf8
    Compress-Archive -Path "$package/*" -DestinationPath (Join-Path $dist "$Tag-pg$PgVersion-windows-$Arch.zip")
} finally {
    $safe = $true
    if ($started -or (Test-Path "$data/postmaster.pid")) {
        & "$pg/bin/pg_ctl.exe" -D $data -m fast -w stop
        if ($LASTEXITCODE -ne 0) { $safe = $false }
    }
    if (-not $safe) { throw "Failed to stop temporary PostgreSQL; retained $work" }
    Remove-Item -LiteralPath $work -Recurse -Force
}
