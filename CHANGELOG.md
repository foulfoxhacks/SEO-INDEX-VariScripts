# Changelog

## 1.3.0 - 2026-07-29

### Added

- Internal Link Graph same-site crawler with depth, incoming/outgoing edges, dead ends, redirects, broken pages, sitemap orphan candidates, generic anchors, noindex pages, canonical drift, duplicate titles, and PageRank-style importance
- standalone interactive HTML relationship reports plus JSON schema v3 reports
- `seo-index serve` localhost workbench with a token-protected live audit API
- local live-mode dashboard and graph canvas in the web workbench
- Windows, Linux, and macOS launchers for the graph and local server
- nine-test deterministic fixture suite
- `.gitattributes` line-ending policy for cross-platform launchers

### Changed

- hosted workbench URL now targets `https://webtools.mellozone.site/`
- workbench tool catalog and command builder now include site intelligence and local live mode
- installer validation now checks the site-intelligence module and workbench assets
- graphical workbench Content Security Policy remains HTTPS-safe while allowing same-origin localhost API calls

### Security

- local server binds to loopback by default
- live API requires a random session token and same-origin requests
- private, loopback, link-local, and reserved audit targets are blocked unless explicitly enabled
- browser API page limits, request-size limits, response-size limits, timeouts, and single-crawl locking are enforced

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
