# Verification record — v0.1.0

Observed locally on 2026-11-04, macOS, Python 3.14.3. This records functional checks, not adoption, production certification or a comparative benchmark.

## Automated behavior

`python -m unittest discover -s tests -v` completed **59 discovered cases: 58 passed, 1 skipped** with the pinned XLSX dependencies installed. The skipped branch checks the actionable missing-dependency error in an environment without that optional dependency. Core CSV checks were also exercised without optional XLSX packages during development.

The suite covers exact/leading-zero identity, duplicate rejection, bounded CSV/XLSX parsing, formula-cache handling, join multiplication evidence, complete-snapshot semantics, three-way conflicts/convergence, missing/reappearing rows, atomic/stale writes, persistent state, consistent SQLite read snapshots across external commits, portable builds and real loopback HTTP requests. Review found and fixed stale-editor exact-row reloading and default XLSX worksheet selection; both have regression cases.

Ruff checks and Node syntax checks pass. Documentation checks cover nine language selectors, identical command blocks, screenshot presence and local Markdown links. The guided preview is deterministically regenerated from the real engine and tested against its source/local/incoming values. The packaged skill excludes generated workspaces and private state.

## Actual browser workflow

The generated inventory workspace was exercised in Chromium through the desktop app:

- Search `00128`, edit reorder level `12` → `20`, save.
- Select the bundled next CSV, preview and apply: one new product, one missing product and one conflict after that edit.
- Review actual source/local/incoming values `12` / `20` / `14`, keep the local edit and reload.
- Export through the button and parse the downloaded CSV: active `00139` included, missing `00136` excluded, `00128` retains `20` with incoming stock `9`.
- At 390 × 844, open navigation, switch to order lines and save an editable status. No page-level horizontal overflow was observed.
- Open an editor, change only reorder level, apply an import from another process, observe stale-save rejection, reload the exact record with the draft retained, then save. Untouched notes take the newer source value.
- No warning/error console messages were observed during these checks.

The public-style guided preview was separately exercised locally: four-state navigation, exact search, missing-record toggle and resolved value. Its 390px layout had no page overflow. It is explicitly a **guided synthetic preview**; full editing/import uses the local generated app.

Actual screenshots: [workspace](assets/workspace.jpg), [conflict](assets/conflict.jpg), [mobile](assets/mobile.jpg), [guided preview](assets/guided-preview.jpg).

## Held-out task

A separate contacts/activities task was executed in isolated runs with this skill and with a capable base agent without the skill. Both produced working apps and passed their recorded HTTP/data checks, including local corrections, a second snapshot, conflict handling, missing/new identities, effective export and restart persistence. The baseline also received browser verification; the with-skill run had no browser tool and reported that limitation.

This single qualitative pair does **not** establish a speed, cost or quality advantage. Timing/token comparison and repeated trials under identical browser access were not measured. Raw run notes and outputs are retained in the development workspace, outside this release. The distributable task prompts and synthetic fixtures are in [evals](../evals/evals.json).

## Limits and release status

Native-speaker translation review, independent security review, assistive-technology testing, concurrent multi-user use and production-scale operation were not performed. Python 3.10/3.14 on Linux, Windows and macOS are configured in CI; actual remote results must be checked in GitHub Actions after publication. A local passing suite alone is not evidence that those six remote jobs ran.

Read the [data contract](DATA-CONTRACT.md) and [privacy boundaries](PRIVACY.md) before using real operational data. Public publication, release assets and adoption are tracked separately from these local checks.
