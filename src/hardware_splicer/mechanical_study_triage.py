"""Fail-closed evidence triage for structural screening; not a physics solver."""
import math


def assess_structural_study(study):
    if study.get('schema') != 'hardware_splicer.quadratic_structural_screen.v1':
        raise ValueError('unsupported structural evidence')
    rows = study.get('mesh_results')
    if not isinstance(rows, list) or len(rows)<2:
        raise ValueError('insufficient mesh readings')
    if any(not isinstance(study.get(k),str) or not study[k].startswith('sha256:')
           for k in ('original_kicad_pcb_sha256','cad_step_sha256')):
        raise ValueError('source provenance absent')
    fields=('mesh_size_mm','num_elements','displacement_mm','peak_von_mises_mpa','volume_integrated_von_mises_rms_mpa')
    for r in rows:
        if any(not isinstance(r.get(k),(int,float)) or not math.isfinite(r[k]) or r[k]<=0 for k in fields):
            raise ValueError('invalid numerical readings')
        residual=r.get('reaction_z_balance_error_n')
        if not isinstance(residual,(int,float)) or not math.isfinite(residual) or not 0<=residual<=1e-5:
            raise ValueError('equilibrium unverified')
    if study.get('fabrication_authorized') is True:
        raise ValueError('simulation cannot authorize fabrication')
    comparisons=[]
    for a,b in zip(rows,rows[1:]):
        if a['mesh_size_mm']<=b['mesh_size_mm']:
            raise ValueError('invalid mesh refinement order')
        rel=lambda k:abs(b[k]-a[k])/max(abs(a[k]),abs(b[k]),1e-18)
        comparisons.append({'growth':b['num_elements']/a['num_elements'],
                            'displacement_change':rel('displacement_mm'),
                            'peak_stress_change':rel('peak_von_mises_mpa'),
                            'rms_stress_change':rel('volume_integrated_von_mises_rms_mpa')})
    blockers=[]
    if any(c['growth']<1.1 for c in comparisons):blockers.append('insufficient_element_growth')
    if any(c['displacement_change']>.035 for c in comparisons):blockers.append('displacement_unstable')
    if any(c['peak_stress_change']>.05 for c in comparisons):blockers.append('peak_stress_unstable')
    if any(c['rms_stress_change']>.035 for c in comparisons):blockers.append('rms_stress_unstable')
    if not study.get('structural_material_strength_verified'):blockers.append('material_unverified')
    if not study.get('full_product_assembly_3d_fit_verified'):blockers.append('assembly_fit_unverified')
    if not study.get('nonlinear_contact_modelled') or not study.get('real_fastener_preload_modelled'):
        blockers.append('contact_unvalidated')
    return {'schema':'hardware_splicer.mechanical_study_triage.v1','part':study.get('part'),
            'cad_step_sha256':study['cad_step_sha256'],'comparisons':comparisons,
            'blockers':blockers,'next_actions':[
                'extend_mesh_study' if any(x in blockers for x in ('insufficient_element_growth','displacement_unstable','peak_stress_unstable','rms_stress_unstable')) else 'verify_boundary_and_material_assumptions',
                'obtain_material_and_assembly_evidence'],
            'fabrication_authorized':False}
