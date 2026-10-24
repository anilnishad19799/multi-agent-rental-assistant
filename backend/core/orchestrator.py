"""Multi-agent orchestrator — routes queries through Supervisor → Specialized Agents.

Memory integration:
  - Short-term: ThreadMemory stores conversation buffer + working state per session
  - Long-term Semantic: Facts (user profile, search criteria) persisted to DB
  - Long-term Episodic: Events (messages, handoffs, extractions) persisted to DB
  - Long-term Procedural: Patterns (agent flow, preferences) learned after each turn
"""
import logging
import backend.models  # noqa: F401 — register ALL models before any query
from backend.agents import AgentFactory
from backend.agents.base_agent import AgentResult
from backend.events.publisher import publish_event
from backend.events.types import EventType
from backend.memory.short_term import ThreadMemory
from backend.memory.long_term import LongTermMemory
from backend.repositories.conversation_repository import ConversationRepository
import backend.services.llm  # noqa: F401 — trigger LLM client registration

logger = logging.getLogger(__name__)

# Shared repository instance
_conversation_repo = ConversationRepository()

# Maximum agent handoffs per request to prevent infinite loops
MAX_HANDOFFS = 5


async def run(session_id: str, user_input: str, provider: str = None):
    """Main orchestration loop for the multi-agent system.

    Flow:
    1. Initialize thread memory + long-term memory
    2. Record user message (thread buffer + episodic memory + DB)
    3. Supervisor agent routes to specialist
    4. Target agent processes and streams response
    5. Save extracted data (thread + semantic + episodic memory)
    6. Learn patterns (procedural memory)
    7. Emit DONE
    """
    thread = ThreadMemory(session_id)
    ltm = LongTermMemory()

    try:
        # ─── Step 1: Initialize conversation in DB ───────────────────
        conversation = await _conversation_repo.get_or_create_conversation(session_id)
        await thread.set("conversation_id", conversation.id)

        # ─── Step 2: Record user message ─────────────────────────────
        # Thread buffer (short-term)
        await thread.add_message("user", user_input)

        # Episodic memory (long-term — records WHAT happened)
        user_id = await thread.get("user_id")
        await ltm.episodic.record_user_message(
            thread_id=session_id,
            content=user_input,
            user_id=user_id,
        )

        # Conversation DB (existing persistence)
        await _conversation_repo.add_message(
            conversation_id=conversation.id,
            sender_type="USER",
            content=user_input,
        )

        # ─── Step 3: Build context from all memory layers ────────────
        context = await thread.get_full_context()

        # ─── Step 4: Supervisor routes the query ─────────────────────
        await publish_event(session_id, EventType.AGENT_START, {"agent": "supervisor"})

        supervisor = AgentFactory.create_agent("supervisor", session_id, provider)
        supervisor_result = await supervisor.process(user_input, context)

        target_agent_name = supervisor_result.next_agent or "general"
        reasoning = supervisor_result.metadata.get("reasoning", "")
        intent = supervisor_result.extracted_data.get("intent", "unknown")

        # Update attention in thread memory
        await thread.set_attention(
            topic=target_agent_name,
            intent=intent,
            agent="supervisor",
        )

        # Record handoff in episodic memory
        await ltm.save_handoff(
            thread_id=session_id,
            from_agent="supervisor",
            to_agent=target_agent_name,
            reasoning=reasoning,
            user_id=user_id,
        )

        await publish_event(session_id, EventType.AGENT_SWITCH, {
            "from_agent": "supervisor",
            "to_agent": target_agent_name,
            "reasoning": reasoning,
        })

        logger.info(f"[{session_id}] Supervisor → {target_agent_name} ({reasoning})")

        # ─── Step 5: Target agent processes and streams ──────────────
        await thread.set("current_agent", target_agent_name)

        # Refresh context after supervisor enrichment
        context = await thread.get_full_context()

        target_agent = AgentFactory.create_agent(target_agent_name, session_id, provider)
        result: AgentResult = await target_agent.process(user_input, context)

        # ─── Step 6: Save extracted data to ALL memory layers ────────
        if result.extracted_data:
            extracted = {
                k: v for k, v in result.extracted_data.items()
                if v is not None and k != "missing_fields"
            }

            if extracted:
                # Short-term: update working memory
                await thread.update_dict("extracted_data", extracted)

                # Semantic memory: store each fact persistently
                await ltm.save_extracted_data(
                    thread_id=session_id,
                    agent_name=result.agent_name,
                    extracted_data=extracted,
                    user_id=user_id,
                )

                # If it's user profile data, also update the profile in working memory
                if result.agent_name == "user_info":
                    await thread.update_dict("user_profile", extracted)
                    await ltm.save_user_profile(
                        thread_id=session_id,
                        profile=extracted,
                        user_id=user_id,
                    )

                # If it's search criteria, update search criteria in working memory
                if result.agent_name == "rent":
                    await thread.update_dict("search_criteria", extracted)
                    await ltm.save_search_criteria(
                        thread_id=session_id,
                        criteria=extracted,
                        user_id=user_id,
                    )

            await publish_event(session_id, EventType.DATA_EXTRACTED, {
                "agent": result.agent_name,
                "data": result.extracted_data,
            })

        # ─── Step 7: Record agent response ───────────────────────────
        if result.response_text:
            # Episodic memory: record the response event
            await ltm.episodic.record_agent_response(
                thread_id=session_id,
                agent_name=result.agent_name,
                content=result.response_text,
                user_id=user_id,
            )

            # Conversation DB
            await _conversation_repo.add_message(
                conversation_id=conversation.id,
                sender_type="AGENT",
                agent_type=result.agent_name,
                content=result.response_text,
            )

        # Update current agent in conversation record
        await _conversation_repo.update_current_agent(session_id, target_agent_name)

        # ─── Step 8: Learn patterns (procedural memory) ──────────────
        agent_history = await thread.get("agent_history") or []
        agent_history.append(target_agent_name)
        await thread.set("agent_history", agent_history)

        # Record the agent flow as a procedural pattern
        await ltm.learn_from_session(
            thread_id=session_id,
            agent_history=agent_history,
            extracted_data=await thread.get("extracted_data") or {},
            user_id=user_id,
        )

        # ─── Step 9: Emit completion ─────────────────────────────────
        await publish_event(session_id, EventType.AGENT_COMPLETE, {
            "agent": result.agent_name,
            "requires_user_input": result.requires_user_input,
        })

    except Exception as e:
        logger.error(f"[{session_id}] Orchestrator error: {e}", exc_info=True)
        await publish_event(session_id, EventType.ERROR, {"error": str(e)})

    # ─── Always send DONE ────────────────────────────────────────────
    await publish_event(session_id, EventType.DONE, {})