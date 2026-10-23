import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws")
async def ws(websocket: WebSocket):
    manager = websocket.app.state.manager
    await websocket.accept()
    queue = manager.subscribe()
    try:
        await websocket.send_json({"type": "snapshot", "devices": manager.snapshot()})
        # İstemciden mesaj beklenmiyor, receive yalnızca kopmayı fark etmek için.
        closed = asyncio.create_task(websocket.receive())
        while True:
            event = asyncio.create_task(queue.get())
            done, _ = await asyncio.wait({event, closed}, return_when=asyncio.FIRST_COMPLETED)
            if closed in done:
                event.cancel()
                return
            await websocket.send_json(event.result())
    except WebSocketDisconnect:
        pass
    finally:
        manager.unsubscribe(queue)
