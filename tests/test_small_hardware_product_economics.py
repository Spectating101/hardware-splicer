"""Physical product BOM economics: no invented orders or favorable pricing."""
from __future__ import annotations
import json
from copy import deepcopy
from pathlib import Path
import pytest
from scripts.evaluate_small_hardware_product_economics import compute_scenarios
ROOT=Path(__file__).resolve().parents[1]
SPEC=json.loads((ROOT/'examples/procurement/taiwan_small_hardware_products_20261020.json').read_text())

def test_three_product_costs_have_sources_and_no_commercial_authorization():
  data=compute_scenarios(SPEC)
  assert len(data['products'])==3
  assert not data['finished_goods_ever_physically_built']
  assert not data['unit_economics_have_observed_sales']
  assert not data['seller_prices_are_checkout_verified']
  assert all(p['sale_price_hypothesis_twd']>0 and p['printed_mass_assumption_grams']>0 for p in data['products'])
  assert all(not p['physical_sample_built'] and not p['actual_customer_demand_verified'] for p in data['products'])

def test_outsourcing_replaces_raw_filament_cost_not_double_counts_it():
  r=compute_scenarios(SPEC)['products'][0]
  assert r['self_print']['printed_piece_cost_twd']==round(180*0.554+60,2)
  assert r['outsource']['printed_piece_cost_twd']==round(180*1.4,2)
  assert r['outsource_higher_quote_sensitivity']['printed_piece_cost_twd']==900
  assert r['outsource_higher_quote_sensitivity']['contribution_margin_fraction']<0

def test_arm_expensive_outsourcing_negative_but_test_utility_still_valid():
  r=compute_scenarios(SPEC)['products'][2]
  assert r['outsource_higher_quote_sensitivity']['contribution_margin_fraction']<0
  assert r['outsource']['contribution_margin_fraction']<0.20
  assert r['self_print']['contribution_margin_fraction']>r['outsource']['contribution_margin_fraction']

def test_unit_selling_fee_is_fraction_of_list_price():
  r=compute_scenarios(SPEC)['products'][0]
  assert r['selling_fee_assumed_twd']==119
  assert r['outsource']['unit_contribution_before_fixed_overhead_and_taxes_twd'] <1190
  assert r['outsource']['list_price_for_20pct_contribution_twd']>0

def test_missing_part_is_not_silently_estimated():
  bad=deepcopy(SPEC)
  bad['candidates'][0]['parts'][0]['id']='invented_motor_supplier'
  with pytest.raises(KeyError):
    compute_scenarios(bad)

@pytest.mark.parametrize('key,value',[
  ('platform_fee_assumption_fraction',-0.01),
  ('platform_fee_assumption_fraction',1.0),
  ('labor_benchmark_twd_hour',float('nan')),
])
def test_invalid_economics_rejected(key,value):
  bad=deepcopy(SPEC)
  bad[key]=value
  with pytest.raises(ValueError):
    compute_scenarios(bad)

def test_positive_revenue_remains_unobserved():
  result=compute_scenarios(SPEC)
  assert result['customer_revenue_realized_twd']==0
  assert not result['marketing_conversion_rate_known']
  assert not result['design_development_hours_amortized']
  assert not result['printer_fixed_cost_included']

def test_new_nonmatching_authority_marker_is_not_accepted():
  bad=deepcopy(SPEC)
  bad['pricing_authority']='FIRM_CHECKOUT_RECEIPT'
  with pytest.raises(ValueError,match='checkout authority'):
    compute_scenarios(bad)
