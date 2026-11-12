# agent-recipes

English | [简体中文](README.zh-CN.md)

Personal configuration for global agent rules, Skills, packages, and MCP declarations.

| File | Purpose |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Global rules |
| [skills.json](skills.json) | Skill and package sources |
| [mcps.json](mcps.json) | MCP declarations |
| [setup](setup) / [setup.cmd](setup.cmd) | Sync rules and manage Skills |

## Quick start

Requires [Git](https://git-scm.com/) and [Bun](https://bun.sh/) on macOS, Linux, or Windows.

```bash
./setup
```

Run `./setup` in macOS, Linux, or Windows PowerShell (`setup.cmd` in Command Prompt).

`setup` links [AGENTS.md](AGENTS.md) into installed Codex, Claude, DSH, and Cursor clients, then installs the pinned Skills and packages from [skills.json](skills.json). Re-run it after pulling changes or editing the manifest.

## Manage Skills

| Task | Command |
| --- | --- |
| View all installed Skills | `./setup skills list` |
| Add a standalone Skill | `./setup skills add SOURCE --skill NAME` |
| Change a Skill version | `./setup skills set NAME --ref REF` |
| Update Skills | `./setup skills update [NAME]` |
| Remove a standalone Skill | `./setup skills remove NAME` |
| View packages | `./setup packages list` |
| Add a package | `./setup packages add NAME SOURCE [--path MANIFEST] [--selector POINTER]` |
| Change a package | `./setup packages set NAME [--source URL] [--path MANIFEST] [--selector POINTER] [--ref REF]` |
| Update and reconcile a package | `./setup packages update [NAME]` |
| Remove a package | `./setup packages remove NAME` |

`NAME` is a Skill, member, or package name; `REF` may be a commit, branch, or tag. See `./setup --help` for all options.

`skills update MEMBER` updates the package to the latest upstream commit and reinstalls only that member. Other members sync on the next `./setup`. If upstream adds, removes, or renames members, run `packages update PACKAGE`.

<details>
<summary>Manifest format</summary>

A standalone Skill records `name`, `source`, `path`, and a full commit SHA in `ref`.

A package also uses `name`, `source`, and `ref`; `path` points to its JSON manifest, and `selector` is the JSON Pointer to its member path array. These default to `.claude-plugin/plugin.json` and `/skills`.

</details>

## Configure MCP

Declare required servers in [mcps.json](mcps.json). Keep credentials on the local machine.

```bash
./setup mcp
```

The command prints configuration steps and a prompt you can give to an Agent. It does not edit or start MCP servers.

## Recovery

`setup` backs up files before replacement and blocks deletion of locally modified Skills. After reviewing the change, use `./setup --force` to replace them.

State and backups are stored in `~/.local/state/agent-recipes/`, or under `$XDG_STATE_HOME` when set. Failed installs restore the affected item.

## Verify

```bash
python3 -m unittest discover -s tests -v
```

Tests use isolated directories. Verify actual client rule loading, Skill discovery, and MCP connections in the target environment.
