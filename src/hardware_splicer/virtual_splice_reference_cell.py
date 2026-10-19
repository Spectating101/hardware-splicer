"""Executable *software-only* barcode indexing reference cell.

The signal names are abstract intent events, not hardware GPIO instructions.
The real device's scanner, motor type, emergency stop and power interfaces
remain completely uncharacterized. No physical safety certification implied.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass
class VirtualInspectionCell:
    state: str = "inhibited"
    interlock_reported_closed: bool = False
    virtual_index_requested: bool = False
    barcode: str | None = None
    faults: list[str] = field(default_factory=list)
    completed_count: int = 0
    event_history: list[dict[str, Any]] = field(default_factory=list)

    def dispatch(self, event: str, value: Any = None) -> dict[str, Any]:
        """Fail-closed virtual controller; input is synthetic/simulated ONLY."""
        allowed = {
            "interlock_closed", "interlock_open", "reset", "load",
            "motion_complete", "scan", "ack", "stop",
            "motion_timeout", "limit_fault",
        }
        if event not in allowed:
            raise ValueError("unknown virtual controller event")
        before = self.state
        if event in {"stop", "interlock_open"}:
            # An ordinary software stop must latch off re-arm until the
            # abstract interlock is deliberately re-closed AND reset.
            # This is NOT certification of a real emergency-stop circuit.
            self.interlock_reported_closed = False
            self.virtual_index_requested = False
            self.state = "inhibited"
        elif event == "interlock_closed":
            self.interlock_reported_closed = True
            # Deliberately requires *separate* reset; no auto motion.
        elif event == "reset":
            self.virtual_index_requested = False
            self.barcode = None
            if self.interlock_reported_closed:
                self.state = "ready"
            else:
                self.state = "inhibited"
        elif event in {"motion_timeout", "limit_fault"}:
            self.virtual_index_requested = False
            self.interlock_reported_closed = False
            self.state = "fault"
            self.faults.append(event)
        elif self.state in {"fault", "inhibited"}:
            # Synthetic event cannot silently bypass a latched stop or fault.
            pass
        elif event == "load" and self.state == "ready":
            self.virtual_index_requested = True
            self.barcode = None
            self.state = "indexing"
        elif event == "motion_complete" and self.state == "indexing":
            self.virtual_index_requested = False
            self.state = "await_scan"
        elif event == "scan" and self.state == "await_scan":
            code = value if isinstance(value, str) else ""
            if not code or not code.isascii() or len(code) > 96 or not code.strip():
                self.state = "fault"
                self.interlock_reported_closed = False
                self.faults.append("invalid_scan")
            else:
                self.barcode = code
                self.state = "complete"
                self.completed_count += 1
        elif event == "ack" and self.state == "complete":
            self.state = "ready"
            self.barcode = None
        result = {
            "event": event,
            "from": before,
            "to": self.state,
            "virtual_index_requested": self.virtual_index_requested,
            "interlock_reported_closed": self.interlock_reported_closed,
            "barcode_recorded": self.barcode,
            "faults": list(self.faults),
            "completed_count": self.completed_count,
            "physical_hardware_actuated": False,
            "actual_safety_stop_verified": False,
            "accepted_event": before != self.state or event in {"interlock_closed", "stop", "interlock_open"},
        }
        self.event_history.append(result)
        return result


SCENARIOS: dict[str,list[tuple[str,Any]]] = {
    "normal_cycle": [
        ("interlock_closed",None), ("reset",None), ("load",None),
        ("motion_complete",None), ("scan","TEST-0001"), ("ack",None),
    ],
    "stop_during_motion": [
        ("interlock_closed",None), ("reset",None), ("load",None),
        ("interlock_open",None), ("motion_complete",None),
        ("scan","SHOULD-NOT-COUNT"),
    ],
    "premature_scan_rejected": [
        ("interlock_closed",None), ("reset",None), ("scan","EARLY"),
        ("load",None), ("scan","EARLY"), ("motion_complete",None),
        ("scan","VALID-0002"),
    ],
    "motion_timeout_fail_closed": [
        ("interlock_closed",None), ("reset",None), ("load",None),
        ("motion_timeout",None), ("scan","SHOULD-NOT-COUNT"),
    ],
    "limit_fault_fail_closed": [
        ("interlock_closed",None), ("reset",None), ("load",None),
        ("limit_fault",None), ("motion_complete",None),
    ],
    "reset_requires_interlock": [
        ("reset",None), ("load",None), ("interlock_closed",None),
        ("reset",None), ("load",None),
    ],
    "stop_requires_explicit_rearm": [
        ("interlock_closed",None), ("reset",None), ("load",None),
        ("stop",None), ("reset",None), ("load",None),
        ("interlock_closed",None), ("reset",None),
    ],
    "invalid_scan_fault": [
        ("interlock_closed",None), ("reset",None), ("load",None),
        ("motion_complete",None), ("scan",""),
    ],
}


def run_virtual_reference_cases() -> dict[str,Any]:
    """Deterministic built-in fault injection, not donor observations."""
    results = []
    expected = {
        "normal_cycle": ("ready",1),
        "stop_during_motion": ("inhibited",0),
        "premature_scan_rejected": ("complete",1),
        "motion_timeout_fail_closed": ("fault",0),
        "limit_fault_fail_closed": ("fault",0),
        "reset_requires_interlock": ("indexing",0),
        "stop_requires_explicit_rearm": ("ready",0),
        "invalid_scan_fault": ("fault",0),
    }
    for name,events in SCENARIOS.items():
        cell = VirtualInspectionCell()
        trace = [cell.dispatch(event,value) for event,value in events]
        target_state,target_completed=expected[name]
        invalid_motion=any(
            t["virtual_index_requested"] and
            (t["to"] != "indexing" or not t["interlock_reported_closed"])
            for t in trace
        )
        unauthorized_physical=any(t["physical_hardware_actuated"] or t["actual_safety_stop_verified"] for t in trace)
        ok=(cell.state == target_state and cell.completed_count == target_completed
            and not invalid_motion and not unauthorized_physical
            and (not cell.virtual_index_requested or (cell.state=="indexing" and cell.interlock_reported_closed)))
        results.append({
            "case":name,"software_test_pass":ok,
            "expected_end_state":target_state,"actual_end_state":cell.state,
            "expected_completed_count":target_completed,"actual_completed_count":cell.completed_count,
            "virtual_event_trace":trace,
            "real_sensor_observed":False,"real_motor_command_issued":False,
            "safety_rated_e_stop_present":False,
        })
    return {
        "schema_version":"hardware_splicer.virtual_splice_reference_cell.v1",
        "test_scope":"deterministic synthetic software events only, no actual barcode reader, machine or safety loop",
        "passed":sum(x["software_test_pass"] for x in results),
        "total":len(results),
        "cases":results,
        "software_reference_logic_passed":all(x["software_test_pass"] for x in results),
        "physical_product_works":False,
        "donor_modules_operational":False,
        "actual_safety_stop_verified":False,
        "physical_operation_authorized":False,
    }


def audit_bounded_sequences(max_depth: int = 4) -> dict:
    """Check software invariants over all short synthetic event sequences."""
    from itertools import product
    if type(max_depth) is not int or not 1 <= max_depth <= 5:
        raise ValueError('max_depth outside audit budget')
    alphabet = ('interlock_closed','interlock_open','reset','load','motion_complete','scan','stop','motion_timeout','limit_fault')
    n=0
    steps=0
    failures=[]
    for depth in range(1,max_depth+1):
        for seq in product(alphabet,repeat=depth):
            n+=1
            cell=VirtualInspectionCell()
            for event in seq:
                before=cell.completed_count
                prior=cell.state
                row=cell.dispatch(event,'SYNTHETIC-001' if event=='scan' else None)
                steps+=1
                if row['virtual_index_requested'] and (row['to']!='indexing' or not row['interlock_reported_closed']):
                    failures.append('index_without_software_enable')
                if event in ('stop','interlock_open') and (row['to']!='inhibited' or row['virtual_index_requested']):
                    failures.append('stop_not_latched')
                if event=='scan' and prior!='await_scan' and cell.completed_count!=before:
                    failures.append('early_scan_counted')
                if row['physical_hardware_actuated'] or row['actual_safety_stop_verified']:
                    failures.append('physical_claim_from_simulation')
            if failures:
                break
        if failures:
            break
    return {'schema_version':'hardware_splicer.bounded_virtual_audit.v1','sequences_checked':n,'events_checked':steps,'max_depth':max_depth,'violations':failures,'passed':not failures,'physical_hardware_evaluated':False}
