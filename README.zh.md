# agent-recipes

[English](README.md) | 中文

集中管理全局 Agent 规则、Skills、包和 MCP 声明的个人配置仓库。

| 文件 | 用途 |
| --- | --- |
| [AGENTS.md](AGENTS.md) | 全局规则 |
| [skills.json](skills.json) | Skill 和包的来源 |
| [mcps.json](mcps.json) | MCP 声明 |
| [setup](setup) / [setup.cmd](setup.cmd) | 同步规则、管理 Skills |

## 快速开始

依赖 [Git](https://git-scm.com/) 和 [Bun](https://bun.sh/)，支持 macOS、Linux 和 Windows。

```bash
./setup
```

macOS、Linux 和 Windows PowerShell 直接运行 `./setup`，CMD 运行 `setup.cmd`。

`setup` 会把 [AGENTS.md](AGENTS.md) 接入已安装的 Codex、Claude、DSH 和 Cursor，并安装 [skills.json](skills.json) 中固定版本的 Skills 和包。拉取更新或修改清单后，重新运行即可。

## 管理 Skills

| 要做什么 | 命令 |
| --- | --- |
| 查看全部安装 | `./setup skills list` |
| 添加独立 Skill | `./setup skills add SOURCE --skill NAME` |
| 切换 Skill 版本 | `./setup skills set NAME --ref REF` |
| 更新 Skills | `./setup skills update [NAME]` |
| 删除独立 Skill | `./setup skills remove NAME` |
| 查看包 | `./setup packages list` |
| 添加包 | `./setup packages add NAME SOURCE [--path MANIFEST] [--selector POINTER]` |
| 修改包 | `./setup packages set NAME [--source URL] [--path MANIFEST] [--selector POINTER] [--ref REF]` |
| 更新并同步包 | `./setup packages update [NAME]` |
| 删除包 | `./setup packages remove NAME` |

`NAME` 可以是 Skill、包成员或包名；`REF` 可以是提交号、分支或标签。完整选项见 `./setup --help`。

`skills update MEMBER` 会把包更新到上游最新提交，但只重新安装指定成员；其他成员会在下次运行 `./setup` 时同步。如果上游新增、删除或重命名成员，请运行 `packages update PACKAGE`。

<details>
<summary>清单格式</summary>

独立 Skill 记录 `name`、`source`、`path` 和完整提交号 `ref`。

包同样使用 `name`、`source` 和 `ref`；`path` 指向 JSON 清单，`selector` 是指向成员路径数组的 JSON Pointer。默认分别为 `.claude-plugin/plugin.json` 和 `/skills`。

</details>

## 配置 MCP

在 [mcps.json](mcps.json) 中声明所需服务，凭据只保存在本机。

```bash
./setup mcp
```

命令会输出配置步骤和可交给 Agent 的提示，但不会修改或启动 MCP 服务。

## 恢复

`setup` 会在替换前备份，并阻止删除本地修改过的 Skill。确认后用 `./setup --force` 替换。

状态和备份位于 `~/.local/state/agent-recipes/`；设置 `XDG_STATE_HOME` 时使用其对应目录。安装失败会恢复受影响的条目。

## 验证

```bash
python3 -m unittest discover -s tests -v
```

测试使用隔离目录。客户端规则加载、Skill 发现和 MCP 连接仍需在目标环境中验证。
