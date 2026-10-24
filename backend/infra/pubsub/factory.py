import os
from backend.infra.pubsub.memory_pubsub import MemoryPubSub

_pubsub_instance = None

def get_pubsub():
    global _pubsub_instance

    if _pubsub_instance:
        return _pubsub_instance

    backend = os.getenv("PUBSUB_BACKEND", "memory")

    if backend == "redis":
        # Lazy import — only load redis when actually needed
        from backend.infra.pubsub.redis_pubsub import RedisPubSub
        _pubsub_instance = RedisPubSub()
    else:
        _pubsub_instance = MemoryPubSub()

    return _pubsub_instance