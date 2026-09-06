"""Every stable PostgreSQL 9.4–9.6 patch release, both Windows architectures."""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time
import urllib.error
import urllib.request

VERSIONS = [f"9.{minor}.{patch}" for minor, last in ((4, 26), (5, 25), (6, 24))
            for patch in range(last + 1)]
TARGETS = [{"pg": version, "arch": arch} for version in VERSIONS for arch in ("x86", "x64")]

def head(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=25) as response:
                return response.status
        except urllib.error.HTTPError as error:
            if error.code in (403, 404, 410):
                return error.code
            if attempt == 2:
                raise
        except (OSError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)


def probe(target):
    platform = "windows" if target["arch"] == "x86" else "windows-x64"
    attempts = []
    try:
        for revision in (1, 2, 3):
            url = f"https://get.enterprisedb.com/postgresql/postgresql-{target['pg']}-{revision}-{platform}-binaries.zip"
            status = head(url)
            attempts.append({"url": url, "http_status": status})
            if status == 200:
                return {**target, "status": "available", "url": url, "attempts": attempts}
        missing = all(a["http_status"] in (404, 410) for a in attempts)
        return {**target, "status": "missing" if missing else "error", "attempts": attempts,
                "reason": "EDB archive not found" if missing else "EDB access denied or unexpected response"}
    except Exception as error:
        return {**target, "status": "error", "attempts": attempts, "reason": str(error)}


def main():
    with ThreadPoolExecutor(max_workers=12) as pool:
        coverage = list(pool.map(probe, TARGETS))
    Path("coverage.json").write_text(json.dumps(coverage, indent=2), encoding="utf-8")
    available = [t for t in coverage if t["status"] == "available"]
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
        summary.write(f"## EDB dependency availability\n\n{len(available)} of {len(TARGETS)} targets available.\n\n")
        summary.write("| PostgreSQL | Architecture | Result | Details |\n|---|---|---|---|\n")
        for target in coverage:
            detail = target.get("url", target.get("reason", ""))
            summary.write(f"| {target['pg']} | {target['arch']} | {target['status']} | {detail} |\n")
            if target["status"] != "available":
                level = "warning" if target["status"] == "missing" else "error"
                print(f"::{level}::PG {target['pg']} {target['arch']}: {target['status']}: {detail}")
    if any(t["status"] == "error" for t in coverage):
        raise SystemExit("Dependency checks failed; network/access errors are not missing versions")
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        matrix = [{k: t[k] for k in ("pg", "arch", "url")} for t in available]
        output.write("matrix=" + json.dumps({"include": matrix}) + "\n")
        output.write("count=" + str(len(matrix)) + "\n")


if __name__ == "__main__":
    main()
