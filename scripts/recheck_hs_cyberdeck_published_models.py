#!/usr/bin/env python3
"""Independently verify *the actual packaged* PCB retainer STEP files.

Do not trust an old 7/7 component audit when its CAD SHA-256s refer to a
newer/different prototype. Original official-model STEP hashes in that audit
serve ONLY as an expected-model inventory, never as geometric test results.
Diagnostic reports are written even when the candidate collides; errors and
missing models never elevate fabrication authority.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import cadquery as cq


def digest(path:Path)->str:
    return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def recheck(pkg:Path,original_models:Path,source_board:Path,original_step:Path)->dict:
    original_report=json.loads((pkg/'CAD_REPORT.json').read_text())
    previous=json.loads((pkg/'INDEPENDENT_COMPONENT_AUDIT.json').read_text())
    registered_board_hash=original_report.get('source_board_sha256')
    if not registered_board_hash or registered_board_hash != digest(source_board):
        raise ValueError('original KiCad source differs from packaged CAD provenance')
    counts=previous.get('publisher_3d_reference_coverage') or {}
    references=previous.get('independent_model_collisions') or []
    if (counts.get('modelled')!=7 or counts.get('expected_models')!=11 or
        counts.get('no_3d_model')!=15 or len(references)!=7):
        raise ValueError('model reference manifest incomplete or inconsistent')
    if len({ref.get('reference') for ref in references})!=len(references):
        raise ValueError('duplicate model references')
    board=cq.importers.importStep(str(original_step))
    original_box=board.val().BoundingBox()
    base_file=pkg/'source_edge_capture_base.step'
    lid_file=pkg/'source_edge_capture_lid.step'
    base=cq.importers.importStep(str(base_file))
    lid=cq.importers.importStep(str(lid_file))
    if len(base.solids().vals())!=1 or len(lid.solids().vals())!=1:
        raise ValueError('packaged base/lid must each be one CAD solid')
    actual={'base':digest(base_file),'lid':digest(lid_file)}
    prior=(previous.get('prior_model_reference_manifest_original_case_step_sha256s')
           or previous.get('cad_case_step_sha256s') or {})
    rows=[]
    for row in references:
        identity=str(row.get('reference') or '')
        if not identity.isalnum() or len(identity)>12:
            raise ValueError('invalid source model identity')
        component_file=original_models/(identity+'.step')
        checked=digest(component_file)
        if row.get('component_step_sha256')!=checked:
            raise ValueError('official model STEP occurrence changed: '+identity)
        raw=cq.importers.importStep(str(component_file))
        solids=raw.solids().vals()
        matching=[i for i,s in enumerate(solids)
                  if all(abs(getattr(s.BoundingBox(),axis)-getattr(original_box,axis))<0.08
                         for axis in ('xlen','ylen','zlen'))]
        if len(matching)!=1 or len(solids)!=2:
            raise ValueError('component model export frame/solid count differs: '+identity)
        comp=cq.Workplane('XY').newObject([solids[1-matching[0]]])
        bv=round(float(comp.intersect(base).val().Volume()),6)
        lv=round(float(comp.intersect(lid).val().Volume()),6)
        rows.append({'reference':identity,'component_step_sha256':checked,
                     'base_intersection_mm3':bv,'lid_intersection_mm3':lv,
                     'both_halves_nominally_clear':bv<=0.02 and lv<=0.02})
    clear=all(row['both_halves_nominally_clear'] for row in rows)
    return {
      'schema':'hs.independent_partial_3d_clearance.v2',
      'status':'seven_original_models_nominally_clear' if clear else 'packaged_case_component_collision_found',
      'cad_case_step_sha256s':actual,
      'original_kicad_pcb_sha256':registered_board_hash,
      'original_kicad_reexport_board_sha256':digest(original_step),
      'publisher_3d_reference_coverage':counts,
      'prior_model_reference_manifest_original_case_step_sha256s':prior,
      'prior_reference_audit_matches_exact_packaged_cad_sha256s':actual==prior,
      'prior_audit_result_reused':False,
      'all_seven_original_model_placements_nominally_clear':clear,
      'independent_model_collisions':rows,
      'unresolved_model_references':previous.get('unresolved_model_references') or [],
      'untested_unmodelled_footprints':previous.get('untested_unmodelled_footprints') or [],
      'other_assembly_and_mating_clearance_verified':False,
      'print_or_fabrication_authorized':False,
      'source_original_model_hashes_verified':True,
    }


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('package_dir',type=Path)
    p.add_argument('--models',type=Path,required=True)
    p.add_argument('--original-board',type=Path,required=True)
    p.add_argument('--original-board-step',type=Path,required=True)
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    data=recheck(args.package_dir,args.models,args.original_board,args.original_board_step)
    dst=args.output or (args.package_dir/'INDEPENDENT_COMPONENT_AUDIT.json')
    dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text(json.dumps(data,indent=2)+'\n')
    print('TESTED_CASE',data['status'],'PASS',data['all_seven_original_model_placements_nominally_clear'])
    for item in data['independent_model_collisions']:
        print('COMPONENT',item['reference'],'BASE_MM3',item['base_intersection_mm3'],
              'LID_MM3',item['lid_intersection_mm3'])
    raise SystemExit(0 if data['all_seven_original_model_placements_nominally_clear'] else 2)
