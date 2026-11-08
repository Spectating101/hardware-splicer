"""Local-only HS dual-panel terminal experiment, xterm.js over real pinned SSH.

Nothing here is evidence of CM4, DSI, touch electronics or physical timing.
Only the supplied short-lived loopback sandbox is connected. Never expose
this test server to LAN/Internet or substitute a production user's SSH keys.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import errno
import fcntl
import json
import os
from pathlib import Path
import pty
import secrets
import signal
import struct
import subprocess
import sys
import termios
from typing import Any

from aiohttp import web

from loopback_ssh import LoopbackSSH

HERE=Path(__file__).resolve().parent
ASSET_DIR=HERE/"web"
ASSET={
    "/":ASSET_DIR/"index.html",
    "/app.js":ASSET_DIR/"app.js",
    "/app.css":ASSET_DIR/"app.css",
    "/vendor/xterm.js":ASSET_DIR/"node_modules/@xterm/xterm/lib/xterm.js",
    "/vendor/xterm.css":ASSET_DIR/"node_modules/@xterm/xterm/css/xterm.css",
    "/vendor/fit.js":ASSET_DIR/"node_modules/@xterm/addon-fit/lib/addon-fit.js",
}
TYPES={".html":"text/html", ".js":"application/javascript", ".css":"text/css"}
HEADERS={
    "Cache-Control":"no-store",
    "X-Content-Type-Options":"nosniff",
    "Referrer-Policy":"no-referrer",
    "X-Frame-Options":"DENY",
    "Content-Security-Policy":"default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self' ws://127.0.0.1:*; img-src 'self' data:; font-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
}
MAX_INPUT=2048


class TerminalSession:
    def __init__(self, command:list[str],ws:web.WebSocketResponse,
                 output_callback=None):
        self.command=command
        self.ws=ws
        self.output_callback=output_callback
        self.proc: subprocess.Popen | None=None
        self.master: int | None=None
        self.send_task: asyncio.Task | None=None
        self.out=asyncio.Queue(maxsize=128)
        self.loop=asyncio.get_running_loop()

    async def start(self)->None:
        master, slave=pty.openpty()
        self.master=master
        try:
            self.proc=subprocess.Popen(self.command,stdin=slave,stdout=slave,
                                       stderr=slave,start_new_session=True,
                                       env={**os.environ,"TERM":"xterm-256color"})
        finally:
            os.close(slave)
        self.set_size(90,24)
        self.send_task=asyncio.create_task(self.send_loop())
        self.loop.add_reader(master,self.on_readable)

    def set_size(self,cols:int,rows:int)->None:
        assert self.master is not None
        cols=max(24,min(int(cols),240))
        rows=max(6,min(int(rows),100))
        fcntl.ioctl(self.master,termios.TIOCSWINSZ,struct.pack("HHHH",rows,cols,0,0))

    def on_readable(self)->None:
        assert self.master is not None
        try:
            data=os.read(self.master,16384)
        except OSError as e:
            if e.errno!=errno.EIO:raise
            data=b""
        if not data:
            self.loop.remove_reader(self.master)
            self.out.put_nowait(None)
            return
        try:
            self.out.put_nowait(data)
        except asyncio.QueueFull:
            self.loop.remove_reader(self.master)
            # Do not silently discard terminal output, close instead.
            self.loop.create_task(self.ws.close(code=1011,message=b"output_backpressure"))

    async def send_loop(self)->None:
        while True:
            item=await self.out.get()
            if item is None:
                if not self.ws.closed:
                    await self.ws.close(code=1000,message=b"ssh_session_ended")
                break
            if self.ws.closed:break
            if self.output_callback is not None:
                await self.output_callback(item)
            else:
                await self.ws.send_bytes(item)

    def write(self,value:str)->None:
        if not isinstance(value,str) or len(value.encode("utf8"))>MAX_INPUT:
            raise ValueError("terminal input must be <=2048 bytes")
        if self.master is None:raise RuntimeError("no tty")
        os.write(self.master,value.encode("utf8"))

    async def close(self)->None:
        if self.master is not None:
            with contextlib.suppress(Exception):
                self.loop.remove_reader(self.master)
            os.close(self.master)
            self.master=None
        if self.send_task is not None:
            self.send_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.send_task
        if self.proc is not None and self.proc.poll() is None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(self.proc.pid,signal.SIGTERM)
            try:
                await asyncio.wait_for(asyncio.to_thread(self.proc.wait),timeout=2)
            except asyncio.TimeoutError:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(self.proc.pid,signal.SIGKILL)
                await asyncio.to_thread(self.proc.wait)
        self.proc=None


class DemoServer:
    def __init__(self,fixture:LoopbackSSH):
        self.fixture=fixture
        self.token=secrets.token_urlsafe(32)
        self.active=False
        self.page_views=0

    def allowed(self,req:web.Request,*,require_token:bool=True)->bool:
        remote=req.remote
        host=req.headers.get("Host","")
        local=(remote in ("127.0.0.1","::1") and
               host.rsplit(":",1)[0] in ("127.0.0.1","localhost"))
        return local and (not require_token or
                          secrets.compare_digest(req.query.get("token",""),self.token))

    async def static(self,req:web.Request)->web.Response:
        # Asset scripts are inert; the HTML route and live SSH websocket
        # require the random per-run token. Browser subresources do not
        # inherit the page query string.
        if not self.allowed(req,require_token=req.path=="/"):
            raise web.HTTPForbidden(reason="local token required")
        resource=req.path
        path=ASSET.get(resource)
        if not path or not path.is_file():raise web.HTTPNotFound()
        self.page_views+=1
        return web.FileResponse(path,headers=HEADERS)

    async def socket(self,req:web.Request)->web.WebSocketResponse:
        if not self.allowed(req):raise web.HTTPForbidden(reason="local token required")
        origin=req.headers.get("Origin")
        if origin not in (None,f"http://127.0.0.1:{req.url.port}",
                          f"http://localhost:{req.url.port}"):
            raise web.HTTPForbidden(reason="cross-origin websocket forbidden")
        if self.active:raise web.HTTPConflict(reason="single isolated session only")
        self.active=True
        ws=web.WebSocketResponse(max_msg_size=MAX_INPUT*4,heartbeat=15)
        session=None
        try:
            await ws.prepare(req)
            session=TerminalSession(self.fixture.ssh_command(),ws)
            await session.start()
            await ws.send_json({"type":"status","value":"connected","mode":"real_ssh_loopback"})
            async for msg in ws:
                if msg.type==web.WSMsgType.TEXT:
                    try:
                        event=json.loads(msg.data)
                        if event.get("type")=="input":
                            session.write(event.get("data"))
                        elif event.get("type")=="resize":
                            session.set_size(event["cols"],event["rows"])
                        else:
                            await ws.send_json({"type":"error","value":"unsupported_event"})
                    except (TypeError,ValueError,KeyError,OverflowError) as e:
                        await ws.send_json({"type":"error","value":"invalid_or_oversized_event"})
                elif msg.type==web.WSMsgType.ERROR:break
        finally:
            if session is not None:await session.close()
            self.active=False
        return ws

    def app(self)->web.Application:
        app=web.Application(client_max_size=16384)
        app.router.add_get("/ws",self.socket)
        for route in ASSET:
            app.router.add_get(route,self.static)
        return app


async def serve(port:int=0,on_ready=None)->None:
    with LoopbackSSH() as fixture:
        service=DemoServer(fixture)
        app=service.app()
        runner=web.AppRunner(app,access_log=None)
        await runner.setup()
        site=web.TCPSite(runner,"127.0.0.1",port)
        await site.start()
        assert site._server is not None
        bound_port=site._server.sockets[0].getsockname()[1]
        url=f"http://127.0.0.1:{bound_port}/?token={service.token}"
        url_file=os.environ.get("HS_WORKFLOW_URL_FILE")
        if url_file:
            # Runtime-only capability URL; never committed to Git or printed
            # by browser automation scripts.
            path=Path(url_file)
            path.write_text(url+"\n")
            path.chmod(0o600)
        print(json.dumps({"url":url if not url_file else "stored_in_private_runtime_file","mode":"local_only_sandboxed_real_ssh",
              "external_network":False,"device_hardware_qualified":False}),
              flush=True)
        try:
            if on_ready is not None:
                await on_ready(service,bound_port)
            else:
                await asyncio.Event().wait()
        finally:
            await runner.cleanup()
            if url_file:
                Path(url_file).unlink(missing_ok=True)


def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument("--port",type=int,default=0)
    args=p.parse_args()
    asyncio.run(serve(args.port))


if __name__=="__main__":
    main()
