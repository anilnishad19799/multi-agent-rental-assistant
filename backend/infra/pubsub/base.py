from abc import ABC, abstractmethod

class BasePubSub(ABC):

    @abstractmethod
    async def publish(self, channel: str, message: dict):
        pass

    @abstractmethod
    def subscribe(self, channel: str):
        pass