# SEO-INDEX VariScripts

A dependency-light, cross-platform indexing and technical SEO toolkit for Windows, macOS, and Linux.

It combines the original sitemap-to-IndexNow runners with a semi-graphical terminal interface, engine-specific index-readiness scoring, canonical auditing, sitemap diagnostics, JSON/Markdown reports, and one-command installers.

```text
          /\_/\
         ( o.o )     ~~~~)
          > ^ <
╭──────────────────────────────────────────────────────────╮
│              SEO-INDEX VariScripts v1.1.0                │
│ foulfoxhacks  •  aka The Dev Sammy                       │
│ Search signals, untangled.                               │
╰──────────────────────────────────────────────────────────╯
```

## Important score disclaimer

The Google, Bing, and general scores are **transparent diagnostic readiness scores**, not official scores issued by a search engine. They do not predict ranking and do not guarantee crawling or indexing.

The tool reports each check, its profile weight, the points earned, and how much of the profile was actually verified. A critical failure such as a non-200 page, a crawler block, or `noindex` caps the result below 50.

## Toolkit features

- Semi-graphical interactive terminal menu
- Animated fox-tail splash, automatically static in non-interactive terminals
- Google-specific, Bing-specific, and general index-readiness profiles
- Canonical Guard for redirects, final URLs, hosts, and `rel=canonical`
- Sitemap Doctor for XML, sitemap indexes, GZip, duplicates, hosts, fragments, `lastmod`, status codes, and redirects
- Page indexability checks for HTTP status, robots.txt, robots meta, `X-Robots-Tag`, canonical, crawlable text, title, description, H1, viewport, and JSON-LD
- Existing IndexNow submission runner available through the unified CLI
- JSON and Markdown reports
- Scriptable exit codes for CI
- PowerShell, shell, macOS `.command`, Python, and installed `seo-index` entry points
- No third-party Python packages required

## Installation

### Windows one-liner

PowerShell users can install directly from the public repository:

```powershell
irm https://raw.githubusercontent.com/foulfoxhacks/SEO-INDEX-VariScripts/main/install.ps1 | iex
```

Because `iex` executes downloaded code immediately, a review-first installation is safer:

```powershell
irm https://raw.githubusercontent.com/foulfoxhacks/SEO-INDEX-VariScripts/main/install.ps1 -OutFile install.ps1
Get-Content .\install.ps1
.\install.ps1
```

Open a new terminal after installation, then run:

```powershell
seo-index
```

### macOS and Linux one-liner

```bash
curl -fsSL https://raw.githubusercontent.com/foulfoxhacks/SEO-INDEX-VariScripts/main/install.sh | sh
```

The installer creates `~/.local/bin/seo-index`. Add that directory to `PATH` if your shell does not already include it.

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
./Py+Linux/Scripts/seo-index-toolkit.sh
```

Python:

```bash
python3 './Py+Linux/Scripts/seo_index_toolkit.py'
```

Running without a subcommand opens the interactive menu. From the repository root you may also use `./seo-index` on macOS/Linux or `seo-index.cmd` on Windows.

## Engine-specific index-readiness score

### All profiles

```bash
seo-index score \
  --url 'https://example.com/about' \
  --sitemap 'https://example.com/sitemap.xml' \
  --key-location 'https://example.com/indexnow-key.txt' \
  --engine all
```

### Google profile

```bash
seo-index score \
  --url 'https://example.com/about' \
  --sitemap 'https://example.com/sitemap.xml' \
  --engine google
```

The Google profile emphasizes the published minimum technical requirements, crawler access, index directives, canonical consistency, indexable content, sitemap inclusion, HTTPS, mobile viewport metadata, titles, descriptions, headings, structured data, and sitemap freshness.

Google is not scored on IndexNow readiness.

### Bing profile

```bash
seo-index score \
  --url 'https://example.com/about' \
  --sitemap 'https://example.com/sitemap.xml' \
  --key-location 'https://example.com/indexnow-key.txt' \
  --engine bing
```

The Bing profile gives additional weight to sitemap discovery, accurate freshness signals, and IndexNow readiness.

### Reports and CI threshold

```bash
seo-index score \
  --url 'https://example.com/about' \
  --engine all \
  --json './reports/about.json' \
  --markdown './reports/about.md' \
  --fail-below 75
```

Exit codes:

- `0`: completed and met the requested threshold
- `1`: validation, parsing, or network setup error
- `2`: audit completed but failed a requested threshold or found critical audit issues
- `130`: cancelled

## Canonical Guard

Audit sitemap URLs for redirect and canonical-host disagreements:

```bash
seo-index canonical \
  --sitemap 'https://example.com/sitemap.xml' \
  --expected-host 'example.com' \
  --limit 200 \
  --workers 8 \
  --json './reports/canonical.json'
```

Set `--limit 0` to check every URL.

PowerShell script endpoint:

```powershell
.\Win\Test-CanonicalSignals.ps1 `
  -Sitemap 'https://example.com/sitemap.xml' `
  -ExpectedHost 'example.com' `
  -Limit 200
```

## Sitemap Doctor

Validate structure and optionally request sitemap URLs:

```bash
seo-index sitemap \
  --sitemap 'https://example.com/sitemap.xml' \
  --check-pages 100 \
  --workers 8 \
  --json './reports/sitemap.json'
```

PowerShell script endpoint:

```powershell
.\Win\Test-SitemapHealth.ps1 `
  -Sitemap 'https://example.com/sitemap.xml' `
  -CheckPages 100
```

## Direct scoring scripts

Windows:

```powershell
.\Win\Get-IndexReadinessScore.ps1 `
  -Url 'https://example.com/about' `
  -Engine all `
  -Sitemap 'https://example.com/sitemap.xml' `
  -KeyLocation 'https://example.com/indexnow-key.txt'
```

Linux/macOS shell endpoints:

```bash
'./Py+Linux/Scripts/index-readiness-score.sh' --url 'https://example.com/about' --engine all
'./Py+Linux/Scripts/canonical-guard.sh' --sitemap 'https://example.com/sitemap.xml'
'./Py+Linux/Scripts/sitemap-doctor.sh' --sitemap 'https://example.com/sitemap.xml'
```

## IndexNow through the unified CLI

Dry run:

```bash
seo-index indexnow \
  --sitemap 'https://example.com/sitemap.xml' \
  --key-location 'https://example.com/indexnow-key.txt' \
  --dry-run
```

Live submission:

```bash
seo-index indexnow \
  --sitemap 'https://example.com/sitemap.xml' \
  --key-location 'https://example.com/indexnow-key.txt'
```

The original standalone runners remain available:

- `Win/Submit-IndexNow.ps1`
- `Py+Linux/Scripts/indexnow_runner.py`
- `Py+Linux/Scripts/submit-indexnow-linux.sh`
- `MacOS/submit-indexnow-macos.command`

## Splash controls

```bash
seo-index --no-animation score --url 'https://example.com' --engine google
seo-index --no-splash score --url 'https://example.com' --engine google
seo-index --no-color score --url 'https://example.com' --engine google
```

`NO_COLOR=1` also disables ANSI colors.

## Custom search-engine profiles

Profiles live in `Config/engine_profiles.json`. Each profile defines:

- Display label
- Crawler user-agent
- Factor weights totaling 100
- Critical checks that can cap the score

Load another profile file with:

```bash
seo-index --profile-file './Config/my_profiles.json' list-engines
```

Only Google, Bing, and general profiles are bundled initially. Additional engines should be added only after their current official documentation is reviewed.

## Repository layout

```text
SEO-INDEX-VariScripts/
├── Config/
│   ├── engine_profiles.json
│   └── custom_engine_profile.example.json
├── MacOS/
│   ├── seo-index-toolkit.command
│   └── submit-indexnow-macos.command
├── Py+Linux/Scripts/
│   ├── seo_index_toolkit.py
│   ├── seo-index-toolkit.sh
│   ├── index-readiness-score.sh
│   ├── canonical-guard.sh
│   ├── sitemap-doctor.sh
│   ├── indexnow_runner.py
│   └── submit-indexnow-linux.sh
├── Tests/
│   └── test_toolkit.py
├── Win/
│   ├── Start-SEOIndexToolkit.ps1
│   ├── Get-IndexReadinessScore.ps1
│   ├── Test-CanonicalSignals.ps1
│   ├── Test-SitemapHealth.ps1
│   └── Submit-IndexNow.ps1
├── seo-index
├── seo-index.cmd
├── install.ps1
├── install.sh
├── CHANGELOG.md
├── LICENSE
└── README.md
```

## Tests

```bash
python3 ./Tests/test_toolkit.py
python3 -m py_compile './Py+Linux/Scripts/seo_index_toolkit.py'
```

## Official references

- Google Search Essentials and technical requirements: https://developers.google.com/search/docs/essentials
- Google canonicalization: https://developers.google.com/search/docs/crawling-indexing/canonicalization
- Google robots metadata: https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag
- Google sitemaps: https://developers.google.com/search/docs/crawling-indexing/sitemaps/overview
- Bing Webmaster Guidelines: https://www.bing.com/webmasters/help/webmaster-guidelines-30fba23a
- Bing robots metadata: https://www.bing.com/webmasters/help/robots-meta-tags-and-attributes-that-bing-supports-5198d240
- IndexNow documentation: https://www.indexnow.org/documentation

## License

See `LICENSE`.
