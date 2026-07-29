# SEO-INDEX VariScripts v1.3.0

## Site intelligence arrives

This release adds the first site-wide diagnostic layer to SEO-INDEX VariScripts.

### Internal Link Graph

```bash
seo-index links --url https://example.com --sitemap https://example.com/sitemap.xml --html report.html
```

The crawler stays on the selected host, respects robots.txt by default, and maps internal relationships, click depth, orphan candidates, redirects, broken pages, canonical drift, noindex pages, dead ends, duplicate titles, generic anchors, and internal importance.

### Local live workbench

```bash
seo-index serve
```

The same workbench used on GitHub Pages is served from localhost with a random session token. Local mode can run a live Internal Link Graph without sending audit targets or reports to a hosted proxy.

### Report compatibility

Link Graph reports use schema version 3.0 and can be opened in the workbench report viewer or the standalone interactive HTML renderer.
