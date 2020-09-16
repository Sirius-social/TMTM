import json
import logging

import aioredis
from django.conf import settings


class StreamLogger:

    def __init__(self, stream: str):
        self.__redis = None
        self.__stream = stream
        self.__channel_name = settings.AGENT['entity']

    @staticmethod
    async def create(stream: str):
        inst = StreamLogger(stream)
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
        if self.__redis:
            await self.__redis.publish(self.__channel_name, event_str)
