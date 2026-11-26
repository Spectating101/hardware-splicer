# HS salvage rover, MicroPython on an ESP32-C3. Copy main.py, rover_logic.py and config.json to the board.
# Joins your Wi-Fi (or makes its own network "hs-rover" if it cannot), serves the drive page on port 80, and stops the
# motors on its own when commands stop coming or the battery runs low.
import json
import socket
import time

import network
from machine import ADC, PWM, Pin

import rover_logic

DEFAULTS = {"wifi_ssid": "", "wifi_password": "", "ap_password": "salvage-rover",
            "pins": {"ain1": 4, "ain2": 5, "bin1": 6, "bin2": 7, "vbat_adc": 3},
            "divider_ratio": 4.03, "motor_v_max": 4.8, "cutoff_v": 6.4, "deadman_ms": 600, "pwm_hz": 20000,
            "phone_stream_url": ""}


def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open("config.json") as fh:
            cfg.update(json.load(fh))
    except OSError:
        pass
    return cfg


def wifi(cfg):
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    if cfg["wifi_ssid"]:
        sta.connect(cfg["wifi_ssid"], cfg["wifi_password"])
        for _ in range(40):
            if sta.isconnected():
                print("joined Wi-Fi, open http://%s/" % sta.ifconfig()[0])
                return sta.ifconfig()[0]
            time.sleep(0.25)
    sta.active(False)
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid="hs-rover", password=cfg["ap_password"])
    print("own network hs-rover, open http://%s/" % ap.ifconfig()[0])
    return ap.ifconfig()[0]


def main():
    cfg = load_config()
    p = cfg["pins"]
    outs = [PWM(Pin(p[k]), freq=cfg["pwm_hz"], duty_u16=0) for k in ("ain1", "ain2", "bin1", "bin2")]
    adc = ADC(Pin(p["vbat_adc"]))
    adc.atten(ADC.ATTN_11DB)
    rover = rover_logic.Rover(cfg)

    def apply(now):
        vbat = rover_logic.battery_volts(adc.read_uv(), cfg["divider_ratio"])
        (a1, a2), (b1, b2) = rover.tick(now, vbat)
        for pwm, duty in zip(outs, (a1, a2, b1, b2)):
            pwm.duty_u16(duty)

    wifi(cfg)
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", 80))
    srv.listen(2)
    srv.settimeout(0.05)
    while True:
        apply(time.ticks_ms())
        try:
            conn, _ = srv.accept()
        except OSError:
            continue
        try:
            conn.settimeout(1.0)
            line = conn.recv(1024).decode().split("\r\n", 1)[0]
            parts = line.split(" ")
            path = parts[1] if len(parts) > 1 else "/"
            code, ctype, body = rover.handle(path, time.ticks_ms())
            apply(time.ticks_ms())
            conn.send("HTTP/1.0 %d OK\r\nContent-Type: %s\r\nAccess-Control-Allow-Origin: *\r\nConnection: close\r\n\r\n" % (code, ctype))
            conn.sendall(body)
        except OSError:
            pass
        finally:
            conn.close()


if __name__ == "__main__":
    main()
