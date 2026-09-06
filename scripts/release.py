"""Publish tested release sets; existing public assets are never overwritten."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile
from targets import TARGETS

tag = os.environ["UPSTREAM_TAG"]
sha = os.environ["UPSTREAM_SHA"]
repo = os.environ["GITHUB_REPOSITORY"]
expected = {f"{tag}-pg{t['pg']}-windows-{t['arch']}.zip" for t in TARGETS}
files = sorted(Path("dist").glob("*.zip"))
assert {p.name for p in files} == expected, "Incomplete release"
for path in files:
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["upstream_commit"] == sha
        assert manifest["upstream_tag"] == tag
        assert manifest["smoke_test"] == "passed"
checksums = Path("dist/SHA256SUMS")
checksums.write_text("".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in files))
notes = Path("dist/RELEASE.md")
notes.write_text(f"""Unofficial Windows builds of [eulerto/wal2json {tag}](https://github.com/eulerto/wal2json/tree/{sha}).

Upstream commit: `{sha}`. Packaging commit: `{os.environ['GITHUB_SHA']}`.

156 tested packages: every PostgreSQL 9.4.0–9.4.26 / 9.5.0–9.5.25 / 9.6.0–9.6.24 patch version, each x86 and x64.
Each ZIP contains wal2json.dll, upstream source/license, manifest and native LOAD + INSERT/UPDATE/DELETE smoke-test output.
Match the exact tested PostgreSQL patch version AND architecture. 9.5.25 DLLs are NOT compatible with 9.5.2 transaction LSN layout; use the dedicated 9.5.2 package.
These PostgreSQL versions are end-of-life; this release does not make them secure or supported.
DLLs are not Authenticode-signed. Verify SHA256SUMS. No PostgreSQL server binaries or user data are redistributed.
""", encoding="utf-8")
existing = subprocess.run(["gh", "release", "view", tag, "--repo", repo, "--json", "isDraft,assets"], capture_output=True, text=True)
public_names = set()
if existing.returncode == 0:
    if not json.loads(existing.stdout)["isDraft"]:
        public_names = {a['name'] for a in json.loads(existing.stdout)['assets']}
        if expected.issubset(public_names):
            raise SystemExit("Release already complete; refusing to overwrite it")
else:
    subprocess.run(["gh", "release", "create", tag, "--repo", repo, "--target", os.environ["GITHUB_SHA"], "--draft", "--title", tag + " — Windows PG 9.4–9.6", "--notes-file", str(notes)], check=True)
upload = [str(p) for p in files if p.name not in public_names]
if public_names:
    # Preserve existing checksums too; additions have a separate checksum file.
    checksums = Path('dist/SHA256SUMS-additions-' + os.environ['GITHUB_RUN_ID'])
    checksums.write_text(''.join(f'{hashlib.sha256(Path(p).read_bytes()).hexdigest()}  {Path(p).name}\n' for p in upload))
subprocess.run(["gh", "release", "upload", tag, "--repo", repo, "--clobber", *upload, str(checksums)], check=True)
subprocess.run(["gh", "release", "edit", tag, "--repo", repo, "--draft=false", "--latest=false", "--notes-file", str(notes)], check=True)
