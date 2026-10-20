#!/usr/bin/env python3
"""Independent reload/STEP-intersection/STL-manifold sanity verifier."""
from __future__ import annotations
import argparse,collections,hashlib,json,struct
from pathlib import Path
import cadquery as cq


def _sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()


def _stl_topology(path):
    raw=path.read_bytes()
    if len(raw)<84:raise ValueError('truncated binary STL')
    n=struct.unpack_from('<I',raw,80)[0]
    if len(raw)!=84+50*n or n<8 or n>1_000_000:
        raise ValueError('STL size/triangle count inconsistent')
    edges=collections.Counter();degenerate=0
    for i in range(n):
        xyz=struct.unpack_from('<12f',raw,84+i*50)
        tri=[tuple(round(x,5) for x in xyz[3+3*j:6+3*j]) for j in range(3)]
        if len(set(tri))<3:degenerate+=1
        for j in range(3):edges[tuple(sorted((tri[j],tri[(j+1)%3])))]+=1
    wrong=sum(count!=2 for count in edges.values())
    return {'triangles':n,'edge_count':len(edges),'non_manifold_edges':wrong,
            'degenerate_triangles':degenerate,
            'closed_two_incident_edges_necessary_condition':wrong==0 and degenerate==0}


def check(folder:Path,board_step:Path,source_pcb:Path)->dict:
    report=json.loads((folder/'source_edge_retention_report.json').read_text())
    if report['status']!='generated_collision_screened_edge_retention_candidate':
        raise ValueError('source worker did not produce a collision-screened candidate')
    if report['source_board_sha256'] != _sha(source_pcb):
        raise ValueError('source KiCad PCB hash inconsistent with generated CAD report')
    manifest={entry['filename']:entry for entry in report['generated_artifacts']}
    basefile=folder/'source_edge_capture_base.step';lidfile=folder/'source_edge_capture_lid.step'
    base=cq.importers.importStep(str(basefile));lid=cq.importers.importStep(str(lidfile))
    board=cq.importers.importStep(str(board_step))
    checks={
      'original_board_against_base_mm3':round(float(board.intersect(base).val().Volume()),6),
      'original_board_against_lid_mm3':round(float(board.intersect(lid).val().Volume()),6),
      'base_against_lid_mm3':round(float(base.intersect(lid).val().Volume()),6),
    }
    for name,shape in [('base',base),('lid',lid)]:
        checks[name+'_step_valid']=len(shape.solids().vals())==1 and shape.val().isValid()
        checks[name+'_solid_volume_mm3']=round(shape.val().Volume(),4)
    mesh={name:_stl_topology(folder/(name+'.stl')) for name in
          ('source_edge_capture_base','source_edge_capture_lid')}
    hashes_ok={name:_sha(folder/name)==spec['sha256']
               for name,spec in manifest.items()}
    result={
      'validation_schema':'hs_independent_edge_retention_check.v1',
      'original_board_sha256':report['source_board_sha256'],
      'independent_KiCad_STEP_reexport_sha256':_sha(board_step),
      'worker_original_KiCad_STEP_sha256':report['derived_source_board_step_sha256'],
      'source_board_original_bytes_sha256_match':True,
      'STEP_export_binary_hashes_need_not_match_due_to_exporter_metadata':True,
      'nominal_step_intersections':checks,
      'source_pad_exclusions_mm3':report['geometric_clearance_checks']['corrected_pad_keepout_overlap_mm3'],
      'step_stl_generated_sha256s_verified':hashes_ok,
      'independent_stl_manifold_edge_incidence':mesh,
      'software_geometry_screen_passed':(
          all(checks[k]<=0.02 for k in (
             'original_board_against_base_mm3','original_board_against_lid_mm3','base_against_lid_mm3'))
          and checks['base_step_valid'] and checks['lid_step_valid']
          and all(hashes_ok.values())
          and all(x['closed_two_incident_edges_necessary_condition'] for x in mesh.values())
          and report['geometric_clearance_checks']['corrected_pad_keepout_overlap_mm3']<=0.02),
      'comprehensive_copper_and_populated_component_fit_proven':False,
      'print_mechanical_authority_granted':False,
    }
    if not result['software_geometry_screen_passed']:
        raise ValueError('independent STEP or STL verification failed')
    return result


if __name__=='__main__':
    a=argparse.ArgumentParser()
    a.add_argument('output_dir',type=Path)
    a.add_argument('original_board_step',type=Path)
    a.add_argument('--source-pcb',required=True,type=Path)
    a.add_argument('--out',type=Path)
    opts=a.parse_args()
    report=check(opts.output_dir,opts.original_board_step,opts.source_pcb)
    if opts.out:
        opts.out.parent.mkdir(parents=True,exist_ok=True)
        opts.out.write_text(json.dumps(report,indent=2)+'\n')
    print('INDEPENDENT_CHECK',json.dumps({k:report[k] for k in (
      'software_geometry_screen_passed','source_pad_exclusions_mm3')}) ,flush=True)
    for k,v in report['independent_stl_manifold_edge_incidence'].items():
        print('STL',k,v,flush=True)
