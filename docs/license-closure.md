# License closure — source-only private repository

Decision date: 2026-11-19 (Asia/Taipei). Candidate: `1.4.0.dev2`; retained research core: 1.4.0.

The user's instruction to close the licensing work and create a private GitHub repository authorizes completing the previously recommended MIT choice for this source candidate. The root LICENSE now identifies **saunter-lin and contributors** for original project work; this is the verified maintainer account, not a claim to own upstream material. No separate signed ownership warranty or complete legal originality determination has been obtained.

## Closed items

| Item | Concrete resolution |
|---|---|
| Project license pending | MIT selected for original source and project documentation; declared in Python package metadata and both READMEs |
| Documented MIT references | Four complete original MIT texts and copyright notices retained under `third_party/licenses/`, indexed by THIRD_PARTY_NOTICES and ACKNOWLEDGEMENTS |
| imlewc ownership attribution | Preserved the actual `2025 ultrasev` notice, rather than substituting the repository owner's account |
| Humanizer / AnySearch | No corresponding implementation is bundled; retained provenance evidence explains the different-project Humanizer copies and deferred AnySearch decision |
| Unlicensed LDJ source / other non-adopted projects | No identified copied component is included; excluded, with a future-reuse restriction rather than assigning them an invented license |
| GPL/MPL/native/model obligations | Distribution is source-only: optional dependencies, executables, models and captured materials are installed or supplied separately and keep their own terms; no bundled-environment commercial-use clearance is asserted |
| Wheel/source archive attribution | Build manifest and package license-file metadata include the project license and all four full reference notices; built archives must be inspected before delivery |
| Private paths / prior history | Git root is only `repository/`; local verification records, original research sessions, binaries, models, build artifacts and old histories are excluded |

This closes the known license-administration blockers for storing the inspected source candidate in a **private** repository. The earlier assessment's LICENSE-pending NO-GO records the state before this decision. It must not be read as the current project license. The private repository remains private; no public release, visibility change or packaged third-party binary distribution is authorized by this action.

## Remaining bounds

The prior review found no exact matches at its specified thresholds, but cannot rule out every short, renamed or translated passage. Reference notices are retained conservatively; they do not retroactively prove authorship or clear an unknown rights holder. Newly discovered substantial third-party material must be mapped to its actual source and terms before redistribution.

Fresh optional-extra installation, live platform/provider behavior, native Windows support, all-Agent workflows and complete dependency vulnerability audits remain engineering/operational limitations, not grounds to relabel third-party licenses as MIT. The [provenance audit](external-skill-provenance.zh-TW.md), [dependency inventory](../THIRD_PARTY.md) and [testing notes](testing.md) remain part of the record.

CI definitions are retained for explicit `workflow_dispatch` only on initial private setup, so repository creation does not automatically launch the optional/native dependency matrix. No paid API call is part of preparation or the offline tests.

## Reference terms

MIT notice-preservation terms: [GitHub's Choose a License](https://choosealicense.com/licenses/mit/). If AnySearch code is added in the future, its [Apache-2.0 terms](https://www.apache.org/licenses/LICENSE-2.0.txt), applicable NOTICE and modification statements must remain; it is not covered by copying the project's MIT notice alone.
