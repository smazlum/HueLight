import asyncio

from backend.yeelight.queue import CommandQueue


async def test_coalesces_same_key_while_waiting_for_token():
    sent = []

    async def send(method, params):
        sent.append(params[0])
        return ["ok"]

    q = CommandQueue(send, capacity=1, per_second=20)
    first = asyncio.create_task(q.submit("set_rgb", [0], key="tone"))
    await asyncio.sleep(0.01)  # ilki jetonu alıp gönderildi
    # Sonraki 9'u jeton beklerken tek komuta birleşir, sonuncunun değeri gider.
    rest = await asyncio.gather(*(q.submit("set_rgb", [i], key="tone") for i in range(1, 10)))
    assert sent == [0, 9]
    assert [await first, *rest] == [["ok"]] * 10


async def test_different_keys_are_not_merged_and_keep_order():
    sent = []

    async def send(method, params):
        sent.append(method)
        return ["ok"]

    q = CommandQueue(send, capacity=10, per_second=1)
    await asyncio.gather(q.submit("set_power", ["on"], key="power"), q.submit("set_bright", [5], key="bright"),
                         q.submit("start_cf", []))
    assert sent == ["set_power", "set_bright", "start_cf"]


async def test_rate_limit_spaces_commands():
    times = []

    async def send(method, params):
        times.append(asyncio.get_running_loop().time())

    q = CommandQueue(send, capacity=1, per_second=10)
    await asyncio.gather(*(q.submit("set_power", [i]) for i in range(3)))
    assert times[2] - times[0] >= 0.18  # 2 jeton dolumu × 0.1 sn


async def test_error_reaches_all_coalesced_callers():
    async def send(method, params):
        raise RuntimeError("boom")

    q = CommandQueue(send, capacity=1, per_second=50)
    results = await asyncio.gather(*(q.submit("set_rgb", [i], key="tone") for i in range(3)), return_exceptions=True)
    assert all(isinstance(r, RuntimeError) for r in results)
