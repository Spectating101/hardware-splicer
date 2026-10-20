import json
from pathlib import Path
import pytest
from scripts.build_x500_dossier import compile_dossier

REFERENCE=json.loads((Path(__file__).resolve().parents[1]/'eval/drone_reference_build/x500_v2.json').read_text())


def sample_html():
    headings=['Payload and Battery Holder','Power Module','Landing Gear','Power','Arms',
              'Propellers','GPS','Pixhawk 6C','Install/Configure PX4','Tuning']
    return ('<main><h1>Holybro X500 V2 + Pixhawk 6C</h1>'+
            ''.join('<h3>'+h+'</h3><ol><li>One step</li></ol>' for h in headings)+'</main>').encode()


def test_compiles_offline_source_sections_and_connection_graph():
    result=compile_dossier(REFERENCE,sample_html())
    assert len(result['source_assembly_sections'])==10
    assert len(result['interfaces'])==9
    assert all(row['listed_step_count']==1 for row in result['source_assembly_sections'])
    assert all(row['status']!='passed' for row in result['verification_gates'])
    assert result['physical_testing_performed'] is False


def test_unrelated_source_rejected():
    with pytest.raises(ValueError,match='wrong source'):
        compile_dossier(REFERENCE,b'<main><h1>Unrelated device</h1></main>')


def test_incomplete_reference_rejected():
    with pytest.raises(ValueError,match='too few'):
        compile_dossier(REFERENCE,b'<main><h1>Holybro X500 V2</h1><h3>Power</h3></main>')
