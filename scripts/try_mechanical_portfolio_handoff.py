"""Explicit isolated HS → Policy Lab → Cite native handoff; no deployed services."""
import argparse
import json
from pathlib import Path

from hardware_splicer.mechanical_portfolio_handoff import run


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--evidence",required=True,type=Path)
    p.add_argument("--review",required=True,type=Path)
    p.add_argument("--source",required=True,type=Path)
    p.add_argument("--cite-root",required=True,type=Path)
    p.add_argument("--citation-source",required=True,type=Path)
    p.add_argument("--policy-root",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    print(json.dumps(run(a.evidence,a.review,a.source,a.cite_root,a.citation_source,a.out,policy_root=a.policy_root),indent=2))


if __name__=="__main__":
    main()
