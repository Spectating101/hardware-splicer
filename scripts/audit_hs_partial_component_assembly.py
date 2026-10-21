#!/usr/bin/env python3
"""Second-implementation CAD reimport checks against original KiCad parts.

Only identifies where verified original model geometry intersects candidate
case geometry. Without all populated parts and connector cables there is no
whole-device fit claim. Deliberately independent of edge-retention worker.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import cadquery as cq


def sha(path:Path)->str:
    return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def audit(case:Path,models:Path,original_board:Path)->dict:
    report=json.loads((case/'source_edge_retention_report.json').read_text())
    expected=report['component_model_clearance']
    if expected['resolved_component_models']!=7 or expected['full_source_3d_coverage']:
        raise ValueError('cannot silently change the partial original 3D model coverage')
    base=cq.importers.importStep(str(case/'source_edge_capture_base.step'))
    lid=cq.importers.importStep(str(case/'source_edge_capture_lid.step'))
    board=cq.importers.importStep(str(original_board))
    board_box=board.val().BoundingBox()
    evidence=[]
    for row in expected['component_references_screened']:
        reference=row['reference']
        file=models/(reference+'.step')
        if not file.is_file():
            raise ValueError('missing KiCad original model occurrence '+reference)
        solids=cq.importers.importStep(str(file)).solids().vals()
        if len(solids)!=2:raise ValueError('original component STEP cannot isolate one component')
        board_like=[i for i,v in enumerate(solids) if abs(v.BoundingBox().xlen-board_box.xlen)<.08 and abs(v.BoundingBox().ylen-board_box.ylen)<.08 and abs(v.BoundingBox().zlen-board_box.zlen)<.08]
        if len(board_like)!=1:raise ValueError('independent component export board frame mismatch')
        component=cq.Workplane('XY').newObject([solids[1-board_like[0]]])
        base_overlap=round(base.intersect(component).val().Volume(),5)
        lid_overlap=round(lid.intersect(component).val().Volume(),5)
        evidence.append({'reference':reference,'component_step_sha256':sha(file),
                         'base_intersection_mm3':base_overlap,'lid_intersection_mm3':lid_overlap,
                         'both_halves_nominally_clear':base_overlap<=.02 and lid_overlap<=.02})
    reconstructed={e['reference'] for e in evidence}
    if reconstructed!={e['reference'] for e in expected['component_references_screened']}:
        raise ValueError('source component 3D reference set changed')
    all_clear=all(e['both_halves_nominally_clear'] for e in evidence)
    result={
      'schema':'hs.independent_partial_3d_clearance.v1',
      'cad_case_step_sha256s':{
        'base':sha(case/'source_edge_capture_base.step'),
        'lid':sha(case/'source_edge_capture_lid.step')},
      'original_kicad_reexport_board_sha256':sha(original_board),
      'publisher_3d_reference_coverage':{'modelled':7,'expected_models':11,'no_3d_model':15},
      'independent_model_collisions':evidence,
      'all_seven_original_model_placements_nominally_clear':all_clear,
      'unresolved_model_references':[x['reference'] for x in expected['unresolved_component_fits']],
      'untested_unmodelled_footprints':expected['footprints_without_original_source_model'],
      'other_assembly_and_mating_clearance_verified':False,
      'print_or_fabrication_authorized':False,
    }
    if not all_clear:raise ValueError('a source model remains in collision')
    return result


if __name__=='__main__':
    a=argparse.ArgumentParser()
    a.add_argument('candidate_dir',type=Path)
    a.add_argument('original_component_steps_dir',type=Path)
    a.add_argument('original_board_only_step',type=Path)
    a.add_argument('--out',type=Path,required=True)
    args=a.parse_args()
    result=audit(args.candidate_dir,args.original_component_steps_dir,args.original_board_only_step)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print('INDEPENDENT_MODEL_CHECK',len(result['independent_model_collisions']),
          'nominal clearance',result['all_seven_original_model_placements_nominally_clear'],
          'FULL_FIT',result['other_assembly_and_mating_clearance_verified'])
