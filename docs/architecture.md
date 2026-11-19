# Repository architecture

```text
LICENSE / THIRD_PARTY_NOTICES.md / third_party/licenses/
README.md / README.zh-TW.md
pyproject.toml / MANIFEST.in
cli.py / __init__.py                 # small console/package adapter
video-analyzer                      # optional POSIX source launcher
scripts/                            # retained 1.4.0 implementation
  va.py                             # sessions, Store, selection, artifacts, CLI, reports
  research_ledger.py                # gaps, reservation, increment/stop accounting
  web_sources.py / video_comments.py / external_subtitles.py
  antigravity_backend.py / antigravity_entry.py
  audio_analysis/ / asr_worker.py / audio_metrics.py
  document_intake.py / benchmark.py / doctor.py
schemas/ / references/              # runtime schemas and detailed research contracts
skills/research-video-analyzer/     # separately copyable Agent Skill + references
examples/offline_research.py        # synthetic, no network/model/API
runtime.example.json / .env.example
requirements-legacy.lock.txt        # production inventory, not a portable install lock
tests/ / tools/ / .github/workflows/ci.yml
docs/ / THIRD_PARTY.md / SECURITY.md / CONTRIBUTING.md
```

CLI -> retained Python modules -> local Store (SQLite + session history + content-addressed cache + pinned evidence). Skill -> host tools + CLI -> validated evidence -> human/Agent semantic review -> report. No new service/framework or direct paid-provider SDK is introduced.

For minimal change, setuptools maps the repository root to the installed private `research_video_analyzer` package. Explicit package/file lists exclude tests, logs and data from wheels; MANIFEST.in controls source archives. The console adapter temporarily exposes legacy top-level modules inside its process. This is a command-line compatibility boundary, not a promised in-process SDK; embedding/import-name isolation would require a later refactor.

Public preparation changes: portable console entry; optional dependency groups; private state/config directories; PATH-based Node discovery; host-neutral default analysis provenance; read-only doctor without a private runtime; portable Skill routing; installation/asset-dependent test adjustments; synthetic examples and CI. No research/evidence/query-budget/selection/report-algorithm rewrite.

Detailed retained workflow references sometimes show source-checkout commands and `runtime.json`. Installed users should use `video-analyzer` and `RESEARCH_RUNTIME`; the Skill entry explains this translation. Full report prose remains Traditional Chinese. Archived sound-event experiments are excluded, rather than reintroduced as qualified production functionality.
