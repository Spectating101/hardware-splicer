#!/usr/bin/env python3
"""Independent P2 tetra FEM regression on unmodified source-derived CAD.
Uses preexisting open-source Gmsh, GEOS/Shapely and scikit-fem, no new physics solver.
Force, material and fully fixed screw-ring assumptions remain hypothetical.
"""
import sys,time,json,argparse,hashlib,math
from pathlib import Path
import numpy as np
import scipy
from shapely.geometry import Polygon
from skfem import MeshTet,Basis,ElementVector,ElementTetP2,asm,solve,condense
from skfem.models.elasticity import lame_parameters,linear_elasticity
from screen_cyberdeck_open_source_fem import mesh_existing_gmsh
from hs_exact_p2_traction import exact_planar_traction

def inspect(part,size,case_dir,outline,original_board_step,*, E=1.5e9,nu=.35,force_magnitude_n=1.0):
    begin=time.monotonic()
    if part not in ('lid','base') or not all(math.isfinite(x) for x in (size,E,nu,force_magnitude_n)):
        raise ValueError('unsupported part or nonfinite FEM input')
    if not (1.<=size<=30. and 5e8<=E<=10e9 and 0<=nu<=.45 and .1<=force_magnitude_n<=30):
        raise ValueError('FEM settings outside declared hypothesis bounds')
    cad=Path(case_dir)/('source_edge_capture_'+part+'.step')
    report=json.loads((Path(case_dir)/'source_edge_retention_report.json').read_text())
    expected={v['filename']:v['sha256'] for v in report['generated_artifacts']}
    if expected[cad.name] != 'sha256:'+hashlib.sha256(cad.read_bytes()).hexdigest():
        raise ValueError('source STEP hash differs from original report')
    if report['source_board_sha256'] != outline['source_sha256']:
        raise ValueError('original PCB source hash differs')
    gm=mesh_existing_gmsh(cad,size)
    mesh=MeshTet(gm['nodes_m'].T,gm['elements'].T)
    xyz=mesh.p
    surface=mesh.facets
    bottom=mesh.boundary_facets()
    import cadquery as cq
    board_box=cq.importers.importStep(str(original_board_step)).val().BoundingBox()
    zplane=float(xyz[2].min()) if part=='lid' else float(board_box.zmin)*0.001
    # Reject unrelated/misregistered external board STEP input. The STEP
    # exporter hash may vary; the bounding XY coordinates still must agree
    # with the hash-verified original KiCad board Edge.Cuts profile.
    points=np.asarray([(v['x'],-v['y']) for v in outline['edge_cuts_profile_mm']])
    if not (abs(board_box.xmin-points[:,0].min())<.15 and
            abs(board_box.xmax-points[:,0].max())<.15 and
            abs(board_box.ymin-points[:,1].min())<.15 and
            abs(board_box.ymax-points[:,1].max())<.15):
        raise ValueError('original board-only STEP bounds do not match source KiCad profile')
    requested_load_z=force_magnitude_n if part=='lid' else -force_magnitude_n
    planar=bottom[np.max(np.abs(xyz[2,surface[:,bottom]]-zplane),axis=0)<.00005]
    poly=Polygon([(v['x'],-v['y']) for v in outline['edge_cuts_profile_mm']])
    element=ElementVector(ElementTetP2())
    basis=Basis(mesh,element,intorder=4)
    F,contact=exact_planar_traction(basis,poly,zplane_m=zplane,
                                  force_z_newtons=requested_load_z,degree=2)
    quad_area=contact['clipped_lip_area_mm2']*1e-6
    screw=report['external_lid_screw_centres_mm']
    radius=(1.55,2.10) if part=='lid' else (1.25,1.90)
    keep=[];counts=[]
    for v in screw:
        radial=np.hypot(basis.doflocs[0]*1000-v['x'],basis.doflocs[1]*1000-v['y'])
        ring=np.flatnonzero((radial>=radius[0])&(radial<=radius[1]))
        if len(ring)<12:raise ValueError('quadratic screw collar underresolved')
        counts.append(len(ring));keep.extend(ring.tolist())
    D=np.unique(keep)
    if np.max(np.abs(F[D]))>1e-7:raise ValueError('quadratic applied contact load intersects Dirichlet screw collar')
    lam,mu=lame_parameters(E,nu)
    t=time.monotonic()
    K=asm(linear_elasticity(lam,mu),basis)
    print('ASSEMBLED',part,size,'dofs',basis.N,'nnz',K.nnz,'sec',round(time.monotonic()-t,2),flush=True)
    t=time.monotonic()
    U=solve(*condense(K,F,D=D))
    print('SOLVED',part,size,'sec',round(time.monotonic()-t,2),flush=True)
    dofs=np.hstack((basis.nodal_dofs,basis.edge_dofs))
    nodal_disp=np.linalg.norm(U[dofs],axis=0)
    grad=basis.interpolate(U).grad
    strain=.5*(grad+grad.swapaxes(0,1))
    stress=2*mu*strain+lam*np.einsum('iieq,ij->ijeq',strain,np.eye(3))
    sx,sy,sz=stress[0,0],stress[1,1],stress[2,2]
    vm=np.sqrt(.5*((sx-sy)**2+(sy-sz)**2+(sz-sx)**2)+3*(stress[0,1]**2+stress[0,2]**2+stress[1,2]**2))
    vm_rms=float(np.sqrt(np.sum(vm*vm*basis.dx)/np.sum(basis.dx)))
    vm_q95=float(np.quantile(vm,0.95))
    reactions=(K@U-F)[D]
    z_dofs=set(np.hstack((basis.nodal_dofs[2],basis.edge_dofs[2])).tolist())
    reaction_z=sum(reaction for dof,reaction in zip(D,reactions) if dof in z_dofs)
    res=abs(float(reaction_z)+requested_load_z)
    if res>1e-5:raise ValueError('reaction does not balance applied force')
    return {'part':part,'mesh_size_mm':size,'num_elements':len(gm['elements']),
            'scalar_polynomial_degree':2,'displacement_dof_count':int(basis.N),
            'integration_patch_area_mm2':quad_area*1e6,
            'screw_clamped_DOF_count':len(D),
            'source_derived_board_seating_z_mm':board_box.zmin,
            'modelled_contact_plane_z_mm':zplane*1000,
            'applied_total_force_z_n':requested_load_z,'screw_collar_dof_counts':counts,
            'displacement_mm':float(nodal_disp.max())*1000,
            'peak_von_mises_mpa':float(vm.max())/1e6,
            'volume_integrated_von_mises_rms_mpa':vm_rms/1e6,
            'quadrature_point_95_percentile_von_mises_mpa':vm_q95/1e6,
            'root_mean_square_displacement_mm':float(np.sqrt(np.mean(nodal_disp**2)))*1000,
            'compliance_n_m':float(F@U),
            'strain_energy_j':.5*float(F@U),
            'source_lid_or_base_step_sha256':'sha256:'+hashlib.sha256(cad.read_bytes()).hexdigest(),
            'material_E_pa_assumed':E,'poisson_ratio_assumed':nu,
            'reaction_z_balance_error_n':res,'hypothetical_force_and_material':True,
            'release_authorized':False,'elapsed_s':round(time.monotonic()-begin,2)}

if __name__=='__main__':
    a=argparse.ArgumentParser(description='Source-validated quadratic CAD/FEM, no physical release')
    a.add_argument('case_dir',type=Path)
    a.add_argument('source_interface_json',type=Path)
    a.add_argument('original_board_step',type=Path)
    a.add_argument('--part',choices=['lid','base'],required=True)
    a.add_argument('--sizes',type=float,nargs='+',default=[10,8,6])
    a.add_argument('--force-n',type=float,default=1.0)
    a.add_argument('--E-pa',type=float,default=1.5e9)
    a.add_argument('--poisson',type=float,default=.35)
    a.add_argument('--out',type=Path,required=True)
    o=a.parse_args()
    if not 2<=len(o.sizes)<=9 or any(not a>b for a,b in zip(o.sizes,o.sizes[1:])):
        raise ValueError('provide 2-9 strictly decreasing mesh sizes')
    folder=o.case_dir
    geometry=json.loads(o.source_interface_json.read_text())
    rows=[]
    for size in o.sizes:
        row=inspect(o.part,size,folder,geometry,o.original_board_step,
                    E=o.E_pa,nu=o.poisson,force_magnitude_n=o.force_n)
        rows.append(row)
        print('QUADRATIC_FEM',o.part,size,'tetra',row['num_elements'],
              'displacement_mm',round(row['displacement_mm'],7),
              'peak_mpa',round(row['peak_von_mises_mpa'],6),flush=True)
    comparisons=[]
    for a,b in zip(rows,rows[1:]):
        relative=lambda name: abs(a[name]-b[name])/max(abs(a[name]),abs(b[name]),1e-18)
        comparisons.append({'coarse_mm':a['mesh_size_mm'],'fine_mm':b['mesh_size_mm'],
                            'tetra_growth':b['num_elements']/a['num_elements'],
                            'maximum_displacement_change':relative('displacement_mm'),
                            'rms_volume_stress_change':relative('volume_integrated_von_mises_rms_mpa'),
                            'local_peak_stress_change':relative('peak_von_mises_mpa'),
                            'compliance_change':relative('compliance_n_m')})
    deformation_stable=all(c['tetra_growth']>=1.1 and
                           c['maximum_displacement_change']<=.035 and
                           c['compliance_change']<=.035 and
                           c['rms_volume_stress_change']<=.035 for c in comparisons)
    peak_stable=all(c['local_peak_stress_change']<=.05 for c in comparisons)
    payload={
       'schema':'hardware_splicer.quadratic_structural_screen.v1',
       'part':o.part,'original_kicad_pcb_sha256':geometry['source_sha256'],
       'original_board_step_sha256':'sha256:'+hashlib.sha256(o.original_board_step.read_bytes()).hexdigest(),
       'cad_step_sha256':rows[0]['source_lid_or_base_step_sha256'],
       'original_board_interface_z_mm':rows[0]['source_derived_board_seating_z_mm'],
       'applied_force_z_n':rows[0]['applied_total_force_z_n'],
       'hypothetical_force_and_material':True,
       'implemented_with_existing': ['Gmsh','scikit-fem','Shapely/GEOS'],
       'new_general_purpose_FEM_solver_written':False,
       'quadratic_P2_surface_exact_integration':True,
       'mesh_results':rows,'mesh_comparisons':comparisons,
       'global_elastic_response_stable_in_tested_window':deformation_stable,
       'local_peak_stress_stable_in_tested_window':peak_stable,
       'single_favorable_refinement_window_is_not_release_evidence':True,
       'real_fastener_preload_modelled':False,
       'nonlinear_contact_modelled':False,
       'print_layer_anisotropy_modelled':False,
       'structural_material_strength_verified':False,
       'full_product_assembly_3d_fit_verified':False,
       'fabrication_authorized':False,
       'operational_safety_verified':False,
    }
    o.out.parent.mkdir(parents=True,exist_ok=True)
    o.out.write_text(json.dumps(payload,indent=2)+'\n')
    print('WINDOW',payload['global_elastic_response_stable_in_tested_window'],
          'LOCAL_STRESS',payload['local_peak_stress_stable_in_tested_window'],
          'FABRICATION',payload['fabrication_authorized'])
