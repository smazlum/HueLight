"""Ağdaki Yeelight ampulleri SSDP ile bulur. Kullanım: python tools/probe.py [yerel_ip]"""
import socket, sys, time

LOCAL_IP = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
MSG = b'M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1982\r\nMAN: "ssdp:discover"\r\nST: wifi_bulb\r\n'

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
if LOCAL_IP != "0.0.0.0":
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(LOCAL_IP))
s.bind((LOCAL_IP, 0))
s.settimeout(1.0)
for _ in range(3):
    s.sendto(MSG, ("239.255.255.250", 1982))
    time.sleep(0.2)

found = {}
end = time.time() + 4
while time.time() < end:
    try:
        data, addr = s.recvfrom(4096)
    except socket.timeout:
        continue
    found[addr[0]] = data.decode(errors="replace")
for ip, txt in found.items():
    print("=== ", ip)
    print(txt)
if not found:
    print("Ampul bulunamadi")
