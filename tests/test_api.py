"""Uçtan uca: gerçek FastAPI uygulaması + ayrı thread'de çalışan sahte ampul ve sahte kurulum ampulü."""
import asyncio
import threading
import time

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from tools.sim_bulb import SimBulb, SimMiio

LOCAL = ("127.0.0.1", 50000)


class SimThread:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True).start()

    def run(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(5)

    def close(self):
        self.loop.call_soon_threadsafe(self.loop.stop)


@pytest.fixture
def sims():
    t = SimThread()
    bulb = t.run(SimBulb().start())
    setup = t.run(SimMiio().start())
    yield t, bulb, setup
    t.run(bulb.stop())
    t.loop.call_soon_threadsafe(setup.stop)
    t.close()


@pytest.fixture(autouse=True)
def saved_wifi(monkeypatch):
    """Windows'taki kayıtlı Wi-Fi şifreleri yerine: {ssid: şifre}. Varsayılan boş (ağ kayıtlı değil)."""
    from backend import wifi
    saved: dict[str, str] = {}
    monkeypatch.setattr(wifi, "_saved_key", lambda ssid: saved.get(ssid))
    return saved


@pytest.fixture
def client(tmp_path, sims):
    _, _, setup = sims
    app = create_app(data_dir=tmp_path, frontend_dir=tmp_path / "yok", scan_interval=0,
                     miio_target="127.0.0.1", miio_port=setup.port)
    with TestClient(app, client=LOCAL) as c:
        yield c


def wait_state(client, dev_id, cond, timeout=3.0):
    end = time.monotonic() + timeout
    while True:
        dev = next(d for d in client.get("/api/devices").json() if d["id"] == dev_id)
        if cond(dev):
            return dev
        assert time.monotonic() < end, f"durum gelmedi: {dev}"
        time.sleep(0.05)


def add_sim(client, sims):
    r = client.post("/api/devices", json={"ip": "127.0.0.1", "port": sims[1].port, "name": "Ofis"})
    assert r.status_code == 201
    dev_id = r.json()["id"]
    wait_state(client, dev_id, lambda d: d["online"])
    return dev_id


def test_rejects_non_local_clients(tmp_path):
    app = create_app(data_dir=tmp_path, scan_interval=0)
    with TestClient(app, client=("8.8.8.8", 1234)) as c:
        assert c.get("/api/devices").status_code == 403


def test_manual_add_validates_ip(client):
    assert client.post("/api/devices", json={"ip": "8.8.8.8"}).status_code == 422
    assert client.post("/api/devices", json={"ip": "abc"}).status_code == 422


def test_full_control_flow(client, sims):
    dev_id = add_sim(client, sims)
    sim = sims[1]

    # Kapalıyken renk: set_scene ile açılır
    assert client.post(f"/api/devices/{dev_id}/color", json={"hex": "#FF0000"}).status_code == 200
    d = wait_state(client, dev_id, lambda d: d["hex"] == "#FF0000")
    assert d["power"] and d["mode"] == "rgb"
    assert sim.commands[-1][0] == "set_scene"

    # Açıkken renk / ton / parlaklık yumuşak geçişli komutlarla gider
    client.post(f"/api/devices/{dev_id}/color", json={"hex": "#00FF00"})
    client.post(f"/api/devices/{dev_id}/temperature", json={"kelvin": 2700})
    client.post(f"/api/devices/{dev_id}/brightness", json={"value": 30})
    d = wait_state(client, dev_id, lambda d: d["brightness"] == 30 and d["kelvin"] == 2700)
    assert d["mode"] == "ct"
    assert [c[0] for c in sim.commands[-3:]] == ["set_rgb", "set_ct_abx", "set_bright"]

    # Sahne, akış, zamanlayıcı
    client.post(f"/api/devices/{dev_id}/scene", json={"scene_id": "gece"})
    wait_state(client, dev_id, lambda d: d["brightness"] == 5)
    client.post(f"/api/devices/{dev_id}/flow", json={"flow_id": "disko"})
    d = wait_state(client, dev_id, lambda d: d["mode"] == "flow")
    assert d["flow_id"] == "disko"
    client.delete(f"/api/devices/{dev_id}/flow")
    wait_state(client, dev_id, lambda d: d["mode"] != "flow")
    assert client.post(f"/api/devices/{dev_id}/timer", json={"minutes": 30}).json()["timer_minutes_left"] == 30
    assert client.delete(f"/api/devices/{dev_id}/timer").json()["timer_minutes_left"] is None

    # Kapat
    client.post(f"/api/devices/{dev_id}/power", json={"on": False})
    wait_state(client, dev_id, lambda d: not d["power"])


def test_validation_and_not_found(client, sims):
    dev_id = add_sim(client, sims)
    assert client.post(f"/api/devices/{dev_id}/brightness", json={"value": 0}).status_code == 422
    assert client.post(f"/api/devices/{dev_id}/temperature", json={"kelvin": 9000}).status_code == 422
    assert client.post(f"/api/devices/{dev_id}/color", json={"hex": "red"}).status_code == 422
    assert client.post("/api/devices/yok/power", json={"on": True}).status_code == 404
    assert client.post(f"/api/devices/{dev_id}/flow", json={"flow_id": "yok"}).status_code == 404


def test_scenes_crud(client):
    r = client.post("/api/scenes", json={"name": "Mor", "mode": "rgb", "hex": "#9640FF", "brightness": 60})
    assert r.status_code == 201
    scene_id = r.json()["id"]
    assert any(s["id"] == scene_id and not s["builtin"] for s in client.get("/api/scenes").json())
    assert client.post("/api/scenes", json={"name": "X", "mode": "ct", "brightness": 50}).status_code == 422
    assert client.delete("/api/scenes/calisma").status_code == 409
    assert client.delete(f"/api/scenes/{scene_id}").status_code == 204
    assert client.delete(f"/api/scenes/{scene_id}").status_code == 404


def test_rename_persists_across_restart(tmp_path, sims):
    app = create_app(data_dir=tmp_path, scan_interval=0)
    with TestClient(app, client=LOCAL) as c:
        dev_id = add_sim(c, sims)
        assert c.patch(f"/api/devices/{dev_id}", json={"name": "Salon"}).json()["name"] == "Salon"
    with TestClient(create_app(data_dir=tmp_path, scan_interval=0), client=LOCAL) as c:
        assert [d["name"] for d in c.get("/api/devices").json()] == ["Salon"]
        assert c.delete(f"/api/devices/{dev_id}").status_code == 204
        assert c.get("/api/devices").json() == []


def test_websocket_snapshot_and_updates(client, sims):
    dev_id = add_sim(client, sims)
    with client.websocket_connect("/ws") as ws:
        snap = ws.receive_json()
        assert snap["type"] == "snapshot" and snap["devices"][0]["id"] == dev_id
        client.post(f"/api/devices/{dev_id}/power", json={"on": True})
        while True:
            msg = ws.receive_json()
            if msg["type"] == "device" and msg["device"]["power"]:
                break


def test_setup_provisioning_flow(client, sims, tmp_path):
    setup = sims[2]
    r = client.post("/api/setup/probe")
    assert r.status_code == 200 and r.json()["did"] == "0x0000000012345678"
    r = client.post("/api/setup/provision", json={"ssid": "EvWifi", "password": "gizli123"})
    assert r.status_code == 200 and r.json()["lan_control"] and r.json()["confirmed"]
    methods = [m["method"] for m in setup.received]
    assert methods == ["set_ps", "miIO.config_router"]
    assert setup.received[1]["params"] == {"ssid": "EvWifi", "passwd": "gizli123", "uid": 0}
    saved = (tmp_path / "config.json").read_text(encoding="utf-8")
    assert "gizli123" not in saved and setup.token.hex() in saved  # şifre değil, yalnızca token saklanır


def test_setup_page_works_offline(tmp_path):
    with TestClient(create_app(data_dir=tmp_path, scan_interval=0), client=LOCAL) as c:
        r = c.get("/kurulum")
        assert c.get("/").status_code == 200
    assert r.status_code == 200 and "Ampul kurulumu" in r.text
    assert "http://" not in r.text and "https://" not in r.text  # kurulumda internet yok: dış kaynak olmamalı


def test_wifi_parsers():
    from backend import wifi
    profiles = ("Profiles on interface Wi-Fi:\n\nGroup policy profiles (read only)\n---\n    SirketProfili\n\n"
                "User profiles\n-------------\n    All User Profile     : EvAgi\n    All User Profile     : Ev 5GHz\n")
    assert wifi.parse_profiles(profiles) == ["EvAgi", "Ev 5GHz"]  # grup ilkesi profili dahil değil
    scan = ("SSID 1 : EvAgi\n    Network type : Infrastructure\n    BSSID 1 : aa\n         Signal : 80%\n"
            "         Channel : 6\n    BSSID 2 : bb\n         Signal : 60%\n         Channel : 44\n"
            "SSID 2 : Sadece5\n    BSSID 1 : cc\n         Signal : 90%\n         Channel : 36\n")
    assert wifi.parse_scan(scan) == [{"ssid": "EvAgi", "signal": 80, "supports_24": True},
                                     {"ssid": "Sadece5", "signal": 90, "supports_24": False}]


def test_setup_networks_puts_home_first(client, sims, monkeypatch):
    from backend import wifi
    monkeypatch.setattr(wifi, "_netsh", lambda *a: None if a[1] == "networks" else
                        "User profiles\n    All User Profile : Alfa\n    All User Profile : EvAgi\n    All User Profile : yeelink-light-x\n")
    nets = client.get("/api/setup/networks").json()
    assert nets["live"] is False and [n["ssid"] for n in nets["networks"]] == ["Alfa", "EvAgi"]  # kurulum ağı gizli
    client.post("/api/setup/probe")
    client.post("/api/setup/provision", json={"ssid": "EvAgi", "password": "deneme123"})
    first = client.get("/api/setup/networks").json()["networks"][0]
    assert first["ssid"] == "EvAgi" and first["home"]


def test_setup_rejects_hidden_token(client, sims):
    sims[2].reveal_token = False
    assert client.post("/api/setup/probe").status_code == 409
    assert client.post("/api/setup/provision", json={"ssid": "x", "password": "deneme123"}).status_code == 409


def test_provision_rejects_wrong_password_before_sending(client, sims, saved_wifi):
    setup = sims[2]
    saved_wifi["EvAgi"] = "dogru-sifre"
    client.post("/api/setup/probe")
    r = client.post("/api/setup/provision", json={"ssid": "EvAgi", "password": "yanlis-sifre"})
    assert r.status_code == 400 and r.json()["code"] == "wrong_password"
    assert setup.received == []  # ampule hiçbir şey gitmedi, kurulum bozulmadı
    r = client.post("/api/setup/provision", json={"ssid": "EvAgi", "password": "dogru-sifre"})
    assert r.status_code == 200 and r.json()["password_verified"]


def test_provision_force_sends_despite_mismatch(client, sims, saved_wifi):
    saved_wifi["EvAgi"] = "eski-sifre-1"
    client.post("/api/setup/probe")
    r = client.post("/api/setup/provision", json={"ssid": "EvAgi", "password": "yeni-sifre-2", "force": True})
    assert r.status_code == 200 and not r.json()["password_verified"]
    assert sims[2].received[-1]["params"]["passwd"] == "yeni-sifre-2"


def test_provision_validates_wpa_length(client, sims):
    client.post("/api/setup/probe")
    r = client.post("/api/setup/provision", json={"ssid": "Ev", "password": "kisa"})
    assert r.status_code == 422 and "8–63" in r.text
    assert client.post("/api/setup/provision", json={"ssid": "AcikAg", "password": ""}).status_code == 200  # şifresiz ağ


def test_wifi_password_check(saved_wifi):
    from backend import wifi
    out = "Security settings\n    Security key           : Present\n    Key Content            : abc 12345\n"
    assert wifi.parse_key(out) == "abc 12345"
    assert wifi.parse_key("Security key : Absent\n") is None
    saved_wifi["EvAgi"] = "abc 12345"
    assert wifi.check_password("EvAgi", "abc 12345") is True
    assert wifi.check_password("EvAgi", "baska-sifre") is False
    assert wifi.check_password("Kayitsiz", "herhangi1") is None
