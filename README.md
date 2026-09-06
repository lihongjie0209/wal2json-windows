# wal2json Windows packages

Unofficial, independently maintained packaging of [eulerto/wal2json](https://github.com/eulerto/wal2json) for **PostgreSQL 9.4, 9.5 and 9.6**, Windows **x86 and x64** only. Not affiliated with PostgreSQL, EDB or the wal2json maintainers.

## Downloads and compatibility

Each successful upstream tag gets a matching GitHub Release with six ZIPs:

| PostgreSQL family | Build/test baseline | Targets |
| --- | --- | --- |
| 9.4 | 9.4.26 | x86, x64 |
| 9.5 | 9.5.25 | x86, x64 |
| 9.6 | 9.6.24 | x86, x64 |

Choose the **server's** architecture, not the operating system's. A DLL is not portable across PG major versions or architectures. Older patch versions and different distributions need independent validation. Windows Server 2022 smoke tests do not certify all historical Windows operating systems. These PostgreSQL releases are **end-of-life** and have security risks; prefer upgrading where possible.

ZIPs contain only the plugin DLL, upstream source/license, metadata and test evidence, not PostgreSQL binaries or databases. DLLs are unsigned; verify release SHA256SUMS. Version-specific PostgreSQL dependencies are downloaded from EDB over HTTPS in CI. Their observed SHA256 hashes are recorded in manifests for traceability; these are not publisher signatures or independently authenticated dependency checksums.

## Installation

1. Back up configuration. Check `SELECT version()` and `pg_config --pkglibdir` on the server.
2. Copy `wal2json.dll` from the matching ZIP into the server's package library directory. Do not overwrite an active plugin DLL.
3. With a privileged database session, run `LOAD 'wal2json';`.
4. Enable `wal_level = logical`, set `max_replication_slots` and `max_wal_senders` to suit your workload, then restart PostgreSQL if startup settings changed. Do not blindly reduce existing values.
5. Use a dedicated logical slot and monitor retained WAL/disk space. Drop test slots after testing.

No `CREATE EXTENSION wal2json` is needed. The plugin converts WAL changes to JSON; HTTP delivery, durable checkpoints and at-least-once semantics belong to the consumer. Older wal2json tags do not support all newer output options.

## Release automation

`Package upstream tags` runs daily or via manual dispatch (`tag`: an upstream tag or `all`). It discovers unpublished upstream tags, resolves each to a commit, and builds all six combinations. Each combination must compile and pass native `LOAD`, slot creation, INSERT/UPDATE/DELETE JSON assertions and slot cleanup. Publication occurs only after all six succeed. Unsupported future upstream tags fail closed rather than publishing partial releases. Published releases are not overwritten. Failed draft uploads can be retried.

Repository release tags point to the **packaging commit**; the exact **upstream commit** is separately recorded in every manifest and release. Runtime dependencies/toolchain details and DLL hashes are recorded. This is traceable packaging, not a claim of bit-for-bit reproducible builds.

Windows smoke tests run directly on an ephemeral Windows runner because a Linux PostgreSQL container cannot load a Windows DLL. They use a fresh synthetic database, loopback-only access and finally cleanup. This repository does not change the Go collector's Testcontainers-based integration tests.

## Local build

Requires Windows, PowerShell 7, Visual Studio 2022 C++ tools, Git and 7-Zip on PATH:

```powershell
./scripts/build.ps1 -Tag wal2json_2_6 -Commit <40-character-upstream-commit> -PgVersion 9.5.25 -Arch x86
```

Port 55495 must be free. Packages appear in `dist`. PostgreSQL archives are build/test inputs only and are not redistributed.

## License

Packaging scripts: MIT (`LICENSE`). wal2json retains its upstream license, included in each binary package as `LICENSE.wal2json`.
