"""Exercise HS's real print-staging operator against a fake transport only.

The genuine G-code bytes are uploaded to an in-memory transport. Attempting
to start without a human artifact-bound grant MUST fail and must not invoke
the backend's physical-start method.
"""
from __future__ import annotations
import hashlib, tempfile
from pathlib import Path
from hardware_splicer.fabrication_operator import FabricationGrantStore, FabricationAuthorityError
from hardware_splicer.printer_operator import FabricationPrinter, OctoPrintBackend
from hardware_splicer.realization_gcode_audit import audit_offline_gcode

class InMemoryTransport:
    def __init__(self):
        self.calls=[]
    def upload(self,path,*,filename,data,fields):
        self.calls.append({"operation":"upload","path":path,"filename":filename,
                           "sha256":hashlib.sha256(data).hexdigest(),
                           "select":fields.get("select"),
                           "print":fields.get("print")})
        return {"files":{"local":{"path":filename}}}
    def request(self,method,path,*,json_body=None):
        self.calls.append({"operation":"request","method":method,"path":path,"body":dict(json_body or {})})
        return {"ok":True}

def simulate_staging_and_denied_start(gcode:Path)->dict:
    audit=audit_offline_gcode(gcode)
    with tempfile.TemporaryDirectory(prefix="hs-printer-dryrun-") as tmp:
        transport=InMemoryTransport()
        printer=FabricationPrinter(
            printer_id="SIMULATED_MK4S_NOT_CONNECTED",
            backend=OctoPrintBackend(),
            transport=transport,
            grants=FabricationGrantStore(Path(tmp)/"grants"),
        )
        prepared=printer.stage_gcode(filename="Casing_MK4S_TEST.gcode",data=Path(gcode).read_bytes())
        start_rejected=False
        try:
            printer.start(
                prepared,project_id="casing_pilot",
                mission_id="printer_handoff_dryrun",
                grant_id="never_issued_test_grant")
        except FabricationAuthorityError:
            start_rejected=True
        if not start_rejected:
            raise AssertionError("start without a human grant was not denied")
        if len(transport.calls)!=1 or transport.calls[0]["operation"]!="upload":
            raise AssertionError("unapproved printing or unexpected printer calls occurred")
        if transport.calls[0]["select"]!="false" or transport.calls[0]["print"]!="false":
            raise AssertionError("staging attempted to start printing")
        if prepared.artifact_sha256!=audit["sha256"]:
            raise AssertionError("staged G-code hash differed from independently audited file")
        return {
            "schema_version":"hs.realization_printer_dryrun.v1",
            "gcode_sha256":audit["sha256"],
            "staged_exact_gcode_in_simulated_transport":True,
            "staging_selection":"false",
            "staging_print":"false",
            "start_without_human_grant_rejected":True,
            "real_printer_or_octoprint_contacted":False,
            "physical_print_performed":False,
            "transport_receipts":transport.calls,
        }
