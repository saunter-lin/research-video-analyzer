# Testing and validation

Checked locally on macOS arm64 / Python 3.12, 2026-11-19. No paid APIs, live provider calls, downloads or production-state writes were used.

## Dependency-free core

```sh
python -B tools/test_core.py
python -B examples/offline_research.py --cli /absolute/path/to/video-analyzer
python -B tools/audit_public_tree.py
```

71 tests discovered: 67 passed, 4 explicitly skipped without optional yt-dlp. The four provider-mocking cases remain in the full suite. The core slice covers research accounting, mixed web evidence, comments, external subtitles and portable state/config/CLI behavior. The real-CLI synthetic example checks that evidence IDs resolve to the captured source in the generated report.

## Complete retained regression

With the optional dependencies from `requirements-test.txt` installed in a dedicated test environment:

```sh
python -B -m unittest discover -s tests -v
python -B tools/coverage_stdlib.py --output /tmp/research-coverage.json
```

The source baseline was run on an isolated copy with read-only access to existing local dependencies/models: **152/152 passed**. The public candidate passed **158/158**, no skips: the retained 151 functional/entry contracts, one public asset-exclusion contract replacing the historical archive-presence assertion, and six portable integration tests. Two original ASR tests now provide synthetic model identity/tool fixtures explicitly instead of depending on production runtime/model files. Backend launch assertions now check isolated state propagation and the running interpreter.

The first baseline copy lacked archived YAMNet files and failed its archive-presence assertion; those two files were copied only to the private baseline copy and all baseline tests then passed. They are never public assets. New portability tests initially needed symlink-normalized temporary paths on macOS; final results above include that correction.

The complete candidate suite used the existing production interpreter/dependency environment read-only, with candidate code and temporary Stores. This is not a fresh installation of all optional extras. The separate clean venv successfully installed the locally built wheel with `--no-index --no-deps`, ran help/doctor/skill-path and completed the synthetic cited-report workflow without optional dependencies.

## Coverage and limits

[Coverage JSON](coverage.json): stdlib trace counted 1,934 / 2,726 executable statement lines in `scripts/` (**70.95%**). This measures the parent test process only, excludes subprocess execution, does not measure branch coverage and is not directly comparable to coverage.py. Zero traced lines for doctor/worker do not prove they never ran: subprocess execution is excluded. `document_intake.py` and `benchmark.py` do lack dedicated tests in this retained suite.

These checks do not establish online platform availability, real-world ASR accuracy, listening/playback acceptance, semantic research correctness, all-model availability, quota safety for every account, native Windows support or Linux/macOS CI matrix success. `.github/workflows/ci.yml` defines future CI; no GitHub job was run in this preparation. Optional index resolution and reproducible all-platform dependency locks remain unverified.

Final wheel (54 entries) and source archive (102 entries, including directories/metadata) were extracted and passed the same public-tree audit with zero findings. The source archive also rebuilt a wheel and passed the dependency-free test group (67 pass, 4 skip). Public-tree audit is a limited first-party pattern/boundary check. Inspect the exact wheel and source-archive file lists before release; it is not a complete credential/PII scan or security certification.

Version `1.4.0` includes project/reference license files and aligned packaging metadata. License-closure verification passed 158/158 full tests and 67 core tests, with four optional-provider cases skipped in the clean environment. The source repository is public. The source-pattern auditor excludes internal `.git/` metadata; actual source and archive contents remain scanned. CI now runs only on explicit manual dispatch.
