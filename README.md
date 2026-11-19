# Research / Video Analyzer

A local Python CLI for evidence-traceable research across public videos, web pages and comments, with an optional Agent Skill. Based on the stable Research 1.4.0 implementation. Version `1.4.0` is publicly available on [GitHub](https://github.com/saunter-lin/research-video-analyzer), with original project source and documentation licensed under MIT. Third-party notices and distribution boundaries are documented below.

[繁體中文](README.zh-TW.md) · [Installation](docs/install.md) · [Agent setup](docs/agents.md) · [Testing](docs/testing.md) · [Readiness assessment](docs/open-source-assessment.zh-TW.md)

## What it does

- Incremental research sessions, immutable source snapshots, content hashes, pinned artifacts, SQLite indexing and cache reuse.
- Research gaps, query reservations, source selection, query/source/cache budgets and zero-paid-API gates.
- YouTube/Bilibili metadata and subtitles; optional local audio/video extraction and existing-model ASR/VAD.
- Offline web snapshots and public comment imports, exact quotes, line/time locators and evidence IDs.
- Quick/deep Markdown reports, evidence appendices, structured JSON, conflicts and explicit evidence limits.
- Optional guarded Antigravity analysis, schema/citation validation, one quota-only fallback and host review/handoff.

The CLI manages records and validates structure. A human or an Agent must evaluate source meaning, independence, comparability and claims. It is not an autonomous web researcher or a substitute for watching/listening to evidence. Report content and CLI diagnostics currently include Traditional Chinese.

## Install the offline core

Python 3.11+ on macOS/Linux (Python 3.12 is the local validation baseline). Native Windows is unsupported because the retained core uses POSIX `fcntl` and optional `resource`; WSL is a possible route, not a verified platform.

From a source checkout:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/video-analyzer --help
.venv/bin/video-analyzer doctor
.venv/bin/python examples/offline_research.py --cli .venv/bin/video-analyzer
```

The core has no runtime Python dependencies and does not require Codex, an API key or a model download. Installation needs standard Python build tooling (`setuptools`, `wheel`), obtainable from your configured package index. To install without network, provide those in a trusted local wheelhouse; see [installation](docs/install.md).

## CLI examples

```sh
video-analyzer --data ./data --cache ./cache create \
  --title 'Public specification review' --question 'What does the captured specification support?'
video-analyzer --data ./data --cache ./cache list
video-analyzer --data ./data --cache ./cache show SESSION_ID
video-analyzer --data ./data --cache ./cache research-status SESSION_ID
```

Global `--data` / `--cache` options go before the subcommand. Session IDs come from `create`; do not copy placeholder IDs. The [synthetic offline example](examples/offline_research.py) runs the real CLI from creation through candidate selection, snapshot import, evidence and a cited report, with no remote access. For live research, read [workflow](references/workflow.md) and [research-ledger](references/research-ledger.md) first.

Optional capabilities: `pip install '.[video]'`, `'.[audio]'`, `'.[documents]'` or `'.[benchmark]'`. These install third-party packages, sometimes native binaries; review [third-party licensing](THIRD_PARTY.md) first. Models and `agy` are never bundled. Online acquisition depends on platform access and may break independently of the offline core. No paid provider is required.

## Agent Skill

Run `video-analyzer skill-path` to locate the self-contained Skill folder. Copy it to a new user/project Skill location without replacing an existing installation; see [Agent setup and portability](docs/agents.md). Any Agent with a shell can invoke the CLI. Codex host authorization and browser fallback operations require host-specific adaptation elsewhere.

## Local state and publication boundaries

Defaults are `~/.local/share/research-video-analyzer` and `~/.cache/research-video-analyzer`, separate from the original tool's state. Set `RESEARCH_DATA_DIR`, `RESEARCH_CACHE_DIR` or explicit CLI options; optional models use a private `RESEARCH_RUNTIME` JSON file. `.env.example` documents variables; `.env` files are not loaded.

Do not publish research sessions, credentials, cookies, signed media URLs, copyrighted captures, model weights, local environments or archived fixtures. `.gitignore` is defense in depth, not a sanitizer. Keep exports and distribution contents consistent with the file manifest and [security guidance](SECURITY.md).

## License

Original project source and documentation are licensed under [MIT](LICENSE). Complete notices for four documented MIT references are retained in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md); see [ACKNOWLEDGEMENTS](ACKNOWLEDGEMENTS.md) and the [license closure](docs/license-closure.md).

Dependencies, executables, model weights and acquired content retain their own terms; they are not bundled or relicensed by this source-only distribution. See [THIRD_PARTY.md](THIRD_PARTY.md). The source repository is public. GitHub Releases are managed separately from repository visibility. CI is available by explicit manual dispatch.
