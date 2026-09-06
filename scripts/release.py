"""Publish only complete, tested six-architecture/version release sets."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile

tag = os.environ["UPSTREAM_TAG"]
sha = os.environ["UPSTREAM_SHA"]
repo = os.environ["GITHUB_REPOSITORY"]
expected = {f"{tag}-pg{pg}-windows-{arch}.zip" for pg in
            ("9.4.26", "9.5.25", "9.6.24") for arch in ("x86", "x64")}
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

Six tested packages: PostgreSQL 9.4.26 / 9.5.25 / 9.6.24, each x86 and x64.
Each ZIP contains wal2json.dll, upstream source/license, manifest and native LOAD + INSERT/UPDATE/DELETE smoke-test output.
Match PostgreSQL major version AND architecture. Older patch levels require their own validation.
These PostgreSQL versions are end-of-life; this release does not make them secure or supported.
DLLs are not Authenticode-signed. Verify SHA256SUMS. No PostgreSQL server binaries or user data are redistributed.
""", encoding="utf-8")
existing = subprocess.run(["gh", "release", "view", tag, "--repo", repo, "--json", "isDraft"], capture_output=True, text=True)
if existing.returncode == 0:
    if not json.loads(existing.stdout)["isDraft"]:
        raise SystemExit("Refusing to overwrite a published release")
else:
    subprocess.run(["gh", "release", "create", tag, "--repo", repo, "--target", os.environ["GITHUB_SHA"], "--draft", "--title", tag + " — Windows PG 9.4–9.6", "--notes-file", str(notes)], check=True)
subprocess.run(["gh", "release", "upload", tag, "--repo", repo, "--clobber", *map(str, files), str(checksums)], check=True)
subprocess.run(["gh", "release", "edit", tag, "--repo", repo, "--draft=false", "--latest=false", "--notes-file", str(notes)], check=True)
