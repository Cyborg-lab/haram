"""Bot va Mini App serverini bitta buyruq bilan ishga tushiradi."""
import asyncio
import logging

import uvicorn

from bot import main as bot_main
from webapp import app


async def run():
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    await asyncio.gather(bot_main(), server.serve())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nBot va Mini App to'xtatildi.")
