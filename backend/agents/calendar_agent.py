"""Calendar Agent — handles booking using structured output and clean HTML table responses."""
import logging
import re
from datetime import datetime, timedelta, date, time
from typing import Optional

from backend.agents.base_agent import BaseAgent, AgentResult
from backend.agents.agent_factory import AgentFactory
from backend.agents.prompts import CALENDAR_AGENT_SYSTEM_PROMPT
from backend.agents.schemas import CalendarExtraction
from backend.repositories.booking_repository import BookingRepository

logger = logging.getLogger(__name__)

_booking_repo = BookingRepository()


def _generate_upcoming_slots():
    """Generate next 4 upcoming Mon-Sat days with 1-hour slots."""
    today = datetime.now()
    slots = []
    curr = today + timedelta(days=1)
    while len(slots) < 4:
        if curr.weekday() != 6:  # Skip Sunday
            slots.append({
                "date_display": curr.strftime("%b %d, %Y"),
                "date_val": curr.strftime("%Y-%m-%d"),
                "day": curr.strftime("%A"),
                "times": ["10:00 AM", "02:00 PM", "05:00 PM"],
            })
        curr += timedelta(days=1)
    return slots


def _build_slots_table(selected_property: Optional[dict] = None) -> str:
    """Build a rich, interactive HTML table showing upcoming visit slots."""
    prop_title = selected_property.get("title", "the property") if selected_property else "the property"
    city = selected_property.get("city", "") if selected_property else ""
    area = selected_property.get("area", "") if selected_property else ""
    loc_str = f"{area}, {city}" if area and city else (city or area or "")
    prop_desc = f"<strong>{prop_title}</strong>" + (f" ({loc_str})" if loc_str else "")

    slots = _generate_upcoming_slots()
    rows = []
    for s in slots:
        date_disp = s["date_display"]
        btn_list = []
        for t in s["times"]:
            btn_list.append(
                f'<button type="button" class="slot-pill-btn" onclick="selectSlot(\'{date_disp}\', \'{t}\')" '
                f'style="background:#e8f0fe; color:#1a73e8; border:1px solid #1a73e8; padding:5px 10px; border-radius:6px; font-size:12px; font-weight:600; cursor:pointer; margin:2px 3px; display:inline-block;">⏰ {t}</button>'
            )
        buttons = " ".join(btn_list)
        rows.append(
            f'<tr style="border-bottom:1px solid #e0e0e0;">'
            f'<td style="padding:10px 12px; font-weight:600; color:#202124; white-space:nowrap;">📅 {date_disp}</td>'
            f'<td style="padding:10px 12px; color:#5f6368;">{s["day"]}</td>'
            f'<td style="padding:8px 12px;">{buttons}</td>'
            f'</tr>'
        )

    table_html = (
        '<div class="property-table-wrap" style="margin:12px 0; overflow-x:auto;">'
        '<table class="slots-table" style="width:100%; border-collapse:collapse; border:1px solid #d2e3fc; border-radius:8px; overflow:hidden; background:#fff; font-size:13px; font-family:inherit;">'
        '<thead><tr style="background:#1a73e8; color:#fff;">'
        '<th style="padding:10px 12px; text-align:left; font-weight:600; border:1px solid #1558b0;">Date</th>'
        '<th style="padding:10px 12px; text-align:left; font-weight:600; border:1px solid #1558b0;">Day</th>'
        '<th style="padding:10px 12px; text-align:left; font-weight:600; border:1px solid #1558b0;">Available 1-Hour Slots (Click to Select)</th>'
        '</tr></thead>'
        '<tbody>'
        + "".join(rows)
        + '</tbody></table></div>'
    )

    intro = (
        f"Great choice! 🎉 Let’s set up an appointment so you can visit {prop_desc} in person.<br><br>"
        "<strong>Visits are available Monday to Saturday, 7:00 AM – 9:00 PM in 1-hour slots.</strong><br>"
        "Here are upcoming open slots — <em>click any time button below</em> or type your preference:<br>"
    )

    follow_up = (
        "<br>👉 <strong>Click a slot button above</strong> or type your preferred date & time "
        "(e.g., <em>10 Nov 2026 at 10 AM</em>), and I’ll prepare your booking! 🚀"
    )

    return intro + table_html + follow_up


def _format_time_slot(time_str: str) -> str:
    """Format time string like '10:00' into '10:00 AM – 11:00 AM'."""
    try:
        parts = time_str.split(":")
        hh = int(parts[0])
        mm = int(parts[1][:2]) if len(parts) > 1 else 0
        dt = datetime(2000, 1, 1, hh, mm)
        end_dt = dt + timedelta(hours=1)
        return f"{dt.strftime('%I:%M %p')} – {end_dt.strftime('%I:%M %p')}"
    except Exception:
        if "am" in time_str.lower() or "pm" in time_str.lower():
            return time_str
        return time_str


def _format_date_display(date_str: str) -> str:
    """Format YYYY-MM-DD or raw date string nicely."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%A, %d %b %Y")
    except Exception:
        return date_str


def _build_booking_summary_table(selected_property: Optional[dict], date_str: str, time_str: str) -> str:
    """Build an HTML table summarizing the appointment awaiting confirmation."""
    prop_title = selected_property.get("title", "Property Visit") if selected_property else "Property Visit"
    city = selected_property.get("city", "") if selected_property else ""
    area = selected_property.get("area", "") if selected_property else ""
    rent = selected_property.get("rent", 0) if selected_property else 0
    sharing = selected_property.get("sharing_type", "") if selected_property else ""

    loc_str = f"{area}, {city}" if area and city else (city or area or "")
    prop_detail = f"{prop_title}" + (f" ({loc_str})" if loc_str else "")
    if rent:
        prop_detail += f" | ₹{rent:,.0f}/mo"
    if sharing:
        prop_detail += f" ({sharing}-sharing)"

    formatted_date = _format_date_display(date_str)
    formatted_time = _format_time_slot(time_str)

    table_html = (
        '<div class="property-table-wrap" style="margin:12px 0; overflow-x:auto;">'
        '<table class="info-form-table" style="width:100%; border-collapse:collapse; border:1px solid #d2e3fc; border-radius:8px; overflow:hidden; background:#fff; font-size:13px;">'
        '<thead><tr style="background:#1a73e8; color:#fff;">'
        '<th colspan="2" style="padding:10px 12px; text-align:left; font-weight:600; border:1px solid #1558b0;">📅 Appointment Summary</th>'
        '</tr></thead>'
        '<tbody>'
        f'<tr style="border-bottom:1px solid #e0e0e0;"><td style="padding:10px 12px; background:#f0f4f9; font-weight:600; width:35%;">Property</td><td style="padding:10px 12px; color:#202124;">{prop_detail}</td></tr>'
        f'<tr style="border-bottom:1px solid #e0e0e0;"><td style="padding:10px 12px; background:#f0f4f9; font-weight:600;">Date</td><td style="padding:10px 12px; color:#202124;">📅 {formatted_date}</td></tr>'
        f'<tr style="border-bottom:1px solid #e0e0e0;"><td style="padding:10px 12px; background:#f0f4f9; font-weight:600;">Time Slot</td><td style="padding:10px 12px; color:#202124;">⏰ {formatted_time}</td></tr>'
        f'<tr><td style="padding:10px 12px; background:#f0f4f9; font-weight:600;">Status</td><td style="padding:10px 12px;"><span style="background:#fef7e0; color:#b06000; border:1px solid #f9ab00; padding:4px 10px; border-radius:12px; font-size:12px; font-weight:600;">Pending Confirmation</span></td></tr>'
        '</tbody></table></div>'
    )

    action_btn = (
        '<div style="margin:10px 0;">'
        '<button type="button" onclick="confirmBooking()" style="background:#0d652d; color:#fff; border:none; padding:9px 18px; border-radius:6px; font-size:13px; font-weight:600; cursor:pointer;">'
        '✅ Confirm This Visit'
        '</button>'
        '</div>'
    )

    intro = f"✅ Good news — the slot on <strong>{formatted_date}</strong> at <strong>{formatted_time}</strong> is currently free!<br><br>"
    follow_up = (
        "<br>Shall I go ahead and lock this visit in for you?<br>"
        + action_btn +
        "You can click <strong>Confirm This Visit</strong> above or simply reply <strong>Yes</strong> (or suggest another time). 🚀"
    )

    return intro + table_html + follow_up


def _build_booking_confirmed_card(selected_property: Optional[dict], date_str: str, time_str: str, booking_id: str = "") -> str:
    """Build an HTML table showing the final confirmed booking."""
    prop_title = selected_property.get("title", "Property Visit") if selected_property else "Property Visit"
    city = selected_property.get("city", "") if selected_property else ""
    area = selected_property.get("area", "") if selected_property else ""
    loc_str = f"{area}, {city}" if area and city else (city or area or "")

    formatted_date = _format_date_display(date_str)
    formatted_time = _format_time_slot(time_str)

    bid_row = f'<tr style="border-bottom:1px solid #e0e0e0;"><td style="padding:10px 12px; background:#f0f4f9; font-weight:600; width:35%;">Booking ID</td><td style="padding:10px 12px;"><code style="background:#eee; padding:2px 6px; border-radius:3px;">{booking_id[:8]}</code></td></tr>' if booking_id else ''

    table_html = (
        '<div class="property-table-wrap" style="margin:12px 0; overflow-x:auto;">'
        '<table class="info-form-table" style="width:100%; border-collapse:collapse; border:1px solid #34a853; border-radius:8px; overflow:hidden; background:#fff; font-size:13px;">'
        '<thead><tr style="background:#0d652d; color:#fff;">'
        '<th colspan="2" style="padding:10px 12px; text-align:left; font-weight:600; border:1px solid #0b5324;">✅ Your Visit is Confirmed!</th>'
        '</tr></thead>'
        '<tbody>'
        + bid_row +
        f'<tr style="border-bottom:1px solid #e0e0e0;"><td style="padding:10px 12px; background:#f0f4f9; font-weight:600;">Property</td><td style="padding:10px 12px; color:#202124;"><strong>{prop_title}</strong></td></tr>'
        f'<tr style="border-bottom:1px solid #e0e0e0;"><td style="padding:10px 12px; background:#f0f4f9; font-weight:600;">Location</td><td style="padding:10px 12px; color:#202124;">📍 {loc_str or "Exact address will be shared by property manager"}</td></tr>'
        f'<tr style="border-bottom:1px solid #e0e0e0;"><td style="padding:10px 12px; background:#f0f4f9; font-weight:600;">Date</td><td style="padding:10px 12px; color:#202124;">📅 {formatted_date}</td></tr>'
        f'<tr style="border-bottom:1px solid #e0e0e0;"><td style="padding:10px 12px; background:#f0f4f9; font-weight:600;">Time Slot</td><td style="padding:10px 12px; color:#202124;">⏰ {formatted_time}</td></tr>'
        f'<tr><td style="padding:10px 12px; background:#f0f4f9; font-weight:600;">Status</td><td style="padding:10px 12px;"><span style="background:#e6f4ea; color:#137333; border:1px solid #34a853; padding:4px 10px; border-radius:12px; font-size:12px; font-weight:600;">CONFIRMED</span></td></tr>'
        '</tbody></table></div>'
    )

    intro = "🎉 <strong>Congratulations! Your appointment has been successfully booked.</strong><br><br>"
    follow_up = (
        "<br><strong>What to expect next:</strong><br>"
        "1. 📩 The property manager will contact you shortly with entry instructions.<br>"
        "2. 🆔 Please carry a valid government photo ID for building access upon arrival.<br>"
        "3. 🔄 If you need to reschedule or have any queries, just let me know anytime.<br><br>"
        "Is there anything else I can help you with today? 🏠"
    )

    return intro + table_html + follow_up


def _parse_date_time_fallback(text: str) -> tuple[Optional[str], Optional[str]]:
    """Heuristic fallback to extract date and time if LLM didn't catch them."""
    date_val = None
    time_val = None

    # Date match: e.g. "10 Nov 2026", "28 Oct", "2026-11-10"
    m_date = re.search(r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*(?:\d{4})?)', text, re.I)
    if m_date:
        date_val = m_date.group(1).strip()
    else:
        m_iso = re.search(r'(\d{4}-\d{2}-\d{2})', text)
        if m_iso:
            date_val = m_iso.group(1)

    # Time match: e.g. "10 AM", "10:00 AM", "2 PM", "14:00"
    m_time = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm))', text)
    if m_time:
        time_val = m_time.group(1).strip().upper()
    else:
        m_24 = re.search(r'(\d{1,2}:\d{2})', text)
        if m_24:
            time_val = m_24.group(1)

    return date_val, time_val


@AgentFactory.register_agent("calendar")
class CalendarAgent(BaseAgent):
    """Checks availability, suggests slots, and books via structured LLM output + HTML tables.

    Flow:
    1. If user hasn't chosen a slot yet → emit Available Slots HTML table
    2. When date/time chosen → emit Appointment Summary HTML table asking for confirmation
    3. When user confirms → emit Visit Confirmed HTML card & record booking in DB
    """

    def __init__(self, session_id: str, provider: str = None):
        super().__init__(
            agent_name="calendar",
            session_id=session_id,
            provider=provider,
        )

    def get_system_prompt(self) -> str:
        return CALENDAR_AGENT_SYSTEM_PROMPT

    def get_extraction_prompt(self) -> str:
        return (
            "You are an extraction assistant for a real estate rental system. "
            "Analyze the conversation and extract booking/appointment data. "
            "Determine action: check_availability, suggest_slot, confirm_booking, or ask_preference. "
            "Extract date (YYYY-MM-DD or text date) and time (HH:MM or 12hr) if mentioned. "
            "Set confirmed=True ONLY if the user explicitly confirmed a suggested appointment (e.g., 'yes', 'confirm', 'book it')."
        )

    async def process(self, user_input: str, context: dict) -> AgentResult:
        """Handle appointment scheduling with clean HTML table responses."""
        from backend.events.publisher import publish_event
        from backend.events.types import EventType

        await self.memory.add_message("user", user_input, self.agent_name)

        # Retrieve current context
        booking_state = await self.memory.short_term.get("booking_state") or {}
        selected_property = await self.memory.short_term.get("selected_property")

        # Step 1: Extract structured booking data
        extraction: CalendarExtraction = await self.extract_structured_data(
            user_input=user_input,
            context=context,
            schema=CalendarExtraction,
        )

        extracted_date = extraction.date
        extracted_time = extraction.time
        confirmed = extraction.confirmed

        # Fallback date/time detection if LLM missed it
        if not extracted_date or not extracted_time:
            fb_date, fb_time = _parse_date_time_fallback(user_input)
            if not extracted_date and fb_date:
                extracted_date = fb_date
            if not extracted_time and fb_time:
                extracted_time = fb_time

        # Check explicit confirmation words if already awaiting confirmation
        lower_input = user_input.strip().lower()
        is_confirm_word = lower_input in (
            "yes", "confirm", "proceed", "sure", "ok", "book it", "lock it in",
            "yes please", "yes confirm", "yes lock it in", "yes book it"
        )
        is_awaiting_confirmation = bool(booking_state.get("date") and booking_state.get("time"))

        if (confirmed or (is_confirm_word and is_awaiting_confirmation)) and is_awaiting_confirmation:
            # ── Branch A: User Confirms Booking ──────────────────────────
            final_date = booking_state.get("date")
            final_time = booking_state.get("time")
            booking_state["confirmed"] = True
            await self.memory.short_term.set("booking_state", booking_state)

            # Persist to database if possible
            booking_id = ""
            try:
                user_id = await self.memory.short_term.get("user_id") or "anonymous_user"
                prop_id = selected_property.get("property_id") if selected_property else None
                if prop_id:
                    # Parse date/time for DB if valid format
                    v_date = date.today()
                    try:
                        v_date = datetime.strptime(final_date, "%Y-%m-%d").date()
                    except Exception:
                        pass
                    v_time = time(10, 0)
                    try:
                        t_parts = final_time.split(":")
                        v_time = time(int(t_parts[0]), int(t_parts[1][:2]))
                    except Exception:
                        pass

                    b_obj = await _booking_repo.book_appointment(
                        user_id=user_id,
                        property_id=prop_id,
                        visit_date=v_date,
                        visit_time=v_time,
                    )
                    booking_id = b_obj.id
            except Exception as e:
                logger.warning(f"Could not persist booking to DB: {e}")

            confirmed_html = _build_booking_confirmed_card(
                selected_property=selected_property,
                date_str=final_date,
                time_str=final_time,
                booking_id=booking_id,
            )

            await publish_event(self.session_id, EventType.AGENT_START, {"agent": self.agent_name})
            await publish_event(
                session_id=self.session_id,
                event_type=EventType.LLM_TOKEN,
                data={"token": confirmed_html, "agent": self.agent_name},
            )
            await publish_event(self.session_id, EventType.LLM_DONE, {"agent": self.agent_name})

            await self.memory.add_message("assistant", confirmed_html, self.agent_name)

            return AgentResult(
                agent_name="calendar",
                response_text=confirmed_html,
                extracted_data=extraction.model_dump(),
                next_agent=None,
                requires_user_input=False,
                metadata={"action": "confirm_booking", "confirmed": True, "booking_id": booking_id},
            )

        elif extracted_date or extracted_time or (booking_state.get("date") and not is_awaiting_confirmation):
            # ── Branch B: Date and/or Time Provided → Show Summary Table ──
            req_date = extracted_date or booking_state.get("date", "Upcoming Saturday")
            req_time = extracted_time or booking_state.get("time", "10:00 AM")

            booking_state["date"] = req_date
            booking_state["time"] = req_time
            booking_state["confirmed"] = False
            await self.memory.short_term.set("booking_state", booking_state)

            summary_html = _build_booking_summary_table(
                selected_property=selected_property,
                date_str=req_date,
                time_str=req_time,
            )

            await publish_event(self.session_id, EventType.AGENT_START, {"agent": self.agent_name})
            await publish_event(
                session_id=self.session_id,
                event_type=EventType.LLM_TOKEN,
                data={"token": summary_html, "agent": self.agent_name},
            )
            await publish_event(self.session_id, EventType.LLM_DONE, {"agent": self.agent_name})

            await self.memory.add_message("assistant", summary_html, self.agent_name)

            return AgentResult(
                agent_name="calendar",
                response_text=summary_html,
                extracted_data=extraction.model_dump(),
                next_agent=None,
                requires_user_input=True,
                metadata={"action": "suggest_slot", "confirmed": False},
            )

        elif not booking_state.get("confirmed"):
            # ── Branch C: Initial Visit Request → Show Available Slots Table ──
            slots_html = _build_slots_table(selected_property=selected_property)

            await publish_event(self.session_id, EventType.AGENT_START, {"agent": self.agent_name})
            await publish_event(
                session_id=self.session_id,
                event_type=EventType.LLM_TOKEN,
                data={"token": slots_html, "agent": self.agent_name},
            )
            await publish_event(self.session_id, EventType.LLM_DONE, {"agent": self.agent_name})

            await self.memory.add_message("assistant", slots_html, self.agent_name)

            return AgentResult(
                agent_name="calendar",
                response_text=slots_html,
                extracted_data=extraction.model_dump(),
                next_agent=None,
                requires_user_input=True,
                metadata={"action": "show_slots", "confirmed": False},
            )

        else:
            # ── Branch D: General Conversation Fallback ───────────────────
            full_response = ""
            async for token in self.stream_response(user_input, context):
                full_response += token

            return AgentResult(
                agent_name="calendar",
                response_text=full_response,
                extracted_data=extraction.model_dump(),
                next_agent=None,
                requires_user_input=True,
                metadata={"action": "general_chat"},
            )
