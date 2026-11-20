"""Nominal-only vs source-constrained engineering design experiment.

One frozen batteryless DC witness fixture; no live hardware, no fabrication.
Inputs and policy declared in experiment-20261120.json.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,math,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path(__file__).resolve().parent/'experiment-20261120.json'
R_FIXED=.05+.015+.010 # nominal engineering modeling assumption, not measured
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(path,v):Path(path).write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
def circuit(v: float, load_ohm: float, series_ohm: float) -> str:
    """Construct one independent ideal DC corner, with an explicit ground."""
    if series_ohm > 0:
        electrical = (f"V_SRC plus 0 DC {v:.9g}\n"
                      f"R_SERIES plus load {series_ohm:.9g}\n")
    else:
        electrical = f"V_SRC load 0 DC {v:.9g}\n"
    return (f"* Source-bound test fixture only: bus={v}, load={load_ohm}, series={series_ohm}\n"
            +electrical+f"R_LOAD load 0 {load_ohm:.9g}\n"
            ".control\nset noaskquit\nop\nprint v(load) i(v_src)\nquit\n.endc\n.end\n")

def spice(v,r,rs):
 b=circuit(v,r,rs)
 p=subprocess.run(['ngspice','-b'],input=b,text=True,capture_output=True,timeout=8)
 if p.returncode:raise RuntimeError(f'ngspice failed: {p.stderr[-400:]}')
 def f(n):
  x=re.search(r'(?m)^'+re.escape(n)+r'\s*=\s*([-+0-9.eE]+)',p.stdout)
  if x is None:raise RuntimeError(f'no ngspice {n}: {p.stdout[-500:]}')
  return float(x.group(1))
 amps=-f('i(v_src)')
 voltage=f('v(load)')
 assert amps>0
 return {'current_a':amps,'load_v':voltage,'load_power_w':amps*voltage}
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--native-replay',required=True,type=Path)
 parser.add_argument('--out',required=True,type=Path)
 args=parser.parse_args()
 if args.out.exists():parser.error('Output directory must not exist')
 d=json.loads(SOURCE.read_bytes())
 spec=json.loads((ROOT/'station-spec-5v.json').read_text())
 native=json.loads((args.native_replay/'verification.json').read_text())
 original_spice=(ROOT/'spice_low_voltage_witness.cir').read_text()
 checks={
  'pinned_spec_bytes':sha(ROOT/'station-spec-5v.json')==d['design_identity']['source_station_spec_sha256'],
  'pinned_original_spice_bytes':sha(ROOT/'spice_low_voltage_witness.cir')==d['design_identity']['source_spice_sha256'],
  'nominal_source_spec_consistent':spec['nominal_voltage_v']==5 and
    spec['maximum_bus_voltage_v']==d['maximum_bus_voltage_v'] and
    spec['maximum_power_w']==d['maximum_declared_load_power_w'],
  'original_spice_load_is_10ohm':bool(re.search(r'(?m)^R_LOAD LOAD_PLUS 0 10\s*$',original_spice)),
  'original_native_ERC_DRC_passed':native['native_erc']=='ZERO_VIOLATIONS' and
    native['native_drc'].startswith('ZERO_VIOLATIONS'),
  'original_native_input_power_model_passed_nominal_only':(
    native['status']=='SOFTWARE_DESIGN_VALIDATED_ONLY' and
    native.get('load_resistance_ohm_assumed')==10 and
    abs(native['spice_load_power_w']-2.462918)<0.00003),
 }
 if not all(checks.values()):
  raise RuntimeError('Pinned source/native baseline disagrees: '+str(checks))
 if d['maximum_bus_voltage_v']>5.25 or d['maximum_declared_load_power_w']!=2.5:
  raise ValueError('Do not silently reinterpret the original power specification')
 loads=d['candidate_load_resistances_ohm']
 if len(loads)!=len(set(loads)) or any((not isinstance(x,(int,float)) or x<=0) for x in loads):
  raise ValueError('Invalid candidate values')
 supply=[d['assumed_low_bus_voltage_v'],spec['nominal_voltage_v'],d['maximum_bus_voltage_v']]
 tolerance=d['load_resistance_tolerance_pct']/100
 res=d['series_resistance_scenarios_ohm']
 corners=[]
 variants=[]
 for load in loads:
  rows=[]
  for voltage in supply:
   for load_ratio in [1-tolerance,1,1+tolerance]:
    for series in res:
     effective=load*load_ratio
     a=voltage/(effective+series)
     w=a*a*effective
     s=spice(voltage,effective,series)
     check=(abs(s['current_a']-a)<1.2e-6 and abs(s['load_power_w']-w)<1e-5)
     if not check:raise AssertionError('SPICE differs from independent oracle')
     row={'load_nominal_ohm':load,'source_v':voltage,'load_actual_ohm':effective,
          'series_ohm':series,'current_a':a,'load_power_w':w,'spice_verified':check}
     rows.append(row);corners.append(row)
  worst=max(rows,key=lambda x:x['load_power_w'])
  mincurr=min(rows,key=lambda x:x['current_a'])
  nominal=next(x for x in rows if x['source_v']==5 and abs(x['load_actual_ohm']-load)<1e-9 and abs(x['series_ohm']-.075)<1e-9)
  max_allowed=d['maximum_declared_load_power_w']*(1-d['required_power_headroom_fraction'])
  controls={
   'load_power_below_declared_ceiling':worst['load_power_w']<=d['maximum_declared_load_power_w'],
   'at_least_declared_headroom':worst['load_power_w']<=max_allowed,
   'minimum_current_for_reference_signal':mincurr['current_a']>=d['minimum_corner_current_a'],
   'source_current_limit_not_needed_at_high_corner':max(x['current_a'] for x in rows)<d['source_current_limit_a'],
  }
  variants.append({'load_nominal_ohm':load,'nominal':nominal,'worst_power':worst,
                   'minimum_current':mincurr,'controls':controls,
                   'eligible':all(controls.values()),'nominal_reference_shunt_mV':nominal['current_a']*.01*1000,
                   'worst_reference_shunt_mV':mincurr['current_a']*.01*1000})
 eligible=[x for x in variants if x['eligible']]
 selected=max(eligible,key=lambda x:(x['minimum_current']['current_a'],-x['load_nominal_ohm'])) if eligible else None
 baseline=next(x for x in variants if x['load_nominal_ohm']==d['original_ohm'])
 if not baseline['controls']['load_power_below_declared_ceiling'] is False:
  raise AssertionError('Expected baseline to violate source spec corners')
 out=args.out;out.mkdir(parents=True,exist_ok=False)
 with (out/'corner-results.csv').open('w',newline='') as stream:
  writer=csv.DictWriter(stream,fieldnames=list(corners[0]));writer.writeheader();writer.writerows(corners)
 result={'schema':'hardware_splicer.witness_envelope_design_experiment.v1',
         'spec_sha256':sha(ROOT/'station-spec-5v.json'),
         'original_spice_sha256':sha(ROOT/'spice_low_voltage_witness.cir'),
         'experiment_sha256':sha(SOURCE),
         'native_verification_sha256':sha(args.native_replay/'verification.json'),
         'baseline':baseline,'candidates':variants,
         'selected':selected,'all_corners_spice_verified':all(x['spice_verified'] for x in corners),
         'number_of_independent_spice_corners':len(corners),
         'evidence_kind':'digital_spice_sensitivity_study',
         'physical_authority_granted':False,
         'limitations':['Zero-series resistance is a hypothetical conservative corner, not measured source resistance',
                        '5% resistive load tolerance and 10% reserve are research trial assumptions, not vendor supplied specs',
                        '13-ohm load is not a procured exact component or commissioned thermal assembly',
                        'KiCad ERC/DRC is for the original unchanged witness PCB, not the external load',
                        'Policy Lab software-fixture intake is not independently calibrated physical metrology',
                        'No feasible load choice resolves actual fuse, isolated source, DMM reference or current-path physical gates']}
 write(out/'feasibility.json',result)
 if selected:
  revised={'schema':'hardware_splicer.proposed_operating_spec_v1',
           'parent_spec_sha256':result['spec_sha256'],'parent_native_verification_sha256':result['native_verification_sha256'],
           'source_max_bus_v':d['maximum_bus_voltage_v'],
           'declared_max_load_power_w':d['maximum_declared_load_power_w'],
           'proposed_external_load_nominal_ohm':selected['load_nominal_ohm'],
           'hypothetical_load_tolerance_pct':d['load_resistance_tolerance_pct'],
           'reserve_policy_fraction':d['required_power_headroom_fraction'],
           'modeled_worst_load_power_w':selected['worst_power']['load_power_w'],
           'modeled_nominal_current_a':selected['nominal']['current_a'],
           'modeled_min_current_a':selected['minimum_current']['current_a'],
           'physical_build_status':'HOLD',
           'decision':'candidate for independent operator review, not approved build or energy measurement'}
  write(out/'proposed-revision.json',revised)
 summary={'baseline_5v_load_w':baseline['nominal']['load_power_w'],
          'baseline_5_25v_worst_w':baseline['worst_power']['load_power_w'],
          'baseline_declared_power_exceeded':not baseline['controls']['load_power_below_declared_ceiling'],
          'selected_ohm':selected['load_nominal_ohm'] if selected else None,
          'selected_nominal_load_w':selected['nominal']['load_power_w'] if selected else None,
          'selected_worst_load_w':selected['worst_power']['load_power_w'] if selected else None,
          'selected_minimum_current_a':selected['minimum_current']['current_a'] if selected else None,
          'corner_count':len(corners),'all_corner_oracles_agree':True,
          'physical_status':'HOLD','out':str(out)}
 print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
