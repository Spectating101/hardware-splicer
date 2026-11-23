"""GPL-3.0-only. Adversarial integrity checks on isolated delivered-artifact copies."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    cases=[]
    with tempfile.TemporaryDirectory(prefix='ender3-digital-audit-') as tmp:
        copy=Path(tmp)/'study'
        shutil.copytree(ROOT,copy,ignore=shutil.ignore_patterns('01 MAIN ASM Ender_3.STEP','__pycache__','e_plate_drawing.png','.cache'))
        codepath=copy/'simulation/example.gcode';engpath=copy/'reports/engineering.json';simpath=copy/'reports/simulation.json'
        original_code=codepath.read_text();original_eng=engpath.read_text();original_sim=simpath.read_text()
        def verify(name,mutation,expect_ok):
            codepath.write_text(original_code);engpath.write_text(original_eng);simpath.write_text(original_sim)
            mutation()
            run=subprocess.run([sys.executable,str(copy/'scripts/verify.py')],capture_output=True,text=True,
                env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'},timeout=90)
            result=json.loads((copy/'reports/verification.json').read_text())
            observed=run.returncode==0 and result['artifact_integrity']
            cases.append(dict(name=name,passed=observed==expect_ok,expected_integrity=expect_ok,
                observed_integrity=observed,returncode=run.returncode,
                rejected_checks=[c['name'] for c in result['checks'] if not c['passed']]))
            print(name, 'PASS' if cases[-1]['passed'] else 'FAIL', flush=True)
        verify('isolated_copy_without_large_assembly',lambda:None,True)
        verify('extrusion_decimal_word_rejected',lambda:codepath.write_text(original_code.replace('G1 Z0.0000 F180','G1 Z0.0000 F180 E.5',1)),False)
        verify('duplicate_heater_setpoint_rejected',lambda:codepath.write_text(original_code.replace('M104 S0','M104 S200 S0',1)),False)
        verify('hidden_excess_Z_move_rejected',lambda:codepath.write_text(original_code.replace('M400','G0 Z1000 F300\nM400',1)),False)
        def forge_numeric():
            for path in (engpath,simpath):
                data=json.loads(path.read_text())
                for con in data['constraints']:
                    if 'fixture_vertical_clearance' in con['id']:con['actual']=500.;con['passed']=True
                data['metrics']['fixture_bed_clearance_mm']=500.
                path.write_text(json.dumps(data,indent=2)+'\n')
        verify('consistent_but_forged_numeric_acceptance_rejected',forge_numeric,False)
        def forge_negative_goal():
            data=json.loads(engpath.read_text());data['constraints'][0]['passed']=False;data['requirements_met']=False
            engpath.write_text(json.dumps(data,indent=2)+'\n')
        verify('self_consistent_forged_failed_goal_rejected',forge_negative_goal,False)
    result=dict(case_id='ender3-penplotter',physical_validation_performed=False,passed=all(c['passed'] for c in cases),cases=cases)
    (ROOT/'reports/tamper_tests.json').write_text(json.dumps(result,indent=2)+'\n')
    return 0 if result['passed'] else 1


if __name__=='__main__':sys.exit(main())
