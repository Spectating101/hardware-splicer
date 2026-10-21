#!/usr/bin/env python3
"""Existing open-source Gmsh 3D mesh + scikit-fem linear elasticity on real HS CAD.

Uses original-source KiCad board outline and source-derived exterior screw
locations. Assumed support/load cases are explicit idealizations, not product
or polymer release. scikit-fem performs FE assembly; this is NOT a new solver.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
import gmsh
from shapely.geometry import Polygon
from skfem import MeshTet,Basis,ElementTetP1,ElementVector,asm,condense,solve
from skfem.models.elasticity import lame_parameters,linear_elasticity

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from hardware_splicer.mechanical_fem import solve_linear_tetra_fem


def sha(path:Path)->str:return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def mesh_existing_gmsh(step:Path,mesh_size_mm:float)->dict:
    if not 1.0 <= mesh_size_mm <= 30:raise ValueError('bounded mesh target required')
    gmsh.initialize()
    try:
        gmsh.option.setNumber('General.Terminal',0)
        gmsh.model.add('real-cyberdeck-3d-retention')
        gmsh.option.setString('Geometry.OCCTargetUnit','MM')
        importeds=gmsh.model.occ.importShapes(str(step))
        gmsh.model.occ.synchronize()
        if len(gmsh.model.getEntities(3))!=1:raise ValueError('source CAD must contain exactly one solid')
        gmsh.option.setNumber('Mesh.MeshSizeMin',mesh_size_mm)
        gmsh.option.setNumber('Mesh.MeshSizeMax',mesh_size_mm)
        gmsh.option.setNumber('Mesh.ElementOrder',1)
        gmsh.model.mesh.generate(3)
        tags,xyz,_=gmsh.model.mesh.getNodes()
        types,_,connect=gmsh.model.mesh.getElements(dim=3)
        if len(types)!=1 or int(types[0])!=4:raise ValueError('mesh must be linear tetrahedra')
        tag_ids=np.asarray(tags,dtype=int)
        xyz_mm=np.asarray(xyz,dtype=float).reshape(-1,3)
        raw=np.asarray(connect[0],dtype=int).reshape(-1,4)
        if len(xyz_mm)>20_000 or len(raw)>50_000:
            raise ValueError('do not overrun large-mesh pilot budget')
        ids={int(tag):i for i,tag in enumerate(tag_ids)}
        tetra=np.asarray([[ids[int(t)] for t in e] for e in raw],dtype=int)
        if len(set(tetra.flat))!=len(xyz_mm):
            raise ValueError('mesh contains unused or isolated 3D nodes')
        surface_types,_,surf_raw=gmsh.model.mesh.getElements(dim=2)
        surface=[]
        for typ,flat in zip(surface_types,surf_raw):
            if int(typ)!=2:raise ValueError('3D solid exterior is not all linear triangles')
            for e in np.asarray(flat,dtype=int).reshape(-1,3):
                surface.append([ids[int(t)] for t in e])
        face=np.asarray(surface,dtype=int)
        xyz_m=xyz_mm*1e-3
        tet_xyz=xyz_m[tetra]
        mat=(tet_xyz[:,1:,:]-tet_xyz[:,0:1,:])
        det=np.linalg.det(mat)
        if np.any(~np.isfinite(det)) or np.any(np.abs(det)<1e-17):
            raise ValueError('bad volume element Jacobian')
        volume=float(np.abs(det).sum()/6)
        kernel=float(gmsh.model.occ.getMass(*gmsh.model.getEntities(3)[0]))*1e-9
        err=abs(volume-kernel)/kernel
        if err>.035:raise ValueError('meshed CAD solid volume mismatch >3.5%')
        return {'nodes_m':xyz_m,'elements':tetra,'surface_triangles':face,
            'cad_volume_m3':kernel,'mesh_volume_m3':volume,
            'mesh_volume_error_fraction':err,'mesh_target_mm':mesh_size_mm}
    finally:
        gmsh.finalize()


def make_case(mesh,geometry,case_report,board_step_bbox,part,force):
    xyz_mm=mesh['nodes_m']*1000
    source_outline=[(float(x['x']),-float(x['y'])) for x in geometry['edge_cuts_profile_mm']]
    source_board_polygon=Polygon(source_outline)
    if not source_board_polygon.is_valid or source_board_polygon.area<=0:
        raise ValueError('invalid original KiCad board outline polygon')
    screw=case_report['external_lid_screw_centres_mm']
    if len(screw)!=4:raise ValueError('expected four original-source exterior screws')
    annulus_radius_mm=(1.60,2.10) if part=='lid' else (1.29,1.90)
    fix=[];collars=[]
    for s in screw:
        x,y=float(s['x']),float(s['y'])
        radii=np.hypot(xyz_mm[:,0]-x,xyz_mm[:,1]-y)
        idx=np.flatnonzero((radii>=annulus_radius_mm[0])&(radii<=annulus_radius_mm[1]))
        if len(idx)<6:raise ValueError('lack of nodes around exterior screw collar')
        fix.extend(idx.tolist())
        collars.append({'center_mm':[x,y],'fixed_node_count':len(idx)})
    fix=np.unique(np.asarray(fix,dtype=int))
    if len(fix)>800:raise ValueError('support mask unexpectedly broad')
    z_plane=float(xyz_mm[:,2].min()) if part=='lid' else float(board_step_bbox['zmin_mm'])
    floads=np.zeros(len(xyz_mm))
    active_facets=0;total_area_mm2=0
    for facet in mesh['surface_triangles']:
        coords=xyz_mm[facet]
        if max(abs(coords[:,2]-z_plane))>0.045:continue
        # GEOS source-footprint intersection is geometrically exact within
        # the original tessellated KiCad outline and meshed triangle facets,
        # rather than a mesh-dependent centroid inclusion threshold.
        surface_triangle=Polygon([(float(x),float(y)) for x,y in coords[:,:2]])
        if not surface_triangle.is_valid or surface_triangle.area<=1e-10:continue
        area=float(surface_triangle.intersection(source_board_polygon).area)
        if not area>1e-6:continue
        for index in facet:floads[int(index)]+=area/3
        total_area_mm2+=area;active_facets+=1
    if total_area_mm2<18 or total_area_mm2>350:
        raise ValueError(f'contact lip area could not be resolved ({total_area_mm2} mm2)')
    if any(floads[fix]>0):raise ValueError('loaded node coincides with fixed screw hole')
    contact_ids=np.flatnonzero(floads>0)
    if len(contact_ids)<25:raise ValueError('too few source lip load nodes')
    nodal_z=force*floads/floads.sum()
    return {'fixed_nodes':fix,'loaded_nodes':contact_ids,'loads_z_newtons':nodal_z,
        'fixed_collars':collars,'loaded_facets':active_facets,
        'loaded_surface_mm2':total_area_mm2,'z_load_plane_mm':z_plane,
        'contact_force_z_n':force,'support_mechanics_assumed':True}


def run_skfem(mesh,bc,E_pa,nu):
    nodes=mesh['nodes_m'];tetra=mesh['elements']
    gm=MeshTet(nodes.T,tetra.T)
    basis=Basis(gm,ElementVector(ElementTetP1()))
    lam,mu=lame_parameters(E_pa,nu)
    K=asm(linear_elasticity(lam,mu),basis)
    F=np.zeros(basis.N)
    F[basis.nodal_dofs[2,:]]+=bc['loads_z_newtons']
    D=np.unique(basis.nodal_dofs[:,bc['fixed_nodes']].ravel())
    U=solve(*condense(K,F,D=D))
    nodal=U[basis.nodal_dofs].T
    max_deflection=float(np.linalg.norm(nodal,axis=1).max())
    xyz=nodes[tetra]
    aff=np.concatenate((np.ones((len(tetra),4,1)),xyz),axis=2)
    grad=np.linalg.inv(aff)[:,1:,:].transpose(0,2,1) # (tet, 4 nodes, xyz)
    u=nodal[tetra]  # (tet,4,3)
    du=np.einsum('eij,eik->ejk',u,grad) # (tet,displacement_comp,xyz_grad)
    epsilon=.5*(du+np.swapaxes(du,1,2))
    stress=2*mu*epsilon+lam*np.trace(epsilon,axis1=1,axis2=2)[:,None,None]*np.eye(3)
    normal=np.diagonal(stress,axis1=1,axis2=2)
    sx,sy,sz=normal[:,0],normal[:,1],normal[:,2]
    von=np.sqrt(.5*((sx-sy)**2+(sy-sz)**2+(sz-sx)**2)+
                3*(stress[:,0,1]**2+stress[:,1,2]**2+stress[:,0,2]**2))
    res=K@U-F
    reaction=np.sum(res[basis.nodal_dofs[:,bc['fixed_nodes']]],axis=1)
    reaction_residual=float(np.linalg.norm(reaction+np.array([0,0,bc['contact_force_z_n']])))
    if reaction_residual>max(1,abs(bc['contact_force_z_n']))*1e-5:
        raise ValueError('FEM equilibrium violation')
    return {'solver':'scikit-fem v11 open-source P1 elastic tetra',
      'max_displacement_mm':max_deflection*1000,
      'max_von_mises_mpa':float(von.max())/1e6,
      'peak_stress_at_mm':(xyz[von.argmax()].mean(axis=0)*1000).tolist(),
      'force_equilibrium_residual_n':reaction_residual,
      'force_fixed_nodes':int(len(bc['fixed_nodes'])),
      'tetrahedral_count':len(tetra),
      'mesh_node_count':len(nodes),
      'boundary_area_mm2':bc['loaded_surface_mm2'],
      'load_patch_intersection_library':'Shapely 2.1.2 GEOS',
      'boundary_facet_count':bc['loaded_facets']}


def compare_existing_hs(mesh,bc,E,nu,reference):
    if len(mesh['nodes_m'])>2000 or len(mesh['elements'])>5000:return {'status':'outside_HS_bounded_budget'}
    req={'nodes_m':mesh['nodes_m'].tolist(),'elements':mesh['elements'].tolist(),
         'constraints':[{'node':int(i),'axes':[True,True,True]} for i in bc['fixed_nodes']],
         'loads_n':[{'node':int(i),'force_n':[0,0,float(bc['loads_z_newtons'][i])]}
               for i in bc['loaded_nodes']],
         'youngs_modulus_pa':E,'poisson_ratio':nu,'units':'SI'}
    hs=solve_linear_tetra_fem(req)
    err=abs(hs['max_displacement_m']*1000-reference['max_displacement_mm'])/reference['max_displacement_mm']
    s_err=abs(hs['max_von_mises_pa']/1e6-reference['max_von_mises_mpa'])/reference['max_von_mises_mpa']
    return {'status':'same_tetra_boundary_and_material_comparison',
         'relative_max_displacement_difference':err,
         'relative_max_von_mises_difference':s_err,
         'hs_equilibrium_residual_n':hs['force_equilibrium_residual_n'],
         'agrees_within_1_percent':err<.01 and s_err<.01}


def run_part(part,case_dir,geometry_path,original_board_step,*,sizes,force,E,nu):
    if (len(sizes)<2 or len(sizes)>10 or any(not math.isfinite(x) or not 1<=x<=30 for x in sizes) or
        any(a<=b for a,b in zip(sizes,sizes[1:]))):
        raise ValueError('mesh sizes must have 2–10 strictly decreasing bounded values')
    if not (0.1<=abs(force)<=30 and 5e8<=E<=10e9 and 0<=nu<=.45):
        raise ValueError('hypothetical force/material assumptions outside declared bounds')
    case_dir=Path(case_dir);step=case_dir/f'source_edge_capture_{part}.step'
    report=json.loads((case_dir/'source_edge_retention_report.json').read_text())
    geometry=json.loads(Path(geometry_path).read_text())
    if geometry['source_sha256']!=report['source_board_sha256']:
        raise ValueError('source KiCad provenance mismatch')
    expected={x['filename']:x['sha256'] for x in report['generated_artifacts']}
    if expected.get(step.name)!=sha(step):raise ValueError('source CAD STEP bytes changed')
    import cadquery as cq
    box=cq.importers.importStep(str(original_board_step)).val().BoundingBox()
    board_bbox={'zmin_mm':box.zmin,'zmax_mm':box.zmax}
    readings=[]
    for sz in sizes:
        mesh=mesh_existing_gmsh(step,sz)
        bc=make_case(mesh,geometry,report,board_bbox,part,force)
        result=run_skfem(mesh,bc,E,nu)
        result.update({'target_mm':sz,'mesh_volume_error_fraction':mesh['mesh_volume_error_fraction'],
                       'hs_bounded_comparison':compare_existing_hs(mesh,bc,E,nu,result)})
        readings.append(result)
        print('PART',part,'MESH',sz,'N',result['mesh_node_count'],
              'TETS',result['tetrahedral_count'],'AREA',round(result['boundary_area_mm2'],3),
              'DISP',round(result['max_displacement_mm'],6),
              'STRESS',round(result['max_von_mises_mpa'],6),
              'HS_XCHECK',result['hs_bounded_comparison']['status'],flush=True)
    changes=[]
    for coarse,fine in zip(readings,readings[1:]):
        changes.append({'coarse_target_mm':coarse['target_mm'],'fine_target_mm':fine['target_mm'],
          'tetra_count_growth':fine['tetrahedral_count']/coarse['tetrahedral_count'],
          'loaded_area_relative_change':abs(fine['boundary_area_mm2']-coarse['boundary_area_mm2'])/max(fine['boundary_area_mm2'],coarse['boundary_area_mm2']),
          'max_disp_relative_change':abs(fine['max_displacement_mm']-coarse['max_displacement_mm'])/max(fine['max_displacement_mm'],coarse['max_displacement_mm']),
          'peak_von_mises_relative_change':abs(fine['max_von_mises_mpa']-coarse['max_von_mises_mpa'])/max(fine['max_von_mises_mpa'],coarse['max_von_mises_mpa'])})
    stable=bool(changes) and all(x['tetra_count_growth']>=1.1 and
                                  x['loaded_area_relative_change']<=.03 and
                                  x['max_disp_relative_change']<=.05 and
                                  x['peak_von_mises_relative_change']<=.1 for x in changes)
    return {'part':part,'source_step_sha256':sha(step),'source_pcb_sha256':geometry['source_sha256'],
        'mesh_sizes_mm':sizes,'case_idealizations':{
          'material_E_pa':E,'poisson':nu,'hypothetical_uniform_board_force_z_n':force,
          'idealized_fixed_screw_collars':True,'no_bolt_preload_friction_contacts':True,
          'unqualified_polymer_print_orientation':True},
        'meshes':readings,'changes':changes,
        'sufficient_mesh_convergence_demonstrated':stable,
        'physical_material_strength_verified':False,
        'fabrication_authorized':False,
        'status':'hypothetical_software_FEM_screen_only'}


if __name__=='__main__':
    ar=argparse.ArgumentParser()
    ar.add_argument('candidate_dir',type=Path)
    ar.add_argument('original_board_geometry',type=Path)
    ar.add_argument('original_board_step',type=Path)
    ar.add_argument('--parts',nargs='+',choices=['base','lid'],default=['base','lid'])
    ar.add_argument('--sizes-mm',nargs='+',type=float,default=[10,6,4])
    ar.add_argument('--force-n',type=float,default=1.0)
    ar.add_argument('--youngs-pa',type=float,default=1.5e9)
    ar.add_argument('--poisson',type=float,default=.35)
    ar.add_argument('--out',type=Path,required=True)
    args=ar.parse_args()
    results=[]
    for part in args.parts:
        results.append(run_part(part,args.candidate_dir,args.original_board_geometry,args.original_board_step,
                  sizes=args.sizes_mm,force=args.force_n,E=args.youngs_pa,nu=args.poisson))
    report={'schema':'hardware_splicer.open_source_cyberdeck_case_FEM.v1',
       'external_upstream_planar_geometry':'https://github.com/shapely/shapely',
       'external_upstream_mesh':'https://gmsh.info','external_upstream_fem':'https://github.com/kinnala/scikit-fem',
       'no_original_FEM_solver_implemented':True,
       'case_results':results,'manufactured_device_tested':False,'release_authorized':False}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+'\n')
    print('REPORT',args.out,flush=True)
