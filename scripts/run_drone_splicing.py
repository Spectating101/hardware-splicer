#!/usr/bin/env python3
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from hardware_splicer.drone_splicing import assess_splice
ref=json.loads((ROOT/'eval/drone_reference_build/x500_v2.json').read_text())
candidates=json.loads((ROOT/'eval/drone_splicing/alternates.json').read_text())
result=assess_splice(ref,candidates)
out=ROOT/'eval/drone_splicing/splice_assessment.json'
out.write_text(json.dumps(result,indent=2)+'\n')
for r in result['candidates']:
 print(r['candidate_id'],r['classification'],'hard_mismatches',len(r['hard_failures']),'evidence_gaps',len(r['unverified_gaps']))
print('APPROVED FOR INSTALLATION',len(result['approved_for_installation']))
