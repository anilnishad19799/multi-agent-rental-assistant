from backend.infra.pubsub.factory import get_pubsub

pubsub = get_pubsub()

async def publish_event(session_id: str, event_type: str, data: dict):

    message = {
        "type": event_type,
        "data": data
    }

    await pubsub.publish(session_id, message)