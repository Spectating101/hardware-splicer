from hardware_splicer.electromechanical_fit import screen_board_enclosure_fit

def scenario(height=5, x=0, layer='F.Cu'):
    placement={'source_mode':'kicad_pcb_geometry','board':{'dimensions_mm':{'w':40,'d':20,'t':1.6}},'components':[{'ref':'J1','center_xy_mm':[x,0],'size_xyz_mm':[8,6,height],'layer':layer,'rotation_deg':0}]}
    assembly={'enclosure':{'inner_dimensions_mm':{'w':50,'d':30,'h':15},'floor_mm':2},'placements':{'pcb':{'origin_xyz_mm':[0,0,6]}}}
    return placement,assembly

def test_board_and_connector_fit_clear_is_still_unverified():
    p,a=scenario()
    out=screen_board_enclosure_fit(p,a)
    assert out['status']=='envelope_screen_clear_unverified'
    assert out['exact_3d_collision_verified'] is False
    assert out['fabrication_authorized'] is False

def test_tall_connector_hits_enclosure_lid():
    p,a=scenario(height=14)
    out=screen_board_enclosure_fit(p,a)
    assert out['status']=='envelope_collision_detected'
    assert any(r['ref']=='J1' and r['axis']=='z_upper' for r in out['checks'] if r['status']=='block')

def test_outboard_component_hits_wall():
    p,a=scenario(x=24)
    out=screen_board_enclosure_fit(p,a)
    assert any(r['ref']=='J1' and r['axis']=='x' for r in out['checks'] if r['status']=='block')

def test_backside_part_hits_floor():
    p,a=scenario(height=6,layer='B.Cu')
    out=screen_board_enclosure_fit(p,a)
    assert any(r['ref']=='J1' and r['axis']=='z_lower' for r in out['checks'] if r['status']=='block')
