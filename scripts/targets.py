"""Every stable PostgreSQL 9.4–9.6 patch release, both Windows architectures."""
import json
import os

VERSIONS = [f"9.{minor}.{patch}" for minor, last in ((4, 26), (5, 25), (6, 24))
            for patch in range(last + 1)]
TARGETS = [{"pg": version, "arch": arch} for version in VERSIONS for arch in ("x86", "x64")]

if __name__ == "__main__":
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        output.write("matrix=" + json.dumps({"include": TARGETS}) + "\n")
