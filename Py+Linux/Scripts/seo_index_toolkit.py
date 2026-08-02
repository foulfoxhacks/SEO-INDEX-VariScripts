#!/usr/bin/env python3
"""SEO-INDEX VariScripts terminal toolkit.

Dependency-light, cross-platform tools for:
- engine-specific index-readiness scoring (Google, Bing, generic)
- canonical signal auditing
- sitemap health checks
- indexability checks
- launching the existing IndexNow runner
- category-focused redirect, robots, hreflang, schema, GEO, and AEO audits

The scores are transparent diagnostics based on public documentation. They are
not official search-engine scores and do not predict ranking or guarantee indexing.
"""

from __future__ import annotations

import argparse
import codecs
import collections
import concurrent.futures
import json
import math
import os
import re
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.request
import urllib.robotparser
import webbrowser
import xml.etree.ElementTree as ET
import zlib
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, Optional
from urllib.parse import SplitResult, urljoin, urlsplit, urlunsplit

VERSION = "1.4.0"
TOOL_NAME = "SEO-INDEX VariScripts"
DEFAULT_USER_AGENT = f"SEO-INDEX-VariScripts/{VERSION}"
SUPPORTED_SCHEMES = {"http", "https"}
KEY_PATTERN = re.compile(r"^[A-Za-z0-9-]{8,128}$")
DIRECTIVE_SPLIT = re.compile(r"[\s,]+")
WORKBENCH_URL = "https://webtools.mellozone.site/"
MAX_SITEMAP_BYTES = 50 * 1024 * 1024
CHARSET_RE = re.compile(r"charset\s*=\s*[\"']?\s*([A-Za-z0-9._:+-]+)", re.I)
META_CHARSET_RE = re.compile(
    br"<meta\s+[^>]*(?:charset\s*=\s*[\"']?\s*([A-Za-z0-9._:+-]+)|content\s*=\s*[\"'][^\"']*charset\s*=\s*([A-Za-z0-9._:+-]+))",
    re.I,
)


class ToolkitError(RuntimeError):
    """Expected user, validation, parsing, or network failure."""


class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[97m"


@dataclass
class Console:
    color: bool = True
    animation: bool = True

    def paint(self, text: str, *styles: str) -> str:
        if not self.color:
            return text
        return "".join(styles) + text + Style.RESET

    def status(self, status: str) -> str:
        labels = {
            "pass": ("PASS", Style.GREEN),
            "warn": ("WARN", Style.YELLOW),
            "fail": ("FAIL", Style.RED),
            "unknown": ("N/A ", Style.DIM),
        }
        label, color = labels.get(status, (status.upper()[:4], Style.WHITE))
        return self.paint(label, Style.BOLD, color)


def supports_color() -> bool:
    if os.environ.get("NO_COLOR") is not None:
        return False
    if not sys.stdout.isatty():
        return False
    if os.name == "nt":
        return bool(os.environ.get("WT_SESSION") or os.environ.get("ANSICON") or os.environ.get("TERM"))
    return os.environ.get("TERM", "") != "dumb"


def clear_previous_lines(count: int) -> None:
    if count <= 0:
        return
    sys.stdout.write(f"\033[{count}F")
    for _ in range(count):
        sys.stdout.write("\033[2K\n")
    sys.stdout.write(f"\033[{count}F")
    sys.stdout.flush()


def show_splash(console: Console) -> None:
    """Render a short fox-tail swish when attached to an interactive terminal."""
    frames = [
        [
            "          /\\_/\\",
            "         ( o.o )       ~~~~)",
            "          > ^ <",
        ],
        [
            "          /\\_/\\",
            "         ( o.o )     ~~~~)",
            "          > ^ <",
        ],
        [
            "          /\\_/\\",
            "         ( o.o )   ~~~~)",
            "          > ^ <",
        ],
        [
            "          /\\_/\\",
            "         ( o.o )     ~~~~)",
            "          > ^ <",
        ],
    ]

    if console.animation and sys.stdout.isatty():
        for index, frame in enumerate(frames):
            if index:
                clear_previous_lines(len(frame))
            for line in frame:
                print(console.paint(line, Style.MAGENTA, Style.BOLD))
            time.sleep(0.09)
    else:
        for line in frames[-1]:
            print(console.paint(line, Style.MAGENTA, Style.BOLD))

    title = f" {TOOL_NAME} v{VERSION} "
    width = 58
    print(console.paint("╭" + "─" * width + "╮", Style.CYAN))
    print(console.paint("│", Style.CYAN) + console.paint(title.center(width), Style.BOLD, Style.WHITE) + console.paint("│", Style.CYAN))
    print(console.paint("│", Style.CYAN) + " foulfoxhacks  •  aka The Dev Sammy".ljust(width) + console.paint("│", Style.CYAN))
    print(console.paint("│", Style.CYAN) + " Search signals, untangled.".ljust(width) + console.paint("│", Style.CYAN))
    print(console.paint("╰" + "─" * width + "╯", Style.CYAN))
    print()


@dataclass
class FetchResult:
    requested_url: str
    final_url: str
    status: int
    headers: dict[str, str]
    data: bytes
    elapsed_ms: int
    error: Optional[str] = None

    @property
    def text(self) -> str:
        return decode_http_body(self.data, self.headers.get("content-type", ""))


@dataclass
class HtmlSignals:
    title: str = ""
    description: str = ""
    canonical: str = ""
    viewport: str = ""
    h1_count: int = 0
    body_text_length: int = 0
    meta_robots: dict[str, set[str]] = field(default_factory=dict)
    json_ld_blocks: int = 0
    json_ld_valid: int = 0
    json_ld_errors: list[str] = field(default_factory=list)


@dataclass
class SitemapEntry:
    url: str
    lastmod: str = ""
    source: str = ""


@dataclass
class SitemapCollection:
    roots: list[str]
    entries: list[SitemapEntry]
    visited: list[str]
    errors: list[str]
    duplicate_count: int

    def by_url(self) -> dict[str, SitemapEntry]:
        result: dict[str, SitemapEntry] = {}
        for entry in self.entries:
            try:
                result.setdefault(normalize_url(entry.url), entry)
            except ToolkitError:
                continue
        return result


@dataclass
class FactorResult:
    status: str
    message: str
    evidence: Any = None


@dataclass
class PageSnapshot:
    requested_url: str
    fetch: FetchResult
    html: HtmlSignals
    robots_url: str
    robots_text: str
    robots_status: Optional[int]
    sitemap: Optional[SitemapCollection]
    sitemap_url_used: Optional[str]
    sitemap_entry: Optional[SitemapEntry]
    key_location: Optional[str]
    key_ready: Optional[bool]
    key_message: str
    notes: list[str] = field(default_factory=list)


@dataclass
class ScoreResult:
    engine: str
    label: str
    raw_points: float
    verified_max: float
    verified_score: int
    assured_score: int
    normalized_score: int
    coverage: int
    grade: str
    capped: bool
    categories: dict[str, dict[str, Any]]
    factors: dict[str, dict[str, Any]]


class PageHTMLParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title_parts: list[str] = []
        self.in_title = False
        self.in_h1 = 0
        self.h1_count = 0
        self.in_script = False
        self.script_type = ""
        self.script_parts: list[str] = []
        self.json_ld_raw: list[str] = []
        self.skip_depth = 0
        self.body_text: list[str] = []
        self.description = ""
        self.canonical = ""
        self.viewport = ""
        self.meta_robots: dict[str, set[str]] = {}

    @staticmethod
    def attrs_dict(attrs: list[tuple[str, Optional[str]]]) -> dict[str, str]:
        return {str(k).lower(): (v or "") for k, v in attrs}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        values = self.attrs_dict(attrs)
        if tag == "title":
            self.in_title = True
        elif tag == "h1":
            self.h1_count += 1
            self.in_h1 += 1
        elif tag in {"style", "noscript"}:
            self.skip_depth += 1
        elif tag == "script":
            self.in_script = True
            self.script_type = values.get("type", "").lower().strip()
            self.script_parts = []
        elif tag == "meta":
            name = values.get("name", "").lower().strip()
            content = values.get("content", "").strip()
            if name == "description" and not self.description:
                self.description = content
            elif name == "viewport" and not self.viewport:
                self.viewport = content
            elif name in {"robots", "googlebot", "bingbot"}:
                self.meta_robots.setdefault(name, set()).update(parse_directives(content))
        elif tag == "link":
            rel_tokens = {token.lower() for token in values.get("rel", "").split()}
            href = values.get("href", "").strip()
            if "canonical" in rel_tokens and href and not self.canonical:
                self.canonical = urljoin(self.base_url, href)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self.in_title = False
        elif tag == "h1" and self.in_h1:
            self.in_h1 -= 1
        elif tag in {"style", "noscript"} and self.skip_depth:
            self.skip_depth -= 1
        elif tag == "script":
            if self.script_type == "application/ld+json":
                self.json_ld_raw.append("".join(self.script_parts).strip())
            self.in_script = False
            self.script_type = ""
            self.script_parts = []

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        if self.in_script:
            self.script_parts.append(data)
            return
        if self.skip_depth == 0:
            text = " ".join(data.split())
            if text:
                self.body_text.append(text)

    def signals(self) -> HtmlSignals:
        errors: list[str] = []
        valid = 0
        for index, raw in enumerate(self.json_ld_raw, start=1):
            if not raw:
                errors.append(f"JSON-LD block {index} is empty.")
                continue
            try:
                json.loads(raw)
                valid += 1
            except json.JSONDecodeError as exc:
                errors.append(f"JSON-LD block {index}: {exc.msg} at line {exc.lineno}.")
        return HtmlSignals(
            title=" ".join("".join(self.title_parts).split()),
            description=self.description,
            canonical=self.canonical,
            viewport=self.viewport,
            h1_count=self.h1_count,
            body_text_length=len(" ".join(self.body_text)),
            meta_robots=self.meta_robots,
            json_ld_blocks=len(self.json_ld_raw),
            json_ld_valid=valid,
            json_ld_errors=errors,
        )


def parse_directives(value: str) -> set[str]:
    return {item.lower() for item in DIRECTIVE_SPLIT.split(value.strip()) if item}


def decode_http_body(data: bytes, content_type: str = "") -> str:
    """Decode an HTTP body using declared/BOM encodings with web-safe fallbacks."""
    candidates: list[str] = []
    header_match = CHARSET_RE.search(content_type or "")
    if header_match:
        candidates.append(header_match.group(1))
    if data.startswith(codecs.BOM_UTF8):
        candidates.insert(0, "utf-8-sig")
    elif data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        candidates.insert(0, "utf-16")
    elif data.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
        candidates.insert(0, "utf-32")
    meta_match = META_CHARSET_RE.search(data[:4096])
    if meta_match:
        raw = meta_match.group(1) or meta_match.group(2)
        if raw:
            candidates.append(raw.decode("ascii", errors="ignore"))
    candidates.extend(["utf-8", "windows-1252"])
    for encoding in dict.fromkeys(item.strip().lower() for item in candidates if item):
        try:
            codecs.lookup(encoding)
            return data.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("utf-8", errors="replace")


def _normalized_hostname(hostname: str) -> str:
    host = hostname.rstrip(".").lower()
    if ":" in host:  # IPv6 literals are already ASCII and need brackets in a URL authority.
        return host
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ToolkitError(f"URL contains an invalid hostname: {hostname}") from exc


def _authority_host(hostname: str) -> str:
    return f"[{hostname}]" if ":" in hostname and not hostname.startswith("[") else hostname


def normalize_url(value: str) -> str:
    parsed = require_http_url(value, "URL")
    host = _normalized_hostname(parsed.hostname or "")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ToolkitError(f"URL contains an invalid port: {value}") from exc
    if (parsed.scheme.lower() == "http" and port == 80) or (parsed.scheme.lower() == "https" and port == 443):
        port = None
    authority_host = _authority_host(host)
    netloc = authority_host if port is None else f"{authority_host}:{port}"
    path = parsed.path or "/"
    return urlunsplit((parsed.scheme.lower(), netloc, path, parsed.query, ""))


def require_http_url(value: str, label: str) -> SplitResult:
    parsed = urlsplit(value.strip())
    if parsed.scheme.lower() not in SUPPORTED_SCHEMES or not parsed.hostname:
        raise ToolkitError(f"{label} must be an absolute HTTP or HTTPS URL: {value}")
    if parsed.username or parsed.password:
        raise ToolkitError(f"{label} must not include embedded credentials: {value}")
    return parsed


def origin_for(value: str) -> str:
    parsed = require_http_url(value, "URL")
    host = _authority_host(_normalized_hostname(parsed.hostname or ""))
    try:
        port = parsed.port
    except ValueError as exc:
        raise ToolkitError(f"URL contains an invalid port: {value}") from exc
    if port and not ((parsed.scheme == "http" and port == 80) or (parsed.scheme == "https" and port == 443)):
        host = f"{host}:{port}"
    return f"{parsed.scheme.lower()}://{host.lower()}"


class ValidatingRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Apply the caller's URL policy to every redirect before opening it."""

    def __init__(self, validator: Callable[[str], None]) -> None:
        super().__init__()
        self.validator = validator

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> Optional[urllib.request.Request]:
        resolved = urljoin(req.full_url, newurl)
        require_http_url(resolved, "Redirect URL")
        self.validator(resolved)
        return super().redirect_request(req, fp, code, msg, headers, resolved)


def _bounded_gzip_decompress(data: bytes, max_bytes: int, url: str) -> bytes:
    try:
        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
        output = decoder.decompress(data, max_bytes + 1)
        if len(output) <= max_bytes:
            output += decoder.flush(max_bytes + 1 - len(output))
    except zlib.error as exc:
        raise ToolkitError(f"Response used invalid gzip compression: {url}") from exc
    if len(output) > max_bytes or decoder.unconsumed_tail:
        raise ToolkitError(f"Decompressed response exceeded {max_bytes:,} bytes: {url}")
    if not decoder.eof:
        raise ToolkitError(f"Response used incomplete gzip compression: {url}")
    return output


def _read_response_body(response: Any, max_bytes: int, url: str) -> bytes:
    data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ToolkitError(f"Response exceeded {max_bytes:,} bytes: {url}")
    if data[:2] == b"\x1f\x8b":
        return _bounded_gzip_decompress(data, max_bytes, url)
    return data


def fetch_url(
    url: str,
    timeout: int,
    user_agent: str,
    accept: str = "text/html,application/xhtml+xml,application/xml,text/xml,text/plain,*/*",
    max_bytes: int = 10 * 1024 * 1024,
    url_validator: Optional[Callable[[str], None]] = None,
) -> FetchResult:
    require_http_url(url, "URL")
    if url_validator:
        url_validator(url)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": accept,
            "Accept-Encoding": "gzip",
        },
        method="GET",
    )
    started = time.perf_counter()
    opener = urllib.request.build_opener(ValidatingRedirectHandler(url_validator)) if url_validator else urllib.request.build_opener()
    try:
        with opener.open(request, timeout=timeout) as response:
            data = _read_response_body(response, max_bytes, url)
            return FetchResult(
                requested_url=url,
                final_url=response.geturl(),
                status=int(response.status),
                headers={k.lower(): v for k, v in response.headers.items()},
                data=data,
                elapsed_ms=int((time.perf_counter() - started) * 1000),
            )
    except urllib.error.HTTPError as exc:
        data = _read_response_body(exc, max_bytes, url)
        return FetchResult(
            requested_url=url,
            final_url=exc.geturl() or url,
            status=int(exc.code),
            headers={k.lower(): v for k, v in exc.headers.items()} if exc.headers else {},
            data=data,
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            error=str(exc),
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return FetchResult(
            requested_url=url,
            final_url=url,
            status=0,
            headers={},
            data=b"",
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            error=str(getattr(exc, "reason", exc)),
        )


def parse_html(fetch: FetchResult) -> HtmlSignals:
    content_type = fetch.headers.get("content-type", "").lower()
    if fetch.status == 0 or ("html" not in content_type and not fetch.text.lstrip().lower().startswith(("<!doctype html", "<html"))):
        return HtmlSignals()
    parser = PageHTMLParser(fetch.final_url)
    try:
        parser.feed(fetch.text)
        parser.close()
    except Exception as exc:  # HTMLParser is permissive, but retain a usable partial result.
        signals = parser.signals()
        signals.json_ld_errors.append(f"HTML parser warning: {exc}")
        return signals
    return parser.signals()


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def fetch_sitemaps(
    roots: Iterable[str],
    timeout: int,
    user_agent: str,
    max_sitemaps: int = 1000,
    max_entries: int = 1_000_000,
    url_validator: Optional[Callable[[str], None]] = None,
) -> SitemapCollection:
    visited: set[str] = set()
    entries: list[SitemapEntry] = []
    errors: list[str] = []
    seen_counts: dict[str, int] = {}
    root_list = list(dict.fromkeys(roots))
    queue = collections.deque(root_list)
    traversal_limited = False
    entry_limited = False

    while queue and not entry_limited:
        url = queue.popleft()
        try:
            normalized = normalize_url(url)
        except ToolkitError as exc:
            errors.append(str(exc))
            continue
        if normalized in visited:
            continue
        if len(visited) >= max_sitemaps:
            if not traversal_limited:
                errors.append(f"Sitemap traversal exceeded {max_sitemaps} files.")
                traversal_limited = True
            continue
        visited.add(normalized)
        result = fetch_url(
            url,
            timeout,
            user_agent,
            accept="application/xml,text/xml,text/plain,*/*",
            max_bytes=MAX_SITEMAP_BYTES,
            url_validator=url_validator,
        )
        if result.status != 200:
            errors.append(f"Sitemap {url} returned HTTP {result.status or 'network error'}.")
            continue
        try:
            root = ET.fromstring(result.text)
        except ET.ParseError as exc:
            errors.append(f"Sitemap {url} is invalid XML: {exc}.")
            continue
        root_type = local_name(root.tag)
        if root_type == "sitemapindex":
            child_count = 0
            for sitemap in root:
                if local_name(sitemap.tag) != "sitemap":
                    continue
                for child in sitemap:
                    if local_name(child.tag) == "loc" and child.text and child.text.strip():
                        child_count += 1
                        queue.append(child.text.strip())
                        break
            if child_count == 0:
                errors.append(f"Sitemap index {url} has no child sitemap URLs.")
            continue
        if root_type != "urlset":
            errors.append(f"Sitemap {url} has unsupported root <{root_type}>.")
            continue
        for node in root:
            if local_name(node.tag) != "url":
                continue
            loc = ""
            lastmod = ""
            for child in node:
                name = local_name(child.tag)
                if name == "loc" and child.text:
                    loc = child.text.strip()
                elif name == "lastmod" and child.text:
                    lastmod = child.text.strip()
            if not loc:
                errors.append(f"An <url> entry in {url} is missing <loc>.")
                continue
            if len(entries) >= max_entries:
                if not entry_limited:
                    errors.append(f"Sitemap inventory exceeded {max_entries:,} URL entries.")
                    entry_limited = True
                break
            entries.append(SitemapEntry(loc, lastmod, url))
            try:
                key = normalize_url(loc)
            except ToolkitError:
                key = loc
            seen_counts[key] = seen_counts.get(key, 0) + 1

    duplicate_count = sum(count - 1 for count in seen_counts.values() if count > 1)
    return SitemapCollection(root_list, entries, sorted(visited), errors, duplicate_count)


def sitemap_urls_from_robots(text: str) -> list[str]:
    values: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("sitemap:"):
            value = stripped.split(":", 1)[1].strip()
            if value:
                values.append(value)
    return list(dict.fromkeys(values))


def parse_x_robots(headers: dict[str, str], engine: str) -> set[str]:
    raw = headers.get("x-robots-tag", "")
    if not raw:
        return set()
    directives: set[str] = set()
    engine_key = {"google": "googlebot", "bing": "bingbot"}.get(engine, "")
    for segment in raw.split(";"):
        segment = segment.strip()
        if not segment:
            continue
        if ":" in segment:
            prefix, value = segment.split(":", 1)
            prefix = prefix.strip().lower()
            if prefix in {"googlebot", "bingbot", "*"}:
                if prefix in {engine_key, "*"}:
                    directives.update(parse_directives(value))
                continue
        directives.update(parse_directives(segment))
    return directives


def robots_can_fetch(robots_text: str, robots_url: str, crawler: str, target_url: str) -> Optional[bool]:
    if not robots_text:
        return None
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(robots_text.splitlines())
    return parser.can_fetch(crawler, target_url)


def key_scope_directory(key_location: str) -> str:
    parsed = require_http_url(key_location, "IndexNow key location")
    directory = str(PurePosixPath(parsed.path or "/").parent)
    if directory in {"", "."}:
        directory = "/"
    if not directory.startswith("/"):
        directory = "/" + directory
    if directory != "/" and not directory.endswith("/"):
        directory += "/"
    return directory


def validate_indexnow_key(key_location: str, target_url: str, timeout: int, user_agent: str) -> tuple[bool, str]:
    result = fetch_url(key_location, timeout, user_agent, accept="text/plain,*/*", max_bytes=4096)
    if result.status != 200:
        return False, f"Key file returned HTTP {result.status or 'network error'}."
    key = result.text.strip().lstrip("\ufeff")
    if not KEY_PATTERN.fullmatch(key):
        return False, "Key file does not contain one valid 8-128 character IndexNow key."
    key_url = urlsplit(result.final_url)
    target = urlsplit(target_url)
    if (key_url.hostname or "").lower() != (target.hostname or "").lower():
        return False, "Key file host differs from the audited URL host."
    scope = key_scope_directory(result.final_url)
    if scope != "/" and not (target.path or "/").startswith(scope):
        return False, f"Audited URL is outside key path scope {scope}."
    return True, f"Hosted key is valid and covers {target.hostname}."


def build_snapshot(
    url: str,
    sitemap_url: Optional[str],
    key_location: Optional[str],
    timeout: int,
    user_agent: str,
    auto_sitemap: bool = True,
) -> PageSnapshot:
    requested = normalize_url(url)
    page = fetch_url(requested, timeout, user_agent)
    html = parse_html(page)
    base_url = page.final_url if page.final_url else requested
    robots_url = origin_for(base_url) + "/robots.txt"
    robots_fetch = fetch_url(robots_url, timeout, user_agent, accept="text/plain,*/*", max_bytes=2 * 1024 * 1024)
    robots_text = robots_fetch.text if robots_fetch.status == 200 else ""
    notes: list[str] = []
    if robots_fetch.status not in {200, 404}:
        notes.append(f"robots.txt returned HTTP {robots_fetch.status or 'network error'}.")

    selected_sitemap = sitemap_url
    if not selected_sitemap and auto_sitemap:
        discovered = sitemap_urls_from_robots(robots_text)
        selected_sitemap = discovered[0] if discovered else origin_for(base_url) + "/sitemap.xml"

    sitemap: Optional[SitemapCollection] = None
    sitemap_entry: Optional[SitemapEntry] = None
    if selected_sitemap:
        sitemap = fetch_sitemaps([selected_sitemap], timeout, user_agent)
        if sitemap.entries:
            index = sitemap.by_url()
            sitemap_entry = index.get(normalize_url(base_url)) or index.get(requested)
        elif not sitemap_url:
            notes.append("No usable sitemap was auto-discovered.")

    key_ready: Optional[bool] = None
    key_message = "IndexNow key location was not supplied."
    if key_location:
        key_ready, key_message = validate_indexnow_key(key_location, base_url, timeout, user_agent)

    return PageSnapshot(
        requested_url=requested,
        fetch=page,
        html=html,
        robots_url=robots_url,
        robots_text=robots_text,
        robots_status=robots_fetch.status,
        sitemap=sitemap,
        sitemap_url_used=selected_sitemap,
        sitemap_entry=sitemap_entry,
        key_location=key_location,
        key_ready=key_ready,
        key_message=key_message,
        notes=notes,
    )


def evaluate_factors(snapshot: PageSnapshot, engine: str, crawler: str) -> dict[str, FactorResult]:
    fetch = snapshot.fetch
    html = snapshot.html
    factors: dict[str, FactorResult] = {}
    page_available = fetch.status > 0 and bool(fetch.data)

    factors["status_200"] = FactorResult(
        "pass" if fetch.status == 200 else "fail",
        f"Final HTTP status is {fetch.status}." if fetch.status else f"Request failed: {fetch.error or 'unknown network error'}.",
        {"requested": fetch.requested_url, "final": fetch.final_url, "status": fetch.status, "elapsedMs": fetch.elapsed_ms},
    )

    scheme = urlsplit(fetch.final_url or snapshot.requested_url).scheme.lower()
    factors["https"] = FactorResult(
        "pass" if scheme == "https" else "warn",
        "Page uses HTTPS." if scheme == "https" else "Page does not use HTTPS.",
        scheme,
    )

    can_fetch = robots_can_fetch(snapshot.robots_text, snapshot.robots_url, crawler, fetch.final_url or snapshot.requested_url)
    if can_fetch is None:
        status = "pass" if snapshot.robots_status == 404 else "unknown"
        message = "No robots.txt restrictions were found." if snapshot.robots_status == 404 else "robots.txt could not be evaluated."
    else:
        status = "pass" if can_fetch else "fail"
        message = f"{crawler} is allowed by robots.txt." if can_fetch else f"{crawler} is blocked by robots.txt."
    factors["robots_allowed"] = FactorResult(status, message, snapshot.robots_url)

    generic_directives = set(html.meta_robots.get("robots", set()))
    engine_meta_name = {"google": "googlebot", "bing": "bingbot"}.get(engine, "")
    engine_directives = set(html.meta_robots.get(engine_meta_name, set())) if engine_meta_name else set()
    header_directives = parse_x_robots(fetch.headers, engine)
    effective_directives = generic_directives | engine_directives | header_directives
    has_noindex = "noindex" in effective_directives or "none" in effective_directives
    if not page_available:
        factors["no_noindex"] = FactorResult("unknown", "Index directives could not be read because the page was unavailable.")
    else:
        factors["no_noindex"] = FactorResult(
            "fail" if has_noindex else "pass",
            f"Effective directives include {', '.join(sorted(effective_directives))}." if effective_directives else "No noindex directive was found.",
            sorted(effective_directives),
        )

    canonical = html.canonical.strip()
    final_normalized = normalize_url(fetch.final_url or snapshot.requested_url)
    if not page_available:
        factors["canonical_consistent"] = FactorResult("unknown", "Canonical annotation could not be read because the page was unavailable.")
    elif not canonical:
        factors["canonical_consistent"] = FactorResult("warn", "No rel=canonical annotation was found.")
    else:
        try:
            canonical_normalized = normalize_url(canonical)
            if canonical_normalized == final_normalized:
                factors["canonical_consistent"] = FactorResult("pass", "Canonical matches the final URL.", canonical_normalized)
            else:
                factors["canonical_consistent"] = FactorResult(
                    "fail",
                    "Canonical points to a different URL than the final page URL.",
                    {"canonical": canonical_normalized, "final": final_normalized},
                )
        except ToolkitError as exc:
            factors["canonical_consistent"] = FactorResult("fail", f"Canonical URL is invalid: {exc}", canonical)

    text_length = html.body_text_length
    if not page_available:
        text_status = "unknown"
        text_message = "Page text could not be evaluated because the page was unavailable."
    elif text_length >= 300:
        text_status = "pass"
        text_message = f"Page exposes about {text_length:,} characters of crawlable text."
    elif text_length >= 80:
        text_status = "warn"
        text_message = f"Page exposes only about {text_length:,} characters of crawlable text."
    else:
        text_status = "fail"
        text_message = f"Very little crawlable text was detected ({text_length:,} characters)."
    factors["indexable_text"] = FactorResult(text_status, text_message, text_length)

    factors["title"] = FactorResult(
        "unknown" if not page_available else ("pass" if html.title else "fail"),
        "Title could not be evaluated." if not page_available else (f"Title: {html.title}" if html.title else "No HTML title was found."),
        html.title,
    )
    factors["meta_description"] = FactorResult(
        "unknown" if not page_available else ("pass" if html.description else "warn"),
        "Meta description could not be evaluated." if not page_available else ("Meta description is present." if html.description else "Meta description is missing."),
        html.description,
    )
    factors["h1"] = FactorResult(
        "unknown" if not page_available else ("pass" if html.h1_count == 1 else ("warn" if html.h1_count > 1 else "fail")),
        "H1 elements could not be evaluated." if not page_available else f"Detected {html.h1_count} H1 element(s).",
        html.h1_count,
    )
    factors["mobile_viewport"] = FactorResult(
        "unknown" if not page_available else ("pass" if html.viewport else "warn"),
        "Viewport metadata could not be evaluated." if not page_available else ("Viewport metadata is present." if html.viewport else "Viewport metadata was not found."),
        html.viewport,
    )
    if not page_available:
        structured_status = "unknown"
        structured_message = "Structured data could not be evaluated."
    elif html.json_ld_blocks == 0:
        structured_status = "warn"
        structured_message = "No JSON-LD structured data blocks were found."
    elif html.json_ld_valid == html.json_ld_blocks:
        structured_status = "pass"
        structured_message = f"All {html.json_ld_blocks} JSON-LD block(s) contain valid JSON."
    else:
        structured_status = "fail"
        structured_message = f"Only {html.json_ld_valid} of {html.json_ld_blocks} JSON-LD block(s) contain valid JSON."
    factors["structured_data"] = FactorResult(
        structured_status,
        structured_message,
        {"blocks": html.json_ld_blocks, "valid": html.json_ld_valid, "errors": html.json_ld_errors},
    )

    if snapshot.sitemap is None or not snapshot.sitemap.entries:
        factors["sitemap_inclusion"] = FactorResult("unknown", "No usable sitemap was supplied or discovered.", snapshot.sitemap_url_used)
        factors["lastmod_present"] = FactorResult("unknown", "Sitemap lastmod could not be evaluated.")
    elif snapshot.sitemap_entry:
        factors["sitemap_inclusion"] = FactorResult("pass", "Final URL is present in the sitemap.", snapshot.sitemap_entry.source)
        factors["lastmod_present"] = FactorResult(
            "pass" if snapshot.sitemap_entry.lastmod else "warn",
            f"Sitemap lastmod: {snapshot.sitemap_entry.lastmod}" if snapshot.sitemap_entry.lastmod else "Sitemap entry has no lastmod value.",
            snapshot.sitemap_entry.lastmod,
        )
    else:
        factors["sitemap_inclusion"] = FactorResult("fail", "Final URL was not found in the sitemap.", snapshot.sitemap_url_used)
        factors["lastmod_present"] = FactorResult("unknown", "No matching sitemap entry exists.")

    if snapshot.key_ready is None:
        factors["indexnow_ready"] = FactorResult("unknown", snapshot.key_message)
    else:
        factors["indexnow_ready"] = FactorResult(
            "pass" if snapshot.key_ready else "fail",
            snapshot.key_message,
            snapshot.key_location,
        )

    return factors


def load_profiles(profile_path: Optional[str] = None) -> dict[str, dict[str, Any]]:
    if profile_path:
        path = Path(profile_path)
    else:
        path = Path(__file__).resolve().parents[2] / "Config" / "engine_profiles.json"
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
        profiles = content["profiles"]
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        raise ToolkitError(f"Could not load engine profiles from {path}: {exc}") from exc
    for name, profile in profiles.items():
        if "categories" in profile:
            categories = profile.get("categories", {})
            category_total = sum(float(value.get("weight", 0)) for value in categories.values())
            if round(category_total, 6) != 100:
                raise ToolkitError(f"Engine profile {name!r} category weights must total 100.")
            for category_name, category in categories.items():
                factor_total = sum(float(value) for value in category.get("factors", {}).values())
                if round(factor_total, 6) != 100:
                    raise ToolkitError(
                        f"Engine profile {name!r} category {category_name!r} factor weights must total 100."
                    )
        else:
            weights = profile.get("weights", {})
            if round(sum(float(value) for value in weights.values()), 6) != 100:
                raise ToolkitError(f"Engine profile {name!r} weights must total 100.")
    return profiles


def _profile_factor_map(profile: dict[str, Any]) -> tuple[dict[str, float], dict[str, dict[str, Any]]]:
    """Return effective factor weights and category metadata.

    Schema v2 profiles weight categories to 100, then weight factors to 100 inside
    each category. Effective factor points are category_weight * factor_weight / 100.
    Legacy flat profiles remain supported.
    """
    if "categories" not in profile:
        return ({name: float(weight) for name, weight in profile.get("weights", {}).items()}, {})
    effective: dict[str, float] = {}
    metadata: dict[str, dict[str, Any]] = {}
    for category_name, category in profile["categories"].items():
        category_weight = float(category["weight"])
        factor_names: list[str] = []
        for factor_name, factor_weight in category.get("factors", {}).items():
            effective_weight = category_weight * float(factor_weight) / 100.0
            effective[factor_name] = effective.get(factor_name, 0.0) + effective_weight
            factor_names.append(factor_name)
        metadata[category_name] = {
            "label": category.get("label", category_name.replace("_", " ").title()),
            "weight": category_weight,
            "factorNames": factor_names,
        }
    return effective, metadata


def calculate_score(engine: str, profile: dict[str, Any], factors: dict[str, FactorResult]) -> ScoreResult:
    multipliers = {"pass": 1.0, "warn": 0.5, "fail": 0.0}
    factor_weights, category_metadata = _profile_factor_map(profile)
    earned = 0.0
    verified_max = 0.0
    serialized: dict[str, dict[str, Any]] = {}
    critical_failure = False
    critical = set(profile.get("critical", []))
    for factor_name, weight in factor_weights.items():
        result = factors.get(factor_name, FactorResult("unknown", "Check is not implemented."))
        points: Optional[float]
        if result.status == "unknown":
            points = None
        else:
            verified_max += weight
            points = weight * multipliers.get(result.status, 0.0)
            earned += points
        if factor_name in critical and result.status == "fail":
            critical_failure = True
        serialized[factor_name] = {
            "status": result.status,
            "message": result.message,
            "evidence": result.evidence,
            "weight": round(weight, 3),
            "points": None if points is None else round(points, 3),
        }

    verified_score = round((earned / verified_max) * 100) if verified_max else 0
    coverage = round(verified_max)
    # Evidence assurance prevents an impressive score from hiding a mostly-unverified profile.
    # Square-root scaling is deliberately moderate: 81% coverage retains 90% of the verified score.
    assured_score = round(verified_score * math.sqrt(max(0.0, min(1.0, verified_max / 100.0)))) if verified_max else 0
    capped = False
    if critical_failure:
        if verified_score > 49:
            verified_score = 49
        if assured_score > 49:
            assured_score = 49
        capped = True

    categories: dict[str, dict[str, Any]] = {}
    for category_name, metadata in category_metadata.items():
        names = metadata["factorNames"]
        category_earned = sum(float(serialized[name]["points"] or 0) for name in names)
        category_verified = sum(float(serialized[name]["weight"]) for name in names if serialized[name]["points"] is not None)
        category_weight = float(metadata["weight"])
        category_verified_score = round((category_earned / category_verified) * 100) if category_verified else 0
        category_coverage = round((category_verified / category_weight) * 100) if category_weight else 0
        category_assured = round(category_verified_score * math.sqrt(max(0.0, min(1.0, category_coverage / 100.0)))) if category_verified else 0
        categories[category_name] = {
            "label": metadata["label"],
            "weight": category_weight,
            "verifiedScore": category_verified_score,
            "assuredScore": category_assured,
            "coverage": category_coverage,
            "earned": round(category_earned, 2),
            "verifiedMax": round(category_verified, 2),
            "factors": names,
        }

    if assured_score >= 90:
        grade = "Excellent"
    elif assured_score >= 75:
        grade = "Strong"
    elif assured_score >= 60:
        grade = "Needs work"
    elif assured_score >= 40:
        grade = "Weak"
    else:
        grade = "Critical"
    return ScoreResult(
        engine=engine,
        label=profile["label"],
        raw_points=round(earned, 1),
        verified_max=round(verified_max, 1),
        verified_score=verified_score,
        assured_score=assured_score,
        normalized_score=assured_score,
        coverage=coverage,
        grade=grade,
        capped=capped,
        categories=categories,
        factors=serialized,
    )


def progress_bar(value: int, width: int = 30) -> str:
    bounded = max(0, min(100, value))
    filled = round((bounded / 100) * width)
    return "█" * filled + "░" * (width - filled)


def score_color(score: int) -> str:
    if score >= 90:
        return Style.GREEN
    if score >= 75:
        return Style.CYAN
    if score >= 60:
        return Style.YELLOW
    return Style.RED


def print_scorecard(console: Console, score: ScoreResult) -> None:
    print(console.paint(score.label, Style.BOLD, Style.WHITE))
    colored_score = console.paint(f"{score.assured_score:3d}/100", Style.BOLD, score_color(score.assured_score))
    print(f"  Assured:  {colored_score}  {console.paint(progress_bar(score.assured_score), score_color(score.assured_score))}  {score.grade}")
    print(f"  Verified: {score.verified_score:3d}/100  • evidence coverage {score.coverage}%" + ("  • critical-failure cap applied" if score.capped else ""))
    print()
    if score.categories:
        print(console.paint("  Category scorecards", Style.BOLD, Style.CYAN))
        for category in score.categories.values():
            value = category["assuredScore"]
            print(
                f"    {category['label'][:27]:27s} {value:3d}/100  "
                f"coverage {category['coverage']:3d}%  weight {category['weight']:g}"
            )
        print()
    factor_to_category: dict[str, str] = {}
    for category in score.categories.values():
        for name in category["factors"]:
            factor_to_category[name] = category["label"]
    current_category = ""
    for name, detail in score.factors.items():
        category = factor_to_category.get(name, "Checks")
        if category != current_category:
            print(console.paint(f"  {category}", Style.BOLD, Style.WHITE))
            current_category = category
        points = detail["points"]
        weight = detail["weight"]
        points_text = "unverified" if points is None else f"{points:g}/{weight:g}"
        print(f"    {console.status(detail['status'])}  {name.replace('_', ' '):24s} {points_text:>11s}  {detail['message']}")
    print()


def snapshot_to_dict(snapshot: PageSnapshot) -> dict[str, Any]:
    return {
        "requestedUrl": snapshot.requested_url,
        "fetch": {
            "requestedUrl": snapshot.fetch.requested_url,
            "finalUrl": snapshot.fetch.final_url,
            "status": snapshot.fetch.status,
            "headers": snapshot.fetch.headers,
            "elapsedMs": snapshot.fetch.elapsed_ms,
            "error": snapshot.fetch.error,
            "bodyBytes": len(snapshot.fetch.data),
        },
        "html": {
            "title": snapshot.html.title,
            "description": snapshot.html.description,
            "canonical": snapshot.html.canonical,
            "viewport": snapshot.html.viewport,
            "h1Count": snapshot.html.h1_count,
            "bodyTextLength": snapshot.html.body_text_length,
            "metaRobots": {name: sorted(values) for name, values in snapshot.html.meta_robots.items()},
            "jsonLdBlocks": snapshot.html.json_ld_blocks,
            "jsonLdValid": snapshot.html.json_ld_valid,
            "jsonLdErrors": snapshot.html.json_ld_errors,
        },
        "robotsUrl": snapshot.robots_url,
        "robotsStatus": snapshot.robots_status,
        "sitemapUrlUsed": snapshot.sitemap_url_used,
        "sitemapEntry": asdict(snapshot.sitemap_entry) if snapshot.sitemap_entry else None,
        "sitemap": {
            "roots": snapshot.sitemap.roots,
            "visited": snapshot.sitemap.visited,
            "errors": snapshot.sitemap.errors,
            "entryCount": len(snapshot.sitemap.entries),
            "duplicateCount": snapshot.sitemap.duplicate_count,
        } if snapshot.sitemap else None,
        "keyLocation": snapshot.key_location,
        "keyReady": snapshot.key_ready,
        "keyMessage": snapshot.key_message,
        "notes": snapshot.notes,
    }


def write_json(path: str, payload: Any) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_markdown(path: str, snapshot: PageSnapshot, scores: list[ScoreResult]) -> None:
    lines = [
        f"# SEO-INDEX report for `{snapshot.requested_url}`",
        "",
        "> Diagnostic readiness scores are not official search-engine scores and do not guarantee indexing or ranking.",
        "",
    ]
    for score in scores:
        lines.extend([
            f"## {score.label}: {score.assured_score}/100 assured ({score.grade})",
            "",
            f"Verified score: {score.verified_score}/100. Evidence coverage: {score.coverage}%.",
            "",
            "| Check | Result | Points | Finding |",
            "|---|---:|---:|---|",
        ])
        for name, detail in score.factors.items():
            points = "N/A" if detail["points"] is None else f"{detail['points']:g}/{detail['weight']:g}"
            message = str(detail["message"]).replace("|", "\\|")
            lines.append(f"| {name.replace('_', ' ').title()} | {detail['status'].upper()} | {points} | {message} |")
        lines.append("")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_score(args: argparse.Namespace, console: Console) -> int:
    profiles = load_profiles(args.profile_file)
    requested_engines = list(profiles) if args.engine == "all" else [args.engine]
    snapshot = build_snapshot(
        args.url,
        args.sitemap,
        args.key_location,
        args.timeout,
        args.user_agent,
        auto_sitemap=not args.no_auto_sitemap,
    )
    print(console.paint("Page snapshot", Style.BOLD, Style.CYAN))
    print(f"  Requested: {snapshot.requested_url}")
    print(f"  Final:     {snapshot.fetch.final_url}")
    print(f"  HTTP:      {snapshot.fetch.status or 'network error'} in {snapshot.fetch.elapsed_ms} ms")
    print(f"  Sitemap:   {snapshot.sitemap_url_used or 'not checked'}")
    print(f"  Robots:    {snapshot.robots_url} ({snapshot.robots_status or 'not available'})")
    print()

    scores: list[ScoreResult] = []
    for engine in requested_engines:
        profile = profiles[engine]
        factors = evaluate_factors(snapshot, engine, profile["crawler"])
        from seo_index_extensions import enhance_factors
        factors.update(enhance_factors(snapshot, engine, profile["crawler"], args.timeout, args.user_agent))
        score = calculate_score(engine, profile, factors)
        scores.append(score)
        print_scorecard(console, score)

    if snapshot.notes:
        print(console.paint("Notes", Style.BOLD, Style.YELLOW))
        for note in snapshot.notes:
            print(f"  • {note}")
        print()

    payload = {
        "tool": TOOL_NAME,
        "version": VERSION,
        "disclaimer": "Diagnostic readiness scores are not official search-engine scores and do not guarantee indexing or ranking.",
        "snapshot": snapshot_to_dict(snapshot),
        "scores": [asdict(item) for item in scores],
    }
    if args.json:
        write_json(args.json, payload)
        print(f"JSON report written to {args.json}")
    if args.markdown:
        write_markdown(args.markdown, snapshot, scores)
        print(f"Markdown report written to {args.markdown}")
    return 0 if all(item.normalized_score >= args.fail_below for item in scores) else 2


def inspect_page_for_canonical(url: str, timeout: int, user_agent: str, expected_host: Optional[str]) -> dict[str, Any]:
    result = fetch_url(url, timeout, user_agent)
    html = parse_html(result)
    final = normalize_url(result.final_url) if result.status else url
    canonical = ""
    canonical_status = "warn"
    message = "No canonical tag."
    if html.canonical:
        try:
            canonical = normalize_url(html.canonical)
            if canonical == final:
                canonical_status = "pass"
                message = "Canonical matches final URL."
            else:
                canonical_status = "fail"
                message = "Canonical differs from final URL."
        except ToolkitError as exc:
            canonical_status = "fail"
            message = f"Invalid canonical: {exc}"
    if result.status != 200:
        canonical_status = "fail"
        message = f"Page returned HTTP {result.status or 'network error'}."
    if expected_host:
        final_host = (urlsplit(final).hostname or "").lower()
        if final_host != expected_host.lower():
            canonical_status = "fail"
            message = f"Final host {final_host} differs from expected host {expected_host}."
    return {
        "url": url,
        "status": result.status,
        "finalUrl": final,
        "canonical": canonical,
        "result": canonical_status,
        "message": message,
        "redirected": normalize_url(url) != final if result.status else False,
    }


def run_canonical(args: argparse.Namespace, console: Console) -> int:
    collection = fetch_sitemaps(
        [args.sitemap], args.timeout, args.user_agent,
        args.max_sitemaps, args.max_urls,
    )
    if not collection.entries:
        raise ToolkitError("No URLs were found in the sitemap.")
    urls = list(dict.fromkeys(entry.url for entry in collection.entries))
    if args.limit:
        urls = urls[: args.limit]
    expected_host = args.expected_host or (urlsplit(args.sitemap).hostname or "")
    print(f"Auditing canonical signals for {len(urls)} URL(s)...")
    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_map = {
            executor.submit(inspect_page_for_canonical, url, args.timeout, args.user_agent, expected_host): url
            for url in urls
        }
        for completed, future in enumerate(concurrent.futures.as_completed(future_map), start=1):
            result = future.result()
            results.append(result)
            print(f"\r  Checked {completed}/{len(urls)}", end="", flush=True)
    print("\n")
    results.sort(key=lambda item: item["url"])
    counts = {name: sum(1 for item in results if item["result"] == name) for name in ("pass", "warn", "fail")}
    print(console.paint("Canonical Guard", Style.BOLD, Style.CYAN))
    print(f"  PASS {counts['pass']}   WARN {counts['warn']}   FAIL {counts['fail']}")
    print()
    problems = [item for item in results if item["result"] != "pass"]
    for item in problems[: args.show_problems]:
        print(f"  {console.status(item['result'])} {item['url']}")
        print(f"       {item['message']}")
        if item["canonical"]:
            print(f"       canonical: {item['canonical']}")
        if item["finalUrl"] != item["url"]:
            print(f"       final:     {item['finalUrl']}")
    if len(problems) > args.show_problems:
        print(f"  ... {len(problems) - args.show_problems} more issue(s) omitted from terminal output.")
    payload = {
        "tool": "Canonical Guard",
        "version": VERSION,
        "sitemap": args.sitemap,
        "expectedHost": expected_host,
        "summary": counts,
        "sitemapErrors": collection.errors,
        "results": results,
    }
    if args.json:
        write_json(args.json, payload)
        print(f"\nJSON report written to {args.json}")
    return 2 if counts["fail"] else 0


def run_sitemap(args: argparse.Namespace, console: Console) -> int:
    collection = fetch_sitemaps(
        [args.sitemap], args.timeout, args.user_agent,
        args.max_sitemaps, args.max_urls,
    )
    entries = collection.entries
    unique: dict[str, SitemapEntry] = {}
    invalid: list[str] = []
    host_counts: dict[str, int] = {}
    http_count = 0
    fragment_count = 0
    missing_lastmod = 0
    for entry in entries:
        try:
            parsed = require_http_url(entry.url, "Sitemap URL")
            normalized = normalize_url(entry.url)
            unique.setdefault(normalized, entry)
            host = (parsed.hostname or "").lower()
            host_counts[host] = host_counts.get(host, 0) + 1
            if parsed.scheme.lower() != "https":
                http_count += 1
            if parsed.fragment:
                fragment_count += 1
            if not entry.lastmod:
                missing_lastmod += 1
        except ToolkitError as exc:
            invalid.append(f"{entry.url}: {exc}")

    page_checks: list[dict[str, Any]] = []
    check_urls = list(unique)[: args.check_pages] if args.check_pages else []
    if check_urls:
        print(f"Checking HTTP status for {len(check_urls)} sitemap URL(s)...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
            future_map = {executor.submit(fetch_url, url, args.timeout, args.user_agent): url for url in check_urls}
            for completed, future in enumerate(concurrent.futures.as_completed(future_map), start=1):
                result = future.result()
                page_checks.append({
                    "url": future_map[future],
                    "status": result.status,
                    "finalUrl": result.final_url,
                    "redirected": result.status > 0 and normalize_url(future_map[future]) != normalize_url(result.final_url),
                    "error": result.error,
                })
                print(f"\r  Checked {completed}/{len(check_urls)}", end="", flush=True)
        print("\n")

    page_failures = [item for item in page_checks if item["status"] != 200 or item["redirected"]]
    summary = {
        "sitemapFiles": len(collection.visited),
        "rawEntries": len(entries),
        "uniqueUrls": len(unique),
        "duplicates": collection.duplicate_count,
        "invalidUrls": len(invalid),
        "hosts": host_counts,
        "nonHttpsUrls": http_count,
        "fragmentUrls": fragment_count,
        "missingLastmod": missing_lastmod,
        "sitemapErrors": len(collection.errors),
        "checkedPages": len(page_checks),
        "pageIssues": len(page_failures),
    }
    print(console.paint("Sitemap Doctor", Style.BOLD, Style.CYAN))
    for key, value in summary.items():
        print(f"  {key:18s} {value}")
    issues = (
        collection.errors
        + invalid
        + [f"{item['url']} -> HTTP {item['status']} final {item['finalUrl']}" for item in page_failures]
    )
    if issues:
        print()
        print(console.paint("Issues", Style.BOLD, Style.YELLOW))
        for issue in issues[: args.show_problems]:
            print(f"  • {issue}")
        if len(issues) > args.show_problems:
            print(f"  ... {len(issues) - args.show_problems} more issue(s) omitted.")
    payload = {
        "tool": "Sitemap Doctor",
        "version": VERSION,
        "sitemap": args.sitemap,
        "summary": summary,
        "errors": collection.errors,
        "invalidUrls": invalid,
        "pageChecks": page_checks,
    }
    if args.json:
        write_json(args.json, payload)
        print(f"\nJSON report written to {args.json}")
    critical = summary["sitemapErrors"] + summary["invalidUrls"] + summary["pageIssues"] + summary["fragmentUrls"]
    return 2 if critical else 0


def run_indexnow(args: argparse.Namespace, console: Console) -> int:
    runner_path = Path(__file__).resolve().with_name("indexnow_runner.py")
    if not runner_path.exists():
        raise ToolkitError(f"IndexNow runner was not found beside this file: {runner_path}")
    command = [sys.executable, str(runner_path)]
    for sitemap in args.sitemap:
        command.extend(["--sitemap", sitemap])
    command.extend(["--key-location", args.key_location])
    optional_pairs = [
        ("--canonical-host", args.canonical_host),
        ("--rewrite-host-from", args.rewrite_host_from),
        ("--endpoint", args.endpoint),
        ("--batch-size", args.batch_size),
        ("--delay", args.delay),
        ("--timeout", args.timeout),
        ("--max-sitemaps", args.max_sitemaps),
        ("--max-urls", args.max_urls),
    ]
    for flag, value in optional_pairs:
        if value is not None:
            command.extend([flag, str(value)])
    if args.show_urls:
        command.append("--show-urls")
    if args.dry_run:
        command.append("--dry-run")
    return subprocess.run(command, check=False).returncode


def prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def interactive_loop(console: Console, profile_file: Optional[str]) -> int:
    while True:
        print(console.paint("Choose a tool", Style.BOLD, Style.WHITE))
        print("  1. Index readiness score")
        print("  2. Canonical Guard")
        print("  3. Sitemap Doctor")
        print("  4. IndexNow submission runner")
        print("  5. Redirect Lab")
        print("  6. Crawler Access Matrix")
        print("  7. Hreflang Auditor")
        print("  8. Structured Data Graph")
        print("  9. GEO / Entity Discoverability")
        print(" 10. AEO / Answer Extractability")
        print(" 11. Internal Link Graph")
        print(" 12. Start local graphical workbench")
        print(" 13. List scoring profiles")
        print(" 14. Open hosted graphical workbench")
        print(" 15. Page Quality Audit")
        print("  0. Exit")
        choice = input("\nSelection: ").strip()
        print()
        try:
            if choice == "0":
                return 0
            if choice == "1":
                namespace = argparse.Namespace(
                    url=prompt("Page URL"),
                    engine=prompt("Profile: google, bing, generic, geo, aeo, or all", "all").lower(),
                    sitemap=prompt("Sitemap URL (optional)") or None,
                    key_location=prompt("IndexNow key URL (optional, useful for Bing score)") or None,
                    timeout=30,
                    user_agent=DEFAULT_USER_AGENT,
                    no_auto_sitemap=False,
                    profile_file=profile_file,
                    json=None,
                    markdown=None,
                    fail_below=0,
                )
                run_score(namespace, console)
            elif choice == "2":
                sitemap = prompt("Sitemap URL")
                namespace = argparse.Namespace(
                    sitemap=sitemap,
                    expected_host=prompt("Expected canonical host", urlsplit(sitemap).hostname or ""),
                    limit=int(prompt("Maximum pages to check", "100")),
                    workers=8,
                    timeout=30,
                    user_agent=DEFAULT_USER_AGENT,
                    max_sitemaps=1000,
                    max_urls=1_000_000,
                    show_problems=20,
                    json=None,
                )
                run_canonical(namespace, console)
            elif choice == "3":
                namespace = argparse.Namespace(
                    sitemap=prompt("Sitemap URL"),
                    check_pages=int(prompt("Page status checks (0 skips)", "50")),
                    workers=8,
                    timeout=30,
                    user_agent=DEFAULT_USER_AGENT,
                    max_sitemaps=1000,
                    max_urls=1_000_000,
                    show_problems=20,
                    json=None,
                )
                run_sitemap(namespace, console)
            elif choice == "4":
                sitemap = prompt("Sitemap URL")
                key = prompt("Hosted IndexNow key URL")
                dry = prompt("Dry run first? y/n", "y").lower().startswith("y")
                namespace = argparse.Namespace(
                    sitemap=[sitemap],
                    key_location=key,
                    canonical_host=None,
                    rewrite_host_from=None,
                    endpoint=None,
                    batch_size=None,
                    delay=None,
                    timeout=None,
                    max_sitemaps=1000,
                    max_urls=1_000_000,
                    show_urls=False,
                    dry_run=dry,
                )
                run_indexnow(namespace, console)
            elif choice == "5":
                from seo_index_extensions import run_redirect
                run_redirect(argparse.Namespace(
                    url=prompt("URL to trace"), max_hops=int(prompt("Maximum redirect hops", "10")),
                    timeout=30, user_agent=DEFAULT_USER_AGENT, json=None,
                ), console)
            elif choice == "6":
                from seo_index_extensions import run_robots_matrix
                run_robots_matrix(argparse.Namespace(
                    url=prompt("Target page URL"), agent=None, timeout=30,
                    user_agent=DEFAULT_USER_AGENT, json=None,
                ), console)
            elif choice == "7":
                from seo_index_extensions import run_hreflang
                run_hreflang(argparse.Namespace(
                    url=prompt("Page URL"), check_alternates=prompt("Check reciprocal alternates? y/n", "y").lower().startswith("y"),
                    limit=int(prompt("Maximum alternates", "20")), timeout=30,
                    user_agent=DEFAULT_USER_AGENT, json=None,
                ), console)
            elif choice == "8":
                from seo_index_extensions import run_schema
                run_schema(argparse.Namespace(
                    url=prompt("Page URL"), show_json=False, timeout=30,
                    user_agent=DEFAULT_USER_AGENT, json=None,
                ), console)
            elif choice == "9":
                from seo_index_extensions import run_geo
                run_geo(argparse.Namespace(
                    url=prompt("Page URL"), timeout=30, user_agent=DEFAULT_USER_AGENT, json=None,
                ), console)
            elif choice == "10":
                from seo_index_extensions import run_aeo
                run_aeo(argparse.Namespace(
                    url=prompt("Page URL"), timeout=30, user_agent=DEFAULT_USER_AGENT, json=None,
                ), console)
            elif choice == "11":
                from seo_index_site import run_links
                run_links(argparse.Namespace(
                    url=prompt("Start URL"), sitemap=prompt("Sitemap URL (optional)") or None,
                    max_pages=int(prompt("Maximum pages", "250")), max_depth=int(prompt("Maximum depth", "6")),
                    delay_ms=int(prompt("Delay between requests in ms", "75")), robots_agent="Googlebot",
                    include_subdomains=False, ignore_robots=False, follow_nofollow=False, drop_query=False,
                    timeout=20, user_agent=DEFAULT_USER_AGENT, show=15, progress=True,
                    json=prompt("JSON report path (optional)") or None,
                    html=prompt("Graphical HTML report path (optional)") or None,
                    fail_on_broken=False,
                ), console)
            elif choice == "12":
                from seo_index_site import serve_workbench
                serve_workbench(argparse.Namespace(
                    host="127.0.0.1", port=8765, docs_dir=None, no_open=False,
                    allow_remote=False, allow_private_targets=False, api_max_pages=500,
                    verbose=False,
                ), console)
            elif choice == "13":
                profiles = load_profiles(profile_file)
                for name, profile in profiles.items():
                    print(f"  {name:8s} {profile['label']}")
                    print(textwrap.fill(profile["description"], width=76, initial_indent="           ", subsequent_indent="           "))
                print()
            elif choice == "14":
                print(f"Opening {WORKBENCH_URL}")
                webbrowser.open(WORKBENCH_URL)
                print()
            elif choice == "15":
                from seo_index_quality import run_page
                run_page(argparse.Namespace(
                    url=prompt("Page URL"), timeout=30, user_agent=DEFAULT_USER_AGENT,
                    json=prompt("JSON report path (optional)") or None,
                    markdown=prompt("Markdown report path (optional)") or None,
                    fail_on="never",
                ), console)
            else:
                print("Unknown selection.\n")
        except (ToolkitError, ValueError, KeyboardInterrupt) as exc:
            print(console.paint(f"Error: {exc}", Style.RED, Style.BOLD))
            print()


def add_common_http_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds.")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="HTTP User-Agent.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="seo-index",
        description="Cross-platform indexing and technical SEO terminal toolkit.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors.")
    parser.add_argument("--no-splash", action="store_true", help="Disable the fox-tail splash.")
    parser.add_argument("--no-animation", action="store_true", help="Show a static splash instead of animation.")
    parser.add_argument("--profile-file", help="Custom engine profile JSON file.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    subparsers = parser.add_subparsers(dest="command")

    score = subparsers.add_parser("score", help="Score one URL for engine-specific index readiness.")
    score.add_argument("--url", required=True)
    score.add_argument("--engine", choices=["google", "bing", "generic", "geo", "aeo", "all"], default="all")
    score.add_argument("--sitemap", help="Explicit sitemap URL. Otherwise robots.txt and /sitemap.xml are tried.")
    score.add_argument("--key-location", help="Hosted IndexNow key URL, used by the Bing profile.")
    score.add_argument("--no-auto-sitemap", action="store_true", help="Do not auto-discover a sitemap.")
    score.add_argument("--json", help="Write a JSON report.")
    score.add_argument("--markdown", help="Write a Markdown report.")
    score.add_argument("--fail-below", type=int, default=0, help="Exit 2 when a selected score is below this value.")
    add_common_http_args(score)

    canonical = subparsers.add_parser("canonical", help="Audit sitemap URLs for redirect and canonical mismatches.")
    canonical.add_argument("--sitemap", required=True)
    canonical.add_argument("--expected-host")
    canonical.add_argument("--limit", type=int, default=100, help="Maximum pages to check; 0 checks all.")
    canonical.add_argument("--workers", type=int, default=8)
    canonical.add_argument("--max-sitemaps", type=int, default=1000)
    canonical.add_argument("--max-urls", type=int, default=1_000_000)
    canonical.add_argument("--show-problems", type=int, default=20)
    canonical.add_argument("--json")
    add_common_http_args(canonical)

    sitemap = subparsers.add_parser("sitemap", help="Validate a sitemap and optionally check page responses.")
    sitemap.add_argument("--sitemap", required=True)
    sitemap.add_argument("--check-pages", type=int, default=0, help="Number of unique page URLs to request; 0 skips.")
    sitemap.add_argument("--workers", type=int, default=8)
    sitemap.add_argument("--max-sitemaps", type=int, default=1000)
    sitemap.add_argument("--max-urls", type=int, default=1_000_000)
    sitemap.add_argument("--show-problems", type=int, default=20)
    sitemap.add_argument("--json")
    add_common_http_args(sitemap)

    indexnow = subparsers.add_parser("indexnow", help="Launch the existing sitemap-to-IndexNow runner.")
    indexnow.add_argument("--sitemap", action="append", required=True)
    indexnow.add_argument("--key-location", required=True)
    indexnow.add_argument("--canonical-host")
    indexnow.add_argument("--rewrite-host-from")
    indexnow.add_argument("--endpoint")
    indexnow.add_argument("--batch-size", type=int)
    indexnow.add_argument("--delay", type=float)
    indexnow.add_argument("--timeout", type=int)
    indexnow.add_argument("--max-sitemaps", type=int, default=1000)
    indexnow.add_argument("--max-urls", type=int, default=1_000_000)
    indexnow.add_argument("--show-urls", action="store_true")
    indexnow.add_argument("--dry-run", action="store_true")

    page = subparsers.add_parser("page", help="Audit page metadata, content, images, social previews, delivery, and security headers.")
    page.add_argument("--url", required=True)
    page.add_argument("--json", help="Write the complete evidence report as JSON.")
    page.add_argument("--markdown", help="Write a human-readable Markdown report.")
    page.add_argument(
        "--fail-on",
        choices=["critical", "warning", "never"],
        default="critical",
        help="Return exit code 2 for critical findings, warnings, or never.",
    )
    add_common_http_args(page)

    redirect = subparsers.add_parser("redirect", help="Trace and assess a redirect chain.")
    redirect.add_argument("--url", required=True)
    redirect.add_argument("--max-hops", type=int, default=10)
    redirect.add_argument("--json")
    add_common_http_args(redirect)

    robots = subparsers.add_parser("robots", help="Check search and AI crawler access for one URL.")
    robots.add_argument("--url", required=True)
    robots.add_argument("--agent", action="append", help="Crawler user-agent; repeat to test several.")
    robots.add_argument("--json")
    add_common_http_args(robots)

    hreflang = subparsers.add_parser("hreflang", help="Validate hreflang declarations and reciprocity.")
    hreflang.add_argument("--url", required=True)
    hreflang.add_argument("--check-alternates", action="store_true")
    hreflang.add_argument("--limit", type=int, default=20)
    hreflang.add_argument("--json")
    add_common_http_args(hreflang)

    schema = subparsers.add_parser("schema", help="Inspect the JSON-LD entity graph.")
    schema.add_argument("--url", required=True)
    schema.add_argument("--show-json", action="store_true")
    schema.add_argument("--json")
    add_common_http_args(schema)

    geo = subparsers.add_parser("geo", help="Audit entity and AI-discovery readiness.")
    geo.add_argument("--url", required=True)
    geo.add_argument("--json")
    add_common_http_args(geo)

    aeo = subparsers.add_parser("aeo", help="Audit answer extractability and semantic answer structure.")
    aeo.add_argument("--url", required=True)
    aeo.add_argument("--json")
    add_common_http_args(aeo)

    links = subparsers.add_parser("links", help="Crawl and graph internal links, depth, orphans, redirects, and dead ends.")
    links.add_argument("--url", required=True, help="Starting page URL.")
    links.add_argument("--sitemap", help="Optional sitemap used to identify orphan candidates.")
    links.add_argument("--max-pages", type=int, default=250)
    links.add_argument("--max-depth", type=int, default=6)
    links.add_argument("--delay-ms", type=int, default=75)
    links.add_argument("--robots-agent", default="Googlebot", help="User-agent used when evaluating robots.txt.")
    links.add_argument("--include-subdomains", action="store_true")
    links.add_argument("--ignore-robots", action="store_true")
    links.add_argument("--follow-nofollow", action="store_true")
    links.add_argument("--drop-query", action="store_true", help="Collapse query variants into the path URL.")
    links.add_argument("--progress", action="store_true")
    links.add_argument("--show", type=int, default=15, help="Number of highest-importance pages to print.")
    links.add_argument("--json", help="Write the graph report as JSON.")
    links.add_argument("--html", help="Write a standalone interactive HTML graph report.")
    links.add_argument("--fail-on-broken", action="store_true", help="Exit 2 when broken pages are found.")
    add_common_http_args(links)

    serve = subparsers.add_parser("serve", help="Start the token-protected local graphical workbench and live audit API.")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--docs-dir", help="Alternate workbench directory containing index.html.")
    serve.add_argument("--no-open", action="store_true", help="Do not open the browser automatically.")
    serve.add_argument("--allow-remote", action="store_true", help="Permit binding to a non-loopback interface.")
    serve.add_argument("--allow-private-targets", action="store_true", help="Permit audits of private or loopback targets.")
    serve.add_argument("--api-max-pages", type=int, default=500, help="Maximum pages accepted by one browser API crawl.")
    serve.add_argument("--verbose", action="store_true", help="Print local HTTP request logs.")

    web = subparsers.add_parser("web", help="Open the hosted graphical workbench.")
    web.add_argument("--print-only", action="store_true", help="Print the workbench URL without opening a browser.")

    subparsers.add_parser("interactive", help="Open the semi-graphical terminal menu.")
    subparsers.add_parser("list-engines", help="List installed scoring profiles.")
    return parser


def validate_cli(args: argparse.Namespace) -> None:
    timeout = getattr(args, "timeout", None)
    if timeout is not None and not 1 <= timeout <= 600:
        raise ToolkitError("--timeout must be between 1 and 600 seconds.")
    workers = getattr(args, "workers", None)
    if workers is not None and not 1 <= workers <= 64:
        raise ToolkitError("--workers must be between 1 and 64.")
    fail_below = getattr(args, "fail_below", None)
    if fail_below is not None and not 0 <= fail_below <= 100:
        raise ToolkitError("--fail-below must be between 0 and 100.")
    max_hops = getattr(args, "max_hops", None)
    if max_hops is not None and not 1 <= max_hops <= 50:
        raise ToolkitError("--max-hops must be between 1 and 50.")
    limit = getattr(args, "limit", None)
    if limit is not None and limit < 0:
        raise ToolkitError("--limit must be zero or greater.")
    max_pages = getattr(args, "max_pages", None)
    if max_pages is not None and not 1 <= max_pages <= 10000:
        raise ToolkitError("--max-pages must be between 1 and 10,000.")
    max_sitemaps = getattr(args, "max_sitemaps", None)
    if max_sitemaps is not None and not 1 <= max_sitemaps <= 10000:
        raise ToolkitError("--max-sitemaps must be between 1 and 10,000.")
    max_urls = getattr(args, "max_urls", None)
    if max_urls is not None and not 1 <= max_urls <= 10_000_000:
        raise ToolkitError("--max-urls must be between 1 and 10,000,000.")
    max_depth = getattr(args, "max_depth", None)
    if max_depth is not None and not 0 <= max_depth <= 50:
        raise ToolkitError("--max-depth must be between 0 and 50.")
    delay_ms = getattr(args, "delay_ms", None)
    if delay_ms is not None and not 0 <= delay_ms <= 60000:
        raise ToolkitError("--delay-ms must be between 0 and 60,000.")
    port = getattr(args, "port", None)
    if port is not None and not 0 <= port <= 65535:
        raise ToolkitError("--port must be between 0 and 65,535.")
    api_max_pages = getattr(args, "api_max_pages", None)
    if api_max_pages is not None and not 1 <= api_max_pages <= 10000:
        raise ToolkitError("--api-max-pages must be between 1 and 10,000.")


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    console = Console(
        color=supports_color() and not args.no_color,
        animation=not args.no_animation,
    )
    if not args.no_splash:
        show_splash(console)
    validate_cli(args)
    command = args.command or "interactive"
    if command == "interactive":
        return interactive_loop(console, args.profile_file)
    if command in {"links", "serve"}:
        from seo_index_site import run_links, serve_workbench
        return run_links(args, console) if command == "links" else serve_workbench(args, console)
    if command == "web":
        print(WORKBENCH_URL)
        if not args.print_only:
            webbrowser.open(WORKBENCH_URL)
        return 0
    if command == "list-engines":
        profiles = load_profiles(args.profile_file)
        for name, profile in profiles.items():
            print(f"{name:8s} {profile['label']}: {profile['description']}")
        return 0
    if command == "score":
        return run_score(args, console)
    if command == "canonical":
        return run_canonical(args, console)
    if command == "sitemap":
        return run_sitemap(args, console)
    if command == "indexnow":
        return run_indexnow(args, console)
    if command == "page":
        from seo_index_quality import run_page
        return run_page(args, console)
    if command in {"redirect", "robots", "hreflang", "schema", "geo", "aeo"}:
        from seo_index_extensions import (
            run_aeo, run_geo, run_hreflang, run_redirect, run_robots_matrix, run_schema,
        )
        handlers = {
            "redirect": run_redirect,
            "robots": run_robots_matrix,
            "hreflang": run_hreflang,
            "schema": run_schema,
            "geo": run_geo,
            "aeo": run_aeo,
        }
        return handlers[command](args, console)
    raise ToolkitError(f"Unsupported command: {command}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ToolkitError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(130)
