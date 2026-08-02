# SEO-INDEX VariScripts v1.4.0

Version 1.4 adds a comprehensive single-page quality lane and hardens every network boundary used by the local graphical workbench.

## Headline feature: Page Quality Audit

```bash
seo-index page \
  --url 'https://example.com/page' \
  --json './reports/page-quality.json' \
  --markdown './reports/page-quality.md'
```

The report groups more than 20 checks across eligibility, search presentation, social previews, images, content and accessibility, delivery, and browser security. Output budgets are transparent heuristics and are not represented as ranking rules or Core Web Vitals.

The same scan is available in `seo-index serve`, alongside Internal Link Graph. Live requests remain local, token protected, concurrency limited, and private-network restricted by default.

## Network hardening

- validates the initial URL and every redirect before opening it
- applies the same public-target rule to discovered and nested sitemap files
- prevents a same-site crawl from following redirects outside its configured host scope
- limits gzip bodies after decompression
- decodes declared HTTP/HTML character sets
- preserves valid IPv6 URL authorities

## Crawler intelligence

Crawler Access Matrix now distinguishes discovery, advertising, training, and user-directed agents, including OAI-AdsBot, Claude-SearchBot, Claude-User, and Perplexity-User.

## Engineering quality

- 20 deterministic tests
- Linux, Windows, and macOS CI
- Python 3.10, 3.12, and 3.14 coverage
- shell, PowerShell, JavaScript, and JSON syntax gates
- one canonical Python implementation behind both current and legacy launchers
