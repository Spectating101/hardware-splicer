#!/usr/bin/env python3
"""Use real CADCLAW native assembly STEP to produce independently mapped GLB meshes."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from hardware_splicer.teardown_cad_mesh import assemble_mesh
p=argparse.ArgumentParser(description=__doc__)
p.add_argument("--multicad",type=Path,required=True)
p.add_argument("--cadclaw",type=Path,required=True)
p.add_argument("--output",type=Path,required=True)
a=p.parse_args()
try: print(json.dumps(assemble_mesh(a.multicad,a.cadclaw,a.output),indent=2,sort_keys=True))
except (OSError,ValueError,KeyError,TypeError) as e:
    print("CAD mesh assembly REFUSED:",e,file=sys.stderr)
    raise SystemExit(1)
