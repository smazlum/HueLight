"""Kurulumda seçilecek ev Wi-Fi ağları (Windows netsh).

Canlı tarama Windows'ta Konum hizmetleri açıksa çalışır; değilse PC'nin kayıtlı ağ profilleri kullanılır.
"""
import hmac
import re
import subprocess

SETUP_PREFIX = "yeelink-"  # ampulün kendi kurulum ağı listede gösterilmez


def _netsh(*args: str) -> str | None:
    try:
        r = subprocess.run(["netsh", "wlan", *args], capture_output=True, text=True, timeout=8,
                           encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def parse_scan(out: str) -> list[dict]:
    """`netsh wlan show networks mode=bssid` çıktısı → [{ssid, signal, band}]. Aynı ağın bantları birleşir."""
    nets: dict[str, dict] = {}
    current = None
    for line in out.splitlines():
        if m := re.match(r"^SSID \d+\s*:\s*(.*)$", line):
            current = m.group(1).strip()
            if current:
                nets.setdefault(current, {"ssid": current, "signal": 0, "bands": set()})
        elif current and (m := re.search(r"(?:Signal|Sinyal)\s*:\s*(\d+)%", line)):
            nets[current]["signal"] = max(nets[current]["signal"], int(m.group(1)))
        elif current and (m := re.search(r"(?:Channel|Kanal)\s*:\s*(\d+)", line)):
            nets[current]["bands"].add("5" if int(m.group(1)) > 14 else "2.4")
    return [{"ssid": n["ssid"], "signal": n["signal"], "supports_24": "2.4" in n["bands"] or not n["bands"]}
            for n in nets.values()]


def parse_profiles(out: str) -> list[str]:
    """`netsh wlan show profiles` → kullanıcı profilleri. Grup ilkesi profillerinde ':' olmadığından dışarıda kalır."""
    return [m.group(1).strip() for line in out.splitlines()
            if (m := re.match(r"^\s{2,}[^:]+?\s:\s(.+)$", line)) and m.group(1).strip()]


def _saved_key(ssid: str) -> str | None:
    """Windows'ta bu ağ için kayıtlı şifre (yönetici izni gerekmez). Yalnızca karşılaştırma için; hiçbir yere yazılmaz."""
    out = _netsh("show", "profile", f"name={ssid}", "key=clear")
    return parse_key(out) if out else None


def parse_key(out: str) -> str | None:
    m = re.search(r"^\s*(?:Key Content|Anahtar İçeriği)\s*:\s(.*)$", out, re.M)
    return m.group(1).strip() if m else None


def check_password(ssid: str, password: str) -> bool | None:
    """True: kayıtlı şifreyle aynı · False: farklı · None: doğrulanamadı (ağ bu PC'de kayıtlı değil)."""
    saved = _saved_key(ssid)
    if saved is None:
        return None
    return hmac.compare_digest(saved.encode(), password.encode())


def looks_5ghz(ssid: str) -> bool:
    return bool(re.search(r"5\s?g(hz)?\b", ssid, re.I))


def connected_ssids() -> list[str]:
    """Şu an bağlı ağların adları. Windows ağ profili adı Wi-Fi'de SSID'dir; Konum izni gerektirmez."""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-NetConnectionProfile).Name"],
                           capture_output=True, text=True, timeout=8, encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return []
    return [line.strip() for line in r.stdout.splitlines() if line.strip()]


def networks(home: str | None = None) -> dict:
    scan = _netsh("show", "networks", "mode=bssid")
    if scan:
        items = [{**n, "saved": False} for n in parse_scan(scan)]
        live = True
    else:
        items = [{"ssid": s, "signal": None, "supports_24": not looks_5ghz(s), "saved": True}
                 for s in parse_profiles(_netsh("show", "profiles") or "")]
        live = False
    items = [{**n, "home": n["ssid"] == home} for n in items if not n["ssid"].lower().startswith(SETUP_PREFIX)]
    items.sort(key=lambda n: (not n["home"], not n["supports_24"], -(n["signal"] or 0), n["ssid"].lower()))
    return {"live": live, "networks": items}
