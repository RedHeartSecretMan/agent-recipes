# agent-recipes

[English](README.md) | 中文

一份个人 Agent 食谱。

| 文件 | 用途 |
| --- | --- |
| [AGENTS.md](AGENTS.md) | 全局规则 |
| [skills.json](skills.json) | 所需 Skills 的来源记录 |
| [mcps.json](mcps.json) | 所需 MCP 的配置记录 |
| [setup](setup) | 同步规则、管理 Skills、查看 MCP 指引 |

## 开始使用

| 环境 | 要求 |
| --- | --- |
| macOS / Linux | Bash 3.2+ |
| Windows | WSL 或 Git Bash |
| 通用依赖 | Git、jq、Bun、Node.js |

```bash
./setup
```

为本机已安装的 Codex、Claude、DSH 和 Cursor 配置同一份个人规则（[AGENTS.md](AGENTS.md)），并按 [skills.json](skills.json) 安装 Skills。

修改 [AGENTS.md](AGENTS.md) 后，再运行 `./setup`。其他机器先 `git pull`，再运行同一命令。

## 管理 Skills

| 要做什么 | 命令 |
| --- | --- |
| 查看清单和本机状态 | `./setup skills list` |
| 添加并安装 | `./setup skills add SOURCE --skill NAME` |
| 切换指定版本 | `./setup skills set NAME --ref REF` |
| 升级一个或全部 Skills | `./setup skills update [NAME]` |
| 移除清单项及本仓库管理的安装 | `./setup skills remove NAME` |

`SOURCE` 填 HTTPS GitHub 仓库地址，`NAME` 填技能名称，`REF` 填提交号、分支或标签。

`set` 也可修改来源和目录，完整选项见 `./setup --help`，版本信息见 `./setup --version`。

`./setup` 使用清单中的版本，升级请用 `update`。上游移除或改名的 Skill 会保留原记录并提示；删除只影响本仓库管理的安装。

<details>
<summary>手动编辑清单</summary>

每项记录四个字段：

| 字段 | 含义 |
| --- | --- |
| `name` | Skill 名称 |
| `source` | HTTPS GitHub 仓库地址 |
| `path` | 仓库内 Skill 目录；仓库根目录使用 `.` |
| `ref` | 已确认的完整 Git 提交号 |

`resolving-merge-conflicts` 已被上游移除，`writing-great-skills` 已改名为清单中的 `writing-for-agents`，这两项保留历史提交。六个 Iluvatar Skills 待确认互联网分发来源后再纳入。

</details>

## 配置 MCP

在 [mcps.json](mcps.json) 记录所需服务，凭据值保留在本机。运行以下命令获取配置指引：

```bash
./setup mcp
```

命令只输出当前 MCP 和可复制的 Agent 提示。将提示交给目标客户端中的 Agent，按指引完成配置与验证。

## 遇到冲突

替换前会备份原内容；开发链接指向的原仓库保留。发现本地修改时会提示冲突，确认要用仓库版本替换后运行：

```bash
./setup --force
```

记录和备份默认位于 `~/.local/state/agent-recipes/`，分别为 `state.json` 和 `backups/`。设置 `XDG_STATE_HOME` 时，使用其下的 `agent-recipes/`。安装失败会按选中项恢复。

## 验证

```bash
python3 -m unittest discover -s tests -v
```

测试使用隔离目录和模拟安装器；客户端实际加载和 MCP 连接需在目标环境验证。
