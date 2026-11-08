"""Real Chrome comparison of HS two-portrait coding space vs gaming DS screens.

This reuses upstream HS xterm.js and the actual sandboxed SSH fixture.
Chrome CSS pixels are assumed equal to panel pixels solely for a WHAT-IF
physical target-size estimate; DPI/scaling and human ergonomics are untested.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
import tempfile
import time

from playwright.sync_api import sync_playwright

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"workflow_lab"))
from server import serve

HERE=Path(__file__).resolve().parent
SCREENS=[
    {"id":"hs_dual_5in_portrait","device":"HS portrait 720x1280 per display",
     "pixels_per_screen":[720,1280],"viewport_css":[720,2560],
     "visible_width_mm":62.28,"visible_height_mm":110.32,
     "physical_dimension_basis":"Waveshare 5inch DSI LCD (D) manufacturer active CG VA"},
    {"id":"anbernic_rgds_4in_landscape","device":"RG DS gaming reference: 640x480 per display",
     "pixels_per_screen":[640,480],"viewport_css":[640,960],
     "visible_width_mm":81.28,"visible_height_mm":60.96,
     "physical_dimension_basis":"approx 4.0 inch diagonal 4:3 marketing size, not measured panel CAD"},
    {"id":"anbernic_rgds_plus_43in_landscape",
     "device":"RG DS Plus gaming reference: 1024x768 per display",
     "pixels_per_screen":[1024,768],"viewport_css":[1024,1536],
     "visible_width_mm":87.376,"visible_height_mm":65.532,
     "physical_dimension_basis":"approx 4.3 inch diagonal 4:3 marketing size, not measured panel CAD"},
]


def _poll(page,expression:str,timeout_s:float=9)->None:
    until=time.monotonic()+timeout_s
    while time.monotonic()<until:
        if page.evaluate(expression):return
        time.sleep(0.1)
    raise AssertionError(f"terminal did not satisfy expected condition: {expression}")


def measure(url:str)->dict:
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=os.getenv("HS_CHROME_PATH","/usr/bin/google-chrome"),
                                   headless=True,args=["--no-sandbox"])
        results=[]
        try:
            for screen in SCREENS:
                w,h=screen["viewport_css"]
                context=browser.new_context(viewport={"width":w,"height":h},
                                            has_touch=True,device_scale_factor=1)
                page=context.new_page()
                errors=[]
                page.on("pageerror",lambda err:errors.append(str(err)))
                r=page.goto(url,wait_until="load")
                assert r.status==200
                page.wait_for_selector('body[data-connected="yes"]',timeout=15000)
                if screen["id"]=="hs_dual_5in_portrait":
                    assert page.evaluate("window.hsBench.getKeyboardLayout()") == "wide"
                    wide_min=page.evaluate("Math.min(...[...document.querySelectorAll('[data-letter]')].map(x=>x.getBoundingClientRect().width))")
                    page.locator('#keyboard-mode').tap()
                    assert page.evaluate("window.hsBench.getKeyboardLayout()") == "full"
                    full_min=page.evaluate("Math.min(...[...document.querySelectorAll('[data-letter]')].map(x=>x.getBoundingClientRect().width))")
                    page.locator('#keyboard-mode').tap()
                    assert wide_min>full_min*1.7
                    profile_gain=round(wide_min/full_min,3)
                else:
                    profile_gain=None
                for font in (18,24,28):
                    page.evaluate("(n)=>{window.hsBench.term.options.fontSize=n; window.dispatchEvent(new Event('resize'));}",font)
                    page.wait_for_timeout(225)
                    stat=page.evaluate("""() => {
                      const keys=[...document.querySelectorAll('.key')];
                      const letters=keys.filter(k=>k.dataset.letter);
                      const shell=document.querySelector('.terminal-screen').getBoundingClientRect();
                      const keyboard=document.querySelector('.keyboard-screen').getBoundingClientRect();
                      return {cols:window.hsBench.term.cols,rows:window.hsBench.term.rows,
                        smallest_letter_css_px:Math.min(...letters.map(k=>k.getBoundingClientRect().width)),
                        smallest_key_css_px:Math.min(...keys.map(k=>k.getBoundingClientRect().width)),
                        letter_key_count:letters.length,
                        top_height_css_px:shell.height,lower_height_css_px:keyboard.height,
                        horizontal_overflow:document.documentElement.scrollWidth>innerWidth,
                        fontsize_css_px:window.hsBench.term.options.fontSize};
                    }""")
                    actual_mm=screen["visible_width_mm"]/w
                    stat["smallest_letter_nominal_mm"]=round(stat["smallest_letter_css_px"]*actual_mm,2)
                    stat["font_nominal_mm"]=round(font*actual_mm,2)
                    stat["physical_input_target_requirement_met_7mm"]=stat["smallest_letter_nominal_mm"]>=7
                    stat["wide_vs_legacy_key_width_gain"]=profile_gain
                    stat["keyboard_layout"]=page.evaluate("window.hsBench.getKeyboardLayout()")
                    if font==24:
                        page.screenshot(path=str(HERE/"evidence"/(screen["id"]+"_24px.png")),full_page=True)
                    assert stat["letter_key_count"]==26
                    assert not stat["horizontal_overflow"]
                    if font==18:
                        for k in ("p","w","d","ENTER"):
                            page.locator(f'[data-key="{k}"]').first.tap()
                        _poll(page,"window.hsBench.getScreenText().includes('/work')")
                        stat["real_ssh_touch_pwd_passed"]=True
                        if screen["id"]=="hs_dual_5in_portrait":
                            # This is an actual keyboard-layer toggle followed
                            # by real touch events entering a shell command.
                            for k in ('e','c','h','o','SPACE','SYM','1','2','3','ENTER'):
                                page.locator(f'[data-key="{k}"]').first.tap()
                            _poll(page,"window.hsBench.getScreenText().includes('123')")
                            stat["symbol_layer_to_real_SSH_verified"]=True
                            page.locator('[data-key="ABC"]').first.tap()
                            assert page.evaluate("window.hsBench.getKeyboardLayer()") == "letters"
                    if font==28:
                        stat["real_ssh_touch_pwd_passed"]=None
                    results.append({"device":screen["id"],**stat})
                assert errors==[],errors
                context.close()
        finally:
            browser.close()
        return {
            "schema":"hs.dual_portrait_vs_DS_real_browser_benchmark.v1",
            "run_kind":"actual Chromium xterm.js upper and clickable keyboard lower, loopback OpenSSH",
            "physical_touchscreen_or_CM5_tested":False,
            "device_pixel_ratio_assumed_1_no_OS_scaling_proof":True,
            "human_typing_tested":False,
            "screens":SCREENS,
            "results":results,
            "screenshots_are_browser_not_devices":True,
        }


async def main()->None:
    (HERE/"evidence").mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="hs-dual-portrait-token-") as tmp:
        os.environ["HS_WORKFLOW_URL_FILE"]=str(Path(tmp)/"url")
        results=[]
        async def on_ready(service,port):
            url=f"http://127.0.0.1:{port}/?token={service.token}"
            results.append(await asyncio.to_thread(measure,url))
        await serve(0,on_ready=on_ready)
        assert len(results)==1
        report=results[0]
        (HERE/"evidence"/"portrait_vs_DS_browser.json").write_text(json.dumps(report,indent=2)+"\n")
        for row in report["results"]:
            print(row["device"],row["fontsize_css_px"],
                  row["cols"],row["rows"],"nominal letter mm",row["smallest_letter_nominal_mm"])
if __name__=="__main__":
    asyncio.run(main())
