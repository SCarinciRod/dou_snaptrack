# Module audit: essential vs. obsolete (preliminary)

This document lists modules in the current workspace and whether they appear essential to the Streamlit UI + CLI workflow, based on import graph scanning. Items marked "candidate for deprecation" are not used by the main entry points, or have a superseded alternative.

Legend:
- KEEP: used by UI or CLI flows.
- DEPRECATE?: no direct references found in current flows; keep temporarily if unsure.

Essential entry points considered:
- UI: src/dou_snaptrack/ui/app.py
- Main CLI: src/dou_snaptrack/05_cascade_cli.py
- CLI modules: src/dou_snaptrack/cli/*.py

## Keep
- dou_snaptrack/ui/app.py — Streamlit UI main app.
- dou_snaptrack/ui/launch.py — convenience runner to start Streamlit.
- dou_snaptrack/05_cascade_cli.py — unified CLI orchestrator.
- dou_snaptrack/constants.py — constants referenced by utils.
- dou_snaptrack/utils/* — browser and DOM helpers used by UI/CLI.
- dou_snaptrack/cli/batch.py — batch execution.
- dou_snaptrack/cli/listing.py — list mode.
- dou_snaptrack/cli/map_page.py — on-demand page scanner (developer tooling).
- dou_snaptrack/cli/map_pairs.py — pairs mapper CLI.
- dou_snaptrack/cli/plan_from_pairs.py — plan from precomputed N1→N2 pairs.
- dou_snaptrack/cli/plan_live.py — plan based on live dropdowns (UI depends on it).
- dou_snaptrack/cli/reporting.py — consolidate/split reporting (UI and CLI use it).
- dou_snaptrack/cli/runner.py — single run execution with bulletin support.
- dou_snaptrack/cli/summary_config.py — summary configuration model.
- dou_snaptrack/mappers/page_mapper.py — used by map_page CLI.
- dou_snaptrack/mappers/pairs_mapper.py — used by map_pairs CLI.
- dou_snaptrack/adapters/services.py — adapters to dou_utils services (EditionRunnerService, planning).
- dou_snaptrack/adapters/utils.py — adapters for bulletin and summarization.

- dou_utils/* — referenced by multiple modules (page_utils, selection/query/detail/logging, services).
  - dou_utils/services/edition_runner_service.py — core run logic used by runner.
  - dou_utils/services/cascade_service.py — detail scraping and dedup.
  - dou_utils/services/planning_service.py — used by plan/map flows.
  - dou_utils/dropdown_strategies.py — discovery and open/list options for dropdowns.
  - dou_utils/page_utils.py, dom/query/detail/selection/hash/log_utils/etc. — infrastructure used by services and utils.

## Candidates for deprecation (no direct references in UI/CLI)
- dou_utils/services/cascade_executor.py — legacy executor; tests reference it but current runner uses cascade_service instead.
- dou_utils/services/multi_level_cascade_service.py — used by EditionRunnerService; KEEP for now.
- dou_utils/services/dropdown_mapper_service.py — not referenced by UI/CLI directly; provides an alternative to map_pairs/map_page; consider KEEP if used externally, else deprecate later.
- dou_snaptrack/mappers/page_mapper.py — developer tool only; KEEP unless we remove map_page CLI.
- dou_snaptrack/ui/launch.py — optional convenience; KEEP.

## Notes
- Several test files under dou_utils/core/tests reference legacy services; they are safe to keep for validation but not required by end-user distribution.
- If we aim to slim down the package for distribution-only, we can exclude tests and developer-only CLIs from installer payloads.
- A next pass should build a static import graph (e.g., with ast) and dynamic coverage from UI smoke runs to confirm.

## Next steps
1) Confirm external consumers: check if dropdown_mapper_service or cascade_executor are used by any external scripts; if not, mark DEPRECATE.
2) Add a small "public API" doc listing supported entry points and services.
3) Optionally move dev-only CLIs (map_page/map_pairs) under a "tools/" group in packaging.
