"""Pure Python contract for a proposed TOUCH-TO-PTY RS485 link.

Not firmware, no socket, serial, GPIO, user credentials or real equipment I/O.
"""
from __future__ import annotations

import hmac
import struct

MAGIC = 0xA5
VERSION = 1
TYPE_KEY = 1
TYPE_ACK = 2
MAX_PAYLOAD = 16
SPECIAL = {
    "ESC": b"\x1b", "TAB": b"\t", "ENTER": b"\r", "BACKSPACE": b"\x7f",
    "UP": b"\x1b[A", "DOWN": b"\x1b[B", "RIGHT": b"\x1b[C",
    "LEFT": b"\x1b[D", "DELETE": b"\x1b[3~", "HOME": b"\x1b[H", "END": b"\x1b[F",
}
SHIFT = {
    "1":"!", "2":"@", "3":"#", "4":"$", "5":"%", "6":"^", "7":"&",
    "8":"*", "9":"(", "0":")", "-":"_", "=":"+", "[":"{", "]":"}",
    ";":":", "'":'"', ",":"<", ".":">", "/":"?", "\\":"|",
}

def key_to_pty(key: str, modifiers: set[str]|frozenset[str]=frozenset()) -> bytes:
    """Reference control-key semantics; target LVGL UI still needs porting."""
    m = frozenset(modifiers)
    if not m.issubset({"CTRL","ALT","SHIFT"}):
        raise ValueError("Unsupported modifier")
    if key in SPECIAL:
        if "CTRL" in m or "SHIFT" in m:
            raise ValueError("Unmapped modifier for special key")
        result = SPECIAL[key]
    elif len(key) == 1 and 32 <= ord(key) <= 126:
        if "CTRL" in m:
            if not key.isalpha() or not key.isascii():
                raise ValueError("Ctrl supports A-Z only")
            result = bytes([ord(key.upper()) & 31])
        elif "SHIFT" in m:
            result = (key.upper() if key.isalpha() else SHIFT.get(key,key)).encode("ascii")
        else:
            result = key.encode("ascii")
    else:
        raise ValueError("Unsupported key")
    return b"\x1b"+result if "ALT" in m else result

def crc16(data: bytes) -> int:
    val=0xffff
    for b in data:
        val ^= b<<8
        for _ in range(8):
            val=((val<<1)^0x1021)&0xffff if val&0x8000 else (val<<1)&0xffff
    return val

def encode_frame(seq:int,payload:bytes=b"",kind:int=TYPE_KEY)->bytes:
    if not 0<=seq<=0xffff: raise ValueError("Sequence out of range")
    if kind not in (TYPE_KEY,TYPE_ACK): raise ValueError("Unsupported kind")
    if kind==TYPE_KEY and not 1<=len(payload)<=MAX_PAYLOAD: raise ValueError("Bad key length")
    if kind==TYPE_ACK and payload: raise ValueError("ACK payload must be empty")
    header=struct.pack("<BBBHB",MAGIC,VERSION,kind,seq,len(payload))+payload
    return header+struct.pack("<H",crc16(header))

def decode_frame(packet:bytes)->tuple[int,int,bytes]:
    if len(packet)<8: raise ValueError("Truncated")
    magic,version,kind,seq,n=struct.unpack_from("<BBBHB",packet)
    if magic!=MAGIC or version!=VERSION or kind not in (TYPE_KEY,TYPE_ACK):
        raise ValueError("Unexpected framing")
    if n>MAX_PAYLOAD or len(packet)!=n+8: raise ValueError("Invalid frame length")
    if kind==TYPE_KEY and n==0 or kind==TYPE_ACK and n!=0:
        raise ValueError("Wrong payload type")
    check=struct.unpack_from("<H",packet,6+n)[0]
    if crc16(packet[:6+n]) != check: raise ValueError("Invalid CRC")
    return kind,seq,packet[6:6+n]

class ReceiveOnce:
    """Proposed in-session duplicate suppression; needs reboot epoch protocol."""
    def __init__(self):
        self.expected=0
        self.last_ack=None
    def accept(self,frame:bytes)->tuple[bytes,bytes]:
        kind,seq,payload=decode_frame(frame)
        if kind!=TYPE_KEY:raise ValueError("Not a key")
        if seq==((self.expected-1)&0xffff) and self.last_ack is not None:
            return b"",self.last_ack
        if seq!=self.expected:raise ValueError("Out-of-order event")
        ack=encode_frame(seq,kind=TYPE_ACK)
        self.expected=(self.expected+1)&0xffff
        self.last_ack=ack
        return payload,ack

def verify_pinned_hostkey(expected:bytes,observed:bytes|None)->bool:
    """Pre-auth rejection contract: source implementation MUST pin real host key."""
    return isinstance(expected,bytes) and isinstance(observed,bytes) and (
        len(expected)==len(observed)==32 and hmac.compare_digest(expected,observed)
    )
