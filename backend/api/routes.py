import asyncio

from fastapi import APIRouter, Request, Response

from .. import wifi
from ..yeelight import discovery, presets
from . import schemas as s

router = APIRouter(prefix="/api")
VERSION = "0.1.0"


def m(request: Request):
    return request.app.state.manager


@router.get("/info")
async def info(request: Request):
    port = request.url.port or 8000
    return {"version": VERSION, "urls": [f"http://{ip}:{port}" for ip in discovery.local_ipv4s()]}


@router.get("/devices")
async def devices(request: Request):
    return m(request).snapshot()


@router.post("/devices/scan")
async def scan(request: Request):
    return await m(request).scan()


@router.post("/devices", status_code=201)
async def add_device(body: s.AddDevice, request: Request):
    return await m(request).add_manual(body.ip, body.port, body.name)


@router.delete("/devices/{dev_id}", status_code=204)
async def remove_device(dev_id: str, request: Request):
    await m(request).remove(dev_id)
    return Response(status_code=204)


@router.patch("/devices/{dev_id}")
async def rename(dev_id: str, body: s.Rename, request: Request):
    return await m(request).rename(dev_id, body.name)


@router.post("/devices/{dev_id}/power")
async def power(dev_id: str, body: s.Power, request: Request):
    return await m(request).power(dev_id, body.on)


@router.post("/devices/{dev_id}/color")
async def color(dev_id: str, body: s.Color, request: Request):
    return await m(request).color(dev_id, body.hex)


@router.post("/devices/{dev_id}/brightness")
async def brightness(dev_id: str, body: s.Brightness, request: Request):
    return await m(request).brightness(dev_id, body.value)


@router.post("/devices/{dev_id}/temperature")
async def temperature(dev_id: str, body: s.Temperature, request: Request):
    return await m(request).temperature(dev_id, body.kelvin)


@router.post("/devices/{dev_id}/scene")
async def scene(dev_id: str, body: s.SceneRef, request: Request):
    return await m(request).apply_scene(dev_id, body.scene_id)


@router.post("/devices/{dev_id}/flow")
async def start_flow(dev_id: str, body: s.FlowRef, request: Request):
    return await m(request).start_flow(dev_id, body.flow_id)


@router.delete("/devices/{dev_id}/flow")
async def stop_flow(dev_id: str, request: Request):
    return await m(request).stop_flow(dev_id)


@router.post("/devices/{dev_id}/timer")
async def set_timer(dev_id: str, body: s.Timer, request: Request):
    return await m(request).set_timer(dev_id, body.minutes)


@router.delete("/devices/{dev_id}/timer")
async def cancel_timer(dev_id: str, request: Request):
    return await m(request).cancel_timer(dev_id)


@router.get("/scenes")
async def scenes(request: Request):
    return m(request).list_scenes()


@router.post("/scenes", status_code=201)
async def add_scene(body: s.NewScene, request: Request):
    return m(request).add_scene(body.model_dump(exclude_none=True))


@router.delete("/scenes/{scene_id}", status_code=204)
async def delete_scene(scene_id: str, request: Request):
    m(request).delete_scene(scene_id)
    return Response(status_code=204)


@router.get("/flows")
async def flows():
    return [presets.flow_public(f) for f in presets.FLOWS]


@router.get("/setup/networks")
async def setup_networks(request: Request):
    return await asyncio.to_thread(wifi.networks, m(request).store.data.get("home_ssid"))


@router.post("/setup/probe")
async def setup_probe(request: Request):
    return await m(request).setup_probe()


@router.post("/setup/provision")
async def setup_provision(body: s.Provision, request: Request):
    return await m(request).setup_provision(body.ssid, body.password, body.force)


@router.post("/setup/finish")
async def setup_finish(request: Request):
    return await m(request).setup_finish()
