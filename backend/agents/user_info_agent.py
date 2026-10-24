"""User Info Agent — collects user profile using structured output."""
import logging
from backend.agents.base_agent import BaseAgent, AgentResult
from backend.agents.agent_factory import AgentFactory
from backend.agents.prompts import USER_INFO_AGENT_SYSTEM_PROMPT
from backend.agents.schemas import UserInfoExtraction

logger = logging.getLogger(__name__)

# Field definitions: (schema_field_name, display_label, hint)
_USER_INFO_FIELDS = [
    ("name", "Full name", ""),
    ("gender", "Gender", "Male / Female / Other"),
    ("working_profession", "Job title or occupation", ""),
    ("age", "Age", "Must be 18+"),
    ("citizenship", "Citizenship", "Indian / Foreign"),
    ("lease_period", "Lease duration (months)", ""),
    ("move_in_date", "Move-in date", "DD/MM/YYYY"),
    ("number_of_person", "Number of people who will stay", ""),
    ("cooking_available", "Cooking facility needed", "Yes / No"),
]


def _build_info_form(missing_fields: list, existing_profile: dict) -> str:
    """Build an HTML form table for missing user info fields.

    This is built in Python (not by the LLM) to guarantee correct HTML
    rendering — same pattern as the rent agent's property table.
    """
    # Show already-collected fields at the top
    collected_rows = []
    for field_name, label, _hint in _USER_INFO_FIELDS:
        if field_name not in missing_fields and field_name in existing_profile:
            value = existing_profile[field_name]
            collected_rows.append(
                f'<tr><td><strong>{label}</strong></td>'
                f'<td style="color:#0d652d;">✅ {value}</td></tr>'
            )

    # Build rows for missing fields
    missing_rows = []
    for field_name, label, hint in _USER_INFO_FIELDS:
        if field_name in missing_fields:
            hint_text = f'<span style="color:#888;">{hint}</span>' if hint else '___'
            missing_rows.append(
                f'<tr><td><strong>{label}</strong></td>'
                f'<td>{hint_text}</td></tr>'
            )

    if not missing_rows:
        return ""

    intro = "To match you with the best options, please fill in the details below:<br><br>"

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
        "<br>Just reply with your answers in any order "
        "— I'll pick them up automatically! 🚀"
    )

    return intro + table + follow_up


def _build_profile_summary(profile: dict, selected_property: dict = None) -> str:
    """Build a clean HTML summary table of the user's completed profile.

    Presents every field line-by-line in a clean table format so the user
    can verify all their details clearly.
    """
    name = profile.get("name", "there")

    prop_banner = ""
    if selected_property:
        title = selected_property.get("title", "")
        city = selected_property.get("city", "")
        area = selected_property.get("area", "")
        rent = selected_property.get("rent", 0)
        sharing = selected_property.get("sharing_type", "")
        loc = f"{area}, {city}" if area else city
        prop_banner = (
            '<div style="background:#e8f0fe; padding:10px 14px; border-radius:6px; margin:10px 0; border-left:4px solid #1a73e8;">'
            f'🏠 <strong>Selected Property:</strong> {title} ({loc}) | <strong>Rent:</strong> ₹{rent:,.0f}/mo ({sharing}-sharing)'
            '</div>'
        )

    rows = []
    for field_name, label, _hint in _USER_INFO_FIELDS:
        val = profile.get(field_name)
        if val is not None:
            if field_name == "cooking_available":
                val_str = "Yes" if str(val).lower() in ("true", "yes", "1") else "No"
            elif field_name == "lease_period":
                val_str = f"{val} months"
            elif field_name == "age":
                val_str = f"{val} years"
            elif field_name == "number_of_person":
                val_str = f"{val} person(s)"
            else:
                val_str = str(val)

            rows.append(
                f'<tr style="border-bottom:1px solid #e0e0e0;">'
                f'<td style="padding:9px 12px; background:#f0f4f9; font-weight:600; width:38%; color:#202124;">{label}</td>'
                f'<td style="padding:9px 12px; color:#202124;">{val_str}</td>'
                f'</tr>'
            )

    table_html = (
        '<div class="property-table-wrap" style="margin:12px 0; overflow-x:auto;">'
        '<table class="info-form-table" style="width:100%; border-collapse:collapse; border:1px solid #d2e3fc; border-radius:8px; overflow:hidden; background:#fff; font-size:13px;">'
        '<thead><tr style="background:#1a73e8; color:#fff;">'
        '<th colspan="2" style="padding:10px 12px; text-align:left; font-weight:600; border:1px solid #1558b0;">👤 Confirmed User Profile</th>'
        '</tr></thead>'
        '<tbody>'
        + "".join(rows)
        + '</tbody></table></div>'
    )

    action_btn = (
        '<div style="margin:10px 0;">'
        '<button type="button" onclick="proceedToCalendar()" style="background:#1a73e8; color:#fff; border:none; padding:9px 18px; border-radius:6px; font-size:13px; font-weight:600; cursor:pointer;">'
        '📅 Schedule Property Visit'
        '</button>'
        '</div>'
    )

    intro = f"Thank you, <strong>{name}</strong>! I’ve captured all of your details:<br>"
    follow_up = (
        "<br>Everything looks great! 🎉 Your profile is complete and saved.<br>"
        + action_btn +
        "You can click <strong>Schedule Property Visit</strong> above or type <strong>proceed</strong> to view available visit slots! 🚀"
    )

    return intro + prop_banner + table_html + follow_up


@AgentFactory.register_agent("user_info")
class UserInfoAgent(BaseAgent):
    """Collects user profile via structured LLM output.

    Flow:
    1. Extract structured UserInfoExtraction via structured_output()
    2. If fields are missing → emit an HTML form table (built in Python)
    3. If all fields collected → stream a confirmation via LLM
    4. Merge into memory and determine next agent
    """

    def __init__(self, session_id: str, provider: str = None):
        super().__init__(
            agent_name="user_info",
            session_id=session_id,
            provider=provider,
        )

    def get_system_prompt(self) -> str:
        return USER_INFO_AGENT_SYSTEM_PROMPT

    def get_extraction_prompt(self) -> str:
        return (
            "You are an extraction assistant for a real estate rental system. "
            "Analyze the conversation and extract user personal information. "
            "Fill in every field you can determine. Set null for unknown fields. "
            "List required fields that the user has NOT yet provided in missing_fields. "
            "Required fields: name, gender, working_profession, age, citizenship, "
            "lease_period, move_in_date, number_of_person, cooking_available."
        )

    async def process(self, user_input: str, context: dict) -> AgentResult:
        """Extract user info, show form for missing fields, or confirm when done."""
        from backend.events.publisher import publish_event
        from backend.events.types import EventType

        # Step 1: Store user message in memory
        await self.memory.add_message("user", user_input, self.agent_name)

        # Step 2: Extract structured data
        extraction: UserInfoExtraction = await self.extract_structured_data(
            user_input=user_input,
            context=context,
            schema=UserInfoExtraction,
        )

        # Step 3: Merge into user profile memory
        extracted_dict = extraction.model_dump(exclude_none=True)
        extracted_dict.pop("missing_fields", None)

        existing_profile = await self.memory.short_term.get("user_profile") or {}
        if extracted_dict:
            existing_profile.update(extracted_dict)
            await self.memory.short_term.set("user_profile", existing_profile)
            await self.memory.short_term.update_dict("extracted_data", existing_profile)

        # Step 4: Decide response
        has_missing = bool(extraction.missing_fields)

        if has_missing:
            # ── Build form HTML in Python — guaranteed correct rendering ──
            form_html = _build_info_form(extraction.missing_fields, existing_profile)

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
            # ── All fields collected — build clean HTML profile summary table in Python ─────
            selected_property = await self.memory.short_term.get("selected_property")
            summary_html = _build_profile_summary(existing_profile, selected_property)

            await publish_event(self.session_id, EventType.AGENT_START, {
                "agent": self.agent_name
            })
            await publish_event(
                session_id=self.session_id,
                event_type=EventType.LLM_TOKEN,
                data={"token": summary_html, "agent": self.agent_name},
            )
            await publish_event(self.session_id, EventType.LLM_DONE, {
                "agent": self.agent_name
            })

            full_response = summary_html
            await self.memory.add_message("assistant", full_response, self.agent_name)

        # Step 5: Determine next agent
        next_agent = None
        if not has_missing:
            next_agent = "calendar"

        return AgentResult(
            agent_name="user_info",
            response_text=full_response,
            extracted_data=extraction.model_dump(),
            next_agent=next_agent,
            requires_user_input=has_missing,
            metadata={"missing_fields": extraction.missing_fields},
        )
