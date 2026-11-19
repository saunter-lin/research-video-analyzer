# Third-party components and license review

Checked 2026-11-19. This candidate redistributes project source/docs, JSON schemas and self-authored synthetic test input. It does not bundle dependencies, binaries, model weights, downloaded media, archived research or noncommercial audio fixtures. Dependency installation still requires compliance with each component's terms.

External Skill provenance was reviewed against Obsidian records, development/PoC reports and upstream snapshots on 2026-11-19. Design borrowing and locally implemented adaptations are documented; no substantial copying was confirmed within the reviewed samples and matching thresholds. Translated, short or otherwise adapted prompts remain unproven; this is not an originality or ownership clearance. See [the source-by-source review](docs/external-skill-provenance.zh-TW.md) and [comparison data](docs/external-skill-provenance.json). Humanizer vendoring belongs to separate Courseware/Storyboard projects; Research records defer AnySearch. AnySearch uses Apache-2.0 with NOTICE, the unlicensed LDJ source remains unresolved if reuse is later found, and the imlewc Skill copyright notice names ultrasev. The original project source and documentation now use the root MIT LICENSE. Complete notices for four documented MIT references are retained in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md); the [license closure](docs/license-closure.md) defines the source-only scope. No blanket commercial-use permission is asserted for the whole dependency environment or source captures.

## Material findings

| Component | Evidence / license | Decision and remaining limits |
|---|---|---|
| yt-dlp | [Official licensing](https://github.com/yt-dlp/yt-dlp#licensing): PyPI source/wheel Unlicense; some standalone builds include GPL code | Optional Python dependency; no standalone binary shipped; installed-version metadata also inventoried |
| yt-dlp-ejs | Installed metadata: Unlicense AND MIT AND ISC | Keep upstream notices in dependencies; not copied into this repository |
| faster-whisper | [MIT](https://github.com/SYSTRAN/faster-whisper/blob/master/LICENSE) | Optional dependency; bundled VAD weight provenance needs exact-version confirmation before any redistribution |
| whisper.cpp | [MIT](https://github.com/ggml-org/whisper.cpp/blob/master/LICENSE) | Existing user-provided tool/model only; not bundled |
| FFmpeg / imageio-ffmpeg / PyAV | [FFmpeg legal](https://ffmpeg.org/legal.html); wrapper BSD does not determine bundled FFmpeg license | Original environment recorded a GPL-enabled FFmpeg build; do not bundle binaries; review actual build and source/notice obligations before future redistribution |
| mutagen | Installed metadata GPL-2.0-or-later | Legacy/transitive inventory, not a mandatory core dependency; whole-environment commercial/redistribution clearance is pending |
| certifi / tqdm | Metadata MPL-2.0; tqdm MPL-2.0 AND MIT | Retain upstream notices and comply if redistributing relevant code/assets |
| tld | Metadata MPL-1.1 OR GPL-2.0-only OR LGPL-2.1-or-later | Optional document-intake dependency; selection/compliance not decided for a bundled distribution |
| trafilatura | [Apache-2.0](https://raw.githubusercontent.com/adbar/trafilatura/master/LICENSE) | Optional dependency; do not confuse extracted page content rights with library rights |
| models / ESC-50 archive | Legacy record includes model licenses and CC BY-NC audio | Excluded entirely; do not infer commercial permission for past research fixtures |
| source captures / comments / subtitles | Rights and personal-data status depend on each source | Excluded; synthetic example only, not authorization to publish acquired content |

## Complete observed dependency inventory

The table inventories the 36-entry production lock and 18-entry optional document lock (54 rows; overlapping packages retained). Versions and license labels were read from existing installed distribution metadata without installing or running new third-party software. All pinned versions matched those local distributions. Metadata labels and presence of notice files are not a complete legal audit, vulnerability audit or exact-source provenance verification. Upstream linked pages may describe a moving branch rather than the exact pinned release.

See [machine-readable inventory](docs/dependency-inventory.json) for observed notice paths and project metadata. Historical locks preserve the original versions and are not certified portable installers.

| Package | Pinned version | Observed license label | Group |
|---|---|---|---|
| anyio | 4.15.1 | MIT | legacy core environment |
| av | 16.1.0 | BSD-3-Clause | legacy core environment |
| brotli | 1.2.1 | MIT | legacy core environment |
| certifi | 2026.10.23 | Mozilla Public License 2.0 (MPL 2.0) | legacy core environment |
| charset-normalizer | 3.5.2 | MIT | legacy core environment |
| click | 8.5.0 | BSD-3-Clause | legacy core environment |
| cmake | 4.4.4 | Apache Software License, BSD License | legacy core environment |
| ctranslate2 | 4.8.4 | MIT | legacy core environment |
| faster-whisper | 1.2.1 | MIT License | legacy core environment |
| filelock | 4.2.1 | MIT | legacy core environment |
| flatbuffers | 25.12.19 | Apache Software License | legacy core environment |
| fsspec | 2026.9.0 | BSD-3-Clause | legacy core environment |
| h11 | 0.16.0 | MIT License | legacy core environment |
| hf-xet | 1.7.0 | Apache-2.0 | legacy core environment |
| httpcore2 | 2.13.1 | BSD-3-Clause | legacy core environment |
| httpx2 | 2.13.1 | BSD-3-Clause | legacy core environment |
| huggingface_hub | 2.2.0 | Apache Software License | legacy core environment |
| idna | 3.20 | BSD-3-Clause | legacy core environment |
| imageio-ffmpeg | 0.6.0 | BSD License | legacy core environment |
| mutagen | 1.48.1 | GPL-2.0-or-later | legacy core environment |
| numpy | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | legacy core environment |
| onnxruntime | 1.31.0 | MIT License | legacy core environment |
| opencc-python-reimplemented | 0.1.7 | Apache Software License | legacy core environment |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | legacy core environment |
| protobuf | 7.36.2 | 3-Clause BSD License | legacy core environment |
| pycryptodomex | 3.24.1 | BSD License, Public Domain | legacy core environment |
| PyYAML | 6.0.3 | MIT License | legacy core environment |
| requests | 2.34.2 | Apache Software License | legacy core environment |
| tokenizers | 0.23.3 | Apache Software License | legacy core environment |
| tqdm | 4.70.1 | MPL-2.0 AND MIT | legacy core environment |
| truststore | 0.10.5 | MIT | legacy core environment |
| typing_extensions | 4.16.0 | PSF-2.0 | legacy core environment |
| urllib3 | 2.8.0 | MIT | legacy core environment |
| websockets | 17.2 | BSD-3-Clause | legacy core environment |
| yt-dlp | 2026.10.26 | Unlicense | legacy core environment |
| yt-dlp-ejs | 0.8.0 | Unlicense AND MIT AND ISC | legacy core environment |
| babel | 2.18.0 | BSD License | documents |
| certifi | 2026.10.23 | Mozilla Public License 2.0 (MPL 2.0) | documents |
| charset_normalizer | 3.5.2 | MIT | documents |
| courlan | 1.4.0 | Apache-2.0 | documents |
| dateparser | 1.5.0 | BSD-3-Clause | documents |
| htmldate | 1.11.0 | Apache-2.0 | documents |
| justext | 3.0.2 | BSD License | documents |
| lxml | 6.1.3 | BSD-3-Clause | documents |
| lxml_html_clean | 0.4.6 | BSD-3-Clause | documents |
| pypdf | 7.0.1 | BSD-3-Clause | documents |
| python_dateutil | 4.0.0 | BSD-3-Clause | documents |
| pytz | 2026.6 | MIT License | documents |
| regex | 2026.11.9 | Apache-2.0 AND CNRI-Python | documents |
| tld | 0.13.2 | MPL-1.1 OR GPL-2.0-only OR LGPL-2.1-or-later | documents |
| trafilatura | 2.3.1 | Apache-2.0 | documents |
| tzdata | 2026.6 | Apache-2.0 | documents |
| tzlocal | 5.4.5 | MIT | documents |
| urllib3 | 2.8.0 | MIT | documents |
