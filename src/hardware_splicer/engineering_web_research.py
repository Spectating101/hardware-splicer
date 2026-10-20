"""Evidence-only web lookup for a pinned engineering information gap.

Provider: public Brave search HTML. Every result is constrained to a curated
list of original publishers, industry documentation or engineering repositories.
Search is advisory, not a design/fabrication/chemical/physical authorization.
Never fetch arbitrary URLs, execute remote code or follow redirects.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import re
import socket
from typing import Any, Callable, Mapping
import urllib.parse
import urllib.request

from bs4 import BeautifulSoup

_SCHEMA = 'hardware_splicer.engineering_web_research.v1'
_SEARCH = 'https://search.brave.com/search?q='
# Curated upstream and established documentation hosts. No suffix matching:
# a user-supplied `evil.holybro.com` cannot turn into a trusted host.
TRUSTED_SOURCE_HOSTS = frozenset({
    'holybro.com', 'docs.holybro.com', 'docs.px4.io',
    'github.com', 'raw.githubusercontent.com', 'api.github.com',
    'www.ifixit.com', 'ifixit.com',
    'help.prusa3d.com', 'www.prusa3d.com', 'prusament.com',
    'www.raspberrypi.com', 'datasheets.raspberrypi.com',
    'www.ti.com', 'www.st.com', 'www.analog.com',
    'www.espressif.com', 'docs.espressif.com',
    'www.arduino.cc', 'docs.arduino.cc',
    'www.pololu.com', 'docs.ros.org',
})
_MAX_HTML_BYTES = 850_000
_MAX_PAGE_BYTES = 1_350_000
_MAX_QUERY_CHARS = 180
_MAX_SOURCES = 3
_HIDE = re.compile(r'[\x00-\x1f\x7f\u200b-\u200f\u202a-\u202e]')


class EngineeringResearchError(ValueError):
    pass


def research_request_sha256(request: Mapping[str,Any]) -> str:
    """Stable identity for exact question, hosts, and direct source locators."""
    data={'id':str(request.get('id') or ''),
          'question':str(request.get('question') or '').strip(),
          'allowed_hosts':sorted(str(h).strip().lower() for h in request.get('allowed_hosts') or []),
          'source_urls':list(request.get('source_urls') or [])}
    return 'sha256:'+hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _valid_public_host(url: str, hosts: frozenset[str]) -> str:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise EngineeringResearchError('only HTTPS source URLs without credentials/custom ports')
    host = str(parsed.hostname or '').lower().rstrip('.')
    if host not in hosts:
        raise EngineeringResearchError('source host is outside curated allowlist')
    if parsed.fragment or '\\' in url or len(url)>1200:
        raise EngineeringResearchError('malformed source URL')
    # DNS defense in depth; exact allowlist also mitigates untrusted host links.
    try:
        addresses = socket.getaddrinfo(host,443,proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise EngineeringResearchError('source hostname unavailable') from exc
    if not addresses:
        raise EngineeringResearchError('source hostname has no public address')
    for item in addresses:
        addr=ipaddress.ip_address(item[4][0])
        if not addr.is_global:
            raise EngineeringResearchError('source hostname resolves to non-public address')
    return host


def _download(url: str, *, max_bytes: int, timeout_s: float,
              fetch: Callable[[str,int,float],tuple[bytes,str]] | None = None) -> tuple[bytes,str]:
    if fetch:
        raw, media_type = fetch(url,max_bytes,timeout_s)
        if len(raw)>max_bytes:
            raise EngineeringResearchError('source exceeds byte budget')
        return raw,media_type
    request=urllib.request.Request(url,headers={
        'User-Agent':'Mozilla/5.0 (compatible; HS-Research/1.0; source-bound only)',
        'Accept':'text/html,application/xhtml+xml',
        'Accept-Language':'en-US,en;q=0.8',
    })
    opener=urllib.request.build_opener(NoRedirect)
    with opener.open(request,timeout=timeout_s) as response:
        if response.status != 200:
            raise EngineeringResearchError('source did not return HTTP 200')
        media_type=response.headers.get('Content-Type','')
        raw=response.read(max_bytes+1)
    if len(raw)>max_bytes:
        raise EngineeringResearchError('source exceeds byte budget')
    return raw,media_type


def _clean(text: str, limit: int) -> str:
    return _HIDE.sub(' ', ' '.join(text.split()))[:limit]


def _page_extract(raw: bytes, content_type: str) -> tuple[str,str]:
    if not ('text/html' in content_type or 'application/xhtml+xml' in content_type):
        raise EngineeringResearchError('only HTML source content can be read')
    soup=BeautifulSoup(raw,'html.parser')
    title=_clean(soup.title.get_text(' ',strip=True) if soup.title else '',140)
    for bad in soup.select('script,style,svg,noscript,nav,footer,header,form,button'):
        bad.decompose()
    article=soup.select_one('article') or soup.select_one('main') or soup.body or soup
    # iFixit exposes discrete step blocks. Prefer these over navigation,
    # marketing snippets, and unrelated links on the surrounding page.
    if soup.select('.step-wrapper.js-step'):
        lines=[]
        for step in soup.select('.step-wrapper.js-step')[:85]:
            step_heading=step.select_one('h2')
            instructions=[_clean(li.get_text(' ',strip=True),380)
                          for li in step.select('.step-lines li')[:8]]
            if instructions:
                lines.append(_clean((step_heading.get_text(' ',strip=True) if step_heading else 'Step')
                                     +' : '+' '.join(instructions),600))
        if lines:
            published_steps=len(soup.select('.step-wrapper.js-step'))
            return title,_clean(f'Publisher page has {published_steps} steps. '+' '.join(lines),3200)
    lines=[]
    for el in article.select('h1,h2,h3,p,li,td,th')[:350]:
        fragment=_clean(el.get_text(' ',strip=True),500)
        if len(fragment)>=18 and fragment not in lines:
            lines.append(fragment)
    if not lines:
        lines=[_clean(article.get_text(' ',strip=True),1600)]
    return title,_clean(' '.join(lines),3200)


def _ifixit_api_for_guide(url:str, *,timeout_s:float,
                          fetch:Callable[[str,int,float],tuple[bytes,str]] | None=None) -> tuple[str,str,bytes,str]:
    """Retrieve a specific original guide through iFixit's public JSON API.

    Only `/Guide/.../{numeric guide id}` is accepted. Never guess another
    product or invent step text if a guide page requires JavaScript.
    """
    parsed=urllib.parse.urlsplit(url)
    if parsed.hostname not in {'www.ifixit.com','ifixit.com'}:
        raise EngineeringResearchError('not an iFixit guide')
    hit=re.fullmatch(r'/Guide/[^/]{4,170}/([0-9]{1,9})',parsed.path)
    if not hit:
        raise EngineeringResearchError('no concrete iFixit guide id')
    api_url='https://www.ifixit.com/api/2.0/guides/'+hit.group(1)
    _valid_public_host(api_url,frozenset({'www.ifixit.com'}))
    raw,media=_download(api_url,max_bytes=_MAX_PAGE_BYTES,timeout_s=timeout_s,fetch=fetch)
    if 'application/json' not in media:
        raise EngineeringResearchError('iFixit API did not return JSON')
    body=json.loads(raw)
    if str(body.get('guideid')) != hit.group(1) or not isinstance(body.get('steps'),list):
        raise EngineeringResearchError('guide identity or step list invalid')
    label=_clean(str(body.get('title') or ''),140)
    steps=body['steps']
    lines=[f'Publisher guide title: {label}. Published steps: {len(steps)}.']
    for i,step in enumerate(steps[:9],1):
        if not isinstance(step,dict):continue
        clauses=[]
        for line in step.get('lines',[])[:4]:
            if isinstance(line,dict):
                clauses.append(_clean(str(line.get('text_raw') or ''),180))
        if clauses:lines.append('Step '+str(i)+' : '+' '.join(clauses))
    return label,_clean(' '.join(lines),2500),raw,api_url


def _search_links(raw:bytes, hosts:frozenset[str], max_results:int)->list[dict[str,str]]:
    doc=BeautifulSoup(raw,'html.parser')
    found=[];seen=set()
    for snippet in doc.select('div.snippet[data-type="web"]'):
        for a in snippet.select('a[href]'):
            url=a.get('href','')
            try:
                parsed=urllib.parse.urlsplit(url)
                host=str(parsed.hostname or '').lower().rstrip('.')
                if parsed.scheme!='https' or host not in hosts or url in seen:
                    continue
                # Additional URL checks occur again immediately before fetch.
                if any(x in url for x in ('/search?', '/search/', '/login')):
                    continue
            except ValueError:
                continue
            heading=_clean(a.get_text(' ',strip=True),180)
            if not heading:continue
            seen.add(url)
            found.append({'url':url,'host':host,'search_title':heading,
                          'search_excerpt':_clean(snippet.get_text(' ',strip=True),500)})
            break
        if len(found)>=max_results:break
    return found


def research_engineering_gap(request: Mapping[str,Any], *,
                             fetch: Callable[[str,int,float],tuple[bytes,str]] | None = None,
                             timeout_s:float=8.0) -> dict[str,Any]:
    """Perform one explicit, bounded knowledge-gap lookup on trusted sources.

    `request` comes from the revision-pinned HS project state, never a model
    constructed URL or unrestricted browser command.
    """
    if not isinstance(request,Mapping):
        raise EngineeringResearchError('pinned engineering research request missing')
    if set(request)-{'id','question','allowed_hosts','purpose','source_urls'}:
        raise EngineeringResearchError('unexpected research request fields')
    identity=str(request.get('id') or '')
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,55}',identity):
        raise EngineeringResearchError('invalid research request identity')
    question=str(request.get('question') or '').strip()
    if not 12<=len(question)<=_MAX_QUERY_CHARS or _HIDE.search(question) or '://' in question:
        raise EngineeringResearchError('invalid/oversized research question')
    hosts=request.get('allowed_hosts') or []
    if not isinstance(hosts,list) or not 1<=len(hosts)<=4:
        raise EngineeringResearchError('explicit trusted source host list required')
    cleaned=frozenset(str(host).lower().strip() for host in hosts)
    if not cleaned.issubset(TRUSTED_SOURCE_HOSTS):
        raise EngineeringResearchError('research request includes unapproved source host')
    pinned_urls=request.get('source_urls') or []
    if not isinstance(pinned_urls,list) or len(pinned_urls)>3:
        raise EngineeringResearchError('pinned source URLs must be a short list')
    for url in pinned_urls:
        if not isinstance(url,str):
            raise EngineeringResearchError('source URL must be text')
        _valid_public_host(url,cleaned)
    report={
        'schema_version':_SCHEMA,'request_id':identity,
        'request_sha256':research_request_sha256(request),
        'question':question,'allowed_hosts':sorted(cleaned),
        'status':'unavailable','source_count':0,'retrieved_page_count':0,'snippet_only_count':0,'sources':[],
        'search_engine':'project_known_publisher_url' if pinned_urls else 'brave_public_html',
        'discovery_mode':'project_provided_known_source' if pinned_urls else 'live_public_search',
        'browser_or_search_enabled':True,
        'search_not_equivalent_to_independent_verification':True,
        'source_text_is_untrusted_external_data':True,
        'vendor_specification_verified_by_experiment':False,
        'engineering_design_approved':False,
        'physical_authority_unchanged':True,
        'searched_at_utc':datetime.now(timezone.utc).isoformat(),
    }
    # A project can supply an exact publisher URL already discovered during
    # engineering. This is source retrieval, not autonomous URL discovery.
    # It remains useful if an external search engine is rate-limiting calls.
    if pinned_urls:
        choices=[{'url':url,'host':str(urllib.parse.urlsplit(url).hostname),
                 'search_title':'Pinned official source',
                 'search_excerpt':'Publisher URL explicitly registered in project'}
                 for url in pinned_urls]
    else:
        # Limit search to approved hosts, not unconstrained worldwide browsing.
        search_query=question+' ('+' OR '.join('site:'+host for host in sorted(cleaned))+')'
        search_url=_SEARCH+urllib.parse.quote(search_query,safe='')
        try:
            _valid_public_host(search_url,frozenset({'search.brave.com'}))
            raw,media=_download(search_url,max_bytes=_MAX_HTML_BYTES,timeout_s=timeout_s,fetch=fetch)
            if 'text/html' not in media:
                raise EngineeringResearchError('search service changed content type')
            choices=_search_links(raw,cleaned,6)
        except (EngineeringResearchError,OSError,ValueError):
            report['reason']='search_unavailable_or_invalid'
            return report
    if not choices:
        report['status']='no_relevant_sources_found'
        return report
    for choice in choices:
        if len(report['sources'])>=_MAX_SOURCES:break
        entry={
            'url':choice['url'],'host':choice['host'],
            'title':choice['search_title'],
            'search_excerpt':choice['search_excerpt'],
        }
        try:
            _valid_public_host(choice['url'],cleaned)
            page,media=_download(choice['url'],max_bytes=_MAX_PAGE_BYTES,timeout_s=timeout_s,fetch=fetch)
            title,body=_page_extract(page,media)
            if not body:raise EngineeringResearchError('empty external page')
            digest='sha256:'+hashlib.sha256(page).hexdigest()
            entry.update({'title':title or choice['search_title'],'excerpt':body,
                'original_sha256':digest,'downloaded_bytes':len(page),
                'evidence_kind':'fetched_primary_webpage',
                'source_scope':'external_published_document_not_physically_verified'})
            report['retrieved_page_count']+=1
        except (EngineeringResearchError,OSError,ValueError,UnicodeError):
            try:
                # Narrow publisher API fallback when only the HTML delivery
                # is blocked; preserve original publisher identity and hash.
                title,body,page,capture_url=_ifixit_api_for_guide(
                    choice['url'],timeout_s=timeout_s,fetch=fetch)
                digest='sha256:'+hashlib.sha256(page).hexdigest()
                entry.update({'title':title,'excerpt':body,
                    'original_sha256':digest,'downloaded_bytes':len(page),
                    'capture_url':capture_url,
                    'evidence_kind':'publisher_api_document',
                    'source_scope':'original_iFixit_guide_from_publisher_API_not_physically_verified'})
                report['retrieved_page_count']+=1
            except (EngineeringResearchError,OSError,ValueError,UnicodeError,TypeError,json.JSONDecodeError):
                # A snippet is a navigation hint, not original-document evidence.
                # Never invent a publisher-page hash if no page was fetched.
                excerpt=choice['search_excerpt']
                if not excerpt:continue
                digest='sha256:'+hashlib.sha256(excerpt.encode()).hexdigest()
                entry.update({'excerpt':excerpt,'original_sha256':None,
                    'search_excerpt_sha256':digest,'downloaded_bytes':0,
                    'evidence_kind':'unverified_search_snippet',
                    'source_scope':'search_engine_snippet_only_source_page_unreadable'})
                report['snippet_only_count']+=1
        entry['source_id']='web-'+hashlib.sha256((choice['url']+'|'+digest).encode()).hexdigest()[:20]
        report['sources'].append(entry)
    report['source_count']=len(report['sources'])
    report['status']=('source_context_retrieved' if report['retrieved_page_count']
                      else ('search_snippets_only' if report['snippet_only_count']
                            else 'search_results_not_readable'))
    return report
