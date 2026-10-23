"""Yalnızca yerel ağdan (özel IP) gelen HTTP ve WebSocket isteklerini kabul eder."""
import ipaddress


def is_private(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback


class LocalNetworkOnly:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        client = scope.get("client")
        if scope["type"] in ("http", "websocket") and not (client and is_private(client[0])):
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
                return
            await send({"type": "http.response.start", "status": 403,
                        "headers": [(b"content-type", b"text/plain; charset=utf-8")]})
            await send({"type": "http.response.body", "body": "Yalnızca yerel ağdan erişilebilir".encode()})
            return
        await self.app(scope, receive, send)
