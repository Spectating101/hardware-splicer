"""Standalone, inspectable HTML field report (not a mockup).

Outputs one offline HTML file with functional phase/model controls,
actual source evidence, KiCad net and pin references, immutable hashes
and local JSON export. All HTML/JS strings are escaped; no CDN or API.
"""
from __future__ import annotations
import hashlib
import html
import json
from pathlib import Path
from typing import Any,Mapping

from .repair_investigator import SCHEMA, sha

PAGE=r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"/>
<meta name="color-scheme" content="dark">
<title>HS / Repair Investigator — Case study</title>
<style>
:root{--bg:#11191d;--pane:#172025;--text:#e7ede9;--muted:#93a5a8;--border:#34454b;--line:#26363b;--accent:#9fc6ae;--alert:#f2c79d}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}
a{color:#bbdecf;text-decoration-color:#4b786b}a:hover{text-decoration-color:var(--accent)}
button{font:inherit;cursor:pointer}button:focus-visible,a:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
header{border-bottom:1px solid var(--border);padding:26px clamp(20px,4vw,64px);display:flex;gap:28px;align-items:baseline;justify-content:space-between}
.brand{font-weight:750;letter-spacing:.22em;font-size:12px;color:var(--accent);text-transform:uppercase}
.topline{font-size:12px;color:var(--muted);letter-spacing:.08em}
main{max-width:1530px;margin:auto;display:grid;grid-template-columns:276px minmax(0,1fr);gap:clamp(25px,3vw,62px);padding:40px clamp(20px,4vw,64px) 110px}
aside{border-right:1px solid var(--border);padding-right:28px;align-self:start;position:sticky;top:24px}
.kicker{text-transform:uppercase;font-size:11px;letter-spacing:.19em;font-weight:750;color:var(--accent)}
h1,h2,h3,p{margin-top:0}h1{font-size:clamp(36px,4.8vw,72px);line-height:1.07;font-weight:650;letter-spacing:-.048em;max-width:880px;margin-bottom:22px}h2{font-size:23px;font-weight:630;letter-spacing:-.018em}h3{font-size:15px;font-weight:700}p{max-width:860px}small,.muted{color:var(--muted)}
.deck{font-size:17px;line-height:1.65;max-width:820px;color:#c3d2d0}
.rule{border:0;border-top:1px solid var(--border);margin:38px 0}
.navitem{padding:14px 0;border-bottom:1px solid var(--line)}.navitem label{display:block;color:var(--muted);font-size:10px;letter-spacing:.15em;text-transform:uppercase}.navitem strong{font-size:14px;font-weight:620}
.block{margin:42px 0 0}.sectionhead{display:flex;justify-content:space-between;gap:12px;align-items:end;border-bottom:1px solid var(--border);padding-bottom:14px;margin-bottom:16px}
.sectionsub{font-size:12px;color:var(--muted);max-width:500px;text-align:right}
.kv{display:grid;grid-template-columns:1fr auto;gap:6px 20px;padding:11px 0;border-bottom:1px solid var(--line)}.kv span:first-child{color:var(--muted)}
.controls{display:flex;flex-wrap:wrap;gap:6px;margin:14px 0 26px}
.control{border:1px solid var(--border);border-radius:2px;background:transparent;color:var(--muted);padding:9px 13px;font-size:12px}
.control[aria-pressed="true"]{color:#101c18;background:var(--accent);border-color:var(--accent);font-weight:700}
.table{width:100%;border-collapse:collapse}.table td,.table th{border-bottom:1px solid var(--line);padding:14px 10px;vertical-align:top;text-align:left}.table th{font-size:11px;letter-spacing:.13em;text-transform:uppercase;color:var(--muted)}.table .number{color:var(--accent);font:15px ui-monospace,monospace;width:34px}
.reading{font-size:20px;line-height:1.35;font-weight:620;letter-spacing:-.018em;margin-bottom:8px}.because{max-width:850px;color:#b6c7c9;font-size:14px}
.evidence-pill{font:11px ui-monospace,monospace;display:inline-block;padding:3px 6px;border:1px solid var(--border);color:var(--accent);margin:5px 4px 0 0}
.provenance{font:11px/1.65 ui-monospace,monospace;overflow-wrap:anywhere;color:#b8c5c7}
.note{border-left:2px solid var(--accent);padding:10px 0 10px 17px;margin:25px 0;max-width:880px}
.note.warning{border-color:var(--alert)}
.note p{margin:0;font-size:14px;color:#c2d0cf}
.signal{display:flex;gap:13px;align-items:center;padding:13px 0;border-bottom:1px solid var(--line)}
.status-dot{width:7px;height:7px;border-radius:100%;background:var(--accent);flex:none}.status-dot.warn{background:var(--alert)}
.signal-title{font-size:13px;font-weight:650}
.signal-body{font-size:12px;color:var(--muted)}
.net-row{display:grid;grid-template-columns:minmax(80px,180px) minmax(0,1fr);align-items:start;gap:15px;border-bottom:1px solid var(--line);padding:12px 0}
.netlabel{font:12px ui-monospace,monospace;color:var(--accent);overflow-wrap:anywhere}
.pin{display:inline-block;background:#1f3031;border:1px solid #3e5552;color:#c4d9d3;border-radius:2px;font:11px ui-monospace,monospace;padding:3px 6px;margin:2px}
.pre{white-space:pre-wrap;word-break:break-word;color:#c9d4d0;font-size:13px}
footer{border-top:1px solid var(--border);padding:22px clamp(20px,4vw,64px);color:var(--muted);font-size:12px}
#top-flag{font:11px ui-monospace,monospace;color:var(--alert)}
#hypothesis-list{margin:0;padding:0;list-style:none}.hypothesis{display:grid;grid-template-columns:50px 1fr;gap:14px;padding:18px 0;border-bottom:1px solid var(--line)}
.hypothesis .index{font:15px ui-monospace,monospace;color:var(--accent);margin-top:1px}
.toggle{display:flex;gap:8px;flex-wrap:wrap;margin:5px 0}
.sectionlinks{display:flex;flex-direction:column;gap:7px;font-size:13px}
@media(max-width:980px){main{grid-template-columns:1fr}aside{position:static;border-right:0;padding-right:0;border-bottom:1px solid var(--border);padding-bottom:24px}.navitem{display:inline-block;min-width:175px;padding:10px 15px 10px 0}.sectionhead{display:block}.sectionsub{text-align:left}.net-row{grid-template-columns:1fr}}
@media print{aside,button,.controls{display:none}main{display:block;padding:10px 24px}body{background:#fff;color:#171b1d}.deck,.muted,.because{color:#444}header{padding:10px 24px}.netlabel{color:#31564c}.pin{color:#171b1d}}
</style>
</head>
<body>
<header><div class="brand">Hardware Splicer <span style="opacity:.5">/ Investigator</span></div><span class="topline">SOURCE-LOCKED FIELD NOTE &nbsp; 001 / 2026</span></header>
<main>
<aside>
<div class="kicker">Case register</div>
<div class="navitem"><label>Device</label><strong id="device-side"></strong></div>
<div class="navitem"><label>Evidence authority</label><strong>Publisher-reported / unverified</strong></div>
<div class="navitem"><label>Diagnostic phase</label><strong id="window-side">Opening narration</strong></div>
<div class="navitem"><label>Physical board</label><strong>Revision not confirmed</strong></div>
<div class="navitem"><label>Repair executed</label><strong>No</strong></div>
<p style="margin-top:28px" class="kicker">Source register</p>
<div class="sectionlinks"><a id="video-link" target="_blank" rel="noopener noreferrer">Creator video</a><a id="schematic-link" target="_blank" rel="noopener noreferrer">Open KiCad reference</a><a href="#circuit">Reference circuit topology</a><a href="#audit">Source integrity ledger</a></div>
<p style="margin-top:26px;color:var(--muted);font-size:12px">The schematic and captions are cited sources. Neither independently proves the condition or pinout of the actual board.</p>
</aside>
<article>
<div class="kicker">Repair field investigation · archival experiment</div>
<h1 id="case-title">Not booting. Multiple possible failure paths.</h1>
<p class="deck" id="intro"></p>
<div class="note warning"><p><b>Authority boundary:</b> This report proposes diagnostic hypotheses only. No physical repair, powered test, internal probing, component replacement or safety certification was conducted. The video was analyzed as auto-caption text, not inspected frame by frame.</p></div>
<section class="block" id="diagnosis">
<div class="sectionhead"><div><div class="kicker">01 / Diagnostic investigation</div><h2>How the hypothesis changes</h2></div><span class="sectionsub">Change the model arm and evidence window. Each state comes from a saved inference receipt.</span></div>
<div class="kicker">Evidence window</div>
<div class="controls" id="stages"><button class="control" data-stage="0" aria-pressed="true">01 · Opening (0–120s)</button><button class="control" data-stage="1" aria-pressed="false">02 · Inspection (120–210s)</button></div>
<div class="kicker">Model path</div>
<div class="controls" id="arms"><button class="control" data-arm="plain" aria-pressed="false">Plain Gemini</button><button class="control" data-arm="hs_circuit" aria-pressed="true">HS + real schematic</button></div>
<div class="signal"><span class="status-dot" id="diag-dot"></span><div><div class="signal-title" id="diag-status">Provisional diagnostic reasoning</div><div class="signal-body" id="diag-meta">Inference record</div></div></div>
<div style="margin-top:22px" class="reading" id="current-summary"></div>
<ol id="hypothesis-list"></ol>
<div class="note"><div class="kicker">Proposed next check</div><p id="next-check" style="margin-top:7px"></p></div>
<div class="note warning"><div class="kicker">Uncertainty / safety boundary</div><p id="uncertainty" style="margin-top:7px"></p></div>
</section>
<section class="block" id="evidence">
<div class="sectionhead"><div><div class="kicker">02 / Evidence review</div><h2>What the source actually says</h2></div><span class="sectionsub">Original auto-caption text is unverified, and later repairs are excluded from these windows.</span></div>
<table class="table"><thead><tr><th>Source ID</th><th>Reported observation</th></tr></thead><tbody id="evidence-rows"></tbody></table>
</section>
<section class="block" id="circuit">
<div class="sectionhead"><div><div class="kicker">03 / Engineering source</div><h2>Actual KiCad electrical nets</h2></div><span class="sectionsub" id="net-summary"></span></div>
<p class="deck" style="font-size:14px">These are extracted connections on the <b>reference design</b>. Pins sharing one net are shown together; this diagram does not imply conduction through an IC, fuse or switch, nor a verified pinout on the physical C64.</p>
<div id="nets"></div>
</section>
<section class="block" id="comparison">
<div class="sectionhead"><div><div class="kicker">04 / Comparative control</div><h2>Plain model vs. source-assisted model</h2></div><span class="sectionsub">Same model and caption evidence per stage. Different system instructions and token budget.</span></div>
<table class="table"><thead><tr><th>Condition</th><th>Plain Gemini</th><th>HS / KiCad</th></tr></thead><tbody id="comparisons"></tbody></table>
<p class="muted" style="font-size:13px;margin-top:20px">No repair outcome or component-level ground truth is supplied. Differences in proposed mechanisms are not necessarily accuracy improvements.</p>
</section>
<section class="block" id="audit">
<div class="sectionhead"><div><div class="kicker">05 / Forensic ledger</div><h2>Reproducibility and known limits</h2></div><span class="sectionsub">Every claim is source-pinned; no independent meter data is present.</span></div>
<div id="audit-rows"></div>
<div class="note warning"><p>Public schematics may differ from the original physical board. The exported KiCad design reports annotation warnings. This report is for source-integrity research and does not authorize electrical intervention.</p></div>
<button type="button" class="control" id="export" style="margin-top:16px">Export machine-readable investigation record (.json)</button>
</section>
</article>
</main>
<footer>HS / Repair Investigator &nbsp; · &nbsp; Public-source engineering research &nbsp; · &nbsp; No independently validated repair</footer>
<script id="payload" type="application/json">__INVESTIGATOR_JSON__</script>
<script>
(function(){
"use strict";
const obj=JSON.parse(document.getElementById("payload").textContent),r=obj.investigation,m=obj.manifest,ref=obj.reference;
const E=id=>document.getElementById(id), mk=(tag,cls,text)=>{
 const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=String(text);return e;
};
let stage=0,arm="hs_circuit";
E("device-side").textContent=m.device;E("case-title").textContent=m.video_title_symptom;
E("intro").textContent="A public-source investigation of a nonworking Commodore 64 motherboard: what the creator reported, what an actual KiCad reference establishes, and how provisional fault hypotheses changed as early inspection evidence arrived.";
E("video-link").href=m.video_url;E("schematic-link").href=ref.source_repository+"/tree/"+ref.source_commit;
E("net-summary").textContent=ref.selected_nets.length+" source-selected nets · "+ref.full_netlist_component_count+" components / "+ref.full_netlist_net_count+" nets in original export";
const schematic=E("nets");
ref.selected_nets.forEach((net)=>{
 const line=mk("div","net-row"),l=mk("div","netlabel",net.name),pins=mk("div","");
 net.pins.filter(x=>["SW1","F1","VR1","VR2","U7","U11","U12","U17","U19","U20","CN2"].includes(x.ref)).slice(0,18).forEach(x=>pins.append(mk("span","pin",x.ref+"."+x.pin)));
 if(!pins.childNodes.length)pins.append(mk("span","muted","Source net: "+net.pin_count+" attached terminals (not listed here)"));
 if(net.pins.length>18)pins.append(mk("span","muted"," · source net has "+net.pin_count+" terminals"));
 line.append(l,pins);schematic.append(line);
});
const addkv=(key,val)=>{const row=mk("div","kv");row.append(mk("span","",key),mk("span","provenance",val));E("audit-rows").append(row)};
addkv("Video ID",m.video_id);addkv("Video transcript SHA-256",m.video_auto_captions_sha256);
addkv("KiCad source project",ref.source_repository);
addkv("Upstream commit",ref.source_commit);
addkv("Derived netlist snapshot SHA-256",obj.reference_file_sha256);
addkv("Source graph SHA-256",r.native_graph.native_source_graph_sha256);
addkv("Source license",ref.source_license);
addkv("Physical target board verified","NO · reported revision only");
addkv("Instrument readings independently captured","NONE");
addkv("Experimental outcome labels in model prompts","NONE");
const dataRows=r.results;
function draw(){
 document.querySelectorAll("[data-arm]").forEach(b=>b.setAttribute("aria-pressed",String(b.dataset.arm===arm)));
 document.querySelectorAll("[data-stage]").forEach(b=>b.setAttribute("aria-pressed",String(Number(b.dataset.stage)===stage)));
 E("window-side").textContent=stage?"Inspection extension / 210s":"Initial opening / 120s";
 const row=(dataRows[arm]||[])[stage],receipt=row?.model_receipt,plan=receipt?.plan;
 const valid=receipt?.status==="proposed_unverified_differential" || receipt?.status==="model_abstained";
 E("diag-dot").className="status-dot"+(valid?"":" warn");
 E("diag-status").textContent=receipt?.status||row?.status||"No valid inference for this phase";
 E("diag-meta").textContent=receipt?(receipt.model_reported||receipt.model_requested)+" · "+(Math.round(receipt.elapsed_seconds*100)/100)+"s inference · receipt "+receipt.receipt_sha256.slice(0,15)+"…":"Source evidence gated; no model call";
 E("current-summary").textContent=plan?plan.summary:"The preceding prediction did not meet the validation gate; no later diagnosis was fabricated.";
 E("next-check").textContent=plan?plan.next_safe_check:"No action authorized. Review model failure and source evidence.";
 E("uncertainty").textContent=plan?plan.uncertainty:"Insufficient validated diagnosis.";
 const list=E("hypothesis-list");list.replaceChildren();
 if(plan)plan.hypotheses.forEach((h,i)=>{
   const li=mk("li","hypothesis"),num=mk("div","index",String(i+1).padStart(2,"0")),body=mk("div","");
   body.append(mk("div","reading",h.mechanism),mk("p","because",h.why),mk("div","muted","Proposed discriminating check: "+h.safe_test));
   h.evidence_ids.forEach(id=>body.append(mk("span","evidence-pill",id)));li.append(num,body);list.append(li);
 });
 const evidence=E("evidence-rows");evidence.replaceChildren();
 const ev=row?.evidence||dataRows[arm][0]?.evidence||[];
 ev.forEach(x=>{
   const tr=mk("tr"),id=mk("td","number",x.id),desc=mk("td","",x.text);
   const src=mk("div","provenance",x.kind+" · "+x.stage);desc.append(src);tr.append(id,desc);evidence.append(tr);
 });
 const cmp=E("comparisons");cmp.replaceChildren();
 const p0=dataRows.plain[stage],p1=dataRows.hs_circuit[stage];
 [
  ["Status",p0?.model_receipt?.status||p0?.status||"—",p1?.model_receipt?.status||p1?.status||"—"],
  ["First-ranked mechanism",p0?.model_receipt?.plan?.hypotheses?.[0]?.mechanism||"—",p1?.model_receipt?.plan?.hypotheses?.[0]?.mechanism||"—"],
  ["First proposed check",p0?.model_receipt?.plan?.next_safe_check||"—",p1?.model_receipt?.plan?.next_safe_check||"—"],
  ["Source netlist provided","No","Yes · actual KiCad source"],
  ["Repair performed","No","No"],
 ].forEach(data=>{const tr=mk("tr");data.forEach((t,i)=>tr.append(mk(i?"td":"th","",t)));cmp.append(tr)});
}
document.querySelectorAll("[data-arm]").forEach(b=>b.addEventListener("click",()=>{arm=b.dataset.arm;draw()}));
document.querySelectorAll("[data-stage]").forEach(b=>b.addEventListener("click",()=>{stage=Number(b.dataset.stage);draw()}));
E("export").addEventListener("click",()=>{
 const a=document.createElement("a");
 const blob=new Blob([JSON.stringify(obj,null,2)],{type:"application/json"});
 const url=URL.createObjectURL(blob);a.href=url;a.download="hs-repair-investigator-c64.json";
 document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),2000);
});
draw();
})();
</script>
</body></html>
"""

def make_html(*,record:Mapping[str,Any],manifest:Mapping[str,Any],
              reference:Mapping[str,Any],snapshot_sha256:str)->str:
    if record.get("schema")!= "hs.repair_investigator.v1" or not record.get("complete"):
        raise ValueError("cannot publish an incomplete or unknown investigator record")
    if record["source_manifest_sha256"]!=sha(manifest):
        raise ValueError("source case metadata changed after model inference")
    if record["source_snapshot_sha256"]!=sha(reference):
        raise ValueError("source circuit changed after model inference")
    if record["video_source_sha256"]!=manifest["video_auto_captions_sha256"]:
        raise ValueError("video source digest mismatch")
    for name in ("plain","hs_circuit"):
        if len(record["results"].get(name,[]))!=2:
            raise ValueError("model arms must have two auditable phase entries")
        for row in record["results"][name]:
            receipt=row.get("model_receipt")
            if receipt is None:
                continue
            signed={k:v for k,v in receipt.items() if k not in ("receipt_sha256","elapsed_seconds")}
            if sha(signed)!=receipt["receipt_sha256"]:
                raise ValueError("model receipt was edited after original inference")
            if receipt["repair_authorized"] is not False or receipt["actual_video_frames_analyzed"] is not False:
                raise ValueError("report would misrepresent hardware or visual authority")
    payload={
        "schema":"hs.repair_investigator.standalone_html_payload.v1",
        "manifest":manifest,"reference":reference,"reference_file_sha256":snapshot_sha256,
        "investigation":record,"repair_completed":False,"physical_board_verified":False,
        "independently_captured_instrument_data":False,
    }
    literal=json.dumps(payload,ensure_ascii=False,sort_keys=True).replace("<","\\u003c").replace(">","\\u003e").replace("&","\\u0026")
    return PAGE.replace("__INVESTIGATOR_JSON__",literal)
