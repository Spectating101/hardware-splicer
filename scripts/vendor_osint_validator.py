# -*- coding: utf-8 -*-
import sys
import os
import asyncio
import json

# Dynamic Pathing to connect the Fleet
# Circuit-AI/scripts -> Root -> OverSight-OSINT
fleet_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../OverSight-OSINT/backend'))
core_path = os.path.join(fleet_root, 'core')

sys.path.append(fleet_root)
sys.path.append(core_path)

try:
    from osint_engine import OSINTEngine
except ImportError:
    print('CRITICAL: Could not load Intelligence Engine from Fleet.')
    sys.exit(1)

async def validate_supply_chain():
    print('--- 🤖 Circuit-AI: Vendor Integrity Protocol 🤖 ---')
    
    # Scenario: Vision AI identified these logos on a PCB
    identified_vendors = ['Hikvision', 'Espressif Systems', 'Texas Instruments']
    
    engine = OSINTEngine()
    
    for vendor in identified_vendors:
        print(f'\n[Scanning Vendor]: {vendor}...')
        report = await engine.investigate(vendor)
        
        # Extract Intelligence
        sanctions = report['risk_profile']['sanctions']
        dev_footprint = len(report['risk_profile']['oss_footprint']['developer_profiles'])
        
        # Decision Logic (The "Contribution")
        status = '✅ APPROVED' 
        if sanctions['is_flagged']:
            status = '⛔ BLOCKED (Sanctioned Entity)'
        elif dev_footprint == 0:
            status = '⚠️ WARNING (No Tech Footprint Found)'
            
        print(f'  -> Status: {status}')
        if sanctions['is_flagged']:
            print(f'  -> Alert: Match found in {sanctions["source"]}')
            # Handle potential list of dicts or strings
            ev = sanctions["evidence"][0]
            name_match = ev.get("match_name", "Unknown") if isinstance(ev, dict) else str(ev)
            print(f'  -> Evidence: {name_match}')

if __name__ == '__main__':
    asyncio.run(validate_supply_chain())
