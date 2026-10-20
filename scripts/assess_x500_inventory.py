#!/usr/bin/env python3
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from hardware_splicer.drone_assembly_readiness import assess_inventory
p=argparse.ArgumentParser();p.add_argument('inventory',type=Path);p.add_argument('--out',type=Path,default=ROOT/'eval/drone_reference_build/generated/inventory_status.json');args=p.parse_args()
ref=json.loads((ROOT/'eval/drone_reference_build/x500_v2.json').read_text())
result=assess_inventory(ref,json.loads(args.inventory.read_text()))
args.out.parent.mkdir(parents=True,exist_ok=True)
args.out.write_text(json.dumps(result,indent=2)+'\n')
print('missing lines',result['unfilled_line_items'],'unverified lines',result['unverified_line_items'])
for row in result['stages']: print(row['stage_id'],row['review_status'],'unready parts',','.join(row['unverified_or_missing_parts']))
