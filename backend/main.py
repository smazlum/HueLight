"""Uygulama girişi: python -m backend.main [--port 8000]"""
import argparse
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import routes, ws
from .manager import DeviceManager, NotFound, SetupError, WrongPassword
from .security import LocalNetworkOnly
from .store import Store
from .yeelight.bulb import BulbError
from .yeelight.miio import MiioError

ROOT = Path(__file__).resolve().parent.parent


def create_app(data_dir: Path = ROOT / "data", frontend_dir: Path = ROOT / "frontend", **manager_options) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.manager = DeviceManager(Store(data_dir / "config.json"), **manager_options)
        await app.state.manager.start()
        yield
        await app.state.manager.stop()

    app = FastAPI(title="HueLight", version=routes.VERSION, lifespan=lifespan)

    def error(status: int):
        return lambda request, exc: JSONResponse({"detail": str(exc)}, status_code=status)

    app.add_exception_handler(NotFound, error(404))
    app.add_exception_handler(SetupError, error(409))
    app.add_exception_handler(MiioError, error(502))
    app.add_exception_handler(WrongPassword, lambda request, exc: JSONResponse(
        {"detail": str(exc), "code": "wrong_password"}, status_code=400))
    app.add_exception_handler(BulbError, lambda request, exc: JSONResponse({"detail": str(exc)}, status_code=exc.status))

    app.include_router(routes.router)
    app.include_router(ws.router)

    # Kurulum sayfası internetsiz açılmalı (PC ampulün ağındayken): /docs CDN'den yüklendiği için orada çalışmaz.
    @app.get("/kurulum", include_in_schema=False)
    async def setup_page():
        return FileResponse(frontend_dir / "kurulum.html")

    if (frontend_dir / "index.html").exists():
        app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
    else:
        @app.get("/", response_class=HTMLResponse)
        async def placeholder(request: Request):
            return ("<meta charset='utf-8'><h1>HueLight</h1><p>Arayüz henüz yok.</p>"
                    "<p><a href='/kurulum'>Ampul kurulumu</a> · <a href='/docs'>API dokümanı</a> (internet gerekir)</p>")

    return LocalNetworkOnly(app)


def main():
    import uvicorn

    parser = argparse.ArgumentParser(description="HueLight sunucusu")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    (ROOT / "data").mkdir(exist_ok=True)
    logging.basicConfig(filename=ROOT / "data" / "huelight.log", encoding="utf-8", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    uvicorn.run(create_app(), host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
