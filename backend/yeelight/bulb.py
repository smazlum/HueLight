"""Tek ampulle kalıcı TCP bağlantısı: istek-cevap eşleştirme, bildirimler, yeniden bağlanma."""
import asyncio

from . import protocol
from .queue import CommandQueue

TIMEOUT = 3.0
MAX_BACKOFF = 30


class BulbError(Exception):
    status = 502


class BulbOffline(BulbError):
    status = 503


class BulbTimeout(BulbError):
    status = 504


class BulbQuota(BulbError):
    status = 429


class Bulb:
    def __init__(self, ip: str, port: int = protocol.PORT, on_change=None):
        self.ip, self.port = ip, port
        self.online = False
        self.state: dict = {}
        self.queue = CommandQueue(self._send)
        self._on_change = on_change or (lambda bulb: None)
        self._writer: asyncio.StreamWriter | None = None
        self._pending: dict[int, asyncio.Future] = {}
        self._next_id = 1
        self._timeouts = 0
        self._task: asyncio.Task | None = None

    def start(self):
        self._task = asyncio.create_task(self._run())

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def move(self, ip: str, port: int):
        """Ampulün IP'si değiştiyse (DHCP) bağlantıyı kopar, döngü yeni adrese bağlanır."""
        self.ip, self.port = ip, port
        self._disconnect()

    async def _run(self):
        delay = 1
        while True:
            try:
                reader, self._writer = await asyncio.wait_for(asyncio.open_connection(self.ip, self.port), TIMEOUT)
            except (OSError, asyncio.TimeoutError):
                await asyncio.sleep(delay)
                delay = min(delay * 2, MAX_BACKOFF)
                continue
            self._timeouts = 0
            read_task = asyncio.create_task(self._read(reader))
            try:
                values = await self._send("get_prop", protocol.PROPS)
                delay = 1
                self._apply(dict(zip(protocol.PROPS, values)), online=True)
                await read_task
            except (BulbError, OSError):
                pass
            finally:
                read_task.cancel()
                self._disconnect()
                self.queue.fail_all(BulbOffline("Ampule ulaşılamıyor"))
                if self.online:
                    self.online = False
                    self._on_change(self)
            await asyncio.sleep(delay)
            delay = min(delay * 2, MAX_BACKOFF)

    async def _read(self, reader: asyncio.StreamReader):
        while line := await reader.readline():
            try:
                msg = protocol.decode(line)
            except ValueError:
                continue
            if msg.get("method") == "props":
                self._apply(msg.get("params", {}))
            elif (future := self._pending.pop(msg.get("id"), None)) and not future.done():
                if "error" in msg:
                    text = msg["error"].get("message", "Ampul hatası")
                    future.set_exception(BulbQuota(text) if "quota" in text else BulbError(text))
                else:
                    future.set_result(msg.get("result"))

    def _apply(self, props: dict, online: bool | None = None):
        self.state.update(protocol.parse_props(props))
        if online is not None:
            self.online = online
        self._on_change(self)

    def _disconnect(self):
        if self._writer:
            self._writer.close()
            self._writer = None
        for future in self._pending.values():
            if not future.done():
                future.set_exception(BulbOffline("Ampule ulaşılamıyor"))
        self._pending.clear()

    async def _send(self, method: str, params: list):
        if not self._writer:
            raise BulbOffline("Ampule ulaşılamıyor")
        msg_id, self._next_id = self._next_id, self._next_id + 1
        future = asyncio.get_running_loop().create_future()
        self._pending[msg_id] = future
        try:
            self._writer.write(protocol.encode(msg_id, method, params))
            await self._writer.drain()
            result = await asyncio.wait_for(future, TIMEOUT)
        except asyncio.TimeoutError:
            self._pending.pop(msg_id, None)
            self._timeouts += 1
            if self._timeouts >= 3:  # bağlantı sessizce ölmüş, yeniden kur
                self._disconnect()
            raise BulbTimeout("Ampul cevap vermedi") from None
        except (ConnectionError, OSError):
            self._disconnect()
            raise BulbOffline("Ampule ulaşılamıyor") from None
        self._timeouts = 0
        return result
