"""Constrained public-source observation for automatic donor investigation.

Retrieves only canonical, predeclared Ruten item URLs and one curated
manufacturer specification URL. No site crawling, user-selected domains,
cookies, browser automation, purchases, physical authorization, or arbitrary
URL following. Observed HTML is untrusted evidence, never tool instructions.
"""
from __future__ import annotations

import hashlib
from html.parser import HTMLParser
import re
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener
from collections.abc import Callable, Mapping

SCHEMA = "hardware_splicer.autonomous_source_observation.v1"
MAX_READ = 900_000
TIMEOUT_SEC = 9
ZEBRA_SPEC = "https://www.zebra.com/us/en/products/spec-sheets/scanners/general-purpose-scanners/ls2208.html"
QNAP_SPEC = "https://www.qnap.com/en-in/product/ts-219p%20ii/specs/hardware"
EPSON_DOC = "https://support2.epson.net/manuals/english/sidm/lq_680/index.html"
_MANUFACTURER_PAGES = {ZEBRA_SPEC, QNAP_SPEC, EPSON_DOC}
_RUTEN_PATTERN = re.compile(r"^/item/([0-9]{10,20})/$")


class _Metadata(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title: list[str] = []
        self.meta: dict[str,str] = {}
        self.in_title = False
        self.body_words: list[str] = []
        self.body_length = 0
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "noscript"}:
            self.skip_depth += 1
        attrs = dict(attrs)
        if tag.lower() == "title":
            self.in_title = True
        if tag.lower() == "meta":
            key = (attrs.get("name") or attrs.get("property") or "").lower()
            value = attrs.get("content")
            if key in {"description", "og:title", "og:description"} and isinstance(value,str):
                self.meta[key] = value[:2048]

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "noscript"}:
            self.skip_depth = max(0,self.skip_depth-1)
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)
        # Manufacturer spec is fairly large; retain bounded words for local
        # manufacturer spec recognition, without copying entire pages to repo.
        if data and self.skip_depth == 0 and self.body_length < 150_000:
            block = data[:150_000-self.body_length]
            self.body_words.append(block)
            self.body_length += len(block)


def _allowlisted_url(url: str, purpose: str) -> str:
    if not isinstance(url,str) or len(url)>400:
        raise ValueError("URL must be a bounded literal")
    parts=urlsplit(url)
    if parts.scheme!="https" or parts.username or parts.password or parts.port or parts.query or parts.fragment:
        raise ValueError("only canonical HTTPS allowlisted URLs accepted")
    if purpose=="market_listing":
        if parts.netloc!="www.ruten.com.tw" or not _RUTEN_PATTERN.fullmatch(parts.path):
            raise ValueError("not a canonical Ruten item URL")
    elif purpose=="manufacturer_spec":
        if url not in _MANUFACTURER_PAGES:
            raise ValueError("unapproved manufacturer specification URL")
    else:
        raise ValueError("unsupported observation purpose")
    return url


def _fetch_public_html(url: str) -> tuple[int, str, bytes, str]:
    """Use a bounded GET; refuse redirects away from the source allowlist."""
    request=Request(url,headers={"Accept":"text/html","User-Agent":"Mozilla/5.0 HardwareSplicer-Research-Check/1.0"})
    response=build_opener().open(request,timeout=TIMEOUT_SEC)
    with response:
        final=response.geturl()
        data=response.read(MAX_READ+1)
        status=int(response.status)
        mime=(response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if len(data)>MAX_READ:
        raise ValueError("source exceeds HTML size budget")
    return status, mime, data, final


def observe_source(
    *,
    source_id: str,
    url: str,
    purpose: str,
    expected_model: str,
    fetcher: Callable[[str],tuple[int,str,bytes,str]]=_fetch_public_html,
    observed_at: str | None=None,
) -> dict[str,Any]:
    """Read untrusted public metadata with factual/physical boundaries intact."""
    source_id=str(source_id)
    if not source_id or len(source_id)>128:
        raise ValueError("source_id required")
    url=_allowlisted_url(url,purpose)
    model=str(expected_model).strip()
    if not 2 <= len(model) <= 80:
        raise ValueError("expected_model required")
    result={
        "schema_version":SCHEMA,
        "source_id":source_id,
        "purpose":purpose,
        "source_url":url,
        "observed_at_utc":observed_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "expected_model":model,
        "status":"NOT_FETCHED",
        "model_match":False,
        "source_available_at_check":False,
        "seller_price_claim_twd":None,
        "seller_stock_claim_units":None,
        "source_excerpt":None,
        "content_sha256":None,
        "manufacturer_family_interface_options":[],
        "manufacturer_family_voltage_range_claim":None,
        "specimen_specification_verified":False,
        "physical_parts_verified":False,
        "interfaces_measured":False,
        "purchase_or_power_authorized":False,
    }
    try:
        status,mime,data,final=fetcher(url)
        if not isinstance(data,bytes) or len(data)>MAX_READ:
            raise ValueError("source exceeds bounded HTML payload or is not bytes")
        _allowlisted_url(final,purpose)
        if final != url:
            raise ValueError("same-origin item/spec redirect changed source identity")
        if status!=200 or mime!="text/html":
            result["status"]="HTTP_OR_CONTENT_TYPE_UNACCEPTED"
            return result
        page=_Metadata()
        page.feed(data.decode("utf-8",errors="replace"))
        title=" ".join(page.title).strip()
        description=page.meta.get("description") or page.meta.get("og:description") or ""
        result["content_sha256"]=hashlib.sha256(data).hexdigest()
        result["source_available_at_check"]=True
        result["title"]=title[:400]
        result["source_excerpt"]=description[:500]
        # Exact model token boundaries defeat e.g. LS22080 matching LS2208.
        result["model_match"]=bool(re.search(r"(?<![A-Za-z0-9])"+re.escape(model)+r"(?![A-Za-z0-9])",title,re.I))
        if purpose=="manufacturer_spec" and url==EPSON_DOC and not result["model_match"]:
            # Epson's official model-specific manual index has generic
            # "EPSON Manual Web-Site" <title>; its visible guide header
            # names LQ-680. Do not broaden this to unknown URLs.
            document_text=" ".join(page.body_words)
            result["model_match"]=bool(re.search(r"(?<![A-Za-z0-9])"+re.escape(model)+r"(?![A-Za-z0-9])",document_text,re.I))
        if not result["model_match"]:
            result["status"]="SOURCE_MODEL_CONFLICT"
            return result
        if purpose=="market_listing":
            # Ruten public metadata often has an advertised price and stock.
            # These are scraped *seller claims*, not prices sold or availability.
            match=re.search(r"(?:直購價)\s*:\s*([0-9,]+)\s*-\s*([0-9,]+)",description)
            if match:
                lo,hi=(int(x.replace(",","")) for x in match.groups())
                if 0<=lo<=hi<=10_000_000:
                    result["seller_price_claim_twd"]={"min":lo,"max":hi}
            match=re.search(r"庫存\s*:\s*([0-9,]+)",description)
            if match:
                stock=int(match.group(1).replace(",",""))
                if 0 <= stock <= 10_000_000:
                    result["seller_stock_claim_units"]=stock
            result["status"]="MARKET_LISTING_METADATA_REOBSERVED"
        else:
            all_text=" ".join(page.body_words)
            all_text=re.sub(r"\s+"," ",all_text)
            normalized=all_text.lower()
            if url==ZEBRA_SPEC:
                for token in ("USB","RS232","RS-232","Keyboard Wedge"):
                    if re.search(re.escape(token.lower()),normalized):
                        result["manufacturer_family_interface_options"].append(token)
                if re.search(r"4[.]5\s+to\s+5[.]5\s*VDC",all_text,re.I):
                    result["manufacturer_family_voltage_range_claim"]="4.5 to 5.5 VDC (manufacturer family; NOT specimen pinout)"
            elif url==QNAP_SPEC:
                for token in ("USB 2.0","USB 3.2","Gigabit","eSATA"):
                    if token.lower() in normalized:
                        result["manufacturer_family_interface_options"].append(token)
                result["manufacturer_family_caveat"]="Published complete NAS model specification, not tested ports or safe power rails of a bare salvaged board"
            else:
                result["manufacturer_family_caveat"]="Epson official LQ-680 reference manual index; no motor/driver electrical specifications validated"
            result["status"]="MANUFACTURER_FAMILY_SPEC_REOBSERVED"
        return result
    except (HTTPError,URLError,TimeoutError,ValueError,OSError,UnicodeError) as exc:
        # Keep a bounded string with no URL params, tokens, cookies or body.
        result["status"]="SOURCE_RETRIEVAL_BLOCKED"
        result["error_type"]=type(exc).__name__
        return result
