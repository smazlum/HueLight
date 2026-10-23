"""Sahte Yeelight ampul: LAN Control (TCP) + kurulum modundaki miIO (UDP) davranışını taklit eder.

Testlerde içe aktarılarak kullanılır. Elle denemek için:
    python -m tools.sim_bulb --port 55443
Sonra arayüzden "IP ile ekle": 127.0.0.1, port 55443.
"""
import argparse
import asyncio
import json
import os

from backend.yeelight import miio, protocol


class SimBulb:
    def __init__(self, quota: int | None = None, silent: bool = False):
        self.props = {"power": "off", "bright": "80", "color_mode": "2", "rgb": "16777215", "ct": "4000",
                      "name": "", "flowing": "0", "delayoff": "0"}
        self.commands: list[tuple[str, list]] = []
        self.quota = quota  # bu kadar komuttan sonra "client quota exceeded"
        self.silent = silent  # True: komutlara hiç cevap verme (zaman aşımı testi)
        self.port = 0
        self._clients: set[asyncio.StreamWriter] = set()
        self._server: asyncio.Server | None = None

    async def start(self, host: str = "127.0.0.1", port: int = 0):
        self._server = await asyncio.start_server(self._handle, host, port)
        self.port = self._server.sockets[0].getsockname()[1]
        return self

    async def stop(self):
        for w in list(self._clients):
            w.close()
        self._server.close()
        await self._server.wait_closed()

    async def _handle(self, reader, writer):
        self._clients.add(writer)
        try:
            while line := await reader.readline():
                msg = json.loads(line)
                if self.silent:
                    continue
                reply, changed = self._execute(msg["method"], msg["params"])
                writer.write((json.dumps({"id": msg["id"], **reply}) + "\r\n").encode())
                if changed:
                    note = (json.dumps({"method": "props", "params": changed}) + "\r\n").encode()
                    for w in self._clients:
                        w.write(note)
                await writer.drain()
        except (ConnectionError, OSError):
            pass
        finally:
            self._clients.discard(writer)

    def _execute(self, method: str, p: list) -> tuple[dict, dict]:
        self.commands.append((method, p))
        if self.quota is not None and len(self.commands) > self.quota:
            return {"error": {"code": -1, "message": "client quota exceeded"}}, {}
        if method == "get_prop":
            return {"result": [self.props.get(k, "") for k in p]}, {}
        on = self.props["power"] == "on"
        changes: dict = {}
        if method == "set_power":
            changes = {"power": p[0]}
        elif method == "set_rgb" and on:  # gerçek ampul gibi: bildirimde değerler sayı
            self.props.update({"color_mode": "1", "rgb": str(p[0])})
            return {"result": ["ok"]}, {"color_mode": 1, "rgb": p[0]}
        elif method == "set_ct_abx" and on:
            self.props.update({"color_mode": "2", "ct": str(p[0])})
            return {"result": ["ok"]}, {"color_mode": 2, "ct": p[0]}
        elif method == "set_bright" and on:
            changes = {"bright": str(p[0])}
        elif method == "set_scene":
            kind = p[0]
            if kind == "color":
                changes = {"power": "on", "rgb": str(p[1]), "bright": str(p[2]), "color_mode": "1", "flowing": "0"}
            elif kind == "ct":
                changes = {"power": "on", "ct": str(p[1]), "bright": str(p[2]), "color_mode": "2", "flowing": "0"}
            elif kind == "cf":
                changes = {"power": "on", "flowing": "1"}
        elif method == "stop_cf":
            changes = {"flowing": "0"}
        elif method == "set_name":
            changes = {"name": p[0]}
        elif method == "cron_add":
            self.props["delayoff"] = str(p[1])  # gerçek ampul gibi bildirim göndermez
        elif method == "cron_del":
            self.props["delayoff"] = "0"
        else:  # kapalıyken set_rgb / set_ct_abx / set_bright dahil
            return {"error": {"code": -1, "message": "method not supported"}}, {}
        self.props.update(changes)
        return {"result": ["ok"]}, changes


class SimMiio(asyncio.DatagramProtocol):
    """Kurulum modundaki ampul: hello'ya token'la cevap verir, set_ps ve config_router'ı kabul eder."""

    def __init__(self, did: int = 0x12345678, reveal_token: bool = True):
        self.did, self.token, self.reveal_token = did, os.urandom(16), reveal_token
        self.stamp = 1000
        self.received: list[dict] = []
        self.port = 0
        self._transport = None

    async def start(self, host: str = "127.0.0.1", port: int = 0):
        loop = asyncio.get_running_loop()
        self._transport, _ = await loop.create_datagram_endpoint(lambda: self, local_addr=(host, port))
        self.port = self._transport.get_extra_info("sockname")[1]
        return self

    def stop(self):
        self._transport.close()

    def connection_made(self, transport):
        self._transport = transport

    def datagram_received(self, data, addr):
        if data == miio.HELLO:
            token = self.token if self.reveal_token else b"\xff" * 16
            header = miio._HEADER.pack(0x2131, 32, 0, self.did, self.stamp)
            self._transport.sendto(header + token, addr)
            return
        msg = miio.parse_packet(self.token, data)
        self.received.append(msg)
        reply = {"id": msg["id"], "result": ["ok"]}
        self._transport.sendto(miio.build_packet(self.token, self.did, self.stamp, reply), addr)


async def _main(port: int):
    sim = await SimBulb().start("127.0.0.1", port)
    print(f"Sahte ampul 127.0.0.1:{sim.port} adresinde. Durdurmak için Ctrl+C.")
    await asyncio.Event().wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=55443)
    asyncio.run(_main(parser.parse_args().port))
