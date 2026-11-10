"""Ferramentas de web do assistente: busca e leitura de páginas.

Resultados da web são conteúdo **não confiável**: o prompt manda ignorar
instruções vindas deles. Além disso, ``fetch_url`` bloqueia esquemas perigosos,
IPs privados/loopback e redirecionamentos para destinos internos (proteção
SSRF), validando o DNS antes de cada requisição.
"""
from __future__ import annotations

import asyncio
import html as html_lib
import ipaddress
import logging
import os
import re
import socket
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

import httpx
from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from services.ai_config import AIProviderError, AIToolError
from services.ai_prompts import sanitize_user_text, short_text

logger = logging.getLogger(__name__)

WEB_TIMEOUT_SECONDS = 12.0
WEB_SEARCH_DEFAULT_RESULTS = 5
WEB_SEARCH_MAX_RESULTS = 8
MAX_FETCH_BYTES = 1_000_000
MAX_FETCH_TEXT_CHARS = 6000
MAX_FETCH_REDIRECTS = 3
WEB_USER_AGENT = "CRMVendasAssistant/1.0 (+contato: suporte@crm-vendas.local)"

_BLOCKED_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "metadata",
    "metadata.google.internal",
    "instance-data",
    "169.254.169.254",
}
_BLOCKED_HOST_SUFFIXES = (".local", ".internal", ".localhost", ".home", ".lan", ".corp")
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}


class WebSearchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=200)
    max_results: StrictInt = Field(default=WEB_SEARCH_DEFAULT_RESULTS, ge=1, le=WEB_SEARCH_MAX_RESULTS)

    @model_validator(mode="after")
    def strip_query(self) -> WebSearchArgs:
        self.query = self.query.strip()
        if not self.query:
            raise ValueError("Consulta vazia.")
        return self


class FetchUrlArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1, max_length=2048)

    @model_validator(mode="after")
    def strip_url(self) -> FetchUrlArgs:
        self.url = self.url.strip()
        if not self.url:
            raise ValueError("URL vazia.")
        return self


def _is_public_ip(value: str) -> bool:
    ip = ipaddress.ip_address(value.split("%", 1)[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _validate_public_http_url(url: str) -> tuple[Any, str]:
    """Valida esquema/host e devolve ``(parsed_url, host)``."""
    if not isinstance(url, str) or not url.strip():
        raise AIToolError("URL vazia.")
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise AIToolError("Apenas URLs http/https são permitidas.")
    if not parsed.hostname:
        raise AIToolError("URL inválida.")
    if parsed.username or parsed.password:
        raise AIToolError("URL com credenciais não é permitida.")
    try:
        _ = parsed.port
    except ValueError as exc:
        raise AIToolError("Porta inválida na URL.") from exc

    host = parsed.hostname.lower().rstrip(".")
    if not host:
        raise AIToolError("URL inválida.")
    if host in _BLOCKED_HOSTS or host.endswith(_BLOCKED_HOST_SUFFIXES):
        raise AIToolError("Destino não permitido.")

    # IP literal: valida imediatamente, sem depender de DNS.
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not _is_public_ip(host):
            raise AIToolError("Destino não permitido.")
    return parsed, host


async def _ensure_public_host(parsed: Any, host: str) -> None:
    """Resolve o host e rejeita se QUALQUER endereço for privado/interno."""
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise AIToolError("Não foi possível resolver o endereço.") from exc

    addresses = {str(info[4][0]) for info in infos if info[4]}
    if not addresses:
        raise AIToolError("Não foi possível resolver o endereço.")
    for address in addresses:
        if not _is_public_ip(address):
            raise AIToolError("Destino não permitido.")


def _strip_tags(fragment: str) -> str:
    text = re.sub(r"(?is)<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html_lib.unescape(text)).strip()


def _html_to_text(markup: str) -> tuple[str, str]:
    """Extrai título e texto legível de HTML, sem scripts/estilos."""
    title = ""
    title_match = re.search(r"(?is)<title[^>]*>(.*?)</title>", markup)
    if title_match:
        title = _strip_tags(title_match.group(1))[:300]

    cleaned = re.sub(
        r"(?is)<(script|style|noscript|svg|template)[^>]*>.*?</\1>",
        " ",
        markup,
    )
    cleaned = re.sub(r"(?is)<(br|p|div|li|tr|h[1-6]|section|article)\b[^>]*>", "\n", cleaned)
    cleaned = re.sub(r"(?is)<[^>]+>", " ", cleaned)
    cleaned = html_lib.unescape(cleaned)
    cleaned = re.sub(r"[ \t\f\v]+", " ", cleaned)
    cleaned = re.sub(r"\n\s*\n+", "\n", cleaned).strip()
    return title, cleaned[:MAX_FETCH_TEXT_CHARS]


def _extract_anchors_by_class(markup: str, class_name: str) -> list[tuple[str, str]]:
    anchors: list[tuple[str, str]] = []
    for match in re.finditer(r"(?is)<a\b([^>]*)>(.*?)</a>", markup):
        attrs = match.group(1)
        if class_name not in attrs:
            continue
        href_match = re.search(r'href\s*=\s*"([^"]+)"', attrs) or re.search(
            r"href\s*=\s*'([^']+)'", attrs
        )
        if not href_match:
            continue
        anchors.append((html_lib.unescape(href_match.group(1)), _strip_tags(match.group(2))))
    return anchors


def _decode_duckduckgo_url(href: str) -> str:
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if parsed.hostname and "duckduckgo.com" in parsed.hostname:
        uddg = parse_qs(parsed.query).get("uddg")
        if uddg:
            return uddg[0]
    return href


def _parse_duckduckgo(markup: str, max_results: int) -> list[dict[str, str]]:
    links = _extract_anchors_by_class(markup, "result__a")
    if not links:
        links = _extract_anchors_by_class(markup, "result-link")

    snippets: list[str] = []
    for match in re.finditer(
        r'(?is)<(?:a|div|td)\b[^>]*class\s*=\s*"[^"]*result(?:__snippet|-snippet)[^"]*"[^>]*>(.*?)</(?:a|div|td)>',
        markup,
    ):
        snippets.append(_strip_tags(match.group(1)))

    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, (href, title) in enumerate(links):
        url = _decode_duckduckgo_url(href)
        if not url.startswith(("http://", "https://")) or url in seen:
            continue
        seen.add(url)
        results.append(
            {
                "title": (title or url)[:300],
                "url": url[:2048],
                "snippet": (snippets[index] if index < len(snippets) else "")[:500],
            }
        )
        if len(results) >= max_results:
            break
    return results


async def _tavily_search(api_key: str, query: str, max_results: int) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=WEB_TIMEOUT_SECONDS) as client:
        response = await client.post(
            "https://api.tavily.com/search",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
                "include_answer": False,
                "include_raw_content": False,
            },
        )
    if response.status_code >= 400:
        raise AIProviderError(f"Tavily respondeu HTTP {response.status_code}.")
    try:
        data = response.json()
    except ValueError as exc:
        raise AIProviderError("Resposta inválida da Tavily.") from exc

    results: list[dict[str, str]] = []
    raw_results = data.get("results") if isinstance(data, dict) else None
    if isinstance(raw_results, list):
        for item in raw_results[:max_results]:
            if not isinstance(item, dict) or not isinstance(item.get("url"), str):
                continue
            results.append(
                {
                    "title": short_text(item.get("title") or item["url"], 300),
                    "url": item["url"][:2048],
                    "snippet": short_text(item.get("content"), 500),
                }
            )
    if not results:
        raise AIProviderError("Tavily não retornou resultados.")
    return {"query": query, "provider": "tavily", "results": results}


async def _duckduckgo_search(query: str, max_results: int) -> dict[str, Any]:
    headers = {
        "User-Agent": WEB_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    }
    async with httpx.AsyncClient(
        timeout=WEB_TIMEOUT_SECONDS,
        follow_redirects=True,
        headers=headers,
    ) as client:
        response = await client.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query, "kl": "pt-br"},
        )
        markup = response.text if response.status_code < 400 else ""
        results = _parse_duckduckgo(markup, max_results) if markup else []
        if not results:
            response = await client.get(
                "https://lite.duckduckgo.com/lite/",
                params={"q": query, "kl": "pt-br"},
            )
            response.raise_for_status()
            markup = response.text
            results = _parse_duckduckgo(markup, max_results)

    if not results:
        raise AIProviderError("DuckDuckGo não retornou resultados.")
    return {"query": query, "provider": "duckduckgo", "results": results}


async def web_search(query: str, max_results: int) -> dict[str, Any]:
    """Busca na web com Tavily (se configurada) ou DuckDuckGo."""
    clean_query = sanitize_user_text(query, 200)
    if not clean_query:
        raise AIToolError("Consulta vazia.")

    tavily_key = (os.getenv("TAVILY_API_KEY") or "").strip()
    if tavily_key:
        try:
            return await _tavily_search(tavily_key, clean_query, max_results)
        except (httpx.HTTPError, ValueError, AIProviderError) as exc:
            logger.warning("ai_web_search_tavily_failed error_type=%s", type(exc).__name__)

    try:
        return await _duckduckgo_search(clean_query, max_results)
    except (httpx.HTTPError, ValueError, AIProviderError) as exc:
        logger.warning("ai_web_search_failed error_type=%s", type(exc).__name__)
        raise AIToolError("Busca na web indisponível no momento.") from exc


def _is_text_content_type(content_type: str) -> bool:
    content_type = content_type.split(";", 1)[0].strip().lower()
    return (
        content_type.startswith("text/")
        or content_type
        in {
            "application/json",
            "application/xml",
            "application/xhtml+xml",
            "application/rss+xml",
            "application/atom+xml",
        }
    )


async def fetch_url(url: str) -> dict[str, Any]:
    """Abre uma URL pública e devolve o texto principal (proteção SSRF)."""
    current = url.strip()
    headers = {
        "User-Agent": WEB_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,text/plain,application/json;q=0.9,*/*;q=0.1",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    }

    async with httpx.AsyncClient(
        timeout=WEB_TIMEOUT_SECONDS,
        follow_redirects=False,
        headers=headers,
    ) as client:
        for _ in range(MAX_FETCH_REDIRECTS + 1):
            parsed, host = _validate_public_http_url(current)
            await _ensure_public_host(parsed, host)

            async with client.stream("GET", current) as response:
                if response.status_code in _REDIRECT_STATUSES:
                    location = response.headers.get("location")
                    if not location:
                        raise AIToolError("Redirecionamento inválido.")
                    current = urljoin(str(response.url), location)
                    continue

                if response.status_code >= 400:
                    raise AIToolError(f"A página respondeu HTTP {response.status_code}.")

                content_type = response.headers.get("content-type", "")
                if content_type and not _is_text_content_type(content_type):
                    raise AIToolError("A URL não aponta para conteúdo de texto.")

                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    remaining = MAX_FETCH_BYTES - total
                    if remaining <= 0:
                        break
                    piece = chunk[:remaining]
                    chunks.append(piece)
                    total += len(piece)

                raw = b"".join(chunks)
                encoding = response.encoding or "utf-8"
                text = raw.decode(encoding, errors="replace")
                if "html" in content_type.lower():
                    title, body = _html_to_text(text)
                else:
                    title, body = "", short_text(text, MAX_FETCH_TEXT_CHARS)

                return {
                    "url": str(response.url),
                    "status": response.status_code,
                    "content_type": content_type.split(";", 1)[0].strip() or "desconhecido",
                    "title": title,
                    "text": body,
                    "truncated": total >= MAX_FETCH_BYTES,
                }

    raise AIToolError("Muitos redirecionamentos.")
