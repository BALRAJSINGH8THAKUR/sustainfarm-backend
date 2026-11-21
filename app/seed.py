"""Seed data + helpers (stdlib only)."""
from __future__ import annotations

from datetime import datetime, timezone

SCHEMES = [
    {"name": "PM-KISAN Samman Nidhi", "tag": "Income Support",
     "benefit": "₹6,000/year direct income support transferred in 3 equal installments for small and marginal farmer families."},
    {"name": "PMKSY (Per Drop More Crop)", "tag": "Micro-Irrigation",
     "benefit": "Up to 55% subsidy on drip and sprinkler micro-irrigation systems to conserve water and boost yields."},
    {"name": "Paramparagat Krishi Vikas Yojana (PKVY)", "tag": "Organic Farming",
     "benefit": "Financial assistance up to ₹50,000/hectare over 3 years for organic inputs, certification, and cluster marketing."},
    {"name": "National Livestock Mission", "tag": "Livestock Aid",
     "benefit": "Up to 50% capital subsidy for poultry, goatry, dairy, and sustainable fodder entrepreneurship units."},
]

# (title, detail, minutes_ago, unread)
NOTIFICATIONS = [
    ("IoT Sensor Node Online", "Zone A soil moisture telemetry is active and streaming normally.", 0, True),
    ("PMKSY Micro-Irrigation Subsidy", "Up to 55% drip irrigation grant window is open for eligible farmers.", 120, True),
    ("Seasonal Soil Tip", "Intercropping legumes like Moong or Tur naturally enriches soil nitrogen.", 1440, False),
]


def relative_time(created: datetime, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    mins = max(0, int((now - created).total_seconds() // 60))
    if mins < 2:
        return "Just now"
    if mins < 60:
        return f"{mins}m ago"
    if mins < 1440:
        return f"{mins // 60}h ago"
    return f"{mins // 1440}d ago"
