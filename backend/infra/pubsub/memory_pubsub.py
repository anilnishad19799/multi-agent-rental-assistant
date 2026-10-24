import asyncio
from collections import defaultdict
from backend.infra.pubsub.base import BasePubSub

class MemoryPubSub(BasePubSub):

    def __init__(self):
        self.channels = defaultdict(asyncio.Queue)

    async def publish(self, channel: str, message: dict):
        await self.channels[channel].put(message)

    def subscribe(self, channel: str):
        return self.channels[channel]