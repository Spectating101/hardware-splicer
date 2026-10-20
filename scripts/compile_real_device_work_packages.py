#!/usr/bin/env python3
"""Compile existing real-device reviews into inspectable project work packages."""
from __future__ import annotations
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from hardware_splicer.real_device_work_package import compile_work_package


def main():
    directory=ROOT/'eval/real_hardware_projects'
    target=directory/'work_packages'
    target.mkdir(exist_ok=True)
    for path in sorted(directory.glob('*.json')):
        case=json.loads(path.read_text())
        review=json.loads((directory/'reports'/path.name).read_text())
        plan=review.get('hs_raw_plan',{})
        package=compile_work_package(case,review,planner=plan)
        (target/path.name).write_text(json.dumps(package,indent=2)+'\n')
        print(case['id'],'requirements',len(package['requirements']),
              'work_steps',len(package['work_steps']),
              'parts',len(package['required_parts']),
              'open_gaps',len(package['critical_unknowns']),
              'status',package['engineering_readiness'])
if __name__=='__main__':main()
