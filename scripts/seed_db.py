"""Seed script — populates the database with sample properties and agent data."""
import asyncio
import sys
import os
from datetime import date, time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models.base import init_db, get_session
# Import ALL models so Base.metadata knows about all tables for FK resolution
from backend.models.user import User, UserPreference  # noqa: F401
from backend.models.property import Property, PropertyConfig, PropertyAmenity, PropertyImage, LandlordPreference  # noqa: F401
from backend.models.booking import SearchRequest, SearchResult, ShortlistedProperty, Booking, RealEstateAgent, AgentAvailability  # noqa: F401
from backend.models.conversation import Conversation, Message, ConversationMemory, UserExtractedInfoLog  # noqa: F401
from backend.models.memory import SemanticMemoryRecord, EpisodicMemoryRecord, ProceduralMemoryRecord  # noqa: F401


SAMPLE_PROPERTIES = [
    {
        "title": "Sunshine PG - Hadapsar",
        "description": "Well-maintained PG with AC rooms, WiFi, and mess facility near IT Park.",
        "city": "Pune",
        "area": "Hadapsar",
        "address": "Lane 5, Hadapsar IT Park Road, Pune 411028",
        "property_type": "PG",
        "gender_allowed": "ANY",
        "rating": 4.2,
        "configs": [
            {"sharing_type": 2, "rent": 7500, "total_beds": 10, "available_beds": 3, "food_included": True, "lease_min_months": 6},
            {"sharing_type": 3, "rent": 6000, "total_beds": 15, "available_beds": 5, "food_included": True, "lease_min_months": 6},
        ],
        "amenities": ["WiFi", "AC", "Laundry", "Mess", "Power Backup"],
        "landlord_prefs": {"gender": "ANY", "min_age": 18, "max_age": 35, "no_cooking": True, "no_visitors": False},
    },
    {
        "title": "Green Valley PG - Hadapsar",
        "description": "Budget-friendly PG with garden view, near Magarpatta City.",
        "city": "Pune",
        "area": "Hadapsar",
        "address": "Near Magarpatta Gate, Hadapsar, Pune 411028",
        "property_type": "PG",
        "gender_allowed": "MALE",
        "rating": 3.8,
        "configs": [
            {"sharing_type": 2, "rent": 6500, "total_beds": 8, "available_beds": 2, "food_included": False, "lease_min_months": 3},
            {"sharing_type": 3, "rent": 5500, "total_beds": 12, "available_beds": 4, "food_included": False, "lease_min_months": 3},
        ],
        "amenities": ["WiFi", "Garden", "Parking", "Water Purifier"],
        "landlord_prefs": {"gender": "MALE", "min_age": 20, "max_age": 30, "profession": "IT", "no_cooking": False},
    },
    {
        "title": "Royal Heights PG - Andheri",
        "description": "Premium PG near Andheri Station with gym and rooftop.",
        "city": "Mumbai",
        "area": "Andheri",
        "address": "Andheri West, Near DN Nagar Metro, Mumbai 400053",
        "property_type": "PG",
        "gender_allowed": "ANY",
        "rating": 4.5,
        "configs": [
            {"sharing_type": 2, "rent": 12000, "total_beds": 6, "available_beds": 2, "food_included": True, "lease_min_months": 6},
            {"sharing_type": 3, "rent": 9000, "total_beds": 9, "available_beds": 3, "food_included": True, "lease_min_months": 6},
        ],
        "amenities": ["WiFi", "AC", "Gym", "Rooftop", "Laundry", "CCTV", "Power Backup"],
        "landlord_prefs": {"gender": "ANY", "min_age": 18, "max_age": 40, "no_cooking": True, "no_visitors": False},
    },
    {
        "title": "Comfort Zone Flat - Andheri",
        "description": "Spacious 2BHK flat with balcony, close to metro.",
        "city": "Mumbai",
        "area": "Andheri",
        "address": "Lokhandwala Complex, Andheri West, Mumbai 400053",
        "property_type": "FLAT",
        "gender_allowed": "ANY",
        "rating": 4.0,
        "configs": [
            {"bhk_type": "2BHK", "sharing_type": 2, "rent": 15000, "total_beds": 4, "available_beds": 2, "food_included": False, "lease_min_months": 11},
        ],
        "amenities": ["WiFi", "AC", "Balcony", "Parking", "Security"],
        "landlord_prefs": {"gender": "ANY", "min_age": 22, "max_age": 45, "lease_required_months": 11, "no_cooking": False},
    },
    {
        "title": "Tech Park PG - Whitefield",
        "description": "Modern PG near ITPL, ideal for techies.",
        "city": "Bangalore",
        "area": "Whitefield",
        "address": "Near ITPL Main Road, Whitefield, Bangalore 560066",
        "property_type": "PG",
        "gender_allowed": "ANY",
        "rating": 4.3,
        "configs": [
            {"sharing_type": 2, "rent": 9000, "total_beds": 12, "available_beds": 4, "food_included": True, "lease_min_months": 3},
            {"sharing_type": 3, "rent": 7000, "total_beds": 18, "available_beds": 6, "food_included": True, "lease_min_months": 3},
        ],
        "amenities": ["WiFi", "AC", "Mess", "Gym", "Laundry", "Game Room"],
        "landlord_prefs": {"gender": "ANY", "min_age": 20, "max_age": 35, "no_cooking": True},
    },
]


SAMPLE_AGENT = {
    "name": "Rajesh Kumar",
    "email": "rajesh@realestate.com",
    "phone": "+91-9876543210",
    "role": "PROPERTY_AGENT",
    "availability": [
        {"date": date(2026, 9, 10), "start": time(9, 0), "end": time(10, 0)},
        {"date": date(2026, 9, 10), "start": time(11, 0), "end": time(12, 0)},
        {"date": date(2026, 9, 10), "start": time(14, 0), "end": time(15, 0)},
        {"date": date(2026, 9, 10), "start": time(16, 0), "end": time(17, 0)},
        {"date": date(2026, 9, 11), "start": time(9, 0), "end": time(10, 0)},
        {"date": date(2026, 9, 11), "start": time(11, 0), "end": time(12, 0)},
        {"date": date(2026, 9, 11), "start": time(14, 0), "end": time(15, 0)},
        {"date": date(2026, 9, 12), "start": time(10, 0), "end": time(11, 0)},
        {"date": date(2026, 9, 12), "start": time(15, 0), "end": time(16, 0)},
    ],
}


async def seed():
    print("🌱 Initializing database...")
    await init_db()

    async with get_session() as session:
        # Seed properties
        for prop_data in SAMPLE_PROPERTIES:
            prop = Property(
                title=prop_data["title"],
                description=prop_data["description"],
                city=prop_data["city"],
                area=prop_data["area"],
                address=prop_data["address"],
                property_type=prop_data["property_type"],
                gender_allowed=prop_data["gender_allowed"],
                rating=prop_data["rating"],
            )
            session.add(prop)
            await session.flush()  # get prop.id

            for cfg in prop_data["configs"]:
                config = PropertyConfig(
                    property_id=prop.id,
                    bhk_type=cfg.get("bhk_type"),
                    total_beds=cfg.get("total_beds"),
                    available_beds=cfg.get("available_beds"),
                    sharing_type=cfg.get("sharing_type"),
                    rent=cfg["rent"],
                    food_included=cfg.get("food_included", False),
                    lease_min_months=cfg.get("lease_min_months"),
                )
                session.add(config)

            for amenity in prop_data.get("amenities", []):
                session.add(PropertyAmenity(property_id=prop.id, amenity_name=amenity))

            lp = prop_data.get("landlord_prefs", {})
            if lp:
                session.add(LandlordPreference(property_id=prop.id, **lp))

            print(f"  ✅ Added: {prop_data['title']}")

        # Seed real estate agent
        agent = RealEstateAgent(
            name=SAMPLE_AGENT["name"],
            email=SAMPLE_AGENT["email"],
            phone=SAMPLE_AGENT["phone"],
            role=SAMPLE_AGENT["role"],
        )
        session.add(agent)
        await session.flush()

        for slot in SAMPLE_AGENT["availability"]:
            session.add(AgentAvailability(
                agent_id=agent.id,
                available_date=slot["date"],
                start_time=slot["start"],
                end_time=slot["end"],
                is_booked=False,
            ))

        print(f"  ✅ Added agent: {SAMPLE_AGENT['name']} with {len(SAMPLE_AGENT['availability'])} slots")

        await session.commit()

    print("\n🎉 Database seeded successfully!")
    print(f"   {len(SAMPLE_PROPERTIES)} properties")
    print(f"   1 real estate agent with availability slots")


if __name__ == "__main__":
    asyncio.run(seed())
