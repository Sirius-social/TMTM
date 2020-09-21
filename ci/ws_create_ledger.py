import os
import json
import asyncio
from time import sleep

import aiohttp


BASE = os.path.realpath(os.path.dirname(__file__))

url = 'ws://localhost:8000/transactions'
path = os.path.join(BASE, 'test_wrapper_init_ledger.json')
txn = json.load(open(path, 'rb'))


async def run():
    session = aiohttp.ClientSession()
    ws = await session.ws_connect(url=url)
    await ws.send_json(txn)
    await asyncio.sleep(1000)


if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(run())
