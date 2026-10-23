"""Yeelight LAN Control mesajları: satır sonlu JSON, TCP 55443."""
import json

PORT = 55443
KELVIN_MIN, KELVIN_MAX = 1700, 6500
TRANSITION_MS = 300
PROPS = ["power", "bright", "color_mode", "rgb", "ct", "name", "flowing", "delayoff"]
# color_mode değerleri: 1 = rgb, 2 = ct, 3 = hsv
MODES = {"1": "rgb", "2": "ct", "3": "hsv"}


def encode(msg_id: int, method: str, params: list) -> bytes:
    return (json.dumps({"id": msg_id, "method": method, "params": params}) + "\r\n").encode()


def decode(line: bytes) -> dict:
    return json.loads(line.decode("utf-8", errors="replace"))


def hex_to_int(hex_color: str) -> int:
    return int(hex_color.lstrip("#"), 16)


def int_to_hex(value: int) -> str:
    return f"#{int(value):06X}"


def flow_expression(steps: list[tuple[int, int, int, int]]) -> str:
    """steps: (süre_ms, mod, değer, parlaklık). mod 1 = rgb, 2 = ct, 7 = bekle."""
    return ",".join(f"{max(d, 50)},{m},{v},{b}" for d, m, v, b in steps)


def parse_props(props: dict) -> dict:
    """Ampulün `props` bildirimini / get_prop cevabını durum alanlarına çevirir. Yalnızca gelen alanlar döner."""
    out = {}
    if "power" in props:
        out["power"] = props["power"] == "on"
    if props.get("bright"):
        out["brightness"] = int(props["bright"])
    if props.get("rgb"):
        out["hex"] = int_to_hex(int(props["rgb"]))
    if props.get("ct"):
        out["kelvin"] = int(props["ct"])
    # get_prop metin ("1"), props bildirimi sayı (1) döndürüyor: ikisi de kabul edilir.
    if str(props.get("color_mode")) in MODES:
        out["mode"] = MODES[str(props["color_mode"])]
    if "name" in props:
        out["bulb_name"] = props["name"]
    if "flowing" in props:
        out["flowing"] = str(props["flowing"]) == "1"
    if "delayoff" in props:
        minutes = int(props["delayoff"] or 0)
        out["timer_minutes_left"] = minutes or None
    return out
