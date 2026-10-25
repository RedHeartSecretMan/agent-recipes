#!/usr/bin/env python3
"""Emulate the public Skills CLI artifacts without touching the real user home."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.parse


def fail(message, code=23):
    sys.stderr.write(message + "\n")
    raise SystemExit(code)


def main():
    args = sys.argv[1:]
    home = Path(os.environ["AGENT_RECIPES_HOME"])
    log = Path(os.environ["TEST_BUNX_LOG"])
    with log.open("a", encoding="utf-8") as output:
        output.write(json.dumps(args) + "\n")
    if args and args[0] == "--version":
        print("1.4.2-test")
        return
    if not args or args[0] != "skills@latest":
        fail("Installer must use skills@latest")
    if args[1:] == ["--version"]:
        print("1.7.4-test")
        return
    if args[1:] in (["--help"], ["-h"]):
        print("add remove list update --global --skill --yes --json")
        return
    if len(args) < 2:
        fail("Missing native Skills command")
    action = args[1]
    if action == "add" and len(args) > 2 and args[2] in ("--help", "-h"):
        print("--global --skill --agent --yes --json")
        return
    selectors = [index for index, arg in enumerate(args) if arg in ("--agent", "-a")]
    for index in selectors:
        values = []
        for value in args[index + 1:]:
            if value.startswith("-"):
                break
            values.append(value)
        if values != ["universal"]:
            fail("Only the platform-neutral universal target is allowed")
    if action == "add" and len(selectors) != 1:
        fail("A universal target is required; auto-detection can include unsupported targets")
    if len(selectors) > 1:
        fail("Repeated target selectors are not supported")
    lock_path = home / ".agents/.skill-lock.json"
    lock = json.loads(lock_path.read_text()) if lock_path.exists() else {"version": 3, "skills": {}}
    skills = lock.setdefault("skills", {})
    if action in ("remove", "rm"):
        names = []
        skip = False
        for arg in args[2:]:
            if skip:
                skip = False
                continue
            if arg in ("--agent", "-a"):
                skip = True
                continue
            if arg in ("--skill", "-s"):
                continue
            if not arg.startswith("-"):
                names.append(arg)
        for name in names:
            destination = home / ".agents/skills" / name
            if destination.is_symlink():
                destination.unlink()
            elif destination.exists():
                shutil.rmtree(destination)
            skills.pop(name, None)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(json.dumps(lock) + "\n")
        print(json.dumps({"success": True, "removed": names}))
        return
    if action != "add":
        fail("Unexpected native Skills action: " + action)
    if len(args) < 3:
        fail("Missing source")
    source_url = args[2]
    parsed = urllib.parse.urlsplit(source_url)
    parts = [urllib.parse.unquote(x) for x in parsed.path.strip("/").split("/")]
    if parsed.scheme != "https" or parsed.hostname != "github.com" or len(parts) < 2:
        fail("Fixture accepts a GitHub HTTPS source")
    repo = "/".join(parts[:2])
    if repo.endswith(".git"):
        repo = repo[:-4]
    source = "https://github.com/" + repo
    mapping = json.loads(os.environ["TEST_GIT_SOURCES"])
    checkout = mapping.get(source)
    if not checkout:
        fail("Unknown fixture repository")
    ref = parsed.fragment or "HEAD"
    subpath = ""
    if len(parts) >= 4 and parts[2] == "tree":
        ref = parts[3]
        subpath = "/".join(parts[4:])
    selection = "--skill" if "--skill" in args else "-s" if "-s" in args else None
    if not selection:
        fail("A selected Skill is required")
    name = args[args.index(selection) + 1]
    real_git = os.environ["TEST_REAL_GIT"]
    def git(*parameters):
        result = subprocess.run([real_git, "-C", checkout, *parameters], capture_output=True, text=True)
        if result.returncode:
            fail(result.stderr.strip() or "Fixture Git operation failed")
        return result.stdout.strip()
    sha = git("rev-parse", ref + "^{commit}")
    all_files = git("ls-tree", "-r", "--name-only", sha).splitlines()
    candidates = [path for path in all_files if path == "SKILL.md" or path.endswith("/SKILL.md")]
    matches = []
    for skill_path in candidates:
        folder = str(Path(skill_path).parent)
        if subpath and folder != subpath.rstrip("/"):
            continue
        content = git("show", sha + ":" + skill_path)
        if any(line.strip() == "name: " + name for line in content.splitlines()[:10]):
            matches.append((skill_path, folder))
    if len(matches) != 1:
        fail("Requested Skill was not uniquely present at the pinned commit")
    skill_path, folder = matches[0]
    destination = home / ".agents/skills" / name
    if destination.is_symlink():
        destination.unlink()
    elif destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    for path in all_files:
        if folder != "." and not path.startswith(folder + "/"):
            continue
        relative = path if folder == "." else path[len(folder) + 1:]
        output = destination / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run([real_git, "-C", checkout, "show", sha + ":" + path], capture_output=True)
        output.write_bytes(result.stdout)
    if os.environ.get("TEST_BUNX_CREATE_ALIAS"):
        alias = home / ".claude/skills" / name
        alias.parent.mkdir(parents=True, exist_ok=True)
        if alias.is_symlink():
            alias.unlink()
        elif alias.exists():
            shutil.rmtree(alias)
        alias.symlink_to(destination, target_is_directory=True)
    mode = os.environ.get("TEST_BUNX_BEHAVIOR", "normal")
    if mode == "partial_failure":
        (destination / "partial.txt").write_text("partial installer output")
    recorded_ref = "0" * 40 if mode == "bad_lock" else sha
    skills[name] = {"source": repo, "sourceType": "github", "sourceUrl": source + ".git",
                    "skillPath": skill_path, "ref": recorded_ref,
                    "skillFolderHash": git("rev-parse", sha + (":" + folder if folder != "." else "^{tree}"))}
    if mode == "bad_source":
        skills[name]["sourceUrl"] = "https://github.com/agent-recipes-test/unexpected"
        skills[name]["source"] = "agent-recipes-test/unexpected"
    if mode == "bad_path":
        skills[name]["skillPath"] = "different/path/SKILL.md"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps(lock) + "\n")
    if mode == "partial_failure":
        fail("Simulated installer failure after writing files and lock", 7)
    if mode == "missing_files":
        shutil.rmtree(destination)
    if mode == "mutate_manifest":
        manifest = Path(os.environ["TEST_MANIFEST"])
        data = json.loads(manifest.read_text())
        data["external_edit"] = "preserve this concurrent change"
        manifest.write_text(json.dumps(data, indent=2) + "\n")
    if mode == "invalid_json":
        print("not-json")
        return
    print(json.dumps([{"name": name, "status": "installed", "source": repo, "ref": sha,
                       "hash": skills[name]["skillFolderHash"], "path": str(destination)}]))


if __name__ == "__main__":
    main()
