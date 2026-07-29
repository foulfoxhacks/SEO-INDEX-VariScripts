# Changelog

## 1.2.0 - 2026-07-29

### Added

- category-based scoring matrix schema v2
- verified score, evidence coverage, and assured score
- Google, Bing, general, GEO, and AEO category profiles
- Redirect Lab with loops, hop count, status semantics, host changes, and HTTPS downgrade checks
- Crawler Access Matrix for search and AI crawler user agents
- Hreflang Auditor with reciprocity checks
- Structured Data Graph inspector
- focused GEO entity-discoverability audit
- focused AEO answer-extractability audit
- Windows, shell, and macOS direct script endpoints
- GitHub Pages graphical workbench
- CLI command builder, matrix explorer, JSON report viewer, and offline browser lab
- GitHub Pages deployment workflow
- expanded six-test deterministic fixture suite

### Changed

- score thresholds now use the assured score
- scoring output includes per-category scorecards
- flat v1 profiles remain readable, while bundled profiles use schema v2
- Windows launcher searches common Python installation paths and ignores Microsoft Store aliases
- Windows installer validates required toolkit files before reporting success
- interactive menu expanded without duplicating existing Canonical Guard, Sitemap Doctor, or IndexNow features

### Notes

- GEO and AEO are explicitly labeled experimental readiness lenses, not official engine scores.
- `llms.txt` is treated as optional and non-standard.

## 1.1.0 - 2026-07-29

- semi-graphical terminal interface
- fox-tail splash
- initial Google, Bing, and general readiness scores
- Canonical Guard
- Sitemap Doctor
- unified IndexNow entry point
- JSON and Markdown reports
- one-command installers

## 1.0.0

- public PowerShell, Python, Linux, and macOS sitemap-to-IndexNow runners
