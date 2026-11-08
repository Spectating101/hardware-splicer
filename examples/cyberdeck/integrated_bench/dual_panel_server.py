"""First HS *two independent display surfaces* terminal bench.

This is TWO browser windows/pages, not a single 720x2560 CSS split. Each panel
has its own WS and input role. Keyboard connects to an actual OpenSSH PTY
owned by the terminal display; keyboard NEVER sees terminal output.

Only a temporary loopback OpenSSH/bwrap test target is permitted here. No
Internet-facing listener, real personal SSH credentials, Li-ion work, or CM5
hardware is involved. Keep this protocol separate from production networking.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
from pathlib import Path
import secrets
from aiohttp import web

import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"workflow_lab"))
from loopback_ssh import LoopbackSSH
from server import DemoServer, TerminalSession, HEADERS, ASSET as BASE_ASSETS

HERE=Path(__file__).resolve().parent
APP_ASSETS={
    "/terminal":HERE/"web/terminal.html",
    "/keyboard":HERE/"web/keyboard.html",
    "/terminal.js":HERE/"web/terminal.js",
    "/keyboard.js":HERE/"web/keyboard.js",
    "/panel.css":HERE/"web/panel.css",
    "/vendor/xterm.js":BASE_ASSETS["/vendor/xterm.js"],
    "/vendor/xterm.css":BASE_ASSETS["/vendor/xterm.css"],
    "/vendor/fit.js":BASE_ASSETS["/vendor/fit.js"],
}
BROWSER_ROUTES={"/terminal","/keyboard"}


class DualPanelServer(DemoServer):
    def __init__(self,fixture:LoopbackSSH):
        super().__init__(fixture)
        self.terminal_ws: web.WebSocketResponse|None=None
        self.keyboard_ws: web.WebSocketResponse|None=None
        self.session: TerminalSession|None=None
        self.keyboard_input_events=0
        self.terminal_output_bytes=0

    def checked_origin(self,req:web.Request)->bool:
        origin=req.headers.get("Origin")
        return origin in (None,f"http://127.0.0.1:{req.url.port}",
                          f"http://localhost:{req.url.port}")

    async def static_panel(self,req:web.Request)->web.StreamResponse:
        if not self.allowed(req,require_token=req.path in BROWSER_ROUTES):
            raise web.HTTPForbidden(reason="local capability URL required")
        path=APP_ASSETS.get(req.path)
        if path is None or not path.is_file():
            raise web.HTTPNotFound()
        return web.FileResponse(path,headers=HEADERS)

    async def terminal(self,req:web.Request)->web.WebSocketResponse:
        if not self.allowed(req) or not self.checked_origin(req):
            raise web.HTTPForbidden(reason="local token and same origin required")
        if self.terminal_ws is not None or self.session is not None:
            raise web.HTTPConflict(reason="one trusted terminal process only")
        ws=web.WebSocketResponse(max_msg_size=8192,heartbeat=12)
        await ws.prepare(req)
        self.terminal_ws=ws
        try:
            async def emit(data:bytes):
                self.terminal_output_bytes+=len(data)
                await ws.send_bytes(data)
            session=TerminalSession(self.fixture.ssh_command(),ws,output_callback=emit)
            self.session=session
            await session.start()
            await ws.send_json({"type":"status","value":"connected",
                                "role":"terminal","sandboxed_real_ssh":True})
            async for msg in ws:
                if msg.type==web.WSMsgType.TEXT:
                    try:
                        event=json.loads(msg.data)
                        # Terminal owns PTY sizing but may NOT send input.
                        if event.get("type")=="resize":
                            session.set_size(event["cols"],event["rows"])
                        else:
                            await ws.send_json({"type":"error","value":"terminal_input_forbidden_use_keyboard"})
                    except (ValueError,TypeError,KeyError,OverflowError):
                        await ws.send_json({"type":"error","value":"invalid_event"})
                elif msg.type==web.WSMsgType.ERROR:
                    break
        finally:
            self.session=None
            self.terminal_ws=None
            if self.keyboard_ws is not None and not self.keyboard_ws.closed:
                await self.keyboard_ws.send_json({"type":"status","value":"terminal_disconnected"})
            if "session" in locals():
                await session.close()
        return ws

    async def keyboard(self,req:web.Request)->web.WebSocketResponse:
        if not self.allowed(req) or not self.checked_origin(req):
            raise web.HTTPForbidden(reason="local token and same origin required")
        if self.keyboard_ws is not None:
            raise web.HTTPConflict(reason="one independent input surface only")
        # Cannot type into a process without an actively connected output
        # surface. Deny pre-connection rather than buffering blind key input.
        if self.session is None or self.terminal_ws is None or self.terminal_ws.closed:
            raise web.HTTPConflict(reason="terminal display must connect first")
        ws=web.WebSocketResponse(max_msg_size=8192,heartbeat=12)
        await ws.prepare(req)
        self.keyboard_ws=ws
        await ws.send_json({"type":"status","value":"connected","role":"keyboard"})
        try:
            async for msg in ws:
                if msg.type!=web.WSMsgType.TEXT:
                    if msg.type==web.WSMsgType.ERROR:
                        break
                    continue
                try:
                    event=json.loads(msg.data)
                    if event.get("type")=="input":
                        value=event["data"]
                        if (self.session is None or self.terminal_ws is None
                            or self.terminal_ws.closed):
                            await ws.send_json({"type":"error","value":"terminal_not_available"})
                        else:
                            self.session.write(value)
                            self.keyboard_input_events+=1
                    else:
                        await ws.send_json({"type":"error","value":"keyboard_cannot_resize_or_read_output"})
                except (ValueError,TypeError,KeyError,OverflowError):
                    await ws.send_json({"type":"error","value":"invalid_event"})
        finally:
            self.keyboard_ws=None
        return ws

    def app(self)->web.Application:
        app=web.Application(client_max_size=16384)
        for route in APP_ASSETS:
            app.router.add_get(route,self.static_panel)
        app.router.add_get("/terminal/ws",self.terminal)
        app.router.add_get("/keyboard/ws",self.keyboard)
        return app


async def serve_dual(port:int=0,on_ready=None)->None:
    with LoopbackSSH() as fixture:
        service=DualPanelServer(fixture)
        runner=web.AppRunner(service.app(),access_log=None)
        await runner.setup()
        site=web.TCPSite(runner,"127.0.0.1",port)
        await site.start()
        socket=site._server.sockets[0]
        bound=socket.getsockname()[1]
        # The token never appears in an artifact or a GitHub log.
        url_file=os.environ.get("HS_DUAL_URL_FILE")
        if url_file:
            loc=Path(url_file)
            loc.write_text(f"http://127.0.0.1:{bound}/terminal?token={service.token}\n")
            loc.chmod(0o600)
        metadata={"mode":"two_separate_browser_surfaces_real_local_SSH",
                  "port":bound,"url_saved_to_private_file":bool(url_file),
                  "physical_CM5_or_dual_DSI":False}
        if not url_file:
            metadata["upper_url"]=f"http://127.0.0.1:{bound}/terminal?token={service.token}"
            metadata["lower_url"]=f"http://127.0.0.1:{bound}/keyboard?token={service.token}"
        print(json.dumps(metadata),flush=True)
        try:
            if on_ready is not None:
                await on_ready(service,bound)
            else:
                await asyncio.Event().wait()
        finally:
            await runner.cleanup()
            if url_file:
                Path(url_file).unlink(missing_ok=True)


def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("--port",type=int,default=0)
    args=cli.parse_args()
    asyncio.run(serve_dual(args.port))


if __name__=="__main__":
    main()
