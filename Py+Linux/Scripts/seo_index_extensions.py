#!/usr/bin/env python3
"""Category-focused SEO, GEO, and AEO extensions for SEO-INDEX VariScripts.

This module intentionally uses only the Python standard library. It provides:
- redirect-chain tracing and policy checks
- robots.txt crawler matrix checks
- hreflang validation and reciprocity checks
- structured-data graph inspection
- GEO/entity discoverability diagnostics
- AEO/answer extractability diagnostics
- additional factors for the category-based scoring matrix
"""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from typing import Any, Iterable, Optional
from urllib.parse import urljoin, urlsplit

import seo_index_toolkit as core

QUESTION_RE = re.compile(r"^(?:who|what|when|where|why|how|which|can|could|do|does|did|is|are|should|will|would)\b", re.I)
HREFLANG_RE = re.compile(r"^(?:x-default|[A-Za-z]{2,3}(?:-[A-Za-z]{4})?(?:-(?:[A-Za-z]{2}|\d{3}))?)$")
DATE_RE = re.compile(r"\b(?:19|20)\d{2}[-/.](?:0?[1-9]|1[0-2])[-/.](?:0?[1-9]|[12]\d|3[01])\b")
SCHEMA_CONTEXTS = {"https://schema.org", "http://schema.org", "https://schema.org/", "http://schema.org/"}
AI_CRAWLERS = {
    "OAI-SearchBot": "OpenAI search discovery",
    "OAI-AdsBot": "OpenAI advertising landing-page validation",
    "GPTBot": "OpenAI model-training crawler",
    "Claude-SearchBot": "Anthropic search indexing",
    "Claude-User": "Anthropic user-directed retrieval",
    "ClaudeBot": "Anthropic model-development crawler",
    "PerplexityBot": "Perplexity search discovery",
    "Perplexity-User": "Perplexity user-directed retrieval",
}
SEARCH_CRAWLERS = {
    "Googlebot": "Google Search",
    "bingbot": "Bing Search",
    **AI_CRAWLERS,
}


@dataclass
class LinkSignal:
    href: str
    rel: list[str] = field(default_factory=list)
    hreflang: str = ""
    text: str = ""


@dataclass
class ExtendedSignals:
    lang: str = ""
    headings: list[dict[str, Any]] = field(default_factory=list)
    paragraph_lengths: list[int] = field(default_factory=list)
    list_count: int = 0
    table_count: int = 0
    links: list[LinkSignal] = field(default_factory=list)
    hreflang: list[LinkSignal] = field(default_factory=list)
    og_url: str = ""
    author_meta: str = ""
    published_time: str = ""
    modified_time: str = ""
    time_values: list[str] = field(default_factory=list)
    json_ld_objects: list[Any] = field(default_factory=list)
    json_ld_errors: list[str] = field(default_factory=list)
    schema_types: list[str] = field(default_factory=list)
    same_as: list[str] = field(default_factory=list)
    schema_ids: list[str] = field(default_factory=list)
    schema_context_valid: int = 0
    schema_context_invalid: int = 0
    body_text: str = ""

    @property
    def question_headings(self) -> int:
        return sum(1 for item in self.headings if item["text"].rstrip().endswith("?") or QUESTION_RE.match(item["text"]))

    @property
    def answer_blocks(self) -> int:
        return sum(1 for length in self.paragraph_lengths if 55 <= length <= 700)

    @property
    def schema_type_set(self) -> set[str]:
        return set(self.schema_types)


class ExtendedHTMLParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.origin_host = (urlsplit(base_url).hostname or "").lower()
        self.lang = ""
        self.headings: list[dict[str, Any]] = []
        self.current_heading_level = 0
        self.current_heading_parts: list[str] = []
        self.in_p = False
        self.paragraph_parts: list[str] = []
        self.paragraph_lengths: list[int] = []
        self.list_count = 0
        self.table_count = 0
        self.links: list[LinkSignal] = []
        self.hreflang: list[LinkSignal] = []
        self.current_anchor: Optional[LinkSignal] = None
        self.anchor_parts: list[str] = []
        self.og_url = ""
        self.author_meta = ""
        self.published_time = ""
        self.modified_time = ""
        self.time_values: list[str] = []
        self.in_script = False
        self.script_type = ""
        self.script_parts: list[str] = []
        self.json_ld_raw: list[str] = []
        self.skip_depth = 0
        self.body_parts: list[str] = []

    @staticmethod
    def attrs_dict(attrs: list[tuple[str, Optional[str]]]) -> dict[str, str]:
        return {str(key).lower(): (value or "") for key, value in attrs}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        values = self.attrs_dict(attrs)
        if tag == "html" and not self.lang:
            self.lang = values.get("lang", "").strip()
        if tag in {"style", "noscript", "template"}:
            self.skip_depth += 1
        elif tag == "script":
            self.in_script = True
            self.script_type = values.get("type", "").lower().strip()
            self.script_parts = []
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.current_heading_level = int(tag[1])
            self.current_heading_parts = []
        elif tag == "p":
            self.in_p = True
            self.paragraph_parts = []
        elif tag in {"ul", "ol", "dl"}:
            self.list_count += 1
        elif tag == "table":
            self.table_count += 1
        elif tag == "a":
            href = values.get("href", "").strip()
            self.current_anchor = LinkSignal(
                href=urljoin(self.base_url, href) if href else "",
                rel=[item.lower() for item in values.get("rel", "").split() if item],
                hreflang=values.get("hreflang", "").strip(),
            )
            self.anchor_parts = []
        elif tag == "link":
            rel = [item.lower() for item in values.get("rel", "").split() if item]
            href = values.get("href", "").strip()
            language = values.get("hreflang", "").strip()
            if "alternate" in rel and language and href:
                self.hreflang.append(LinkSignal(urljoin(self.base_url, href), rel, language, ""))
        elif tag == "meta":
            name = values.get("name", "").lower().strip()
            prop = values.get("property", "").lower().strip()
            content = values.get("content", "").strip()
            if prop == "og:url" and not self.og_url:
                self.og_url = urljoin(self.base_url, content) if content else ""
            elif name == "author" and not self.author_meta:
                self.author_meta = content
            elif prop in {"article:published_time", "og:published_time"} and not self.published_time:
                self.published_time = content
            elif prop in {"article:modified_time", "og:updated_time"} and not self.modified_time:
                self.modified_time = content
        elif tag == "time":
            value = values.get("datetime", "").strip()
            if value:
                self.time_values.append(value)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"style", "noscript", "template"} and self.skip_depth:
            self.skip_depth -= 1
        elif tag == "script":
            if self.script_type == "application/ld+json":
                self.json_ld_raw.append("".join(self.script_parts).strip())
            self.in_script = False
            self.script_type = ""
            self.script_parts = []
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and self.current_heading_level:
            text = " ".join("".join(self.current_heading_parts).split())
            if text:
                self.headings.append({"level": self.current_heading_level, "text": text})
            self.current_heading_level = 0
            self.current_heading_parts = []
        elif tag == "p" and self.in_p:
            text = " ".join("".join(self.paragraph_parts).split())
            if text:
                self.paragraph_lengths.append(len(text))
            self.in_p = False
            self.paragraph_parts = []
        elif tag == "a" and self.current_anchor is not None:
            self.current_anchor.text = " ".join("".join(self.anchor_parts).split())
            if self.current_anchor.href:
                self.links.append(self.current_anchor)
            self.current_anchor = None
            self.anchor_parts = []

    def handle_data(self, data: str) -> None:
        if self.in_script:
            self.script_parts.append(data)
            return
        if self.skip_depth:
            return
        text = " ".join(data.split())
        if not text:
            return
        self.body_parts.append(text)
        if self.current_heading_level:
            self.current_heading_parts.append(text + " ")
        if self.in_p:
            self.paragraph_parts.append(text + " ")
        if self.current_anchor is not None:
            self.anchor_parts.append(text + " ")

    def signals(self) -> ExtendedSignals:
        objects: list[Any] = []
        errors: list[str] = []
        for index, raw in enumerate(self.json_ld_raw, 1):
            if not raw:
                errors.append(f"JSON-LD block {index} is empty.")
                continue
            try:
                objects.append(json.loads(raw))
            except json.JSONDecodeError as exc:
                errors.append(f"JSON-LD block {index}: {exc.msg} at line {exc.lineno}.")
        types: set[str] = set()
        same_as: list[str] = []
        ids: list[str] = []
        valid_context = 0
        invalid_context = 0
        for node in walk_json_nodes(objects):
            context = node.get("@context")
            if context is not None:
                values = context if isinstance(context, list) else [context]
                if any(str(value) in SCHEMA_CONTEXTS or "schema.org" in str(value) for value in values):
                    valid_context += 1
                else:
                    invalid_context += 1
            raw_type = node.get("@type")
            for value in raw_type if isinstance(raw_type, list) else ([raw_type] if raw_type else []):
                types.add(str(value))
            raw_same = node.get("sameAs")
            for value in raw_same if isinstance(raw_same, list) else ([raw_same] if raw_same else []):
                if isinstance(value, str):
                    same_as.append(value)
            raw_id = node.get("@id")
            if isinstance(raw_id, str):
                ids.append(raw_id)
        return ExtendedSignals(
            lang=self.lang,
            headings=self.headings,
            paragraph_lengths=self.paragraph_lengths,
            list_count=self.list_count,
            table_count=self.table_count,
            links=self.links,
            hreflang=self.hreflang,
            og_url=self.og_url,
            author_meta=self.author_meta,
            published_time=self.published_time,
            modified_time=self.modified_time,
            time_values=self.time_values,
            json_ld_objects=objects,
            json_ld_errors=errors,
            schema_types=sorted(types),
            same_as=list(dict.fromkeys(same_as)),
            schema_ids=ids,
            schema_context_valid=valid_context,
            schema_context_invalid=invalid_context,
            body_text=" ".join(self.body_parts),
        )


def walk_json_nodes(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_json_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_json_nodes(child)


def parse_extended_html(fetch: core.FetchResult) -> ExtendedSignals:
    content_type = fetch.headers.get("content-type", "").lower()
    if fetch.status == 0 or ("html" not in content_type and not fetch.text.lstrip().lower().startswith(("<!doctype html", "<html"))):
        return ExtendedSignals()
    parser = ExtendedHTMLParser(fetch.final_url or fetch.requested_url)
    try:
        parser.feed(fetch.text)
        parser.close()
    except Exception as exc:
        signals = parser.signals()
        signals.json_ld_errors.append(f"HTML parser warning: {exc}")
        return signals
    return parser.signals()


@dataclass
class RedirectHop:
    url: str
    status: int
    location: str
    resolved_location: str
    elapsed_ms: int
    content_type: str
    cache_control: str
    error: str = ""


@dataclass
class RedirectReport:
    requested_url: str
    hops: list[RedirectHop]
    final_url: str
    final_status: int
    loop_detected: bool
    max_hops_reached: bool
    downgraded_https: bool
    crossed_host: bool


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


def _fetch_no_redirect(url: str, timeout: int, user_agent: str) -> RedirectHop:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": user_agent, "Accept": "text/html,*/*", "Accept-Encoding": "identity"},
        method="GET",
    )
    opener = urllib.request.build_opener(NoRedirectHandler())
    started = time.perf_counter()
    try:
        with opener.open(request, timeout=timeout) as response:
            response.read(65536)
            headers = {key.lower(): value for key, value in response.headers.items()}
            status = int(response.status)
            location = headers.get("location", "")
            return RedirectHop(
                url=url,
                status=status,
                location=location,
                resolved_location=urljoin(url, location) if location else "",
                elapsed_ms=int((time.perf_counter() - started) * 1000),
                content_type=headers.get("content-type", ""),
                cache_control=headers.get("cache-control", ""),
            )
    except urllib.error.HTTPError as exc:
        headers = {key.lower(): value for key, value in exc.headers.items()} if exc.headers else {}
        location = headers.get("location", "")
        return RedirectHop(
            url=url,
            status=int(exc.code),
            location=location,
            resolved_location=urljoin(url, location) if location else "",
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            content_type=headers.get("content-type", ""),
            cache_control=headers.get("cache-control", ""),
            error=str(exc),
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return RedirectHop(
            url=url,
            status=0,
            location="",
            resolved_location="",
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            content_type="",
            cache_control="",
            error=str(getattr(exc, "reason", exc)),
        )


def trace_redirects(url: str, timeout: int, user_agent: str, max_hops: int = 10) -> RedirectReport:
    current = core.normalize_url(url)
    original = current
    visited: set[str] = set()
    hops: list[RedirectHop] = []
    loop = False
    maxed = False
    downgraded = False
    crossed = False
    original_host = (urlsplit(current).hostname or "").lower()
    original_scheme = urlsplit(current).scheme.lower()
    for _ in range(max_hops + 1):
        normalized = core.normalize_url(current)
        if normalized in visited:
            loop = True
            break
        visited.add(normalized)
        hop = _fetch_no_redirect(current, timeout, user_agent)
        hops.append(hop)
        if hop.status in {300, 301, 302, 303, 305, 307, 308} and hop.resolved_location:
            next_url = core.normalize_url(hop.resolved_location)
            parsed = urlsplit(next_url)
            if original_scheme == "https" and parsed.scheme.lower() == "http":
                downgraded = True
            if (parsed.hostname or "").lower() != original_host:
                crossed = True
            current = next_url
            continue
        break
    else:
        maxed = True
    if len(hops) > max_hops + 1:
        maxed = True
    final_url = hops[-1].url if hops else original
    final_status = hops[-1].status if hops else 0
    if hops and hops[-1].resolved_location and hops[-1].status in {300, 301, 302, 303, 305, 307, 308}:
        final_url = hops[-1].resolved_location
        if len(hops) >= max_hops + 1:
            maxed = True
    return RedirectReport(original, hops, final_url, final_status, loop, maxed, downgraded, crossed)


def redirect_factor(report: RedirectReport) -> core.FactorResult:
    redirects = [hop for hop in report.hops if 300 <= hop.status < 400]
    if report.loop_detected:
        return core.FactorResult("fail", "Redirect loop detected.", asdict(report))
    if report.max_hops_reached:
        return core.FactorResult("fail", "Redirect trace exceeded the hop limit.", asdict(report))
    if report.downgraded_https:
        return core.FactorResult("fail", "Redirect chain downgrades HTTPS to HTTP.", asdict(report))
    if report.final_status != 200:
        return core.FactorResult("fail", f"Redirect destination returns HTTP {report.final_status or 'network error'}.", asdict(report))
    if not redirects:
        return core.FactorResult("pass", "URL resolves directly with no redirect.", asdict(report))
    temporary = [hop.status for hop in redirects if hop.status in {302, 303, 307}]
    if len(redirects) == 1 and not temporary:
        return core.FactorResult("pass", f"One permanent redirect ({redirects[0].status}) reaches HTTP 200.", asdict(report))
    if len(redirects) <= 2:
        note = "temporary status present" if temporary else "two-hop chain"
        return core.FactorResult("warn", f"Redirect chain has {len(redirects)} hop(s); {note}.", asdict(report))
    return core.FactorResult("fail", f"Redirect chain has {len(redirects)} hops before the final page.", asdict(report))


def _heading_structure(signals: ExtendedSignals) -> tuple[str, str, Any]:
    if not signals.headings:
        return "fail", "No headings were detected.", []
    jumps: list[tuple[int, int]] = []
    previous = signals.headings[0]["level"]
    for item in signals.headings[1:]:
        current = item["level"]
        if current > previous + 1:
            jumps.append((previous, current))
        previous = current
    if jumps:
        return "warn", f"Heading hierarchy contains {len(jumps)} skipped level transition(s).", jumps
    return "pass", f"Heading hierarchy contains {len(signals.headings)} heading(s) without skipped levels.", signals.headings[:20]


def _schema_date_count(objects: list[Any]) -> int:
    keys = {"datePublished", "dateModified", "lastReviewed", "uploadDate", "foundingDate"}
    return sum(1 for node in walk_json_nodes(objects) for key in keys if node.get(key))


def _schema_people_count(objects: list[Any]) -> int:
    keys = {"author", "reviewedBy", "editor", "creator"}
    count = 0
    for node in walk_json_nodes(objects):
        for key in keys:
            value = node.get(key)
            if value:
                count += len(value) if isinstance(value, list) else 1
    return count


def _internal_external_counts(signals: ExtendedSignals, base_url: str) -> tuple[int, int, int]:
    host = (urlsplit(base_url).hostname or "").lower()
    internal = external = source_like = 0
    for link in signals.links:
        parsed = urlsplit(link.href)
        if parsed.scheme not in {"http", "https"}:
            continue
        if (parsed.hostname or "").lower() == host:
            internal += 1
        else:
            external += 1
            text = link.text.lower()
            if any(token in text for token in ("source", "reference", "citation", "study", "documentation", "report")):
                source_like += 1
    return internal, external, source_like


def _about_contact_count(signals: ExtendedSignals, base_url: str) -> int:
    host = (urlsplit(base_url).hostname or "").lower()
    count = 0
    for link in signals.links:
        parsed = urlsplit(link.href)
        if (parsed.hostname or "").lower() != host:
            continue
        path = (parsed.path or "/").lower()
        text = link.text.lower()
        if any(token in path or token in text for token in ("about", "contact", "team", "staff", "editorial", "authors")):
            count += 1
    return count


def _fetch_llms(origin: str, timeout: int, user_agent: str) -> core.FactorResult:
    result = core.fetch_url(origin.rstrip("/") + "/llms.txt", timeout, user_agent, accept="text/plain,*/*", max_bytes=2 * 1024 * 1024)
    if result.status == 200 and len(result.text.strip()) >= 20:
        return core.FactorResult("pass", "llms.txt is publicly reachable and non-empty.", {"url": result.final_url, "bytes": len(result.data)})
    if result.status == 404:
        return core.FactorResult("warn", "No llms.txt file was found. This is an experimental, non-standard signal.", result.final_url)
    return core.FactorResult("warn", f"llms.txt returned HTTP {result.status or 'network error'}.", result.final_url)


def enhance_factors(snapshot: core.PageSnapshot, engine: str, crawler: str, timeout: int = 30, user_agent: str = core.DEFAULT_USER_AGENT) -> dict[str, core.FactorResult]:
    """Return additional scoring factors without duplicating the core eligibility checks."""
    fetch = snapshot.fetch
    base_url = fetch.final_url or snapshot.requested_url
    signals = parse_extended_html(fetch)
    types = signals.schema_type_set
    internal, external, source_like = _internal_external_counts(signals, base_url)
    factors: dict[str, core.FactorResult] = {}

    content_type = fetch.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    indexable_type = content_type.startswith("text/") or content_type in {"application/xhtml+xml", "application/pdf"}
    factors["content_type_indexable"] = core.FactorResult(
        "pass" if indexable_type else ("unknown" if not content_type else "fail"),
        f"Content-Type is {content_type or 'not available'}.",
        content_type,
    )

    try:
        redirect_report = trace_redirects(snapshot.requested_url, timeout, user_agent, max_hops=10)
        factors["redirect_hygiene"] = redirect_factor(redirect_report)
        factors["host_consistency"] = core.FactorResult(
            "warn" if redirect_report.crossed_host else "pass",
            "Redirect chain changes hostname." if redirect_report.crossed_host else "Redirect chain stays on the same hostname.",
            asdict(redirect_report),
        )
    except core.ToolkitError as exc:
        factors["redirect_hygiene"] = core.FactorResult("unknown", f"Redirect chain could not be traced: {exc}")
        factors["host_consistency"] = core.FactorResult("unknown", "Hostname consistency could not be evaluated.")

    factors["canonical_present"] = core.FactorResult(
        "pass" if snapshot.html.canonical else "warn",
        "A canonical annotation is present." if snapshot.html.canonical else "No canonical annotation was found.",
        snapshot.html.canonical,
    )
    factors["og_url_consistent"] = core.FactorResult(
        "unknown" if not signals.og_url else ("pass" if core.normalize_url(signals.og_url) == core.normalize_url(base_url) else "warn"),
        "og:url is not present." if not signals.og_url else ("og:url matches the final URL." if core.normalize_url(signals.og_url) == core.normalize_url(base_url) else "og:url differs from the final URL."),
        signals.og_url,
    )
    factors["sitemap_in_robots"] = core.FactorResult(
        "pass" if core.sitemap_urls_from_robots(snapshot.robots_text) else ("unknown" if snapshot.robots_status not in {200, 404} else "warn"),
        "robots.txt declares at least one sitemap." if core.sitemap_urls_from_robots(snapshot.robots_text) else "robots.txt does not declare a sitemap.",
        core.sitemap_urls_from_robots(snapshot.robots_text),
    )
    if snapshot.sitemap:
        clean = not snapshot.sitemap.errors and snapshot.sitemap.duplicate_count == 0
        factors["sitemap_clean"] = core.FactorResult(
            "pass" if clean else "warn",
            "Sitemap traversal found no parsing errors or duplicates." if clean else f"Sitemap has {len(snapshot.sitemap.errors)} error(s) and {snapshot.sitemap.duplicate_count} duplicate URL(s).",
            {"errors": snapshot.sitemap.errors, "duplicates": snapshot.sitemap.duplicate_count},
        )
    else:
        factors["sitemap_clean"] = core.FactorResult("unknown", "No sitemap was evaluated.")

    title_length = len(snapshot.html.title)
    factors["title_length"] = core.FactorResult(
        "unknown" if not snapshot.html.title else ("pass" if 25 <= title_length <= 65 else "warn"),
        "Title is missing." if not snapshot.html.title else f"Title length is {title_length} characters.",
        title_length,
    )
    factors["lang_declared"] = core.FactorResult(
        "pass" if signals.lang else "warn",
        f"Document language is {signals.lang}." if signals.lang else "The html element has no lang attribute.",
        signals.lang,
    )
    heading_status, heading_message, heading_evidence = _heading_structure(signals)
    factors["heading_structure"] = core.FactorResult(heading_status, heading_message, heading_evidence)
    factors["internal_links_present"] = core.FactorResult(
        "pass" if internal else "warn",
        f"Detected {internal} same-host link(s)." if internal else "No same-host links were detected in the HTML response.",
        internal,
    )

    valid_structured = bool(signals.json_ld_objects) and not signals.json_ld_errors
    factors["structured_data_valid"] = core.FactorResult(
        "pass" if valid_structured else ("warn" if not signals.json_ld_objects and not signals.json_ld_errors else "fail"),
        f"Parsed {len(signals.json_ld_objects)} JSON-LD block(s); {len(signals.json_ld_errors)} error(s).",
        {"types": signals.schema_types, "errors": signals.json_ld_errors},
    )
    factors["schema_webpage"] = core.FactorResult(
        "pass" if types.intersection({"WebPage", "Article", "NewsArticle", "BlogPosting", "FAQPage", "QAPage"}) else "warn",
        "A page-level schema type is present." if types.intersection({"WebPage", "Article", "NewsArticle", "BlogPosting", "FAQPage", "QAPage"}) else "No explicit page-level schema type was found.",
        signals.schema_types,
    )
    factors["schema_website"] = core.FactorResult(
        "pass" if "WebSite" in types else "warn",
        "WebSite schema is present." if "WebSite" in types else "WebSite schema was not found on this page.",
        signals.schema_types,
    )
    entity_types = types.intersection({"Organization", "Corporation", "LocalBusiness", "Person", "NewsMediaOrganization", "OnlineBusiness"})
    factors["schema_entity"] = core.FactorResult(
        "pass" if entity_types else "warn",
        f"Entity schema present: {', '.join(sorted(entity_types))}." if entity_types else "No Organization or Person-style entity schema was found.",
        signals.schema_types,
    )
    factors["schema_breadcrumb"] = core.FactorResult(
        "pass" if "BreadcrumbList" in types else "warn",
        "BreadcrumbList schema is present." if "BreadcrumbList" in types else "BreadcrumbList schema was not found.",
        signals.schema_types,
    )
    factors["schema_sameas"] = core.FactorResult(
        "pass" if signals.same_as else "warn",
        f"Structured data declares {len(signals.same_as)} sameAs identity link(s)." if signals.same_as else "No sameAs identity links were found in structured data.",
        signals.same_as,
    )
    date_count = _schema_date_count(signals.json_ld_objects) + len(signals.time_values) + bool(signals.published_time) + bool(signals.modified_time)
    factors["dates_present"] = core.FactorResult(
        "pass" if date_count else "warn",
        f"Detected {date_count} machine-readable publication/review date signal(s)." if date_count else "No machine-readable publication, modification, or review dates were found.",
        {"published": signals.published_time, "modified": signals.modified_time, "time": signals.time_values},
    )
    people_count = _schema_people_count(signals.json_ld_objects) + bool(signals.author_meta)
    factors["author_or_reviewer"] = core.FactorResult(
        "pass" if people_count else "warn",
        f"Detected {people_count} author/reviewer signal(s)." if people_count else "No author or reviewer signal was detected.",
        {"metaAuthor": signals.author_meta},
    )
    about_count = _about_contact_count(signals, base_url)
    factors["about_contact_links"] = core.FactorResult(
        "pass" if about_count else "warn",
        f"Detected {about_count} About/Contact/Team-style internal link(s)." if about_count else "No About, Contact, Team, Staff, or editorial link was detected.",
        about_count,
    )
    factors["source_links"] = core.FactorResult(
        "pass" if source_like >= 1 else ("warn" if external else "fail"),
        f"Detected {external} external link(s), including {source_like} source-labelled link(s)." if external else "No external source links were detected.",
        {"external": external, "sourceLabelled": source_like},
    )

    encoding = fetch.headers.get("content-encoding", "").lower()
    factors["compression"] = core.FactorResult(
        "pass" if encoding in {"gzip", "br", "zstd"} else "warn",
        f"Response compression is {encoding}." if encoding else "No Content-Encoding compression header was observed.",
        encoding,
    )
    cache_headers = {key: fetch.headers.get(key, "") for key in ("cache-control", "etag", "last-modified")}
    factors["cache_headers"] = core.FactorResult(
        "pass" if any(cache_headers.values()) else "warn",
        "Cache/freshness response headers are present." if any(cache_headers.values()) else "No Cache-Control, ETag, or Last-Modified header was observed.",
        cache_headers,
    )

    factors["question_headings"] = core.FactorResult(
        "pass" if signals.question_headings >= 1 else "warn",
        f"Detected {signals.question_headings} question-oriented heading(s).",
        [item for item in signals.headings if item["text"].rstrip().endswith("?") or QUESTION_RE.match(item["text"])][:20],
    )
    factors["answer_blocks"] = core.FactorResult(
        "pass" if signals.answer_blocks >= 2 else ("warn" if signals.answer_blocks == 1 else "fail"),
        f"Detected {signals.answer_blocks} concise paragraph-sized answer block(s).",
        signals.paragraph_lengths[:50],
    )
    factors["lists_or_tables"] = core.FactorResult(
        "pass" if signals.list_count + signals.table_count else "warn",
        f"Detected {signals.list_count} list(s) and {signals.table_count} table(s).",
        {"lists": signals.list_count, "tables": signals.table_count},
    )
    faq_qa = types.intersection({"FAQPage", "QAPage"})
    factors["faq_qa_schema"] = core.FactorResult(
        "pass" if faq_qa else "warn",
        f"Answer-oriented schema present: {', '.join(sorted(faq_qa))}." if faq_qa else "FAQPage or QAPage schema was not found.",
        signals.schema_types,
    )
    factors["speakable"] = core.FactorResult(
        "pass" if any("speakable" in node for node in walk_json_nodes(signals.json_ld_objects)) else "warn",
        "Speakable markup is present." if any("speakable" in node for node in walk_json_nodes(signals.json_ld_objects)) else "Speakable markup was not found; this is optional and use-case dependent.",
    )
    factors["concise_structure"] = core.FactorResult(
        "pass" if signals.headings and signals.answer_blocks >= 1 else "warn",
        f"Page has {len(signals.headings)} heading(s) and {signals.answer_blocks} concise answer block(s).",
        {"headings": len(signals.headings), "answerBlocks": signals.answer_blocks},
    )

    origin = core.origin_for(base_url)
    factors["llms_txt"] = _fetch_llms(origin, timeout, user_agent)
    ai_agent = crawler if crawler in SEARCH_CRAWLERS else "OAI-SearchBot"
    can_ai_fetch = core.robots_can_fetch(snapshot.robots_text, snapshot.robots_url, ai_agent, base_url)
    factors["ai_crawler_access"] = core.FactorResult(
        "unknown" if can_ai_fetch is None and snapshot.robots_status not in {404} else ("pass" if can_ai_fetch is not False else "fail"),
        f"{ai_agent} is allowed by robots.txt." if can_ai_fetch is not False else f"{ai_agent} is blocked by robots.txt.",
        {"crawler": ai_agent, "robots": snapshot.robots_url},
    )
    return factors


def _print_problem(console: core.Console, status: str, label: str, message: str) -> None:
    print(f"  {console.status(status)}  {label:25s} {message}")


def run_redirect(args: argparse.Namespace, console: core.Console) -> int:
    report = trace_redirects(args.url, args.timeout, args.user_agent, args.max_hops)
    finding = redirect_factor(report)
    print(console.paint("Redirect Lab", core.Style.BOLD, core.Style.CYAN))
    print(f"  Requested: {report.requested_url}")
    for index, hop in enumerate(report.hops, 1):
        arrow = f" -> {hop.resolved_location}" if hop.resolved_location else ""
        print(f"  {index:2d}. HTTP {hop.status or 'ERR':>3}  {hop.url}{arrow}  ({hop.elapsed_ms} ms)")
    print()
    _print_problem(console, finding.status, "chain assessment", finding.message)
    _print_problem(console, "warn" if report.crossed_host else "pass", "hostname", "Chain changes host." if report.crossed_host else "Chain stays on one host.")
    _print_problem(console, "fail" if report.downgraded_https else "pass", "protocol", "HTTPS downgrades to HTTP." if report.downgraded_https else "No HTTPS downgrade detected.")
    if args.json:
        core.write_json(args.json, {"tool": "redirect", "version": core.VERSION, "report": asdict(report), "finding": asdict(finding)})
        print(f"\nJSON report written to {args.json}")
    return 2 if finding.status == "fail" else 0


def run_robots_matrix(args: argparse.Namespace, console: core.Console) -> int:
    target = core.normalize_url(args.url)
    robots_url = core.origin_for(target) + "/robots.txt"
    result = core.fetch_url(robots_url, args.timeout, args.user_agent, accept="text/plain,*/*", max_bytes=2 * 1024 * 1024)
    robots_text = result.text if result.status == 200 else ""
    agents = args.agent or list(SEARCH_CRAWLERS)
    rows: list[dict[str, Any]] = []
    print(console.paint("Crawler Access Matrix", core.Style.BOLD, core.Style.CYAN))
    print(f"  robots.txt: {robots_url} (HTTP {result.status or 'network error'})")
    print(f"  target:     {target}\n")
    for agent in agents:
        allowed = core.robots_can_fetch(robots_text, robots_url, agent, target)
        if allowed is None:
            allowed = result.status == 404
            status = "pass" if allowed else "unknown"
        else:
            status = "pass" if allowed else "fail"
        label = SEARCH_CRAWLERS.get(agent, "custom crawler")
        message = "allowed" if allowed else "blocked"
        _print_problem(console, status, agent, f"{message} for {target} ({label})")
        rows.append({"agent": agent, "label": label, "allowed": allowed, "status": status})
    sitemaps = core.sitemap_urls_from_robots(robots_text)
    print(f"\n  Sitemap directives: {len(sitemaps)}")
    for value in sitemaps[:20]:
        print(f"    {value}")
    if args.json:
        core.write_json(args.json, {"tool": "robots", "version": core.VERSION, "robotsUrl": robots_url, "status": result.status, "target": target, "agents": rows, "sitemaps": sitemaps})
        print(f"\nJSON report written to {args.json}")
    return 2 if any(row["status"] == "fail" for row in rows) else 0


def _basic_hreflang_valid(value: str) -> bool:
    return bool(HREFLANG_RE.fullmatch(value.strip()))


def run_hreflang(args: argparse.Namespace, console: core.Console) -> int:
    page = core.fetch_url(args.url, args.timeout, args.user_agent)
    signals = parse_extended_html(page)
    alternates = signals.hreflang
    problems: list[dict[str, Any]] = []
    print(console.paint("Hreflang Auditor", core.Style.BOLD, core.Style.CYAN))
    print(f"  Page: {page.final_url} (HTTP {page.status or 'network error'})")
    print(f"  Alternates found: {len(alternates)}\n")
    seen_languages: dict[str, list[str]] = {}
    for alt in alternates:
        language = alt.hreflang.lower()
        seen_languages.setdefault(language, []).append(alt.href)
        status = "pass" if _basic_hreflang_valid(alt.hreflang) else "fail"
        message = f"{alt.hreflang} -> {alt.href}"
        _print_problem(console, status, "language tag", message)
        if status == "fail":
            problems.append({"type": "invalid-language", "hreflang": alt.hreflang, "url": alt.href})
    for language, urls in seen_languages.items():
        if len(urls) > 1:
            problems.append({"type": "duplicate-language", "hreflang": language, "urls": urls})
            _print_problem(console, "fail", "duplicate", f"{language} is declared {len(urls)} times.")
    page_normalized = core.normalize_url(page.final_url or args.url)
    self_refs = [alt for alt in alternates if core.normalize_url(alt.href) == page_normalized]
    _print_problem(console, "pass" if self_refs else "warn", "self reference", "Present." if self_refs else "No self-referencing hreflang was found.")
    if args.check_alternates:
        for alt in alternates[: args.limit if args.limit else None]:
            target = core.fetch_url(alt.href, args.timeout, args.user_agent)
            target_signals = parse_extended_html(target)
            reciprocal = any(core.normalize_url(item.href) == page_normalized for item in target_signals.hreflang)
            status = "pass" if target.status == 200 and reciprocal else "fail"
            _print_problem(console, status, alt.hreflang, f"HTTP {target.status}; reciprocal={'yes' if reciprocal else 'no'}")
            if status == "fail":
                problems.append({"type": "alternate-check", "hreflang": alt.hreflang, "url": alt.href, "status": target.status, "reciprocal": reciprocal})
    if args.json:
        core.write_json(args.json, {"tool": "hreflang", "version": core.VERSION, "url": page.final_url, "alternates": [asdict(item) for item in alternates], "problems": problems})
        print(f"\nJSON report written to {args.json}")
    return 2 if any(item["type"] in {"invalid-language", "duplicate-language", "alternate-check"} for item in problems) else 0


def schema_findings(fetch: core.FetchResult) -> tuple[ExtendedSignals, list[dict[str, Any]]]:
    signals = parse_extended_html(fetch)
    findings: list[dict[str, Any]] = []
    for error in signals.json_ld_errors:
        findings.append({"status": "fail", "check": "json-syntax", "message": error})
    duplicates = sorted({value for value in signals.schema_ids if signals.schema_ids.count(value) > 1})
    if duplicates:
        findings.append({"status": "warn", "check": "duplicate-id", "message": f"Duplicate @id values: {', '.join(duplicates[:10])}"})
    if signals.schema_context_invalid:
        findings.append({"status": "warn", "check": "context", "message": f"{signals.schema_context_invalid} JSON-LD node(s) use a non-schema.org context."})
    if not signals.schema_types:
        findings.append({"status": "warn", "check": "types", "message": "No Schema.org @type values were found."})
    return signals, findings


def run_schema(args: argparse.Namespace, console: core.Console) -> int:
    page = core.fetch_url(args.url, args.timeout, args.user_agent)
    signals, findings = schema_findings(page)
    print(console.paint("Structured Data Graph", core.Style.BOLD, core.Style.CYAN))
    print(f"  Page: {page.final_url} (HTTP {page.status or 'network error'})")
    print(f"  JSON-LD blocks: {len(signals.json_ld_objects)}")
    print(f"  Schema types:   {', '.join(signals.schema_types) if signals.schema_types else 'none'}")
    print(f"  sameAs links:   {len(signals.same_as)}")
    print(f"  @id values:     {len(signals.schema_ids)}\n")
    if not findings:
        _print_problem(console, "pass", "graph", "No static JSON-LD syntax or identity-graph problems were detected.")
    for item in findings:
        _print_problem(console, item["status"], item["check"], item["message"])
    if args.show_json:
        print("\n" + json.dumps(signals.json_ld_objects, indent=2, ensure_ascii=False))
    if args.json:
        core.write_json(args.json, {"tool": "schema", "version": core.VERSION, "url": page.final_url, "signals": asdict(signals), "findings": findings})
        print(f"\nJSON report written to {args.json}")
    return 2 if any(item["status"] == "fail" for item in findings) else 0


def _focused_audit(url: str, timeout: int, user_agent: str, kind: str) -> tuple[core.PageSnapshot, dict[str, core.FactorResult]]:
    snapshot = core.build_snapshot(url, None, None, timeout, user_agent, auto_sitemap=True)
    base = core.evaluate_factors(snapshot, "generic", "*")
    base.update(enhance_factors(snapshot, "geo" if kind == "geo" else "aeo", "OAI-SearchBot", timeout, user_agent))
    return snapshot, base


def run_geo(args: argparse.Namespace, console: core.Console) -> int:
    snapshot, factors = _focused_audit(args.url, args.timeout, args.user_agent, "geo")
    groups = {
        "Crawler access": ["status_200", "robots_allowed", "no_noindex", "ai_crawler_access", "llms_txt"],
        "Entity clarity": ["schema_entity", "schema_website", "schema_sameas", "about_contact_links", "author_or_reviewer"],
        "Source and freshness": ["source_links", "dates_present", "sitemap_inclusion", "lastmod_present"],
        "Machine readability": ["structured_data_valid", "schema_webpage", "canonical_consistent", "lang_declared"],
    }
    print(console.paint("GEO / Entity Discoverability Audit", core.Style.BOLD, core.Style.CYAN))
    print(f"  Page: {snapshot.fetch.final_url} (HTTP {snapshot.fetch.status or 'network error'})")
    print("  This is a diagnostic lens, not a guarantee of inclusion in an AI answer.\n")
    failures = 0
    for label, names in groups.items():
        print(console.paint(label, core.Style.BOLD, core.Style.WHITE))
        for name in names:
            result = factors[name]
            _print_problem(console, result.status, name.replace("_", " "), result.message)
            failures += result.status == "fail"
        print()
    if args.json:
        core.write_json(args.json, {"tool": "geo", "version": core.VERSION, "url": snapshot.fetch.final_url, "groups": groups, "factors": {key: asdict(value) for key, value in factors.items()}})
        print(f"JSON report written to {args.json}")
    return 2 if failures else 0


def run_aeo(args: argparse.Namespace, console: core.Console) -> int:
    snapshot, factors = _focused_audit(args.url, args.timeout, args.user_agent, "aeo")
    groups = {
        "Answer structure": ["question_headings", "answer_blocks", "lists_or_tables", "concise_structure", "heading_structure"],
        "Semantic answer markup": ["faq_qa_schema", "structured_data_valid", "schema_webpage", "speakable"],
        "Trust and freshness": ["author_or_reviewer", "dates_present", "source_links", "schema_entity"],
        "Eligibility": ["status_200", "robots_allowed", "no_noindex", "canonical_consistent", "indexable_text"],
    }
    print(console.paint("AEO / Answer Extractability Audit", core.Style.BOLD, core.Style.CYAN))
    print(f"  Page: {snapshot.fetch.final_url} (HTTP {snapshot.fetch.status or 'network error'})")
    print("  This measures machine-readable answer structure, not answer-engine placement.\n")
    failures = 0
    for label, names in groups.items():
        print(console.paint(label, core.Style.BOLD, core.Style.WHITE))
        for name in names:
            result = factors[name]
            _print_problem(console, result.status, name.replace("_", " "), result.message)
            failures += result.status == "fail"
        print()
    if args.json:
        core.write_json(args.json, {"tool": "aeo", "version": core.VERSION, "url": snapshot.fetch.final_url, "groups": groups, "factors": {key: asdict(value) for key, value in factors.items()}})
        print(f"JSON report written to {args.json}")
    return 2 if failures else 0
