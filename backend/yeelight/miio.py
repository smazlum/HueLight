"""Xiaomi miIO protokolü (UDP 54321). Yalnızca ilk kurulum için: ev Wi-Fi'sini ve LAN Control'ü ampule yazar."""
import hashlib
import json
import re
import socket
import struct
import subprocess
import time

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

PORT = 54321
HELLO = bytes.fromhex("21310020" + "ff" * 28)
_HEADER = struct.Struct(">HHIII")  # magic, uzunluk, bilinmeyen, cihaz no, zaman damgası


class MiioError(Exception):
    pass


def _md5(data: bytes) -> bytes:
    return hashlib.md5(data).digest()


def _cipher(token: bytes) -> Cipher:
    key = _md5(token)
    return Cipher(algorithms.AES(key), modes.CBC(_md5(key + token)))


def encrypt(token: bytes, plain: bytes) -> bytes:
    padder = padding.PKCS7(128).padder()
    enc = _cipher(token).encryptor()
    return enc.update(padder.update(plain) + padder.finalize()) + enc.finalize()


def decrypt(token: bytes, data: bytes) -> bytes:
    dec = _cipher(token).decryptor()
    unpadder = padding.PKCS7(128).unpadder()
    return unpadder.update(dec.update(data) + dec.finalize()) + unpadder.finalize()


def build_packet(token: bytes, did: int, stamp: int, payload: dict) -> bytes:
    data = encrypt(token, json.dumps(payload).encode())
    header = _HEADER.pack(0x2131, 32 + len(data), 0, did, stamp)
    return header + _md5(header + token + data) + data


def parse_packet(token: bytes, packet: bytes) -> dict:
    header, checksum, data = packet[:16], packet[16:32], packet[32:]
    if _md5(header + token + data) != checksum:
        raise MiioError("Sağlama hatası: token yanlış")
    return json.loads(decrypt(token, data).rstrip(b"\x00").decode())


def parse_hello(packet: bytes) -> tuple[int, int, bytes | None]:
    """Cevaptan (cihaz no, zaman damgası, token) çıkarır. Token gizliyse (ff.. / 00..) None."""
    if len(packet) < 32 or packet[:2] != b"\x21\x31":
        raise MiioError("Geçersiz hello cevabı")
    _, _, _, did, stamp = _HEADER.unpack(packet[:16])
    token = packet[16:32]
    return did, stamp, None if token in (b"\xff" * 16, b"\x00" * 16) else token


BROADCAST = "255.255.255.255"
AP_GATEWAY = "192.168.13.1"  # Xiaomi cihazlarının kurulum ağındaki sabit adresi


def _plan(target: str) -> dict[str, list[str]]:
    """Kaynak adres → hello gönderilecek hedefler.

    Bağlanmamış ("") soket her zaman var: Windows ağ değişince eski kart adresini döndürebiliyor,
    o adrese bağlanamayan soket sessizce düşer ve hiç paket gitmez. Kart adresleri ise
    Ethernet de bağlıyken yayının Wi-Fi'den de çıkması için ayrıca denenir.
    """
    if target != BROADCAST:
        return {"": [target]}
    ips = _local_ipv4s()
    # Kurulum ağında ampul aynı zamanda ağ geçididir (ör. PC 192.168.10.2 → ampul 192.168.10.1).
    # Yayına cevap vermeyen donanım yazılımları doğrudan adrese sorulunca cevap veriyor.
    direct = sorted(set(_gateways()) | {ip.rsplit(".", 1)[0] + ".1" for ip in ips} | {AP_GATEWAY})
    plan = {"": [BROADCAST, *direct] + [ip.rsplit(".", 1)[0] + ".255" for ip in ips]}
    for ip in ips:
        plan[ip] = [BROADCAST, ip.rsplit(".", 1)[0] + ".255", *(g for g in direct if g.rsplit(".", 1)[0] == ip.rsplit(".", 1)[0])]
    return plan


def _gateways() -> list[str]:
    """Varsayılan ağ geçitleri, `route print` çıktısından (dil bağımsız: yalnızca sayısal satırlar okunur)."""
    try:
        out = subprocess.run(["route", "print", "-4"], capture_output=True, text=True, timeout=3).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [m.group(1) for m in re.finditer(r"^\s*0\.0\.0\.0\s+0\.0\.0\.0\s+(\d+\.\d+\.\d+\.\d+)\s", out, re.M)]


def discover(target: str = BROADCAST, timeout: float = 3.0, port: int = PORT, trace: list | None = None) -> list[dict]:
    """Hello gönderir, cevap veren miIO cihazlarını döner: {ip, did, stamp, token}.

    `trace` verilirse ne gönderildiği ve ne geldiği (bozuk paketler dahil) içine yazılır; tanı kaydı için.
    """
    note = trace.append if trace is not None else (lambda _: None)
    socks = []
    for src, targets in _plan(target).items():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.bind((src, 0))
            s.setblocking(False)
        except OSError as e:
            note(f"kaynak {src or '*'} açılamadı: {e}")
            s.close()
            continue
        for dst in targets:
            try:
                for _ in range(3):
                    s.sendto(HELLO, (dst, port))
                note(f"{src or '*'} → {dst}:{port} gönderildi")
            except OSError as e:
                note(f"{src or '*'} → {dst}:{port} gönderilemedi: {e}")
        socks.append(s)
    found: dict[int, dict] = {}
    end = time.monotonic() + timeout
    try:
        while time.monotonic() < end:
            for s in socks:
                try:
                    packet, (ip, _) = s.recvfrom(1024)
                except BlockingIOError:
                    continue
                except ConnectionResetError:
                    # Windows: hedef "port kapalı" (ICMP) döndü; cihaz var ama 54321'i dinlemiyor.
                    note("bir hedeften 'port kapalı' cevabı geldi")
                    continue
                try:
                    did, stamp, token = parse_hello(packet)
                except MiioError:
                    note(f"{ip} geçersiz paket: {packet[:48].hex()}")
                    continue
                note(f"{ip} cevap verdi: did={did:#x} token={'var' if token else 'gizli'}")
                found[did] = {"ip": ip, "did": did, "stamp": stamp, "token": token, "at": time.monotonic()}
            time.sleep(0.05)
    finally:
        for s in socks:
            s.close()
    return list(found.values())


def _local_ipv4s() -> list[str]:
    from .discovery import local_ipv4s
    return local_ipv4s()


def send(device: dict, token: bytes, method: str, params, timeout: float = 5.0, port: int = PORT):
    """`discover()` ile bulunan cihaza tek bir şifreli komut gönderir, `result` döner. Ampul `error` dönerse MiioError."""
    # Ampul, kendi saatinden geride kalan zaman damgalı paketleri yok sayar.
    stamp = device["stamp"] + int(time.monotonic() - device["at"]) + 1
    msg_id = int(time.time()) % 100000
    packet = build_packet(token, device["did"], stamp, {"id": msg_id, "method": method, "params": params})
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        for _ in range(3):  # UDP: cevap gelmezse iki kez daha dene
            sock.sendto(packet, (device["ip"], port))
            try:
                reply = parse_packet(token, sock.recvfrom(4096)[0])
            except socket.timeout:
                continue
            if "error" in reply:
                raise MiioError(reply["error"].get("message", str(reply["error"])))
            return reply.get("result")
    finally:
        sock.close()
    raise MiioError(f"{ip} cevap vermedi")
