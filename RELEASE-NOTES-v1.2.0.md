# SEO-INDEX VariScripts 1.2.0

## Headline changes

- category-based, confidence-aware scoring matrix
- Redirect Lab
- Crawler Access Matrix
- Hreflang Auditor
- Structured Data Graph
- GEO entity-discoverability audit
- AEO answer-extractability audit
- graphical GitHub Pages workbench
- stronger Windows Python discovery and installer validation

## Compatibility

Existing commands remain available:

- `score`
- `canonical`
- `sitemap`
- `indexnow`
- `interactive`
- `list-engines`

New commands:

- `redirect`
- `robots`
- `hreflang`
- `schema`
- `geo`
- `aeo`
- `web`

The JSON score output adds `verified_score`, `assured_score`, and `categories`. `normalized_score` remains present and now mirrors the assured score for compatibility.

## Upgrade validation

```bash
python3 -m py_compile './Py+Linux/Scripts/'*.py
python3 ./Tests/test_toolkit.py
seo-index --no-splash list-engines
seo-index web --print-only
```
