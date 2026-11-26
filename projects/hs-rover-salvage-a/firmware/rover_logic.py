# Rover control logic, no hardware calls: runs on MicroPython (ESP32-C3) and on a PC for tests and simulation.
# Two brushed motors on a DRV8833 (IN1/IN2 per motor), battery voltage through a resistor divider, a dead-man stop.

MAX_PULSE_MS = 2000


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def max_duty(motor_v_max, battery_v):
    """Toy motors are made for their own battery (often 3-6 V). Limit the PWM so the average voltage stays there."""
    if not battery_v or battery_v <= 0:
        battery_v = 8.4  # a full 2S pack, the worst case
    return clamp(motor_v_max / battery_v, 0.0, 1.0)


def bridge(speed, limit):
    """Speed -1..1 to (IN1, IN2) duty 0..65535 for one DRV8833 channel: forward drives IN1, reverse IN2, 0 coasts."""
    speed = clamp(speed, -1.0, 1.0)
    duty = int(abs(speed) * limit * 65535)
    if speed > 0:
        return duty, 0
    if speed < 0:
        return 0, duty
    return 0, 0


def battery_volts(adc_uv, divider_ratio):
    return adc_uv / 1000000.0 * divider_ratio


def parse_query(path):
    q = {}
    if "?" in path:
        for part in path.split("?", 1)[1].split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                q[k] = v
    return q


class Rover:
    def __init__(self, cfg):
        self.cfg = cfg
        self.left = 0.0
        self.right = 0.0
        self.until_ms = 0
        self.commands = 0
        self.refused = 0
        self.deadman_stops = 0
        self.battery_v = None
        self.started_ms = None

    def low_battery(self):
        return self.battery_v is not None and self.battery_v < self.cfg["cutoff_v"]

    def tick(self, now_ms, battery_v=None):
        """Called often. Stops the motors when the last command's time is up, or the battery is low."""
        if self.started_ms is None:
            self.started_ms = now_ms
        if battery_v is not None:
            self.battery_v = battery_v
        moving = self.left != 0 or self.right != 0
        if moving and (now_ms >= self.until_ms or self.low_battery()):
            self.left = self.right = 0.0
            self.deadman_stops += 1
        limit = max_duty(self.cfg["motor_v_max"], self.battery_v)
        return bridge(self.left, limit), bridge(self.right, limit)

    def status(self, now_ms):
        return {"left": self.left, "right": self.right, "moving": self.left != 0 or self.right != 0,
                "battery_v": None if self.battery_v is None else round(self.battery_v, 2), "low_battery": self.low_battery(),
                "cutoff_v": self.cfg["cutoff_v"], "max_duty": round(max_duty(self.cfg["motor_v_max"], self.battery_v), 3),
                "commands": self.commands, "refused": self.refused, "deadman_stops": self.deadman_stops,
                "uptime_s": 0 if self.started_ms is None else (now_ms - self.started_ms) // 1000,
                "phone_stream_url": self.cfg.get("phone_stream_url", "")}

    def handle(self, path, now_ms):
        """One HTTP request path to (status code, content type, body)."""
        route = path.split("?", 1)[0]
        if route == "/drive":
            q = parse_query(path)
            try:
                left = clamp(float(q.get("l", "0")), -1.0, 1.0)
                right = clamp(float(q.get("r", "0")), -1.0, 1.0)
                ms = int(clamp(int(q.get("ms", str(self.cfg["deadman_ms"]))), 0, MAX_PULSE_MS))
            except ValueError:
                self.refused += 1
                return 400, "application/json", '{"error": "l and r are -1..1, ms is milliseconds"}'
            if self.low_battery():
                self.refused += 1
                return 503, "application/json", '{"error": "battery below cutoff; charge it"}'
            self.left, self.right, self.until_ms = left, right, now_ms + ms
            self.commands += 1
            return 200, "application/json", '{"ok": true}'
        if route == "/stop":
            self.left = self.right = 0.0
            self.until_ms = now_ms
            return 200, "application/json", '{"ok": true}'
        if route == "/status":
            return 200, "application/json", _json(self.status(now_ms))
        if route == "/":
            return 200, "text/html", page(self.cfg.get("phone_stream_url", ""))
        return 404, "text/plain", "not found"


def _json(d):
    try:
        import json
    except ImportError:  # pragma: no cover - MicroPython ships json as ujson on some builds
        import ujson as json
    return json.dumps(d)


def page(stream_url):
    return """<!doctype html><html><head><meta name=viewport content="width=device-width,initial-scale=1">
<title>HS salvage rover</title><style>body{font-family:sans-serif;margin:0;background:#111;color:#eee;text-align:center}
img{width:100%;max-width:640px;background:#000;min-height:200px}button{width:30%;height:70px;font-size:28px;margin:4px}
#s{font-size:14px;padding:6px}</style></head><body>
<img id=v src="STREAM" alt="phone camera (set phone_stream_url in config.json)">
<div><button data-l=0.6 data-r=0.6>&#8593;</button></div>
<div><button data-l=-0.5 data-r=0.5>&#8592;</button><button data-l=0 data-r=0>&#9632;</button><button data-l=0.5 data-r=-0.5>&#8594;</button></div>
<div><button data-l=-0.5 data-r=-0.5>&#8595;</button></div><div id=s></div>
<script>
let t=null;function go(l,r){fetch('/drive?l='+l+'&r='+r+'&ms=400')}
document.querySelectorAll('button').forEach(b=>{const l=b.dataset.l,r=b.dataset.r;
b.onpointerdown=()=>{go(l,r);t=setInterval(()=>go(l,r),250)};b.onpointerup=b.onpointerleave=()=>{clearInterval(t);fetch('/stop')}});
setInterval(()=>fetch('/status').then(r=>r.json()).then(j=>{document.getElementById('s').textContent=
'battery '+j.battery_v+' V'+(j.low_battery?' LOW: charge':'')+' | commands '+j.commands+' | stops '+j.deadman_stops}),1000);
</script></body></html>""".replace("STREAM", stream_url)
