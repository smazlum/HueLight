"""Ampul başına komut kuyruğu: hız sınırı (kova) + aynı türden bekleyen komutları birleştirme."""
import asyncio
import time
from collections import deque


class _Item:
    __slots__ = ("key", "method", "params", "futures")

    def __init__(self, key, method, params, future):
        self.key, self.method, self.params, self.futures = key, method, params, [future]


class CommandQueue:
    def __init__(self, send, capacity: int = 10, per_second: float = 1.0):
        self._send = send
        self._capacity = self._tokens = capacity
        self._rate = per_second
        self._last = time.monotonic()
        self._items: deque[_Item] = deque()
        self._worker: asyncio.Task | None = None

    async def submit(self, method: str, params: list, key: str | None = None):
        """`key` verilirse, sırada bekleyen aynı anahtarlı komutun yerine geçer; bekleyenlerin hepsi sonucu alır."""
        future = asyncio.get_running_loop().create_future()
        pending = next((it for it in self._items if key and it.key == key), None)
        if pending:
            pending.method, pending.params = method, params
            pending.futures.append(future)
        else:
            self._items.append(_Item(key, method, params, future))
            if not self._worker or self._worker.done():
                self._worker = asyncio.create_task(self._run())
        return await future

    def fail_all(self, error: Exception):
        while self._items:
            for f in self._items.popleft().futures:
                if not f.done():
                    f.set_exception(error)

    async def _take_token(self):
        while True:
            now = time.monotonic()
            self._tokens = min(self._capacity, self._tokens + (now - self._last) * self._rate)
            self._last = now
            if self._tokens >= 1:
                self._tokens -= 1
                return
            await asyncio.sleep((1 - self._tokens) / self._rate)

    async def _run(self):
        while self._items:
            await self._take_token()
            if not self._items:  # fail_all beklerken sırayı boşaltmış olabilir
                return
            item = self._items.popleft()
            try:
                result = await self._send(item.method, item.params)
            except Exception as e:
                for f in item.futures:
                    if not f.done():
                        f.set_exception(e)
            else:
                for f in item.futures:
                    if not f.done():
                        f.set_result(result)
