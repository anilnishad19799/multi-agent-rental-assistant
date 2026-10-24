"""Rent Agent — extracts search criteria using structured output, queries DB for real listings."""
import logging
import re
from backend.agents.base_agent import BaseAgent, AgentResult
from backend.agents.agent_factory import AgentFactory
from backend.agents.prompts import RENT_AGENT_SYSTEM_PROMPT
from backend.agents.schemas import RentExtraction
from backend.repositories.property_repository import PropertyRepository

logger = logging.getLogger(__name__)

# Shared repository instance
_property_repo = PropertyRepository()

# Field definitions for rent search: (schema_field, display_label, hint)
_RENT_FIELDS = [
    ("city", "City", ""),
    ("area", "Area / Neighborhood", ""),
    ("budget_max", "Maximum budget (₹/month)", ""),
    ("beds", "Number of beds", ""),
    ("sharing_type", "Sharing type", "e.g. 2-sharing, 3-sharing"),
    ("property_type", "Property type", "PG / Flat (default: PG)"),
    ("food_included", "Food included", "Yes / No (optional)"),
]


def _build_rent_form(missing_fields: list, existing_criteria: dict) -> str:
    """Build an HTML form table for missing rental search fields."""
    collected_rows = []
    for field_name, label, _hint in _RENT_FIELDS:
        if field_name not in missing_fields and field_name in existing_criteria:
            value = existing_criteria[field_name]
            collected_rows.append(
                f'<tr><td><strong>{label}</strong></td>'
                f'<td style="color:#0d652d;">✅ {value}</td></tr>'
            )

    missing_rows = []
    for field_name, label, hint in _RENT_FIELDS:
        if field_name in missing_fields:
            hint_text = f'<span style="color:#888;">{hint}</span>' if hint else '___'
            missing_rows.append(
                f'<tr><td><strong>{label}</strong></td>'
                f'<td>{hint_text}</td></tr>'
            )

    if not missing_rows:
        return ""

    intro = "I'd love to help you find the perfect place! Please fill in the details below:<br><br>"

    table = (
        '<div class="property-table-wrap" style="margin:12px 0; overflow-x:auto;">'
        '<table class="info-form-table" style="width:100%; border-collapse:collapse; border:1px solid #d2e3fc; border-radius:8px; overflow:hidden; background:#fff; font-size:13px;">'
        '<thead><tr style="background:#1a73e8; color:#fff;">'
        '<th style="padding:10px 12px; text-align:left; font-weight:600; border:1px solid #1558b0;">Field</th>'
        '<th style="padding:10px 12px; text-align:left; font-weight:600; border:1px solid #1558b0;">Your Answer</th>'
        '</tr></thead>'
        '<tbody>'
        + "".join(collected_rows)
        + "".join(missing_rows)
        + '</tbody></table></div>'
    )

    follow_up = (
        "<br>Just reply with all the details and I'll search for matching properties! 🏠"
    )

    return intro + table + follow_up


def _format_single_property(prop) -> str:
    """Format a single Property ORM object into a readable text block (used when only 1 result)."""
    lines = [f"🏠 **{prop.title}**"]
    lines.append(f"   📍 {prop.city}, {prop.area}")
    if prop.address:
        lines.append(f"   🗺️  Address: {prop.address}")
    lines.append(f"   Type: {prop.property_type} | Gender Allowed: {prop.gender_allowed or 'Any'}")
    if prop.rating:
        lines.append(f"   ⭐ Rating: {prop.rating}")
    if prop.description:
        lines.append(f"   📝 {prop.description}")

    for cfg in prop.configs:
        sharing = f"{cfg.sharing_type}-sharing" if cfg.sharing_type else "N/A"
        bhk = f" ({cfg.bhk_type})" if cfg.bhk_type else ""
        food = "Yes" if cfg.food_included else "No"
        lines.append(
            f"   💰 ₹{cfg.rent:,.0f}/month{bhk} | {sharing} | "
            f"Beds: {cfg.available_beds or '?'}/{cfg.total_beds or '?'} available | "
            f"Food Included: {food} | "
            f"Min Lease: {cfg.lease_min_months or 'Flexible'} months"
        )

    if prop.amenities:
        amenity_names = [a.amenity_name for a in prop.amenities]
        lines.append(f"   🎯 Amenities: {', '.join(amenity_names)}")

    for lp in prop.landlord_preferences:
        prefs = []
        if lp.gender:
            prefs.append(f"Gender: {lp.gender}")
        if lp.min_age or lp.max_age:
            prefs.append(f"Age: {lp.min_age or '?'}-{lp.max_age or '?'}")
        if lp.profession:
            prefs.append(f"Profession: {lp.profession}")
        if lp.no_cooking:
            prefs.append("No Cooking")
        if lp.no_visitors:
            prefs.append("No Visitors")
        if prefs:
            lines.append(f"   🏡 Landlord Prefs: {', '.join(prefs)}")

    lines.append(f"   🆔 Property ID: {prop.id}")
    return "\n".join(lines)


def _build_property_table(properties: list) -> str:
    """Build an HTML table directly from Property ORM objects.

    Every cell is populated from actual database values — no LLM involvement.
    """
    rows = []
    idx = 0
    for prop in properties:
        for cfg in prop.configs:
            idx += 1
            sharing = f"{cfg.sharing_type}-sharing" if cfg.sharing_type else "N/A"
            bhk = f" ({cfg.bhk_type})" if cfg.bhk_type else ""
            food = "✅" if cfg.food_included else "❌"
            beds = f"{cfg.available_beds or '?'}/{cfg.total_beds or '?'}"
            amenities = ", ".join(a.amenity_name for a in prop.amenities) if prop.amenities else "—"
            rating = f"⭐ {prop.rating}" if prop.rating else "—"
            gender = prop.gender_allowed or "Any"
            lease = f"{cfg.lease_min_months} mo" if cfg.lease_min_months else "Flexible"

            rows.append(
                f"<tr>"
                f"<td>{idx}</td>"
                f"<td><strong>{prop.title}</strong>{bhk}</td>"
                f"<td>{prop.city}, {prop.area}</td>"
                f"<td>₹{cfg.rent:,.0f}/mo</td>"
                f"<td>{sharing}</td>"
                f"<td>{beds}</td>"
                f"<td>{food}</td>"
                f"<td>{gender}</td>"
                f"<td>{lease}</td>"
                f"<td>{amenities}</td>"
                f"<td>{rating}</td>"
                f"<td><code>{prop.id[:8]}</code></td>"
                f"</tr>"
            )

    # If no configs exist at all (edge case), fall back to one row per property
    if not rows:
        for i, prop in enumerate(properties, 1):
            rows.append(
                f"<tr>"
                f"<td>{i}</td>"
                f"<td><strong>{prop.title}</strong></td>"
                f"<td>{prop.city}, {prop.area}</td>"
                f"<td colspan='9'>No configuration details available</td>"
                f"</tr>"
            )

    table = (
        '<div class="property-table-wrap">'
        '<table class="property-table">'
        "<thead><tr>"
        "<th>#</th>"
        "<th>Property</th>"
        "<th>Location</th>"
        "<th>Rent</th>"
        "<th>Sharing</th>"
        "<th>Beds (Avail/Total)</th>"
        "<th>Food</th>"
        "<th>Gender</th>"
        "<th>Lease</th>"
        "<th>Amenities</th>"
        "<th>Rating</th>"
        "<th>ID</th>"
        "</tr></thead>"
        "<tbody>" + "".join(rows) + "</tbody>"
        "</table></div>"
    )
    return table


def _build_selection_index(properties: list) -> list:
    """Build a flat list of (property, config) tuples indexed by row # in the table.

    Row 1 corresponds to index 0, etc.
    """
    index = []
    for prop in properties:
        for cfg in prop.configs:
            index.append({
                "property_id": prop.id,
                "title": prop.title,
                "city": prop.city,
                "area": prop.area,
                "rent": cfg.rent,
                "sharing_type": cfg.sharing_type,
                "food_included": cfg.food_included,
            })
    return index


def _parse_selection(user_input: str) -> int | None:
    """Try to extract a row number from user input like 'first one', '1', 'select #2', etc.

    Returns 1-based row number or None if no selection detected.
    """
    text = user_input.lower().strip()

    # Ordinal words
    ordinals = {
        "first": 1, "1st": 1, "second": 2, "2nd": 2,
        "third": 3, "3rd": 3, "fourth": 4, "4th": 4,
        "fifth": 5, "5th": 5, "sixth": 6, "6th": 6,
    }
    for word, num in ordinals.items():
        if word in text:
            return num

    # Direct number: "select 1", "#2", "number 3", just "1"
    m = re.search(r'(?:select|choose|pick|number|option|#)\s*(\d+)', text)
    if m:
        return int(m.group(1))

    # Bare number if short input
    m = re.match(r'^\s*(\d+)\s*$', text)
    if m:
        return int(m.group(1))

    return None


@AgentFactory.register_agent("rent")
class RentAgent(BaseAgent):
    """Extracts city, area, rent, beds, sharing type via structured LLM output.

    Flow:
    1. Extract structured RentExtraction via structured_output()
    2. If all criteria collected → query DB for matching properties
    3. Show results and ask user to SELECT a property by number
    4. Once selected → store selection and route to user_info
    """

    def __init__(self, session_id: str, provider: str = None):
        super().__init__(
            agent_name="rent",
            session_id=session_id,
            provider=provider,
        )

    def get_system_prompt(self) -> str:
        return RENT_AGENT_SYSTEM_PROMPT

    def get_extraction_prompt(self) -> str:
        return (
            "You are an extraction assistant for a real estate rental system. "
            "Analyze the conversation and extract rental search criteria. "
            "Fill in every field you can determine. Set null for unknown fields. "
            "List required fields that the user has NOT yet provided in missing_fields. "
            "Required fields: city, area, budget_max, beds, sharing_type."
        )

    async def _search_database(self, criteria: dict) -> list:
        """Query the property database using extracted search criteria."""
        try:
            properties = await _property_repo.search_properties(
                city=criteria.get("city"),
                area=criteria.get("area"),
                budget_max=criteria.get("budget_max"),
                beds=criteria.get("beds"),
                sharing_types=criteria.get("sharing_type"),
                property_type=criteria.get("property_type"),
            )
            logger.info(
                f"[{self.session_id}] DB search returned {len(properties)} properties "
                f"for criteria: {criteria}"
            )
            return properties
        except Exception as e:
            logger.error(f"[{self.session_id}] DB search failed: {e}", exc_info=True)
            return []

    def _check_criteria_complete(self, extraction: RentExtraction) -> bool:
        """Check if we have enough criteria to search."""
        return bool(extraction.city) and (
            bool(extraction.area) or bool(extraction.budget_max)
        )

    async def process(self, user_input: str, context: dict) -> AgentResult:
        """Extract criteria, query DB if ready, then respond with real data.

        Flow with property selection:
          1. Search → show results → ask user to select by number
          2. User selects → store selected property → route to user_info
          3. If user says "filter" / "show" again → re-run search and show results
        """
        from backend.events.publisher import publish_event
        from backend.events.types import EventType

        # ── Check if user is selecting a previously shown property ────
        search_results_index = await self.memory.short_term.get("search_results_index")
        selected_property = await self.memory.short_term.get("selected_property")

        # If results were shown and user hasn't selected yet, check for selection
        if search_results_index and not selected_property:
            selection = _parse_selection(user_input)
            if selection is not None and 1 <= selection <= len(search_results_index):
                chosen = search_results_index[selection - 1]
                await self.memory.short_term.set("selected_property", chosen)

                # Build confirmation HTML
                confirm_html = (
                    '<div style="background:#e8f0fe; padding:12px 16px; border-radius:8px; border-left:4px solid #1a73e8; margin:10px 0;">'
                    f'✅ <strong>Selected Property:</strong> #{selection} — {chosen["title"]}<br>'
                    f'📍 {chosen["city"]}, {chosen["area"]} | '
                    f'💰 ₹{chosen["rent"]:,.0f}/mo ({chosen["sharing_type"]}-sharing)'
                    '</div>'
                    'Great choice! 🎉 Now let’s set up your profile so we can finalize this for you! 👤'
                )

                await publish_event(self.session_id, EventType.AGENT_START, {
                    "agent": self.agent_name
                })
                await publish_event(
                    session_id=self.session_id,
                    event_type=EventType.LLM_TOKEN,
                    data={"token": confirm_html, "agent": self.agent_name},
                )
                await publish_event(self.session_id, EventType.LLM_DONE, {
                    "agent": self.agent_name
                })

                await self.memory.add_message("assistant", confirm_html, self.agent_name)

                return AgentResult(
                    agent_name="rent",
                    response_text=confirm_html,
                    extracted_data={},
                    next_agent="user_info",
                    requires_user_input=False,
                    metadata={
                        "selected_property": chosen,
                        "properties_found": len(search_results_index),
                    },
                )

        # ── Normal flow: extract criteria, search, show results ──────

        # Step 1: Extract structured data using Pydantic schema
        extraction: RentExtraction = await self.extract_structured_data(
            user_input=user_input,
            context=context,
            schema=RentExtraction,
        )

        # Step 2: Merge with existing search criteria in memory
        extracted_dict = extraction.model_dump(exclude_none=True)
        extracted_dict.pop("missing_fields", None)

        if extracted_dict:
            existing_criteria = await self.memory.short_term.get("search_criteria") or {}
            existing_criteria.update(extracted_dict)
            await self.memory.short_term.set("search_criteria", existing_criteria)
            await self.memory.short_term.update_dict("extracted_data", existing_criteria)
        else:
            existing_criteria = await self.memory.short_term.get("search_criteria") or {}

        # Build merged criteria for search
        merged_criteria = dict(existing_criteria)
        for key, val in extraction.model_dump(exclude_none=True).items():
            if key != "missing_fields" and val is not None:
                merged_criteria[key] = val

        # Step 3: Decide whether to search the DB
        properties_found = []

        if self._check_criteria_complete(extraction) or (
            merged_criteria.get("city") and not extraction.missing_fields
        ):
            properties_found = await self._search_database(merged_criteria)

        # ── Branch A: Properties found → emit DB table + ask to select ─
        if properties_found:
            # Build the selection index and store it for later
            selection_index = _build_selection_index(properties_found)
            await self.memory.short_term.set("search_results_index", selection_index)
            # Clear any previous selection
            await self.memory.short_term.set("selected_property", None)

            await publish_event(self.session_id, EventType.AGENT_START, {
                "agent": self.agent_name
            })

            # Build header summary from actual search criteria
            city = merged_criteria.get("city", "")
            area = merged_criteria.get("area", "")
            location = f"{area}, {city}" if area else city
            count = len(properties_found)

            intro = (
                f"I found <strong>{count}</strong> properties in "
                f"<strong>{location}</strong> matching your criteria:<br><br>"
            )

            # Build the table from raw DB data
            table_html = _build_property_table(properties_found)

            follow_up = (
                "<br>👆 <strong>Please select a property by typing its number</strong> "
                "(e.g., <em>1</em>, <em>select 2</em>, <em>first one</em>) "
                "to proceed with your profile and booking."
            )

            full_response = intro + table_html + follow_up

            # Emit the entire block as a single token so the frontend
            # renders it in one go (no partial HTML issues)
            await publish_event(
                session_id=self.session_id,
                event_type=EventType.LLM_TOKEN,
                data={"token": full_response, "agent": self.agent_name},
            )

            await publish_event(self.session_id, EventType.LLM_DONE, {
                "agent": self.agent_name
            })

            # Store in thread memory
            await self.memory.add_message("assistant", full_response, self.agent_name)

        # ── Branch B: No properties found after search ───────────────
        elif self._check_criteria_complete(extraction) or (
            merged_criteria.get("city") and not extraction.missing_fields
        ):
            no_results_ctx = dict(context)
            no_results_ctx["db_search_results"] = (
                "\n\nDATABASE SEARCH RESULTS — No properties found matching the criteria. "
                "Tell the user no exact matches were found and suggest adjusting their "
                "filters (e.g., increasing budget, trying a different area, or changing sharing type). "
                "Do NOT make up any properties."
            )
            full_response = ""
            async for token in self.stream_response(user_input, no_results_ctx):
                full_response += token

        # ── Branch C: Still collecting criteria — show form table ────
        else:
            form_html = _build_rent_form(
                extraction.missing_fields, merged_criteria
            )
            if form_html:
                # Emit form built in Python — guaranteed correct HTML
                await publish_event(self.session_id, EventType.AGENT_START, {
                    "agent": self.agent_name
                })
                await publish_event(
                    session_id=self.session_id,
                    event_type=EventType.LLM_TOKEN,
                    data={"token": form_html, "agent": self.agent_name},
                )
                await publish_event(self.session_id, EventType.LLM_DONE, {
                    "agent": self.agent_name
                })
                full_response = form_html
                await self.memory.add_message("assistant", full_response, self.agent_name)
            else:
                # Fallback: LLM conversation if no missing fields identified
                full_response = ""
                async for token in self.stream_response(user_input, context):
                    full_response += token

        # Step 5: Determine next agent
        has_missing = bool(extraction.missing_fields)
        next_agent = None
        # Do NOT auto-route to user_info — wait for the user to select a property first

        return AgentResult(
            agent_name="rent",
            response_text=full_response,
            extracted_data=extraction.model_dump(),
            next_agent=next_agent,
            requires_user_input=True,  # Always wait for user (either criteria or selection)
            metadata={
                "missing_fields": extraction.missing_fields,
                "properties_found": len(properties_found),
            },
        )
