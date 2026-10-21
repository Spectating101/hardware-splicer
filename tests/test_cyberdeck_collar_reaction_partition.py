"""Require all idealized screw reactions to reconcile with global equilibrium."""
import json
from pathlib import Path

P=Path(__file__).resolve().parents[1]/'projects/cyberdeck_structural_validation_20261021'


def test_all_four_collar_reactions_partition_force_for_both_parts():
    for part,size in [('LID',4),('BASE',10)]:
        d=json.loads((P/f'P2_{part}_COLLAR_REACTIONS_{size}.json').read_text())
        reactions=d['fixed_z_reaction_by_collar_n']
        assert len(reactions)==4
        assert all(abs(r)>1e-5 for r in reactions)
        assert abs(sum(reactions)+d['applied_total_force_z_n'])<1e-8
        assert d['reaction_z_balance_error_n']<1e-8
        assert d['support_mode']=='normal_only'
        assert d['release_authorized'] is False


def test_idealized_collar_load_distribution_is_not_identical():
    d=json.loads((P/'P2_LID_COLLAR_REACTIONS_4.json').read_text())
    magnitudes=[abs(v) for v in d['fixed_z_reaction_by_collar_n']]
    assert max(magnitudes)-min(magnitudes)>.1
