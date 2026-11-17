#!/usr/bin/env python3
"""Run the packaged HS-3G-B physics again; no CAD tools or hardware required."""
import argparse
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from hs3g_sim import run,assess,freefall_oracle


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--package',type=Path,default=HERE if (HERE/'model.json').is_file() else HERE/'reference')
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--render',action='store_true',help='Also generate native camera PNG/GIF views')
    args=p.parse_args()
    if args.out.exists() and any(args.out.iterdir()):p.error('Use a new/empty output directory')
    args.out.mkdir(parents=True,exist_ok=True)
    model=json.loads((args.package/'model.json').read_text())
    config=json.loads((args.package/'simulation-contract.json').read_text())
    table=json.loads((args.package/'thrust-table.json').read_text())
    scenarios=[]
    for scenario in config['scenarios']:
        rows=run(model,table,config,scenario,args.out,render=args.render and scenario['id']=='nominal')
        scenarios.append(assess(rows,model,config,scenario))
    oracle=freefall_oracle(model,table,config)
    result={'schema':'hardware_splicer.hs3g_packaged_simulation_run.v1',
            'simulation_acceptance':all(x['accepted'] for x in scenarios) and oracle['accepted'],
            'scenarios':scenarios,'gravity_oracle':oracle,
            'scope_limits':config['scope_limits'],'physical_work_requested':False,'physical_validation':False}
    (args.out/'SIMULATION.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'simulation_acceptance':result['simulation_acceptance'],'scenarios':[{'id':x['scenario']['id'],'accepted':x['accepted']} for x in scenarios]}))
    return 0 if result['simulation_acceptance'] else 1


if __name__=='__main__':raise SystemExit(main())
