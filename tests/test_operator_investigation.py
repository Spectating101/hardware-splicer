from hardware_splicer.operator_investigation import investigate_case

CASE={'intake':{'goal':'Assess two unidentified salvaged motors','available_parts':[{'name':'DC motor','type':'dc_motor'}],
                'constraints':{'supply_current_limit_a':1}},
      'engineering_sources':[{'source_id':'guide','source_type':'datasheet','version':'rev-a',
                             'claims':['driver current limit must be respected']}],
      'declared_conflicts':[{'conflict_id':'unknown_motor','claim_a':'stall unknown','claim_b':'driver has finite limit'}]}

def test_multi_step_reads_actual_hs_evidence_and_stays_blocked():
    calls=[]
    def operator(prompt):
        calls.append(prompt)
        if len(calls)==1: return {'action':'inspect','tool':'source_graph'}
        if len(calls)==2:
            assert 'unknown_motor' in prompt and 'guide' in prompt
            return {'action':'inspect','tool':'engineering_checks'}
        assert 'analysis-current-margin' in prompt
        return {'action':'finish','decision':'propose_review','reasoning':'gather missing evidence',
                'next_tests':['measure current'],'measurements_claimed':False}
    result=investigate_case(CASE,operator=operator,max_steps=3)
    assert result['operator_status']=='reviewed'
    assert len(result['inspections'])==2
    assert 'unknown_motor' in result['blocking_conflict_ids']
    assert result['decision']=='hold' and result['physical_authority']=='not_authorized'

def test_injection_tool_name_rejected():
    result=investigate_case(CASE,operator=lambda _: {'action':'inspect','tool':'shell'})
    assert result['operator_status']=='invalid_tool_request'
    assert result['inspections']==[]

def test_repeated_tool_read_rejected():
    result=investigate_case(CASE,operator=lambda _: {'action':'inspect','tool':'source_graph'})
    assert result['operator_status']=='invalid_tool_request'

def test_model_never_confers_release():
    result=investigate_case({'goal':'Review harmless proposed wiring','constraints':{}},
        operator=lambda _:{'action':'finish','decision':'propose_review','reasoning':'plausible',
                           'next_tests':[],'measurements_claimed':False})
    assert result['physical_authority']=='not_authorized'
    assert not result['ready_for_physical_execution']


def test_no_final_review_without_inspection():
    result=investigate_case(CASE,operator=lambda _:{'action':'finish','decision':'hold',
        'reasoning':'insufficient', 'next_tests':[], 'measurements_claimed':False})
    assert result['operator_status']=='missing_required_inspection'
    assert result['decision']=='hold'

def test_operator_failure_after_evidence_preserves_trace_and_holds():
    calls=[]
    def operator(_prompt):
        calls.append(1)
        if len(calls)==1:
            return {'action':'inspect','tool':'source_graph'}
        raise RuntimeError('provider rate limit')
    result=investigate_case(CASE,operator=operator,max_steps=3)
    assert result['operator_status']=='operator_error'
    assert [entry['tool'] for entry in result['inspections']]==['source_graph']
    assert result['decision']=='hold'
    assert not result['ready_for_physical_execution']


def test_premature_finish_can_recover_via_allowed_inspection():
    calls=[]
    def operator(_prompt):
        calls.append(1)
        if len(calls)==1:
            return {'action':'finish','decision':'hold','reasoning':'no need','next_tests':[], 'measurements_claimed':False}
        if len(calls)==2:
            return {'action':'inspect','tool':'engineering_checks'}
        return {'action':'finish','decision':'hold','reasoning':'needs physical data','next_tests':['measure current'],'measurements_claimed':False}
    result=investigate_case(CASE,operator=operator,max_steps=3)
    assert result['operator_status']=='reviewed'
    assert [entry['tool'] for entry in result['inspections']]==['engineering_checks']
