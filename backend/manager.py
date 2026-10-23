"""Ampul kaydı, kontrol komutları, kurulum akışı ve durum yayını."""
import asyncio
import logging
import subprocess
import uuid

from . import wifi
from .store import Store
from .yeelight import discovery, miio, presets, protocol
from .yeelight.bulb import Bulb

SMOOTH = ["smooth", protocol.TRANSITION_MS]
log = logging.getLogger("huelight")


def _arp_table() -> str:
    """Tanı için: ampul ağda görünüyor mu (MAC adresi ARP'de var mı)?"""
    try:
        return subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=3).stdout.strip()
    except (OSError, subprocess.SubprocessError) as e:
        return f"okunamadı: {e}"


class NotFound(Exception):
    pass


class SetupError(Exception):
    status = 409


class WrongPassword(Exception):
    pass


class Device:
    def __init__(self, id: str, name: str, model: str, ip: str, port: int, on_change):
        self.id, self.name, self.model = id, name, model
        self.flow_id: str | None = None
        self.bulb = Bulb(ip, port, on_change=lambda _: on_change(self))


class DeviceManager:
    def __init__(self, store: Store, scan_interval: float = 60, scan=discovery.scan_async,
                 miio_target: str = "255.255.255.255", miio_port: int = miio.PORT):
        self.store = store
        self.devices: dict[str, Device] = {}
        self._scan_interval = scan_interval
        self._scan = scan
        self._miio_target, self._miio_port = miio_target, miio_port
        self._subscribers: set[asyncio.Queue] = set()
        self._scan_task: asyncio.Task | None = None
        self._setup_device: dict | None = None

    # --- yaşam döngüsü ---
    async def start(self):
        for d in self.store.data["devices"]:
            self._add(d["id"], d.get("name", ""), d.get("model", ""), d["ip"], d.get("port", protocol.PORT))
        if self._scan_interval:
            self._scan_task = asyncio.create_task(self._scan_loop())
            asyncio.create_task(self._remember_home_ssid())

    async def _remember_home_ssid(self):
        """Kurulumda ev ağını listenin başına koymak için: PC'nin şu an bağlı olduğu (kurulum ağı olmayan) Wi-Fi."""
        names = [n for n in await asyncio.to_thread(wifi.connected_ssids) if not n.lower().startswith(wifi.SETUP_PREFIX)]
        known = set(wifi.parse_profiles(await asyncio.to_thread(wifi._netsh, "show", "profiles") or ""))
        home = next((n for n in names if n in known), None)
        if home and home != self.store.data.get("home_ssid"):
            self.store.data["home_ssid"] = home
            self.store.save()

    async def stop(self):
        if self._scan_task:
            self._scan_task.cancel()
        for dev in self.devices.values():
            await dev.bulb.stop()

    async def _scan_loop(self):
        while True:
            try:
                await self.scan()
            except OSError:
                pass  # ağ geçici olarak yok (ör. kurulum sırasında PC ampulün ağında)
            await asyncio.sleep(self._scan_interval)

    # --- durum ve yayın ---
    def state(self, dev: Device) -> dict:
        s = dev.bulb.state
        flowing = s.get("flowing", False)
        return {
            "id": dev.id, "name": dev.name or s.get("bulb_name") or f"Yeelight {dev.model.capitalize()}".strip(),
            "model": dev.model, "ip": dev.bulb.ip, "online": dev.bulb.online,
            "power": s.get("power", False), "mode": "flow" if flowing else s.get("mode", "rgb"),
            "brightness": s.get("brightness", 100), "hex": s.get("hex", "#FFFFFF"), "kelvin": s.get("kelvin", 4000),
            "flow_id": dev.flow_id if flowing else None, "timer_minutes_left": s.get("timer_minutes_left"),
        }

    def snapshot(self) -> list[dict]:
        return [self.state(d) for d in self.devices.values()]

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        self._subscribers.discard(q)

    def _broadcast(self, event: dict):
        for q in list(self._subscribers):
            if q.full():  # yavaş istemci: eskiyi at, son durum önemli
                q.get_nowait()
            q.put_nowait(event)

    def _changed(self, dev: Device):
        self._broadcast({"type": "device", "device": self.state(dev)})

    # --- kayıt ---
    def get(self, dev_id: str) -> Device:
        if dev_id not in self.devices:
            raise NotFound("Ampul bulunamadı")
        return self.devices[dev_id]

    def _add(self, dev_id, name, model, ip, port) -> Device:
        dev = Device(dev_id, name, model, ip, port, self._changed)
        self.devices[dev_id] = dev
        dev.bulb.start()
        return dev

    def _save_devices(self):
        self.store.data["devices"] = [{"id": d.id, "name": d.name, "model": d.model, "ip": d.bulb.ip, "port": d.bulb.port}
                                      for d in self.devices.values()]
        self.store.save()

    async def scan(self) -> list[dict]:
        found = await self._scan()
        for f in found:
            dev = self.devices.get(f["id"])
            if dev:
                if (dev.bulb.ip, dev.bulb.port) != (f["ip"], f["port"]):
                    dev.bulb.move(f["ip"], f["port"])
                continue
            # Elle eklenmiş aynı ampul gerçek kimliğiyle bulunduysa kaydı devral, adı koru.
            manual = next((d for d in self.devices.values() if d.id.startswith("ip-") and d.bulb.ip == f["ip"]), None)
            name = ""
            if manual:
                name = manual.name
                await manual.bulb.stop()
                del self.devices[manual.id]
                self._broadcast({"type": "removed", "id": manual.id})
            self._changed(self._add(f["id"], name, f["model"], f["ip"], f["port"]))
        self._save_devices()
        return [self.state(self.devices[f["id"]]) for f in found]

    async def add_manual(self, ip: str, port: int, name: str) -> dict:
        dev_id = f"ip-{ip}" if port == protocol.PORT else f"ip-{ip}-{port}"
        if dev_id in self.devices:
            raise SetupError("Bu ampul zaten listede")
        dev = self._add(dev_id, name, "", ip, port)
        self._save_devices()
        self._changed(dev)
        return self.state(dev)

    async def remove(self, dev_id: str):
        dev = self.get(dev_id)
        await dev.bulb.stop()
        del self.devices[dev_id]
        self._save_devices()
        self._broadcast({"type": "removed", "id": dev_id})

    async def rename(self, dev_id: str, name: str) -> dict:
        dev = self.get(dev_id)
        dev.name = name
        self._save_devices()
        if dev.bulb.online:
            await dev.bulb.queue.submit("set_name", [name])
        self._changed(dev)
        return self.state(dev)

    # --- kontrol ---
    async def _cmd(self, dev: Device, method: str, params: list, key: str | None = None):
        await dev.bulb.queue.submit(method, params, key)
        return self.state(dev)

    def _is_on(self, dev: Device) -> bool:
        return dev.bulb.state.get("power", False)

    async def power(self, dev_id: str, on: bool) -> dict:
        dev = self.get(dev_id)
        return await self._cmd(dev, "set_power", ["on" if on else "off", *SMOOTH], key="power")

    async def color(self, dev_id: str, hex_color: str) -> dict:
        dev, value = self.get(dev_id), protocol.hex_to_int(hex_color)
        dev.flow_id = None
        if self._is_on(dev):
            return await self._cmd(dev, "set_rgb", [value, *SMOOTH], key="tone")
        return await self._cmd(dev, "set_scene", ["color", value, dev.bulb.state.get("brightness", 100)], key="tone")

    async def temperature(self, dev_id: str, kelvin: int) -> dict:
        dev = self.get(dev_id)
        dev.flow_id = None
        if self._is_on(dev):
            return await self._cmd(dev, "set_ct_abx", [kelvin, *SMOOTH], key="tone")
        return await self._cmd(dev, "set_scene", ["ct", kelvin, dev.bulb.state.get("brightness", 100)], key="tone")

    async def brightness(self, dev_id: str, value: int) -> dict:
        dev = self.get(dev_id)
        if self._is_on(dev):
            return await self._cmd(dev, "set_bright", [value, *SMOOTH], key="bright")
        s = dev.bulb.state
        if s.get("mode") == "ct":
            return await self._cmd(dev, "set_scene", ["ct", s.get("kelvin", 4000), value], key="bright")
        return await self._cmd(dev, "set_scene", ["color", protocol.hex_to_int(s.get("hex", "#FFFFFF")), value], key="bright")

    async def apply_scene(self, dev_id: str, scene_id: str) -> dict:
        dev = self.get(dev_id)
        scene = next((s for s in self.list_scenes() if s["id"] == scene_id), None)
        if not scene:
            raise NotFound("Sahne bulunamadı")
        dev.flow_id = None
        if scene["mode"] == "ct":
            return await self._cmd(dev, "set_scene", ["ct", scene["kelvin"], scene["brightness"]], key="tone")
        return await self._cmd(dev, "set_scene", ["color", protocol.hex_to_int(scene["hex"]), scene["brightness"]], key="tone")

    async def start_flow(self, dev_id: str, flow_id: str) -> dict:
        dev = self.get(dev_id)
        flow = presets.FLOWS_BY_ID.get(flow_id)
        if not flow:
            raise NotFound("Akış bulunamadı")
        dev.flow_id = flow_id
        return await self._cmd(dev, "set_scene", ["cf", *presets.flow_params(flow)], key="tone")

    async def stop_flow(self, dev_id: str) -> dict:
        dev = self.get(dev_id)
        dev.flow_id = None
        return await self._cmd(dev, "stop_cf", [])

    async def set_timer(self, dev_id: str, minutes: int) -> dict:
        dev = self.get(dev_id)
        await dev.bulb.queue.submit("cron_add", [0, minutes])
        return await self._refresh_timer(dev)

    async def cancel_timer(self, dev_id: str) -> dict:
        dev = self.get(dev_id)
        await dev.bulb.queue.submit("cron_del", [0])
        return await self._refresh_timer(dev)

    async def _refresh_timer(self, dev: Device) -> dict:
        # cron_add/cron_del her donanım yazılımında `props` bildirimi göndermiyor, kalan süreyi kendimiz okuyoruz.
        (left,) = await dev.bulb.queue.submit("get_prop", ["delayoff"])
        dev.bulb.state["timer_minutes_left"] = int(left or 0) or None
        self._changed(dev)
        return self.state(dev)

    # --- sahneler ---
    def list_scenes(self) -> list[dict]:
        return [{**s, "builtin": True} for s in presets.SCENES] + [{**s, "builtin": False} for s in self.store.data["scenes"]]

    def add_scene(self, scene: dict) -> dict:
        scene = {"id": f"u-{uuid.uuid4().hex[:8]}", **scene}
        self.store.data["scenes"].append(scene)
        self.store.save()
        return {**scene, "builtin": False}

    def delete_scene(self, scene_id: str):
        if any(s["id"] == scene_id for s in presets.SCENES):
            raise SetupError("Hazır sahneler silinemez")
        before = len(self.store.data["scenes"])
        self.store.data["scenes"] = [s for s in self.store.data["scenes"] if s["id"] != scene_id]
        if len(self.store.data["scenes"]) == before:
            raise NotFound("Sahne bulunamadı")
        self.store.save()

    # --- ilk kurulum (miIO) ---
    async def setup_probe(self) -> dict:
        trace: list[str] = []
        found = await asyncio.to_thread(miio.discover, self._miio_target, 3.0, self._miio_port, trace)
        log.info("setup probe: yerel=%s ağ geçidi=%s bulunan=%d", discovery.local_ipv4s(), miio._gateways(), len(found))
        for line in trace:
            log.info("  %s", line)
        if not found:
            log.info("  ARP tablosu:\n%s", await asyncio.to_thread(_arp_table))
            ips = ", ".join(discovery.local_ipv4s()) or "yok"
            raise NotFound(f"Kurulum bekleyen ampul bulunamadı. PC ampulün Wi-Fi ağına bağlı mı? (PC'nin IP adresleri: {ips})")
        ready = [d for d in found if d["token"]]
        if not ready:
            raise SetupError("Ampul bulundu ama şifreleme anahtarını (token) vermiyor. Ampulü 5 kez aç/kapa ile sıfırlayıp tekrar deneyin.")
        self._setup_device = ready[0]
        return {"did": self._did(ready[0]["did"]), "ip": ready[0]["ip"]}

    async def setup_provision(self, ssid: str, password: str, force: bool = False) -> dict:
        dev = self._setup_device
        if not dev:
            raise SetupError("Önce ampulü bulun (probe)")
        # Yanlış şifre ampule giderse ampul ağa bağlanamaz ve kurulum baştan yapılmak zorunda kalır: önce doğrula.
        verified = await asyncio.to_thread(wifi.check_password, ssid, password)
        log.info("setup provision: ssid=%s şifre kontrolü=%s force=%s", ssid,
                 {True: "eşleşti", False: "eşleşmedi", None: "kayıtlı değil"}[verified], force)
        if verified is False and not force:
            raise WrongPassword(f"Şifre '{ssid}' ağı için doğru değil. Doğru şifreyi girin.")
        try:
            await asyncio.to_thread(miio.send, dev, dev["token"], "set_ps", ["cfg_lan_ctrl", "1"], 5.0, self._miio_port)
            lan = True
        except miio.MiioError:
            lan = False  # ev ağına geçince finish adımında tekrar denenir
        self.store.data["tokens"][self._did(dev["did"])] = dev["token"].hex()
        self.store.data["home_ssid"] = ssid
        self.store.save()
        try:
            await asyncio.to_thread(miio.send, dev, dev["token"], "miIO.config_router",
                                    {"ssid": ssid, "passwd": password, "uid": 0}, 5.0, self._miio_port)
            confirmed = True
        except miio.MiioError as e:
            if "cevap vermedi" not in str(e):
                raise
            confirmed = False  # ampul ağ değiştirirken cevabı yollamadan bağlantıyı kesebiliyor
        self._setup_device = None
        return {"did": self._did(dev["did"]), "lan_control": lan, "confirmed": confirmed,
                "password_verified": verified is True}

    async def setup_finish(self, wait: float = 45) -> list[dict]:
        """Kurulan ampul ev ağında görünene kadar `wait` saniye arar: ağa katılması 10-30 sn sürebiliyor."""
        tokens = self.store.data["tokens"]
        deadline = asyncio.get_running_loop().time() + wait
        while True:
            found = await asyncio.to_thread(miio.discover, self._miio_target, 3.0, self._miio_port)
            for d in found:
                token = tokens.get(self._did(d["did"]))
                if token:
                    try:
                        await asyncio.to_thread(miio.send, d, bytes.fromhex(token), "set_ps", ["cfg_lan_ctrl", "1"], 5.0, self._miio_port)
                    except miio.MiioError:
                        pass  # LAN Control zaten açıksa da tarama bulur
            bulbs = await self.scan()
            if bulbs or asyncio.get_running_loop().time() >= deadline:
                log.info("setup finish: bulunan=%s", [(b["id"], b["ip"]) for b in bulbs])
                return bulbs
            await asyncio.sleep(2)

    @staticmethod
    def _did(did: int) -> str:
        return f"0x{did:016x}"  # Yeelight SSDP'deki `id` ile aynı biçim
