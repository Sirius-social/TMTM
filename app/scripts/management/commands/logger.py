import json
import logging

import aioredis
from django.conf import settings


class StreamLogger:

    def __init__(self, stream: str, cb=None):
        self.__redis = None
        self.__stream = stream
        self.__channel_name = settings.AGENT['entity']
        self.__cb = cb

    @staticmethod
    async def create(stream: str, cb=None):
        inst = StreamLogger(stream, cb)
        if settings.REDIS:
            inst.__redis = await aioredis.create_redis('redis://%s' % settings.REDIS, timeout=3)
        return inst

    async def __call__(self, *args, **kwargs):
        event = dict(
            stream=self.__stream,
            payload=dict(**kwargs)
        )
        event_str = json.dumps(event, sort_keys=True, indent=4)
        logging.error('============== LOG =============')
        logging.error(event_str)
        logging.error('================================')
        if self.__cb:
            await self.__cb(event)
        if self.__redis:
            await self.__redis.publish(self.__channel_name, event_str)
