# agent-recipes

English | [中文](README.zh.md)

A personal agent recipe book.

| File | Purpose |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Global rules |
| [skills.json](skills.json) | Skill sources |
| [mcps.json](mcps.json) | MCP server configuration |
| [setup](setup) | Sync rules, manage Skills, and view MCP guidance |

## Getting started

| Environment | Requirements |
| --- | --- |
| macOS / Linux | Bash 3.2+ |
| Windows | WSL or Git Bash |
| Shared dependencies | Git, jq, Bun, Node.js |

```bash
./setup
```

The command configures the same personal rules ([AGENTS.md](AGENTS.md)) for installed Codex, Claude, DSH, and Cursor clients, and installs Skills from [skills.json](skills.json).

After editing [AGENTS.md](AGENTS.md), run `./setup` again. On other machines, run `git pull` first, then the same command.

## Manage Skills

| Task | Command |
| --- | --- |
| View the manifest and local status | `./setup skills list` |
| Add and install | `./setup skills add SOURCE --skill NAME` |
| Use a specific version | `./setup skills set NAME --ref REF` |
| Upgrade one or all Skills | `./setup skills update [NAME]` |
| Remove the entry and its repository-managed installation | `./setup skills remove NAME` |

Set `SOURCE` to an HTTPS GitHub repository URL, `NAME` to the Skill name, and `REF` to a commit, branch, or tag.

`set` can also change the source and directory. See `./setup --help` for all options and `./setup --version` for the version.

`./setup` uses the recorded versions; use `update` to upgrade. If an upstream Skill is removed or renamed, the current entry is retained and a message is shown. Removal affects only installations managed by this repository.

<details>
<summary>Edit the manifest manually</summary>

Each entry records four fields:

| Field | Meaning |
| --- | --- |
| `name` | Skill name |
| `source` | HTTPS GitHub repository URL |
| `path` | Skill directory in the repository; use `.` for the repository root |
| `ref` | Confirmed full Git commit SHA |

`resolving-merge-conflicts` was removed upstream. `writing-great-skills` was renamed to `writing-for-agents`, which is also in the manifest. These two entries retain historical commits. The six Iluvatar Skills will be added once their online installation sources are confirmed.

</details>

## Configure MCP

Record the services you need in [mcps.json](mcps.json), and keep credential values on the local machine. Run the following command for configuration guidance:

```bash
./setup mcp
```

The command only lists the current MCP entries and prints a prompt you can copy to an Agent. Give the prompt to an Agent in the target client to complete configuration and verification.

## Resolve conflicts

Original contents are backed up before replacement; repositories targeted by development links are preserved. Local modifications are reported as conflicts. To replace them with the repository version after confirming the change, run:

```bash
./setup --force
```

Records and backups are stored in `~/.local/state/agent-recipes/` by default, as `state.json` and `backups/`. When `XDG_STATE_HOME` is set, its `agent-recipes/` directory is used instead. Installation failures restore the selected item.

## Verification

```bash
python3 -m unittest discover -s tests -v
```

Tests use isolated directories and a simulated installer. Actual client loading and MCP connections need verification in the target environment.
