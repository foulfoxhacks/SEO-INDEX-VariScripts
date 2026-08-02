#!/usr/bin/env python3
"""Site intelligence and local graphical server for SEO-INDEX VariScripts.

The module is intentionally dependency-free and provides two distinct features:

* Internal Link Graph: a same-site crawler that maps page relationships, crawl
  depth, orphan candidates, redirects, broken destinations, canonical drift,
  dead ends, generic anchors, and a lightweight PageRank-style importance score.
* Local Workbench Server: serves the repository's graphical workbench from
  localhost and exposes a token-protected API for live Internal Link Graph runs.

The crawler is an auditor, not a high-volume spider. It respects robots.txt by
Default, applies page/depth/response limits, and stays on the selected host.
"""
from __future__ import annotations

import argparse
import collections
import html
import ipaddress
import json
import secrets
import socket
import threading
import time
import urllib.parse
import urllib.robotparser
import webbrowser
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urljoin, urlsplit, urlunsplit

import seo_index_extensions as extensions
import seo_index_toolkit as core

SKIP_EXTENSIONS = {
    ".7z", ".avi", ".avif", ".bin", ".bmp", ".css", ".csv", ".dmg",
    ".doc", ".docx", ".eot", ".exe", ".flac", ".gif", ".gz", ".ico",
    ".iso", ".jpeg", ".jpg", ".js", ".json", ".m4a", ".m4v", ".map",
    ".mkv", ".mov", ".mp3", ".mp4", ".mpeg", ".mpg", ".ogg", ".otf",
    ".pdf", ".png", ".ppt", ".pptx", ".rar", ".rss", ".svg", ".tar",
    ".tgz", ".tif", ".tiff", ".ttf", ".txt", ".wav", ".webm", ".webp",
    ".woff", ".woff2", ".xls", ".xlsx", ".xml", ".zip",
}
GENERIC_ANCHORS = {
    "click here", "here", "learn more", "more", "read more", "details",
    "this page", "link", "website", "continue", "view", "open",
}


@dataclass
class GraphEdge:
    source: str
    target: str
    resolved_target: str = ""
    text: str = ""
    rel: list[str] = field(default_factory=list)
    nofollow: bool = False
    external: bool = False


@dataclass
class GraphPage:
    url: str
    requested_url: str
    final_url: str
    status: int
    depth: int
    title: str = ""
    canonical: str = ""
    content_type: str = ""
    elapsed_ms: int = 0
    noindex: bool = False
    error: str = ""
    incoming: int = 0
    outgoing: int = 0
    pagerank: float = 0.0


@dataclass
class LinkGraphReport:
    schema_version: str
    tool: str
    tool_version: str
    generated_at: str
    start_url: str
    allowed_host: str
    settings: dict[str, Any]
    summary: dict[str, Any]
    pages: list[GraphPage]
    edges: list[GraphEdge]
    sitemap_urls: list[str]
    findings: dict[str, list[Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "tool": self.tool,
            "toolVersion": self.tool_version,
            "generatedAt": self.generated_at,
            "startUrl": self.start_url,
            "allowedHost": self.allowed_host,
            "settings": self.settings,
            "summary": self.summary,
            "pages": [asdict(page) for page in self.pages],
            "edges": [asdict(edge) for edge in self.edges],
            "sitemapUrls": self.sitemap_urls,
            "findings": self.findings,
        }


def _host_matches(host: str, allowed_host: str, include_subdomains: bool) -> bool:
    host = host.lower().rstrip(".")
    allowed_host = allowed_host.lower().rstrip(".")
    return host == allowed_host or (include_subdomains and host.endswith("." + allowed_host))


def normalize_link(value: str, base_url: str, drop_query: bool = False) -> Optional[str]:
    """Resolve and normalize one crawlable HTTP(S) link."""
    raw = (value or "").strip()
    if not raw or raw.startswith(("#", "mailto:", "tel:", "sms:", "javascript:", "data:")):
        return None
    joined = urljoin(base_url, raw)
    parsed = urlsplit(joined)
    if parsed.scheme.lower() not in core.SUPPORTED_SCHEMES or not parsed.hostname:
        return None
    host = parsed.hostname.encode("idna").decode("ascii").lower()
    try:
        port = parsed.port
    except ValueError:
        return None
    if (parsed.scheme.lower() == "http" and port == 80) or (parsed.scheme.lower() == "https" and port == 443):
        port = None
    netloc = host if port is None else f"{host}:{port}"
    path = parsed.path or "/"
    query = "" if drop_query else parsed.query
    return urlunsplit((parsed.scheme.lower(), netloc, path, query, ""))


def _should_skip_path(url: str) -> bool:
    path = urlsplit(url).path.lower()
    suffix = Path(path).suffix
    return suffix in SKIP_EXTENSIONS


def _noindex(fetch: core.FetchResult, signals: core.HtmlSignals) -> bool:
    header = core.parse_directives(fetch.headers.get("x-robots-tag", ""))
    directives = set(header)
    for values in signals.meta_robots.values():
        directives.update(values)
    return "noindex" in directives or "none" in directives


def _robots_policy(start_url: str, timeout: int, user_agent: str) -> tuple[Optional[urllib.robotparser.RobotFileParser], str, int]:
    robots_url = core.origin_for(start_url) + "/robots.txt"
    fetched = core.fetch_url(robots_url, timeout, user_agent, accept="text/plain,*/*", max_bytes=2 * 1024 * 1024)
    if fetched.status != 200:
        return None, robots_url, fetched.status
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(fetched.text.splitlines())
    return parser, robots_url, fetched.status


def _sitemap_inventory(
    start_url: str,
    explicit_sitemap: Optional[str],
    robots_text: str,
    timeout: int,
    user_agent: str,
    max_entries: int,
    url_validator: Optional[Callable[[str], None]] = None,
) -> tuple[list[str], list[str]]:
    candidates: list[str] = []
    if explicit_sitemap:
        candidates.append(explicit_sitemap)
    else:
        candidates.extend(core.sitemap_urls_from_robots(robots_text))
        candidates.append(core.origin_for(start_url) + "/sitemap.xml")
    seen: set[str] = set()
    errors: list[str] = []
    for candidate in candidates:
        try:
            candidate = core.normalize_url(candidate)
        except core.ToolkitError:
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        collection = core.fetch_sitemaps(
            [candidate], timeout, user_agent, max_sitemaps=1000,
            max_entries=max_entries,
            url_validator=url_validator,
        )
        errors.extend(collection.errors)
        if collection.entries:
            normalized_entries: set[str] = set()
            for entry in collection.entries:
                try:
                    normalized_entries.add(core.normalize_url(entry.url))
                except core.ToolkitError as exc:
                    errors.append(f"Invalid sitemap page URL {entry.url}: {exc}")
            return sorted(normalized_entries), errors
    return [], errors


def _compute_pagerank(pages: list[GraphPage], edges: list[GraphEdge]) -> None:
    nodes = {page.final_url for page in pages if page.final_url}
    if not nodes:
        return
    adjacency: dict[str, set[str]] = {node: set() for node in nodes}
    for edge in edges:
        target = edge.resolved_target or edge.target
        if not edge.external and edge.source in nodes and target in nodes:
            adjacency[edge.source].add(target)
    count = len(nodes)
    scores = {node: 1.0 / count for node in nodes}
    damping = 0.85
    for _ in range(30):
        dangling = sum(scores[node] for node, targets in adjacency.items() if not targets)
        next_scores = {node: (1.0 - damping) / count + damping * dangling / count for node in nodes}
        for source, targets in adjacency.items():
            if not targets:
                continue
            share = damping * scores[source] / len(targets)
            for target in targets:
                next_scores[target] += share
        scores = next_scores
    highest = max(scores.values()) or 1.0
    by_url = {page.final_url: page for page in pages}
    for url, score in scores.items():
        by_url[url].pagerank = round((score / highest) * 100, 2)


def crawl_internal_links(
    start_url: str,
    *,
    sitemap: Optional[str] = None,
    max_pages: int = 250,
    max_depth: int = 6,
    timeout: int = 20,
    user_agent: str = core.DEFAULT_USER_AGENT,
    robots_agent: str = "Googlebot",
    delay_ms: int = 75,
    include_subdomains: bool = False,
    ignore_robots: bool = False,
    follow_nofollow: bool = False,
    drop_query: bool = False,
    progress: Optional[Callable[[int, int, str], None]] = None,
    url_validator: Optional[Callable[[str], None]] = None,
) -> LinkGraphReport:
    """Crawl one host and return a deterministic site relationship report."""
    if not 1 <= max_pages <= 10000:
        raise core.ToolkitError("max_pages must be between 1 and 10,000.")
    if not 0 <= max_depth <= 50:
        raise core.ToolkitError("max_depth must be between 0 and 50.")
    if not 0 <= delay_ms <= 60000:
        raise core.ToolkitError("delay_ms must be between 0 and 60,000.")

    normalized_start = normalize_link(start_url, start_url, drop_query)
    if not normalized_start:
        raise core.ToolkitError("Start URL must be an absolute HTTP or HTTPS URL.")
    allowed_host = (urlsplit(normalized_start).hostname or "").lower()

    def validate_page_target(value: str) -> None:
        if url_validator:
            url_validator(value)
        target_host = (urlsplit(value).hostname or "").lower()
        if not _host_matches(target_host, allowed_host, include_subdomains):
            raise core.ToolkitError(f"Redirect left the configured crawl host: {value}")

    robots_parser: Optional[urllib.robotparser.RobotFileParser] = None
    robots_text = ""
    robots_url = core.origin_for(normalized_start) + "/robots.txt"
    robots_status = 0
    if not ignore_robots:
        fetched_robots = core.fetch_url(
            robots_url, timeout, user_agent, accept="text/plain,*/*",
            max_bytes=2 * 1024 * 1024, url_validator=url_validator,
        )
        robots_status = fetched_robots.status
        if fetched_robots.status == 200:
            robots_text = fetched_robots.text
            robots_parser = urllib.robotparser.RobotFileParser()
            robots_parser.set_url(robots_url)
            robots_parser.parse(robots_text.splitlines())

    sitemap_urls, sitemap_errors = _sitemap_inventory(
        normalized_start, sitemap, robots_text, timeout, user_agent,
        max_entries=min(1_000_000, max(10_000, max_pages * 20)),
        url_validator=url_validator,
    )

    queue: collections.deque[tuple[str, int]] = collections.deque([(normalized_start, 0)])
    queued = {normalized_start}
    visited: set[str] = set()
    pages: list[GraphPage] = []
    edges: list[GraphEdge] = []
    edge_keys: set[tuple[str, str, str]] = set()
    final_by_requested: dict[str, str] = {}

    while queue and len(pages) < max_pages:
        requested, depth = queue.popleft()
        if requested in visited:
            continue
        visited.add(requested)
        if robots_parser and not robots_parser.can_fetch(robots_agent, requested):
            pages.append(GraphPage(
                url=requested,
                requested_url=requested,
                final_url=requested,
                status=0,
                depth=depth,
                error=f"Blocked by {robots_url} for {robots_agent}",
            ))
            if progress:
                progress(len(pages), max_pages, requested)
            continue

        fetched = core.fetch_url(requested, timeout, user_agent, url_validator=validate_page_target)
        final_url = normalize_link(fetched.final_url or requested, requested, drop_query) or requested
        final_by_requested[requested] = final_url
        content_type = fetched.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        signals = core.parse_html(fetched) if "html" in content_type or not content_type else core.HtmlSignals()
        canonical = normalize_link(signals.canonical, final_url, drop_query) if signals.canonical else ""
        page = GraphPage(
            url=final_url,
            requested_url=requested,
            final_url=final_url,
            status=fetched.status,
            depth=depth,
            title=signals.title,
            canonical=canonical or "",
            content_type=content_type,
            elapsed_ms=fetched.elapsed_ms,
            noindex=_noindex(fetched, signals),
            error=fetched.error or "",
        )
        pages.append(page)
        if progress:
            progress(len(pages), max_pages, requested)

        is_html = fetched.status == 200 and ("html" in content_type or not content_type)
        if not is_html or depth >= max_depth:
            if delay_ms:
                time.sleep(delay_ms / 1000)
            continue

        extended = extensions.parse_extended_html(fetched)
        for link in extended.links:
            target = normalize_link(link.href, final_url, drop_query)
            if not target:
                continue
            target_host = (urlsplit(target).hostname or "").lower()
            external = not _host_matches(target_host, allowed_host, include_subdomains)
            rel = sorted(set(link.rel))
            nofollow = "nofollow" in rel
            key = (final_url, target, (link.text or "").strip())
            if key not in edge_keys:
                edge_keys.add(key)
                edges.append(GraphEdge(
                    source=final_url,
                    target=target,
                    text=(link.text or "").strip()[:500],
                    rel=rel,
                    nofollow=nofollow,
                    external=external,
                ))
            if external or _should_skip_path(target) or (nofollow and not follow_nofollow):
                continue
            if target not in queued and target not in visited and len(queued) < max_pages * 5:
                queued.add(target)
                queue.append((target, depth + 1))
        if delay_ms:
            time.sleep(delay_ms / 1000)

    # Deduplicate pages reached through several redirecting aliases, retaining the
    # shallowest request while preserving all requested URLs in findings.
    page_by_final: dict[str, GraphPage] = {}
    for page in pages:
        current = page_by_final.get(page.final_url)
        if current is None or page.depth < current.depth:
            page_by_final[page.final_url] = page
    unique_pages = list(page_by_final.values())
    unique_pages.sort(key=lambda item: (item.depth, item.final_url))

    for edge in edges:
        edge.resolved_target = final_by_requested.get(edge.target, edge.target)

    incoming: collections.Counter[str] = collections.Counter()
    outgoing: collections.Counter[str] = collections.Counter()
    for edge in edges:
        if edge.external:
            continue
        incoming[edge.resolved_target or edge.target] += 1
        outgoing[edge.source] += 1
    for page in unique_pages:
        page.incoming = incoming[page.final_url]
        page.outgoing = outgoing[page.final_url]
    _compute_pagerank(unique_pages, edges)

    crawled_urls = {page.final_url for page in unique_pages}
    start_final = page_by_final.get(final_by_requested.get(normalized_start, normalized_start), GraphPage("", "", normalized_start, 0, 0)).final_url
    redirects = [
        {"requested": requested, "final": final}
        for requested, final in sorted(final_by_requested.items())
        if requested != final
    ]
    robots_blocked = [asdict(page) for page in unique_pages if page.error.startswith("Blocked by ")]
    broken = [
        asdict(page) for page in unique_pages
        if page.status >= 400 or (page.status == 0 and not page.error.startswith("Blocked by "))
    ]
    noindex = [page.final_url for page in unique_pages if page.noindex]
    dead_ends = [page.final_url for page in unique_pages if page.status == 200 and page.outgoing == 0]
    deep_pages = [page.final_url for page in unique_pages if page.depth >= 4]
    canonical_mismatches = [
        {"url": page.final_url, "canonical": page.canonical}
        for page in unique_pages if page.canonical and page.canonical != page.final_url
    ]
    orphans = [url for url in sitemap_urls if url not in incoming and url != start_final]
    discovered_not_sitemap = [url for url in sorted(crawled_urls) if sitemap_urls and url not in set(sitemap_urls)]
    generic_anchors = [
        {"source": edge.source, "target": edge.target, "text": edge.text}
        for edge in edges if edge.text.strip().lower() in GENERIC_ANCHORS
    ]
    redirect_map = {item["requested"]: item["final"] for item in redirects}
    links_to_redirects = [
        {"source": edge.source, "target": edge.target, "final": redirect_map[edge.target], "text": edge.text}
        for edge in edges if not edge.external and edge.target in redirect_map
    ]

    title_groups: dict[str, list[str]] = collections.defaultdict(list)
    for page in unique_pages:
        title = " ".join(page.title.lower().split())
        if title:
            title_groups[title].append(page.final_url)
    duplicate_titles = [urls for urls in title_groups.values() if len(urls) > 1]

    findings: dict[str, list[Any]] = {
        "brokenPages": broken,
        "robotsBlockedPages": robots_blocked,
        "redirects": redirects,
        "linksToRedirects": links_to_redirects,
        "orphanCandidates": orphans,
        "discoveredNotInSitemap": discovered_not_sitemap,
        "deadEnds": dead_ends,
        "deepPages": deep_pages,
        "noindexPages": noindex,
        "canonicalMismatches": canonical_mismatches,
        "genericAnchors": generic_anchors,
        "duplicateTitleClusters": duplicate_titles,
        "sitemapErrors": sitemap_errors,
    }
    internal_edges = sum(1 for edge in edges if not edge.external)
    external_edges = len(edges) - internal_edges
    summary = {
        "pagesCrawled": len(unique_pages),
        "queuedButNotCrawled": max(0, len(queue)),
        "internalEdges": internal_edges,
        "externalEdges": external_edges,
        "brokenPages": len(broken),
        "robotsBlockedPages": len(robots_blocked),
        "redirects": len(redirects),
        "orphanCandidates": len(orphans),
        "deadEnds": len(dead_ends),
        "deepPages": len(deep_pages),
        "noindexPages": len(noindex),
        "canonicalMismatches": len(canonical_mismatches),
        "sitemapUrls": len(sitemap_urls),
        "sitemapErrors": len(sitemap_errors),
        "robotsStatus": robots_status,
        "truncated": bool(queue),
    }
    return LinkGraphReport(
        schema_version="3.0",
        tool="internal-link-graph",
        tool_version=core.VERSION,
        generated_at=datetime.now(timezone.utc).isoformat(),
        start_url=normalized_start,
        allowed_host=allowed_host,
        settings={
            "maxPages": max_pages,
            "maxDepth": max_depth,
            "timeout": timeout,
            "robotsAgent": robots_agent,
            "delayMs": delay_ms,
            "includeSubdomains": include_subdomains,
            "ignoreRobots": ignore_robots,
            "followNofollow": follow_nofollow,
            "dropQuery": drop_query,
        },
        summary=summary,
        pages=unique_pages,
        edges=edges,
        sitemap_urls=sitemap_urls,
        findings=findings,
    )


def write_link_report_html(report: LinkGraphReport, path: str) -> None:
    payload = json.dumps(report.to_dict(), ensure_ascii=False).replace("</", "<\\/")
    summary_cards = "".join(
        f'<article><strong>{html.escape(str(value))}</strong><span>{html.escape(key)}</span></article>'
        for key, value in report.summary.items()
        if key in {"pagesCrawled", "internalEdges", "brokenPages", "redirects", "orphanCandidates", "deadEnds", "deepPages", "noindexPages"}
    )
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'">
<title>Internal Link Graph · {html.escape(report.allowed_host)}</title>
<style>
:root{{--bg:#0d0916;--panel:#171124;--line:#3d3154;--text:#f6efff;--muted:#b9aec9;--purple:#b86cff;--pink:#ff6bc7;--cyan:#65e6ff;--green:#70f5a4;--yellow:#ffd76a;--red:#ff7188;color-scheme:dark;font-family:Inter,system-ui,sans-serif}}*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at 20% -10%,#31184f,transparent 34%),var(--bg);color:var(--text)}}header,main{{width:min(1400px,calc(100% - 32px));margin:auto}}header{{padding:38px 0 20px}}h1{{font-size:clamp(2rem,5vw,4.5rem);margin:0;letter-spacing:-.05em}}p{{color:var(--muted)}}.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:22px 0}}.cards article,.panel{{background:#171124dd;border:1px solid var(--line);border-radius:18px;padding:18px}}.cards strong{{font-size:1.8rem;display:block}}.cards span{{color:var(--muted);font-size:.82rem}}.layout{{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(320px,.7fr);gap:16px}}canvas{{width:100%;height:650px;background:#08060d;border-radius:14px;display:block}}.toolbar{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}}button,input{{font:inherit;border:1px solid var(--line);background:#20182e;color:white;border-radius:10px;padding:9px 12px}}button{{cursor:pointer}}button:hover{{border-color:var(--purple)}}.findings{{max-height:650px;overflow:auto}}details{{border-bottom:1px solid #ffffff12;padding:12px 0}}summary{{cursor:pointer;font-weight:700}}pre{{white-space:pre-wrap;word-break:break-word;color:var(--muted);font-size:.75rem}}table{{width:100%;border-collapse:collapse;margin:18px 0 50px;font-size:.82rem}}th,td{{padding:10px;border-bottom:1px solid #ffffff12;text-align:left}}th{{position:sticky;top:0;background:var(--bg)}}a{{color:var(--cyan)}}@media(max-width:900px){{.layout{{grid-template-columns:1fr}}.cards{{grid-template-columns:1fr 1fr}}canvas{{height:480px}}}}
</style></head><body><header><p>SEO-INDEX VariScripts · foulfoxhacks / The Dev Sammy</p><h1>Internal Link Graph</h1><p>{html.escape(report.start_url)} · generated {html.escape(report.generated_at)}</p></header><main>
<section class="cards">{summary_cards}</section>
<section class="layout"><div class="panel"><div class="toolbar"><button id="reset">Reset view</button><button id="labels">Toggle labels</button><input id="search" placeholder="Filter URL"></div><canvas id="graph"></canvas></div><aside class="panel findings"><h2>Findings</h2><div id="findings"></div></aside></section>
<section><h2>Page inventory</h2><table><thead><tr><th>Depth</th><th>Status</th><th>URL</th><th>Incoming</th><th>Outgoing</th><th>Importance</th><th>Title</th></tr></thead><tbody id="pages"></tbody></table></section>
<script id="report" type="application/json">{payload}</script><script>
const data=JSON.parse(document.getElementById('report').textContent),canvas=document.getElementById('graph'),ctx=canvas.getContext('2d');let labels=true,query='',nodes=[],edges=[];
function esc(v=''){{return String(v).replace(/[&<>\"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}}[c]))}}
function rebuild(){{query=document.getElementById('search').value.toLowerCase();const src=data.pages.filter(p=>!query||p.final_url.toLowerCase().includes(query));const keep=new Set(src.map(p=>p.final_url));nodes=src.slice(0,500).map((p,i)=>({{...p,x:Math.cos(i/src.length*Math.PI*2)*220,y:Math.sin(i/src.length*Math.PI*2)*220,vx:0,vy:0}}));const limited=new Set(nodes.map(n=>n.final_url));edges=data.edges.filter(e=>!e.external&&limited.has(e.source)&&limited.has(e.resolved_target||e.target));fit();}}
function fit(){{const r=canvas.getBoundingClientRect(),d=devicePixelRatio||1;canvas.width=r.width*d;canvas.height=r.height*d;ctx.setTransform(d,0,0,d,0,0);draw()}}
function simulate(){{const map=new Map(nodes.map(n=>[n.final_url,n]));for(let k=0;k<100;k++){{for(let i=0;i<nodes.length;i++)for(let j=i+1;j<nodes.length;j++){{let a=nodes[i],b=nodes[j],dx=a.x-b.x,dy=a.y-b.y,d2=dx*dx+dy*dy+20,f=350/d2;a.vx+=dx*f;a.vy+=dy*f;b.vx-=dx*f;b.vy-=dy*f}}for(const e of edges){{let a=map.get(e.source),b=map.get(e.resolved_target||e.target);if(!a||!b)continue;let dx=b.x-a.x,dy=b.y-a.y,d=Math.hypot(dx,dy)||1,f=(d-90)*.0015;a.vx+=dx*f;a.vy+=dy*f;b.vx-=dx*f;b.vy-=dy*f}}for(const n of nodes){{n.vx+=-n.x*.0008;n.vy+=-n.y*.0008;n.vx*=.82;n.vy*=.82;n.x+=n.vx;n.y+=n.vy}}}}draw()}}
function draw(){{const w=canvas.clientWidth,h=canvas.clientHeight,map=new Map(nodes.map(n=>[n.final_url,n]));ctx.clearRect(0,0,w,h);ctx.save();ctx.translate(w/2,h/2);ctx.strokeStyle='#6b4e8844';ctx.lineWidth=1;for(const e of edges){{const a=map.get(e.source),b=map.get(e.resolved_target||e.target);if(a&&b){{ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke()}}}}for(const n of nodes){{const r=4+Math.sqrt(n.pagerank||0)*.65;ctx.fillStyle=n.status>=400||!n.status?'#ff7188':n.noindex?'#ffd76a':'#70f5a4';ctx.beginPath();ctx.arc(n.x,n.y,r,0,Math.PI*2);ctx.fill();if(labels&&nodes.length<120){{ctx.fillStyle='#f5efff';ctx.font='11px system-ui';ctx.fillText(new URL(n.final_url).pathname||'/',n.x+r+3,n.y+3)}}}}ctx.restore()}}
document.getElementById('reset').onclick=()=>{{rebuild();simulate()}};document.getElementById('labels').onclick=()=>{{labels=!labels;draw()}};document.getElementById('search').oninput=()=>{{rebuild();simulate()}};addEventListener('resize',fit);
document.getElementById('findings').innerHTML=Object.entries(data.findings).map(([k,v])=>`<details ${{v.length?'open':''}}><summary>${{k}} (${{v.length}})</summary><pre>${{esc(JSON.stringify(v.slice(0,100),null,2))}}</pre></details>`).join('');
document.getElementById('pages').innerHTML=data.pages.map(p=>`<tr><td>${{p.depth}}</td><td style="color:${{p.status>=400||!p.status?'#ff7188':'#70f5a4'}}">${{p.status||'blocked'}}</td><td><a href="${{esc(p.final_url)}}" rel="noopener noreferrer">${{esc(p.final_url)}}</a></td><td>${{p.incoming}}</td><td>${{p.outgoing}}</td><td>${{p.pagerank}}</td><td>${{esc(p.title)}}</td></tr>`).join('');rebuild();simulate();
</script></main></body></html>"""
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")


def run_links(args: argparse.Namespace, console: core.Console) -> int:
    last_print = 0.0

    def progress(count: int, maximum: int, url: str) -> None:
        nonlocal last_print
        if not getattr(args, "progress", False):
            return
        now = time.monotonic()
        if now - last_print > 0.08:
            print(f"  [{count:4d}/{maximum:4d}] {url}")
            last_print = now

    print(console.paint("Internal Link Graph", core.Style.BOLD, core.Style.CYAN))
    print(f"  Start: {args.url}")
    print(f"  Limit: {args.max_pages} pages · depth {args.max_depth}\n")
    report = crawl_internal_links(
        args.url,
        sitemap=args.sitemap,
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        timeout=args.timeout,
        user_agent=args.user_agent,
        robots_agent=args.robots_agent,
        delay_ms=args.delay_ms,
        include_subdomains=args.include_subdomains,
        ignore_robots=args.ignore_robots,
        follow_nofollow=args.follow_nofollow,
        drop_query=args.drop_query,
        progress=progress,
    )
    s = report.summary
    print(console.paint("Site map summary", core.Style.BOLD, core.Style.WHITE))
    rows = [
        ("Pages crawled", s["pagesCrawled"]),
        ("Internal edges", s["internalEdges"]),
        ("External edges", s["externalEdges"]),
        ("Broken pages", s["brokenPages"]),
        ("Robots-blocked pages", s["robotsBlockedPages"]),
        ("Redirecting URLs", s["redirects"]),
        ("Orphan candidates", s["orphanCandidates"]),
        ("Dead ends", s["deadEnds"]),
        ("Deep pages", s["deepPages"]),
        ("Noindex pages", s["noindexPages"]),
        ("Canonical mismatches", s["canonicalMismatches"]),
        ("Sitemap errors", s["sitemapErrors"]),
    ]
    for label, value in rows:
        color = core.Style.RED if label in {"Broken pages", "Noindex pages"} and value else core.Style.YELLOW if value and label not in {"Pages crawled", "Internal edges", "External edges"} else core.Style.GREEN
        print(f"  {label:<24} {console.paint(str(value), core.Style.BOLD, color)}")
    if s.get("truncated"):
        print(console.paint("\n  WARN Crawl stopped at the configured page limit.", core.Style.YELLOW))

    top = sorted(report.pages, key=lambda page: page.pagerank, reverse=True)[: min(args.show, len(report.pages))]
    if top:
        print(console.paint("\nHighest internal importance", core.Style.BOLD, core.Style.WHITE))
        for page in top:
            print(f"  {page.pagerank:6.2f}  depth {page.depth:<2}  in {page.incoming:<3}  {page.final_url}")

    if args.json:
        core.write_json(args.json, report.to_dict())
        print(f"\nJSON report written to {args.json}")
    if args.html:
        write_link_report_html(report, args.html)
        print(f"Graphical HTML report written to {args.html}")
    if args.fail_on_broken and report.summary["brokenPages"]:
        return 2
    return 0


def _is_private_target(url: str) -> bool:
    parsed = core.require_http_url(url, "Target URL")
    host = parsed.hostname or ""
    if host.lower() == "localhost":
        return True
    try:
        addresses = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise core.ToolkitError(f"Could not resolve target host: {host}") from exc
    for item in addresses:
        address = ipaddress.ip_address(item[4][0])
        if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved or address.is_multicast or address.is_unspecified:
            return True
    return False


def _require_public_target(url: str) -> None:
    if _is_private_target(url):
        raise core.ToolkitError(
            "Private, loopback, link-local, reserved, multicast, and unspecified targets are blocked. "
            "Restart with --allow-private-targets only when intended."
        )


def serve_workbench(args: argparse.Namespace, console: core.Console) -> int:
    host = args.host
    try:
        bind_ip = ipaddress.ip_address(host)
    except ValueError:
        bind_ip = None
    if not args.allow_remote and (bind_ip is None or not bind_ip.is_loopback):
        raise core.ToolkitError("The local server binds to loopback by default. Use --allow-remote deliberately for another host.")

    scripts_dir = Path(__file__).resolve().parent
    root = scripts_dir.parents[1]
    docs_dir = Path(args.docs_dir).expanduser().resolve() if args.docs_dir else root / "docs"
    if not (docs_dir / "index.html").is_file():
        raise core.ToolkitError(f"Workbench index.html was not found in {docs_dir}")

    token = secrets.token_urlsafe(24)
    crawl_lock = threading.Lock()
    server_ref: dict[str, Any] = {}

    class Handler(SimpleHTTPRequestHandler):
        server_version = "SEOIndexLocal/1.0"

        def __init__(self, *handler_args: Any, **handler_kwargs: Any) -> None:
            super().__init__(*handler_args, directory=str(docs_dir), **handler_kwargs)

        def log_message(self, fmt: str, *values: Any) -> None:
            if args.verbose:
                super().log_message(fmt, *values)

        def end_headers(self) -> None:
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            if self.path.startswith("/api/"):
                self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def _authorized(self) -> bool:
            parsed = urllib.parse.urlsplit(self.path)
            query = urllib.parse.parse_qs(parsed.query)
            supplied = self.headers.get("X-SEO-Index-Token", "") or (query.get("token", [""])[0])
            return secrets.compare_digest(supplied, token)

        def _json(self, status: int, payload: Any) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = urllib.parse.urlsplit(self.path)
            if parsed.path == "/api/health":
                if not self._authorized():
                    self._json(HTTPStatus.UNAUTHORIZED, {"error": "Invalid local session token."})
                    return
                self._json(HTTPStatus.OK, {
                    "ok": True,
                    "tool": core.TOOL_NAME,
                    "version": core.VERSION,
                    "capabilities": ["internal-link-graph", "page-quality"],
                    "privateTargets": bool(args.allow_private_targets),
                })
                return
            super().do_GET()

        def do_POST(self) -> None:
            parsed = urllib.parse.urlsplit(self.path)
            if parsed.path not in {"/api/links", "/api/page"}:
                self._json(HTTPStatus.NOT_FOUND, {"error": "Unknown API endpoint."})
                return
            if not self._authorized():
                self._json(HTTPStatus.UNAUTHORIZED, {"error": "Invalid local session token."})
                return
            origin = self.headers.get("Origin")
            port = server_ref["server"].server_address[1]
            allowed_origins = {f"http://{host}:{port}", f"http://localhost:{port}", f"http://127.0.0.1:{port}"}
            if origin and origin not in allowed_origins:
                self._json(HTTPStatus.FORBIDDEN, {"error": "Cross-origin API request rejected."})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length <= 0 or length > 65536:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "Request body must be JSON and no larger than 64 KiB."})
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                target = str(payload.get("url", "")).strip()
                if not target:
                    raise core.ToolkitError("A target URL is required.")
                url_validator = None if args.allow_private_targets else _require_public_target
                if url_validator:
                    url_validator(target)
                if parsed.path == "/api/page":
                    from seo_index_quality import audit_page
                    if not crawl_lock.acquire(blocking=False):
                        self._json(HTTPStatus.CONFLICT, {"error": "Another live audit is already running."})
                        return
                    try:
                        report = audit_page(
                            target,
                            min(max(int(payload.get("timeout", 20)), 1), 120),
                            core.DEFAULT_USER_AGENT,
                            url_validator=url_validator,
                        )
                    finally:
                        crawl_lock.release()
                    self._json(HTTPStatus.OK, report.to_dict())
                    return
                options = {
                    "sitemap": payload.get("sitemap") or None,
                    "max_pages": min(max(int(payload.get("maxPages", 100)), 1), args.api_max_pages),
                    "max_depth": min(max(int(payload.get("maxDepth", 5)), 0), 20),
                    "timeout": min(max(int(payload.get("timeout", 20)), 1), 120),
                    "user_agent": core.DEFAULT_USER_AGENT,
                    "robots_agent": str(payload.get("robotsAgent", "Googlebot")),
                    "delay_ms": min(max(int(payload.get("delayMs", 75)), 0), 5000),
                    "include_subdomains": bool(payload.get("includeSubdomains", False)),
                    "ignore_robots": bool(payload.get("ignoreRobots", False)),
                    "follow_nofollow": bool(payload.get("followNofollow", False)),
                    "drop_query": bool(payload.get("dropQuery", False)),
                    "url_validator": url_validator,
                }
                if not crawl_lock.acquire(blocking=False):
                    self._json(HTTPStatus.CONFLICT, {"error": "Another live crawl is already running."})
                    return
                try:
                    report = crawl_internal_links(target, **options)
                finally:
                    crawl_lock.release()
                self._json(HTTPStatus.OK, report.to_dict())
            except (ValueError, json.JSONDecodeError, core.ToolkitError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except Exception as exc:  # keep the localhost API from dropping the connection
                self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"Live audit failed: {exc}"})

    server = ThreadingHTTPServer((host, args.port), Handler)
    server_ref["server"] = server
    actual_host, actual_port = server.server_address[:2]
    browser_host = "127.0.0.1" if actual_host in {"0.0.0.0", "::"} else actual_host
    url = f"http://{browser_host}:{actual_port}/?token={urllib.parse.quote(token)}"
    print(console.paint("Local graphical workbench", core.Style.BOLD, core.Style.CYAN))
    print(f"  URL: {url}")
    print(f"  Root: {docs_dir}")
    print(f"  API page limit: {args.api_max_pages}")
    print("  Press Ctrl+C to stop.\n")
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\nStopping local workbench.")
    finally:
        server.shutdown()
        server.server_close()
    return 0
