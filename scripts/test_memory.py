"""Test script for the memory system — validates all three memory types."""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import ALL models at module level so Base.metadata has all tables
from backend.models.user import User, UserPreference  # noqa: F401
from backend.models.property import Property, PropertyConfig, PropertyAmenity, PropertyImage, LandlordPreference  # noqa: F401
from backend.models.booking import SearchRequest, SearchResult, ShortlistedProperty, Booking, RealEstateAgent, AgentAvailability  # noqa: F401
from backend.models.conversation import Conversation, Message, ConversationMemory, UserExtractedInfoLog  # noqa: F401
from backend.models.memory import SemanticMemoryRecord, EpisodicMemoryRecord, ProceduralMemoryRecord  # noqa: F401

from backend.models.base import init_db
from backend.memory.short_term import ThreadMemory
from backend.memory.long_term import LongTermMemory


async def test():
    await init_db()

    print("═══ SHORT-TERM MEMORY (ThreadMemory) ═══")
    thread = ThreadMemory("test-session-1")
    await thread.add_message("user", "Show me PG in Hadapsar under 8000")
    await thread.add_message("assistant", "Sure! Let me help.", agent="rent")
    await thread.set("current_agent", "rent")
    await thread.set_attention(topic="property_search", intent="rent_search")
    await thread.update_dict("search_criteria", {"city": "Pune", "area": "Hadapsar", "budget_max": 8000})

    msgs = await thread.get_messages()
    print(f"  Buffer: {len(msgs)} messages")
    print(f"  Agent: {await thread.get('current_agent')}")
    print(f"  Attention: {await thread.get_attention()}")
    print("  ✅ Short-term OK")

    print()
    print("═══ LONG-TERM: SEMANTIC MEMORY (Facts) ═══")
    ltm = LongTermMemory()
    await ltm.semantic.store_fact("USER", "name", "Rahul", thread_id="test-session-1", source_agent="user_info")
    await ltm.semantic.store_fact("USER", "age", "25", thread_id="test-session-1", source_agent="user_info")
    await ltm.semantic.store_fact("SEARCH", "city", "Pune", thread_id="test-session-1", source_agent="rent")
    await ltm.semantic.store_fact("SEARCH", "budget_max", "8000", thread_id="test-session-1", source_agent="rent")

    facts = await ltm.semantic.get_facts_by_entity("USER", thread_id="test-session-1")
    print(f"  User facts: {facts}")
    search = await ltm.semantic.get_facts_by_entity("SEARCH", thread_id="test-session-1")
    print(f"  Search facts: {search}")

    # Test upsert
    await ltm.semantic.store_fact("SEARCH", "budget_max", "10000", thread_id="test-session-1", source_agent="rent")
    updated = await ltm.semantic.get_fact("SEARCH", "budget_max", thread_id="test-session-1")
    print(f"  Budget after upsert: {updated}")
    print("  ✅ Semantic OK")

    print()
    print("═══ LONG-TERM: EPISODIC MEMORY (Events) ═══")
    await ltm.episodic.record_user_message("test-session-1", "Show me PG in Hadapsar")
    await ltm.episodic.record_agent_handoff("test-session-1", "supervisor", "rent", "search query")
    await ltm.episodic.record_data_extraction("test-session-1", "rent", {"city": "Pune"})
    await ltm.episodic.record_agent_response("test-session-1", "rent", "Found 3 PGs!")
    episodes = await ltm.episodic.get_thread_episodes("test-session-1")
    print(f"  Episodes: {len(episodes)}")
    for ep in episodes:
        print(f"    {ep['action']}: {(ep.get('content') or '')[:50]}")
    print("  ✅ Episodic OK")

    print()
    print("═══ LONG-TERM: PROCEDURAL MEMORY (Patterns) ═══")
    await ltm.procedural.record_preference("city", "Pune")
    await ltm.procedural.record_preference("property_type", "PG")
    await ltm.procedural.record_preference("city", "Pune")  # reinforce
    await ltm.procedural.record_agent_sequence(["supervisor", "rent", "user_info"])
    patterns = await ltm.procedural.get_patterns()
    print(f"  Patterns: {len(patterns)}")
    for p in patterns:
        print(f"    [{p['type']}] {p['key']}: {p['value']} (freq={p['frequency']})")
    print("  ✅ Procedural OK")

    print()
    print("═══ FULL CONTEXT (all 3 combined) ═══")
    full = await ltm.build_context(thread_id="test-session-1")
    print(full)

    await ThreadMemory.cleanup_thread("test-session-1")
    print()
    print("🎉 ALL MEMORY TESTS PASSED!")


if __name__ == "__main__":
    asyncio.run(test())
