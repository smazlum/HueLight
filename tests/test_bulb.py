import asyncio

import pytest

from backend.yeelight import bulb as bulb_mod
from backend.yeelight.bulb import Bulb, BulbOffline, BulbQuota, BulbTimeout
from tools.sim_bulb import SimBulb


async def wait_for(cond, timeout=3.0):
    end = asyncio.get_running_loop().time() + timeout
    while not cond():
        assert asyncio.get_running_loop().time() < end, "zaman aşımı"
        await asyncio.sleep(0.02)


@pytest.fixture
async def sim():
    s = await SimBulb().start()
    yield s
    await s.stop()


async def test_connects_reads_state_and_follows_notifications(sim):
    b = Bulb("127.0.0.1", sim.port)
    b.start()
    await wait_for(lambda: b.online)
    assert b.state["power"] is False and b.state["kelvin"] == 4000
    await b.queue.submit("set_scene", ["color", 0x00FF00, 50])
    await wait_for(lambda: b.state.get("hex") == "#00FF00")
    assert b.state["power"] is True and b.state["brightness"] == 50 and b.state["mode"] == "rgb"
    await b.stop()


async def test_bulb_error_and_quota_map_to_exceptions():
    sim = await SimBulb(quota=1).start()
    b = Bulb("127.0.0.1", sim.port)
    b.start()
    await wait_for(lambda: b.online)  # get_prop kotanın tek hakkını kullandı
    with pytest.raises(BulbQuota):
        await b.queue.submit("set_power", ["on", "smooth", 300])
    await b.stop()
    await sim.stop()


async def test_timeout_when_bulb_silent(monkeypatch):
    monkeypatch.setattr(bulb_mod, "TIMEOUT", 0.2)
    sim = await SimBulb().start()
    b = Bulb("127.0.0.1", sim.port)
    b.start()
    await wait_for(lambda: b.online)
    sim.silent = True
    with pytest.raises(BulbTimeout):
        await b.queue.submit("set_power", ["on", "smooth", 300])
    await b.stop()
    await sim.stop()


async def test_goes_offline_and_reconnects(monkeypatch):
    monkeypatch.setattr(bulb_mod, "MAX_BACKOFF", 0.2)
    sim = await SimBulb().start()
    port = sim.port
    b = Bulb("127.0.0.1", port)
    b.start()
    await wait_for(lambda: b.online)
    await sim.stop()  # elektrik kesildi
    await wait_for(lambda: not b.online)
    with pytest.raises(BulbOffline):
        await b.queue.submit("set_power", ["on", "smooth", 300])
    sim2 = await SimBulb().start(port=port)  # elektrik geldi
    await wait_for(lambda: b.online, timeout=5)
    await b.stop()
    await sim2.stop()
