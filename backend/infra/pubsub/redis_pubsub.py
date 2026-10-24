import asyncio
import json
import redis.asyncio as redis
from backend.infra.pubsub.base import BasePubSub

class RedisPubSub(BasePubSub):

    def __init__(self):
        self.redis = redis.Redis(host="localhost", port=6379, decode_responses=True)
        self.queues = {}

    async def publish(self, channel: str, message: dict):
        await self.redis.publish(channel, json.dumps(message))

    def subscribe(self, channel: str):
        if channel not in self.queues:
            self.queues[channel] = asyncio.Queue()
            asyncio.create_task(self._listener(channel))

        return self.queues[channel]

    async def _listener(self, channel: str):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)

        async for msg in pubsub.listen():
            if msg["type"] == "message":
                data = json.loads(msg["data"])
                await self.queues[channel].put(data)