"""Yeelight ampullerini SSDP benzeri multicast ile bulur (239.255.255.250:1982)."""
import asyncio
import ipaddress
import socket
import time

ADDR = ("239.255.255.250", 1982)
SEARCH = b'M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1982\r\nMAN: "ssdp:discover"\r\nST: wifi_bulb\r\n'


def _route_ip(dst: str) -> str | None:
    """dst'ye giden yolun yerel adresi. UDP connect paket göndermez, yalnızca yönlendirme tablosuna bakar."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((dst, 9))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def local_ipv4s() -> list[str]:
    """PC'nin özel ağdaki IPv4 adresleri (Wi-Fi, Ethernet, VPN). Keşif hepsinden yapılır."""
    # getaddrinfo, Wi-Fi ağ değiştirdiğinde eski adresi döndürebiliyor; yönlendirme tablosu her zaman güncel.
    ips = {info[4][0] for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)}
    ips |= {ip for dst in ("192.168.13.1", "8.8.8.8") if (ip := _route_ip(dst))}
    return sorted(ip for ip in ips if ipaddress.ip_address(ip).is_private
                  and not ipaddress.ip_address(ip).is_link_local and not ip.startswith("127."))


def parse_response(text: str) -> dict | None:
    headers = {}
    for line in text.splitlines()[1:]:
        key, sep, value = line.partition(":")
        if sep:
            headers[key.strip().lower()] = value.strip()
    location = headers.get("location", "")
    if not location.startswith("yeelight://") or "id" not in headers:
        return None
    host, _, port = location.removeprefix("yeelight://").partition(":")
    return {"id": headers["id"], "ip": host, "port": int(port or 55443), "model": headers.get("model", ""),
            "name": headers.get("name", ""), "props": headers}


def scan(timeout: float = 3.0) -> list[dict]:
    socks = []
    for ip in local_ipv4s():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        try:
            s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(ip))
            s.bind((ip, 0))
            s.setblocking(False)
            for _ in range(2):
                s.sendto(SEARCH, ADDR)
            socks.append(s)
        except OSError:
            s.close()
    found: dict[str, dict] = {}
    end = time.monotonic() + timeout
    try:
        while time.monotonic() < end:
            for s in socks:
                try:
                    data, _ = s.recvfrom(4096)
                except (BlockingIOError, ConnectionResetError):
                    continue
                bulb = parse_response(data.decode(errors="replace"))
                if bulb:
                    found[bulb["id"]] = bulb
            time.sleep(0.05)
    finally:
        for s in socks:
            s.close()
    return list(found.values())


async def scan_async(timeout: float = 3.0) -> list[dict]:
    return await asyncio.to_thread(scan, timeout)
