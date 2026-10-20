from __future__ import annotations
import argparse,json
from pathlib import Path
from hardware_splicer.realization_printer_dryrun import simulate_staging_and_denied_start

def main():
 p=argparse.ArgumentParser()
 p.add_argument("--gcode",type=Path,required=True)
 p.add_argument("--out",type=Path,required=True)
 a=p.parse_args()
 result=simulate_staging_and_denied_start(a.gcode)
 a.out.write_text(json.dumps(result,indent=2)+"\n")
 print(json.dumps({k:v for k,v in result.items() if k not in {"transport_receipts"}},indent=2))
 return 0
if __name__=="__main__":raise SystemExit(main())
