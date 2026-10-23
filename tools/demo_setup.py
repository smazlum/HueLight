"""Kurulum sayfasını gerçek ampul olmadan denemek için: sahte kurulum ampulü + uygulama (port 8001, geçici veri)."""
import asyncio
import tempfile
from pathlib import Path

import uvicorn

from backend.main import create_app
from tools.sim_bulb import SimMiio


async def main():
    sim = await SimMiio().start()
    app = create_app(data_dir=Path(tempfile.mkdtemp()), scan_interval=0, miio_target="127.0.0.1", miio_port=sim.port)
    print("Deneme sunucusu: http://localhost:8001/kurulum")
    await uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8001, log_level="warning")).serve()


if __name__ == "__main__":
    asyncio.run(main())
