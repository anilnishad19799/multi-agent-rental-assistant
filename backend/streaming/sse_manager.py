import json
from fastapi.responses import StreamingResponse
from backend.infra.pubsub.factory import get_pubsub

pubsub = get_pubsub()

class SSEManager:

    def stream(self, session_id: str):

        queue = pubsub.subscribe(session_id)

        async def event_generator():

            while True:
                event = await queue.get()

                yield f"data: {json.dumps(event)}\n\n"

                if event.get("type") == "DONE":
                    break

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream"
        )