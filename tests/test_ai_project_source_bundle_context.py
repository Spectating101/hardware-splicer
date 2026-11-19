from hardware_splicer.ai_project_orchestrator import build_ai_project_context


def test_structured_bundled_netlist_visible_without_raw_and_authority():
    snapshot={'engineeringSourceBundleRuns':[{
      'schema_version':'hardware_splicer.project_source_bundle.v1',
      'source_set_sha256':'sha256:aabb',
      'input_sources':{'device.kicad_sch':{'sha256':'sha256:0123','raw':'NOT-PUBLIC'}},
      'software_checks':{'drc':{'status':'findings_present','rule_finding_count':16,
                               'rule_findings_by_type':{'lib_footprint_issues':15}}},
      'netlist':{'status':'exported_project_netlist','component_count':1,'net_count':1,
                 'components':[{'ref':'J1','value':'Raspberry Pi pin header'}],
                 'nets':[{'name':'+5V','nodes':[{'ref':'J1','pin':'1'}]}]},
      'geometry':{'enclosure.stl':{'axis_span':[20,30,4],'units':'unresolved'}},
      'release_authorized':True,
    }]}
    context=build_ai_project_context('real-cyberdeck',6,snapshot,mission='Design a Linux cyberdeck')
    bundles=context['project_source_bundle_checks']
    assert bundles[0]['netlist']['components'][0]['ref']=='J1'
    assert bundles[0]['checks']['drc']['rule_finding_count']==16
    assert bundles[0]['netlist']['nets'][0]['nodes'][0]['pin']=='1'
    assert bundles[0]['design_or_physical_authority_raised'] is False
    assert 'NOT-PUBLIC' not in str(context)
    assert 'release_authorized' not in str(bundles)
    assert context['context_policy']['release_authorized'] is False
