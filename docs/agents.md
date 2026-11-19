# Agent Skill installation and portability

Install the CLI in its own environment first. Find the packaged Skill with `video-analyzer skill-path`; it contains SKILL.md and its own references. You can copy that directory without copying implementation code, private settings or research data.

For Codex, choose a fresh project directory under `.agents/skills/research-video-analyzer`, or a fresh user directory under `~/.agents/skills/research-video-analyzer`. Check for an existing directory first and do not overwrite it. Example from a source checkout:

```sh
mkdir -p .agents/skills
test ! -e .agents/skills/research-video-analyzer
cp -R skills/research-video-analyzer .agents/skills/research-video-analyzer
```

Run these steps individually and stop if the existence check fails. The CLI must be on the Agent's PATH, or tell the Agent its venv executable location. Invoke `$research-video-analyzer` in a compatible Codex Skill interface. No global Skill or permission rule is installed by this repository.

The local discovery paths and Skill format were checked against [official OpenAI documentation](https://learn.chatgpt.com/docs/build-skills) on 2026-11-19. Installing the files does not grant command execution, network or browser permissions.

| Host | Core CLI | Skill / orchestration |
|---|---|---|
| Codex | Standard shell commands | SKILL.md format + local discovery documented; live Agent workflow not exercised in this preparation |
| Other Skill-capable Agents | Standard shell commands | Read/copy SKILL.md + references into host-supported locations; discovery paths and permissions vary, untested |
| Other Agents / human terminal | Standard shell commands | Follow the same contracts manually; no Skill loader required |

Portable: query reservation, evidence classification, snapshots, reports, budgets and model-result validation. Host-specific: browser subtitle recovery, official login handoff, tool authorization, `exec_command` permission metadata and report opening. Translate these explicitly rather than claiming native compatibility.

The preserved Antigravity adapter is optional and macOS-specific (`sandbox-exec` mandatory); model IDs/quotas and account access are historical assumptions, not a guarantee of free service. No agy invocation was made for preparation. Other hosts can review content and supply the existing report/review JSON directly; keep the same schema, citation and review gates. Internal provenance labels such as `current_codex_session` are retained legacy protocol values; generic Agent provenance naming is a future compatibility task.
