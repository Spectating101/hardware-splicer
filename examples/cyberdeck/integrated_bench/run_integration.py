"""Integration: two real Chrome pages and WS roles, one sandboxed OpenSSH PTY.

No physical display, DSI, CM5 or battery is inferred from this browser run.
"""
from __future__ import annotations
import asyncio
from datetime import datetime,timezone
import json,os,time,tempfile
from pathlib import Path
from aiohttp import ClientSession,WSServerHandshakeError
from playwright.sync_api import sync_playwright
from dual_panel_server import serve_dual

HERE=Path(__file__).resolve().parent
EVIDENCE=HERE/"evidence"

def wait_for(page,expr,timeout=12):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if page.evaluate(expr):return
        time.sleep(.08)
    raise AssertionError("browser timeout: "+expr)

def tap(page,key):
    page.locator('[data-key="'+key+'"]').first.tap(timeout=7000)

def browser_run(base,token,fixture):
    with sync_playwright() as pw:
        browser=pw.chromium.launch(
            executable_path=os.getenv("HS_CHROME_PATH","/usr/bin/google-chrome"),
            headless=True,args=["--no-sandbox"])
        try:
            context=browser.new_context(viewport={"width":720,"height":1280},
                                         device_scale_factor=1,has_touch=True)
            upper=context.new_page();lower=context.new_page()
            errors=[]
            upper.on("pageerror",lambda e:errors.append("upper:"+str(e)))
            lower.on("pageerror",lambda e:errors.append("lower:"+str(e)))
            assert upper.goto(f"{base}/terminal?token={token}").status==200
            upper.wait_for_selector('body[data-connected="yes"]',timeout=15000)
            wait_for(upper,"window.hsUpper.text().includes('bash-5.2$')")
            assert lower.goto(f"{base}/keyboard?token={token}").status==200
            lower.wait_for_selector('body[data-connected="yes"]',timeout=12000)
            assert upper.url.split("?")[0]!=lower.url.split("?")[0]
            assert upper.evaluate("window.hsUpper.cells().cols")>=24
            assert lower.locator(".key").count()>=25

            for key in ("p","w","d","ENTER"):tap(lower,key)
            wait_for(upper,"window.hsUpper.text().includes('/work')")
            assert lower.evaluate("window.hsLower.count()")==4

            # Use the independent symbol keyboard page, not the terminal page.
            lower.locator("#symbols").tap()
            assert lower.evaluate("window.hsLower.layer()")=="symbols"
            for key in ("1","2","3"):tap(lower,key)
            lower.locator("#letters").tap();tap(lower,"ENTER")
            wait_for(upper,"window.hsUpper.text().includes('123')")

            lower.evaluate("window.hsLower.send('nano dual_probe.txt\\r')")
            wait_for(upper,"window.hsUpper.text().includes('GNU nano')")
            for key in ("h","s","SPACE","d","u","a","l"):tap(lower,key)
            tap(lower,"CTRL");tap(lower,"o")
            wait_for(upper,"window.hsUpper.text().includes('Write to File:')")
            tap(lower,"ENTER");tap(lower,"CTRL");tap(lower,"x")
            wait_for(upper,"window.hsUpper.text().includes('bash-5.2$')")
            content=(fixture.root/"work/dual_probe.txt").read_text()
            assert content=="hs dual\n",repr(content)

            lower.evaluate("window.hsLower.send('tmux new -s hs_dual\\r')")
            wait_for(upper,"window.hsUpper.text().includes('0:bash')")
            tap(lower,"TMUX");tap(lower,"d")
            wait_for(upper,"window.hsUpper.text().includes('[detached')")

            assert upper.evaluate("typeof window.hsUpper.send")=="undefined"
            assert lower.evaluate("typeof window.hsLower.text")=="undefined"
            output=upper.evaluate("window.hsUpper.outputBytes()")
            touches=lower.evaluate("window.hsLower.count()")
            assert output>300
            upper.screenshot(path=str(EVIDENCE/"upper_terminal_720x1280.png"),full_page=True)
            lower.screenshot(path=str(EVIDENCE/"lower_keyboard_720x1280.png"),full_page=True)
            assert errors==[],errors
            return {"two_separate_720x1280_browser_pages":True,
                    "two_distinct_websockets":True,
                    "physical_dual_DSI_tested":False,
                    "upper_cells":upper.evaluate("window.hsUpper.cells()"),
                    "lower_touch_events":touches,
                    "symbol_layer_to_real_shell":True,
                    "real_nano_file":content.strip(),
                    "tmux_detach":True,"upper_output_bytes":output,
                    "terminal_has_no_input_API":True,
                    "keyboard_has_no_output_API":True,
                    "javascript_errors":errors}
        finally:
            browser.close()

async def security_test(base,token):
    async with ClientSession() as session:
        for page in ("/terminal","/keyboard"):
            async with session.get(base+page) as res:assert res.status==403
        for ws in ("/terminal/ws","/keyboard/ws"):
            try:
                async with session.ws_connect(base+ws+"?token=bad"):
                    raise AssertionError("wrong token accepted")
            except WSServerHandshakeError as e:assert e.status==403
        try:
            async with session.ws_connect(base+"/keyboard/ws?token="+token):
                raise AssertionError("blind keyboard permitted")
        except WSServerHandshakeError as e:assert e.status==409
        try:
            async with session.ws_connect(base+"/terminal/ws?token="+token,
                    headers={"Origin":"https://unauthorized.example"}):
                raise AssertionError("cross-origin WS accepted")
        except WSServerHandshakeError as e:assert e.status==403
    return {"pages_require_bearer_token":True,
            "websockets_require_bearer_token":True,
            "keyboard_must_wait_for_terminal":True,
            "foreign_origin_blocked":True}

async def main():
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    result={}
    with tempfile.TemporaryDirectory(prefix="hs-two-pane-token-") as tmp:
        os.environ["HS_DUAL_URL_FILE"]=str(Path(tmp)/"url")
        async def on_ready(svc,port):
            base=f"http://127.0.0.1:{port}"
            result["security"]=await security_test(base,svc.token)
            result["browser"]=await asyncio.to_thread(browser_run,base,svc.token,svc.fixture)
            assert svc.keyboard_input_events>=12
            assert svc.terminal_output_bytes>300
        await serve_dual(on_ready=on_ready)
    report={"schema":"hs.two_independent_surface_local_ssh_integration.v1",
            "date":datetime.now(timezone.utc).date().isoformat(),
            "result":"TWO_SEPARATE_BROWSER_SURFACES_TO_REAL_OPENSSH_PASSED",
            "actual_CM5_tested":False,"actual_DSI_pair_tested":False,
            "battery_power_applied":False,"fabrication_authorized":False,
            **result}
    (EVIDENCE/"dual_surface_integration.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"result":report["result"],
          "actual_touch_events":report["browser"]["lower_touch_events"],
          "real_nano_file":report["browser"]["real_nano_file"],
          "physical_CM5_tested":report["actual_CM5_tested"]},indent=2))
if __name__=="__main__":asyncio.run(main())
