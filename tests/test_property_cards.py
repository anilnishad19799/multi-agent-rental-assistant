"""Tests for responsive vertical property cards generation."""
import pytest
from unittest.mock import MagicMock
from backend.agents.rent_agent import _build_property_cards, _build_selection_index


def test_build_property_cards_empty():
    html = _build_property_cards([])
    assert "No matching properties found" in html


def test_build_property_cards_vertical_stack():
    # Mock property and config
    cfg1 = MagicMock(
        rent=12000,
        sharing_type=2,
        bhk_type="1RK",
        food_included=True,
        available_beds=2,
        total_beds=4,
        lease_min_months=6,
    )
    amenity1 = MagicMock(amenity_name="High-Speed WiFi")
    amenity2 = MagicMock(amenity_name="Air Conditioning")

    prop1 = MagicMock(
        id="prop-abc-123",
        title="Stanza Living Boston House",
        city="Bangalore",
        area="Koramangala",
        property_type="PG",
        gender_allowed="Male",
        rating=4.5,
        configs=[cfg1],
        amenities=[amenity1, amenity2],
    )

    cfg2 = MagicMock(
        rent=25000,
        sharing_type=None,
        bhk_type="2BHK",
        food_included=False,
        available_beds=1,
        total_beds=1,
        lease_min_months=11,
    )
    prop2 = MagicMock(
        id="prop-def-456",
        title="Prestige Falcon City Flat",
        city="Bangalore",
        area="Kanakapura Road",
        property_type="Flat",
        gender_allowed="Family",
        rating=4.8,
        configs=[cfg2],
        amenities=[],
    )

    html = _build_property_cards([prop1, prop2])

    # Must contain list wrapper for vertical stacking
    assert 'class="property-cards-list"' in html
    # Must contain both cards
    assert 'Option #1' in html
    assert 'Option #2' in html
    assert 'Stanza Living Boston House' in html
    assert 'Prestige Falcon City Flat' in html
    # Must display prices
    assert '₹12,000' in html
    assert '₹25,000' in html
    # Must have interactive select buttons with click handlers
    assert 'selectProperty(1,' in html
    assert 'selectProperty(2,' in html
    # Check specs
    assert '2-Sharing' in html
    assert 'Food Included' in html


def test_build_selection_index():
    cfg1 = MagicMock(
        rent=10000,
        sharing_type=3,
        food_included=True,
    )
    prop1 = MagicMock(
        id="p1",
        title="Test PG",
        city="Pune",
        area="Hinjewadi",
        configs=[cfg1],
    )

    index = _build_selection_index([prop1])
    assert len(index) == 1
    assert index[0]["property_id"] == "p1"
    assert index[0]["rent"] == 10000
    assert index[0]["sharing_type"] == 3
