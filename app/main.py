import json
import requests
import asyncio
from time import sleep

from sirius_sdk import Agent, P2PConnection


async def test():
    agent = Agent(
        server_address='http://178.63.1.220:8082',
        credentials='VWxAV10NzPIp583WBUMaQsEVOORP2OtDhpUCtL6wnCH3vxdCjEGvwWZ0q2YILaZjI0DxGMGf6OU1YHmuzSa8i/bRnGU7zTv9X++FyrQLcWM='.encode('ascii'),
        p2p=P2PConnection(
            my_keys=('4JgX1eHHfzKsjtsNbtmJgiVVs4LxbUsT4qx563U4Sv9v', '29YWW1523qaS7mzEvcwshskvCP9H6tkvMpCeytreEDJBXnP3CzHWY81wp8PJfxYrhWpYvygCKTdVDENfJxR74tAc'),
            their_verkey='EU9nKVA5QUVpgvTycjQDv3wmri21PqoCg2AsJwwzBTSQ'
        )
    )
    print('@1')
    await agent.open()
    print('@2')
    await agent.close()
    print('@3')


if __name__ == '__main__':
    # asyncio.get_event_loop().run_until_complete(test())
    print('------')
    sleep(1000)
