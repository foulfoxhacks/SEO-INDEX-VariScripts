# SEO-INDEX VariScripts

A dependency-light, cross-platform indexing, technical SEO, GEO, and AEO diagnostic toolkit for Windows, macOS, Linux, CI, and GitHub Pages.

```text
          /\_/\
         ( o.o )     ~~~~)
          > ^ <
╭──────────────────────────────────────────────────────────╮
│              SEO-INDEX VariScripts v1.3.0                │
│ foulfoxhacks  •  aka The Dev Sammy                       │
│ Search signals, untangled.                               │
╰──────────────────────────────────────────────────────────╯
```

## What v1.3 adds

### Internal Link Graph

`seo-index links` crawls one canonical host and produces a site-level relationship report rather than another single-page checklist. It includes:

- internal and external edge inventory
- click depth and dead-end detection
- sitemap-to-crawl orphan candidates
- discovered pages missing from the sitemap
- broken pages and links to redirects
- `noindex` and canonical mismatch findings
- generic anchor-text findings
- duplicate title clusters
- a lightweight PageRank-style internal importance score
- JSON evidence and a standalone interactive HTML graph
- robots.txt compliance, request delays, page/depth caps, and optional query collapsing

### Local graphical workbench

`seo-index serve` opens the same workbench from `127.0.0.1` and enables a token-protected live audit API. The hosted GitHub Pages copy remains static; localhost mode can run Internal Link Graph without a cloud proxy.

Safety defaults:

- loopback-only binding
- random session token
- same-origin API checks
- one crawl at a time
- response and request size limits
- private, loopback, link-local, and reserved audit targets blocked unless explicitly enabled
- configurable API page ceiling

## What v1.2 added

The toolkit is now organized by diagnostic category instead of cloning the same check into several differently named scripts.

### Technical SEO

- **Redirect Lab**: complete redirect chain, loops, hop count, permanent versus temporary status, host transitions, HTTPS downgrades, and final status
- **Crawler Access Matrix**: Googlebot, bingbot, OAI-SearchBot, ClaudeBot, PerplexityBot, GPTBot, or custom user agents
- **Hreflang Auditor**: syntax, duplicates, self-reference, alternate status, and reciprocal declarations
- **Structured Data Graph**: JSON-LD syntax, Schema.org types, contexts, duplicate `@id`, and `sameAs`
- Existing Canonical Guard, Sitemap Doctor, indexability scoring, and IndexNow submission remain intact

### GEO diagnostics

- AI-search crawler access
- Organization, Person, and WebSite entity signals
- `sameAs` identity connections
- About, Contact, Team, Staff, and editorial pathways
- authorship and review signals
- publication, modification, and review dates
- source-labelled outbound references
- machine-readable page identity
- optional `llms.txt` visibility, clearly marked experimental

### AEO diagnostics

- question-oriented headings
- concise paragraph-sized answer blocks
- lists and tables
- FAQPage and QAPage schema
- speakable markup
- authorship, sources, and freshness
- semantic heading hierarchy
- answer-source eligibility

### Graphical workbench

The `docs/` directory contains a responsive static GitHub Pages interface with:

- category-filtered tool catalog
- Windows, Linux, and macOS command builder
- score-matrix explorer
- local JSON report viewer
- pasted HTML and response-header analyzer
- pasted robots.txt evaluator
- Redirect Lab JSON visualizer
- animated fox-tail branding

The hosted page does not proxy arbitrary websites. It analyzes pasted evidence and CLI-generated JSON in the browser. Run `seo-index serve` to open a localhost copy that can call the local live-audit API without mixed-content or CORS detours.

## Important score disclaimer

Google, Bing, general-search, GEO, and AEO scores are **transparent diagnostic readiness scores**. They are not issued by a search engine or answer engine, do not predict ranking or citation, and do not guarantee crawling or indexing.

## Scoring matrix v2

The old flat matrix has been replaced by category scorecards.

Every profile defines:

1. categories totaling 100 points
2. factors totaling 100 percent within each category
3. critical eligibility checks
4. a crawler identity appropriate to the profile

The report shows three distinct values:

- **Verified score**: performance on checks the tool could actually verify
- **Evidence coverage**: how much of the 100-point profile was verified
- **Assured score**: `verified score × sqrt(evidence coverage)`

The assurance adjustment prevents a 95/100 result based on only a handful of available checks. Unknown checks do not count as failures, but they lower evidence coverage and therefore lower the assured score. A critical failure such as an unsuccessful page, blocked crawler, `noindex`, or non-indexable content type caps the result below 50.

Detailed methodology: [`docs/SCORING-METHODOLOGY.md`](docs/SCORING-METHODOLOGY.md)

Bundled profiles:

| Profile | Type | Primary emphasis |
|---|---|---|
| `google` | search engine | eligibility, canonical integrity, content, discovery, structured data |
| `bing` | search engine | eligibility plus stronger sitemap, freshness, and IndexNow coverage |
| `generic` | search-neutral | portable crawl and index readiness |
| `geo` | readiness lens | AI-search access, entity clarity, sources, freshness, machine readability |
| `aeo` | readiness lens | answer structure, semantic answer markup, trust, freshness, extractability |

## Installation

### Windows

```powershell
irm https://raw.githubusercontent.com/foulfoxhacks/SEO-INDEX-VariScripts/main/install.ps1 | iex
```

The installer now validates the required Python core and extension files before reporting success. The Windows launcher searches PATH and common per-user Python installation directories, avoiding the Microsoft Store placeholder aliases.

Review-first installation:

```powershell
irm https://raw.githubusercontent.com/foulfoxhacks/SEO-INDEX-VariScripts/main/install.ps1 -OutFile install.ps1
Get-Content .\install.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

### macOS and Linux

```bash
curl -fsSL https://raw.githubusercontent.com/foulfoxhacks/SEO-INDEX-VariScripts/main/install.sh | sh
```

### Run without installing

Windows:

```powershell
.\Win\Start-SEOIndexToolkit.ps1
```

macOS:

```bash
chmod +x ./MacOS/seo-index-toolkit.command
./MacOS/seo-index-toolkit.command
```

Linux:

```bash
chmod +x './Py+Linux/Scripts/seo-index-toolkit.sh'
'./Py+Linux/Scripts/seo-index-toolkit.sh'
```

## Interactive terminal

```bash
seo-index
```

Menu:

```text
  1. Index readiness score
  2. Canonical Guard
  3. Sitemap Doctor
  4. IndexNow submission runner
  5. Redirect Lab
  6. Crawler Access Matrix
  7. Hreflang Auditor
  8. Structured Data Graph
  9. GEO / Entity Discoverability
 10. AEO / Answer Extractability
 11. Internal Link Graph
 12. Start local graphical workbench
 13. List scoring profiles
 14. Open hosted graphical workbench
```

## Core commands

### Category scorecards

```bash
seo-index score \
  --url 'https://example.com/about' \
  --sitemap 'https://example.com/sitemap.xml' \
  --key-location 'https://example.com/indexnow-key.txt' \
  --engine all \
  --json './reports/about.json' \
  --markdown './reports/about.md'
```

Focused profiles:

```bash
seo-index score --url 'https://example.com' --engine google
seo-index score --url 'https://example.com' --engine bing --key-location 'https://example.com/key.txt'
seo-index score --url 'https://example.com' --engine geo
seo-index score --url 'https://example.com/faq' --engine aeo
```

### Internal Link Graph

```bash
seo-index links \
  --url 'https://example.com/' \
  --sitemap 'https://example.com/sitemap.xml' \
  --max-pages 500 \
  --max-depth 7 \
  --json './reports/internal-links.json' \
  --html './reports/internal-links.html'
```

Windows endpoint:

```powershell
.\Win\Test-InternalLinkGraph.ps1 `
  -Url 'https://example.com/' `
  -Sitemap 'https://example.com/sitemap.xml' `
  -Json '.\reports\internal-links.json' `
  -Html '.\reports\internal-links.html'
```

The crawler respects `robots.txt` by default and stays on the selected host. Use `--include-subdomains`, `--drop-query`, or `--follow-nofollow` only when those choices match the intended audit scope.

### Local live workbench

```bash
seo-index serve
```

The command opens a tokenized localhost URL, usually:

```text
http://127.0.0.1:8765/?token=...
```

Useful options:

```bash
seo-index serve --port 9000 --api-max-pages 1000
seo-index serve --no-open
seo-index serve --allow-private-targets
```

`--allow-private-targets` is intentionally opt-in for local development sites and intranet audits.

### Redirect Lab

```bash
seo-index redirect \
  --url 'http://example.com/old-page' \
  --max-hops 10 \
  --json './reports/redirect.json'
```

Windows script endpoint:

```powershell
.\Win\Test-RedirectChain.ps1 -Url 'http://example.com/old-page' -Json '.\reports\redirect.json'
```

### Crawler Access Matrix

```bash
seo-index robots --url 'https://example.com/page'
```

Custom agents:

```bash
seo-index robots \
  --url 'https://example.com/page' \
  --agent Googlebot \
  --agent OAI-SearchBot \
  --agent ClaudeBot
```

### Hreflang Auditor

```bash
seo-index hreflang \
  --url 'https://example.com/en/' \
  --check-alternates \
  --limit 30 \
  --json './reports/hreflang.json'
```

### Structured Data Graph

```bash
seo-index schema --url 'https://example.com/about'
seo-index schema --url 'https://example.com/about' --show-json
```

### GEO focused audit

```bash
seo-index geo \
  --url 'https://example.com/about' \
  --json './reports/geo.json'
```

### AEO focused audit

```bash
seo-index aeo \
  --url 'https://example.com/faq' \
  --json './reports/aeo.json'
```

### Open the graphical workbench

```bash
seo-index web
seo-index web --print-only
```

### Existing tools

```bash
seo-index canonical --sitemap 'https://example.com/sitemap.xml' --expected-host example.com
seo-index sitemap --sitemap 'https://example.com/sitemap.xml' --check-pages 100
seo-index indexnow --sitemap 'https://example.com/sitemap.xml' --key-location 'https://example.com/key.txt' --dry-run
```

## Direct script endpoints

Windows:

```text
Win/Test-RedirectChain.ps1
Win/Test-CrawlerAccess.ps1
Win/Test-Hreflang.ps1
Win/Test-StructuredData.ps1
Win/Test-GEOReadiness.ps1
Win/Test-AEOReadiness.ps1
```

Linux/macOS shell endpoints:

```text
Py+Linux/Scripts/redirect-audit.sh
Py+Linux/Scripts/robots-audit.sh
Py+Linux/Scripts/hreflang-audit.sh
Py+Linux/Scripts/schema-audit.sh
Py+Linux/Scripts/geo-audit.sh
Py+Linux/Scripts/aeo-audit.sh
```

macOS clickable launchers:

```text
MacOS/redirect-lab.command
MacOS/geo-audit.command
MacOS/aeo-audit.command
```

## Publish the graphical workbench

1. Push the `docs/` directory and `.github/workflows/pages.yml` to `main`.
2. Open the repository on GitHub.
3. Go to **Settings → Pages**.
4. Set **Source** to **GitHub Actions**.
5. Run the workflow manually or push a change under `docs/`.

The configured custom-domain address is:

```text
https://webtools.mellozone.site/
```

GitHub's project-site fallback is `https://foulfoxhacks.github.io/SEO-INDEX-VariScripts/`. The custom hostname must resolve by CNAME to `foulfoxhacks.github.io` before GitHub can provision HTTPS.

The workflow deploys only `docs/`, not the installer or source tree.

## Reports and CI

```bash
seo-index score \
  --url 'https://example.com' \
  --engine google \
  --json './reports/google.json' \
  --fail-below 75
```

Exit codes:

- `0`: completed and met the requested threshold
- `1`: validation, parsing, setup, or network error
- `2`: audit completed but found critical issues or failed the requested threshold
- `130`: cancelled

## Repository layout

```text
SEO-INDEX-VariScripts/
├── .github/workflows/pages.yml
├── Config/
│   ├── engine_profiles.json
│   └── custom_engine_profile.example.json
├── docs/
│   ├── index.html
│   ├── matrix.json
│   ├── SCORING-METHODOLOGY.md
│   └── assets/
├── MacOS/
│   ├── internal-link-graph.command
│   ├── serve-workbench.command
│   └── ...
├── Py+Linux/Scripts/
│   ├── seo_index_toolkit.py
│   ├── seo_index_extensions.py
│   ├── seo_index_site.py
│   ├── internal-link-graph.sh
│   ├── serve-workbench.sh
│   └── ...
├── Tests/test_toolkit.py
├── Win/
│   ├── Test-InternalLinkGraph.ps1
│   ├── Start-SEOIndexServer.ps1
│   └── ...
├── install.ps1
├── install.sh
├── seo-index
└── seo-index.cmd
```

## Tests

```bash
python3 -m py_compile './Py+Linux/Scripts/'*.py
python3 ./Tests/test_toolkit.py  # 9 deterministic tests
bash -n ./Py+Linux/Scripts/*.sh ./MacOS/*.command ./install.sh ./seo-index
```

## Official references

- Google Search technical requirements: https://developers.google.com/search/docs/essentials/technical
- Google canonicalization: https://developers.google.com/search/docs/crawling-indexing/canonicalization
- Google robots metadata: https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag
- Google sitemaps: https://developers.google.com/search/docs/crawling-indexing/sitemaps/overview
- Bing Webmaster guidance: https://www.bing.com/webmasters/help/webmaster-guidelines-30fba23a
- Bing sitemaps: https://www.bing.com/webmasters/help/sitemaps-3b5cf6ed
- IndexNow: https://www.indexnow.org/documentation
- OpenAI publisher crawler guidance: https://help.openai.com/en/articles/12627856-publishers-and-developers-faq
- Anthropic crawler guidance: https://support.anthropic.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler
- Perplexity crawlers: https://docs.perplexity.ai/docs/resources/perplexity-crawlers
- Schema.org: https://schema.org/docs/documents.html
- GitHub Pages custom workflows: https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages

## License

MIT. See `LICENSE`.
