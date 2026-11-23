"""Audit external reference BOM category totals without assuming live market prices."""
from __future__ import annotations

import re
from typing import Any

_PRICE=re.compile(r'\$\s*(\d+(?:\.\d+)?)\s*(?:[–—-]\s*(\d+(?:\.\d+)?))?')


def _currency_range(text: str) -> tuple[float,float] | None:
    match=_PRICE.search(text)
    if not match:return None
    low=float(match.group(1))
    high=float(match.group(2) or low)
    if high<low:raise ValueError('invalid cost range')
    return (low,high)


def audit_markdown_reference_bom(content: bytes, *, cap_usd: float | None = None) -> dict[str,Any]:
    if len(content)>512_000:raise ValueError('reference BOM above audit size limit')
    doc=content.decode('utf-8')
    categories=[]
    current=''
    found_header=False
    claimed=None
    for line in doc.splitlines():
        if line.startswith('#'):
            current=line.strip('# ').lower()
            found_header=False
            continue
        cells=[c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells)>=2 and cells[0].lower()=='category' and cells[1].lower().startswith('est. cost'):
            if 'total by category' in current:
                found_header=True
            continue
        if not found_header or not line.lstrip().startswith('|') or len(cells)<2:continue
        if all(c.strip('- :|')=='' for c in cells):continue
        price=_currency_range(cells[1])
        if price is None:continue
        if 'total' in cells[0].lower():
            claimed=price
        else:
            categories.append({'name':cells[0].strip('* '),'min_usd':price[0],
                               'max_usd':price[1], 'source':'declared_external_repo_estimate'})
    if not categories:
        return {'status':'unparsed','reason':'no category estimate table',
                'source_claims_verified_with_vendors':False}
    lower=round(sum(c['min_usd'] for c in categories),2)
    upper=round(sum(c['max_usd'] for c in categories),2)
    claim={'min_usd':claimed[0],'max_usd':claimed[1]} if claimed else None
    exact=bool(claim and lower==claim['min_usd'] and upper==claim['max_usd'])
    cap=float(cap_usd) if cap_usd is not None else None
    return {'status':'analyzed_external_cost_claims',
            'category_count':len(categories),'category_estimates':categories,
            'category_sum_min_usd':lower,'category_sum_max_usd':upper,
            'published_total':claim,
            'published_total_reconciles_with_category_sum':exact,
            'published_total_discrepancy_usd':(
                {'min':round(lower-claim['min_usd'],2),'max':round(upper-claim['max_usd'],2)}
                if claim else None),
            'budget_cap_usd':cap,
            'listed_category_upper_bound_below_cap':upper<=cap if cap is not None else None,
            'unit_prices_vendor_verified':False,
            'excludes_unquantified_enclosure_shipping_tools_labor':True,
            'source_cost_not_purchase_quote':True,
            'purchase_approved':False}
