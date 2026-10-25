#!/usr/bin/env python3
"""Network-free Git adapter for black-box tests; all objects are real Git objects."""
import json
import os
import subprocess
import sys


def main():
    args = sys.argv[1:]
    real_git = os.environ["TEST_REAL_GIT"]
    sources = json.loads(os.environ["TEST_GIT_SOURCES"])
    original = list(args)
    for i, arg in enumerate(args):
        if arg in sources:
            args[i] = sources[arg]
        elif arg.rstrip("/")[:-4] in sources and arg.rstrip("/").endswith(".git"):
            args[i] = sources[arg.rstrip("/")[:-4]]
        elif arg.startswith(("https://", "http://", "ssh://", "git@")):
            sys.stderr.write("Test Git adapter refuses unmapped network source\n")
            return 91
    # A fetched checkout can keep its public URL as origin without reaching it.
    if "fetch" in args and "origin" in args:
        cmd_index = args.index("fetch")
        prefix = args[:cmd_index]
        result = subprocess.run([real_git, *prefix, "remote", "get-url", "origin"], text=True, capture_output=True)
        if result.returncode == 0:
            origin = result.stdout.strip().rstrip("/")
            normalized = origin[:-4] if origin.endswith(".git") else origin
            if normalized in sources:
                args[args.index("origin", cmd_index)] = sources[normalized]
            elif origin.startswith(("https://", "http://", "ssh://", "git@")):
                sys.stderr.write("Test Git adapter refuses unmapped origin\n")
                return 91
    log = os.environ.get("TEST_GIT_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as output:
            output.write(json.dumps(original) + "\n")
    return subprocess.run([real_git, *args]).returncode


if __name__ == "__main__":
    raise SystemExit(main())
