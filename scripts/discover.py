"""Discover upstream tags without executing upstream workflow code."""
import json
import os
import re
import subprocess
from targets import TARGETS


def api(path):
    return json.loads(subprocess.check_output(["gh", "api", path], text=True))


requested = os.environ.get("REQUESTED_TAG", "all")
if requested != "all" and not re.fullmatch(r"wal2json_\d+_\d+(?:_\d+)?", requested):
    raise SystemExit("Invalid upstream tag")
tags = []
page = 1
while True:
    batch = api(f"repos/eulerto/wal2json/tags?per_page=100&page={page}")
    if not batch:
        break
    tags.extend(batch)
    page += 1
releases = []
page = 1
while True:
    batch = api(f"repos/{os.environ['GITHUB_REPOSITORY']}/releases?per_page=100&page={page}")
    if not batch:
        break
    releases.extend(batch)
    page += 1
published = {r["tag_name"] for r in releases if not r["draft"] and
             len([a for a in r["assets"] if a["name"].endswith('.zip')]) >= len(TARGETS)}
selected = [
    {"tag": t["name"], "sha": t["commit"]["sha"]}
    for t in tags
    if re.fullmatch(r"wal2json_\d+_\d+(?:_\d+)?", t["name"])
    and (requested == "all" or requested == t["name"])
    and t["name"] not in published
]
if requested != "all" and not any(t["name"] == requested for t in tags):
    raise SystemExit("Tag does not exist upstream")
# One upstream tag per run keeps the nested Windows matrix bounded to 156 jobs.
selected = selected[:1]
with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
    output.write("matrix=" + json.dumps({"include": selected}) + "\n")
    output.write("count=" + str(len(selected)) + "\n")
print(json.dumps(selected, indent=2))
