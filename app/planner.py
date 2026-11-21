"""
Sustainfarm farm-model engine.

Why rule-based (and not an image/LLM generator)?
  * Free: no API keys, quotas or per-call cost; runs offline.
  * Visually accurate: every zone's drawn area is EXACTLY its share of the land
    (an image model cannot keep areas to scale; an LLM can hallucinate numbers).
  * Reproducible: same inputs -> same plan, easy to audit and tune.

Pure Python (standard library only) so it is trivial to unit-test.
All money figures are INDICATIVE planning estimates, not guarantees.
"""
from __future__ import annotations

import math
from datetime import date
from typing import Any

CANVAS_W, CANVAS_H = 600, 400  # 3:2 map; zone areas are proportional to land share

# --------------------------------------------------------------------------
# Regional crop knowledge (indicative, by state & season)
# --------------------------------------------------------------------------
def _r(irr, dry, veg, orchard):
    return {"irrigated": irr, "dryland": dry, "vegetables": veg, "orchard": orchard}

REGIONS: dict[str, dict[str, Any]] = {
    "Maharashtra": _r(
        {"kharif": ["Soybean", "Tur (pigeon pea)", "Maize"], "rabi": ["Wheat", "Chickpea (Harbhara)", "Rabi Jowar"], "zaid": ["Summer Groundnut", "Moong", "Fodder Maize"]},
        {"kharif": ["Jowar", "Bajra", "Tur", "Moong"], "rabi": ["Rabi Jowar", "Chickpea", "Safflower"], "zaid": ["Fodder Sorghum", "Cowpea"]},
        {"kharif": ["Okra", "Brinjal", "Chilli"], "rabi": ["Onion", "Tomato", "Cabbage"], "zaid": ["Cucumber", "Bottle Gourd", "Okra"]},
        ["Mango", "Guava", "Custard Apple", "Lemon"],
    ),
    "Punjab": _r(
        {"kharif": ["Basmati Rice (direct-seeded)", "Maize", "Moong"], "rabi": ["Wheat", "Mustard", "Potato"], "zaid": ["Moong", "Sunflower", "Fodder Maize"]},
        {"kharif": ["Bajra", "Guar", "Moong"], "rabi": ["Mustard", "Chickpea", "Barley"], "zaid": ["Fodder Sorghum", "Cowpea"]},
        {"kharif": ["Okra", "Bottle Gourd", "Chilli"], "rabi": ["Potato", "Cauliflower", "Peas"], "zaid": ["Muskmelon", "Cucumber", "Okra"]},
        ["Kinnow", "Guava", "Pear", "Mango"],
    ),
    "Madhya Pradesh": _r(
        {"kharif": ["Soybean", "Maize", "Rice"], "rabi": ["Wheat", "Chickpea", "Mustard"], "zaid": ["Moong", "Fodder Maize", "Summer Groundnut"]},
        {"kharif": ["Soybean", "Tur", "Jowar"], "rabi": ["Chickpea", "Lentil", "Mustard"], "zaid": ["Cowpea", "Fodder Sorghum"]},
        {"kharif": ["Okra", "Brinjal", "Tomato"], "rabi": ["Onion", "Garlic", "Peas"], "zaid": ["Bottle Gourd", "Cucumber", "Okra"]},
        ["Guava", "Mango", "Papaya", "Lemon"],
    ),
    "Karnataka": _r(
        {"kharif": ["Paddy", "Maize", "Groundnut"], "rabi": ["Jowar", "Chickpea", "Sunflower"], "zaid": ["Groundnut", "Moong", "Fodder Maize"]},
        {"kharif": ["Ragi (finger millet)", "Tur", "Groundnut"], "rabi": ["Rabi Jowar", "Chickpea", "Horse Gram"], "zaid": ["Cowpea", "Fodder Sorghum"]},
        {"kharif": ["Tomato", "Beans", "Brinjal"], "rabi": ["Carrot", "Cabbage", "Beetroot"], "zaid": ["Cucumber", "Okra", "Ridge Gourd"]},
        ["Mango", "Sapota", "Banana", "Guava"],
    ),
    "Uttar Pradesh": _r(
        {"kharif": ["Paddy", "Maize", "Sugarcane"], "rabi": ["Wheat", "Mustard", "Potato"], "zaid": ["Moong", "Urad", "Fodder Maize"]},
        {"kharif": ["Bajra", "Urad", "Sesame"], "rabi": ["Chickpea", "Mustard", "Lentil"], "zaid": ["Cowpea", "Fodder Sorghum"]},
        {"kharif": ["Okra", "Brinjal", "Bottle Gourd"], "rabi": ["Cauliflower", "Peas", "Potato"], "zaid": ["Cucumber", "Bitter Gourd", "Okra"]},
        ["Mango", "Guava", "Banana", "Papaya"],
    ),
    "Gujarat": _r(
        {"kharif": ["Groundnut", "Cotton", "Bajra"], "rabi": ["Wheat", "Cumin", "Chickpea"], "zaid": ["Summer Bajra", "Moong", "Fodder Maize"]},
        {"kharif": ["Bajra", "Castor", "Groundnut"], "rabi": ["Chickpea", "Mustard", "Cumin"], "zaid": ["Fodder Sorghum", "Cowpea"]},
        {"kharif": ["Okra", "Brinjal", "Chilli"], "rabi": ["Onion", "Tomato", "Cabbage"], "zaid": ["Cucumber", "Bottle Gourd", "Okra"]},
        ["Mango", "Pomegranate", "Sapota", "Lemon"],
    ),
}
DEFAULT_REGION = _r(
    {"kharif": ["Maize", "Soybean", "Rice"], "rabi": ["Wheat", "Chickpea", "Mustard"], "zaid": ["Moong", "Fodder Maize"]},
    {"kharif": ["Bajra", "Tur", "Moong"], "rabi": ["Chickpea", "Mustard"], "zaid": ["Cowpea", "Fodder Sorghum"]},
    {"kharif": ["Okra", "Brinjal"], "rabi": ["Onion", "Tomato"], "zaid": ["Cucumber", "Bottle Gourd"]},
    ["Mango", "Guava", "Lemon"],
)

# --------------------------------------------------------------------------
# Zones: label, colour (map), indicative gross revenue per acre in INR
# --------------------------------------------------------------------------
ZONE_META = {
    "field_crops": ("Field Crops", "#A8D86B"),
    "vegetables": ("Vegetables (drip)", "#5FB760"),
    "orchard": ("Orchard & Border Trees", "#2E8B57"),
    "fodder": ("Fodder Plot", "#C5D86D"),
    "kitchen_garden": ("Family Kitchen Garden", "#F2C94C"),
    "water": ("Water Source / Pond", "#4DA6E8"),
    "livestock_shed": ("Livestock Shed", "#C58B5A"),
    "compost": ("Compost & Vermicompost", "#8D6E4B"),
    "storage": ("Storage & Access Path", "#B0B7BE"),
}
REVENUE_PER_ACRE = {"field_irrigated": 55_000, "field_dryland": 30_000, "vegetables": 150_000, "orchard": 80_000}
ORGANIC_PREMIUM = 1.15
FAMILY_ONLY_MARKET_SHARE = 0.6  # share of output sold when goal is only "Food for Family"
LIVESTOCK = {  # indicative unit, revenue/unit/yr, shed %, fodder %
    "Poultry": {"unit": "50 desi birds", "revenue": 30_000, "shed": 1.5, "fodder": 0.0},
    "Goats": {"unit": "10 does + 1 buck", "revenue": 45_000, "shed": 2.0, "fodder": 4.0},
    "Cattle": {"unit": "2 milch animals", "revenue": 60_000, "shed": 3.0, "fodder": 6.0},
    "Fish": {"unit": "1 farm pond", "revenue": 40_000, "shed": 0.0, "fodder": 0.0},
}
MIN_FIELD_PERCENT = 30.0


def current_season(today: date | None = None) -> tuple[str, str]:
    """(season key, label). Kharif Jun-Oct, Rabi Nov-Mar, Zaid Apr-May."""
    today = today or date.today()
    m, y = today.month, today.year
    if 6 <= m <= 10:
        return "kharif", f"Kharif {y}"
    if m >= 11:
        return "rabi", f"Rabi {y}-{str(y + 1)[-2:]}"
    if m <= 3:
        return "rabi", f"Rabi {y - 1}-{str(y)[-2:]}"
    return "zaid", f"Zaid {y}"


def _allocate(p: dict, has_water: bool, animals: list[str], organic: bool, commercial: bool, acres: float):
    land_animals = [a for a in animals if a != "Fish"]
    fish = "Fish" in animals

    pct: dict[str, float] = {
        "vegetables": (26 if (organic and commercial) else 24 if organic else 28 if commercial else 22) if has_water else 10,
        "orchard": 14 if organic else 12,
        "compost": 4 if organic else 3,
        "water": 8 if (fish or not has_water) else 5,
        "kitchen_garden": min(10.0, max(4.0, 3 + 0.7 * p["family"])) + (2 if p["food"] == "Vegan" else 0),
        "storage": 3,
    }
    if land_animals:
        pct["livestock_shed"] = min(6.0, sum(LIVESTOCK[a]["shed"] for a in land_animals))
        fodder = sum(LIVESTOCK[a]["fodder"] for a in land_animals)
        if fodder:
            pct["fodder"] = min(10.0, fodder)

    others = sum(pct.values())
    budget = 100 - MIN_FIELD_PERCENT
    if others > budget:  # tiny/complex farms: scale supporting zones, keep >=30% for field crops
        k = budget / others
        pct = {z: v * k for z, v in pct.items()}
    pct = {z: round(v, 1) for z, v in pct.items()}
    pct["field_crops"] = round(100 - sum(pct.values()), 1)
    return pct


def _layout(pct: dict[str, float]):
    """Binary balanced slice layout. Area of each rect == percent of canvas exactly."""
    items = sorted(pct.items(), key=lambda kv: -kv[1])
    rects: dict[str, tuple[float, float, float, float]] = {}

    def split(group, x, y, w, h):
        if len(group) == 1:
            rects[group[0][0]] = (x, y, w, h)
            return
        total = sum(v for _, v in group)
        best_i, best_diff, run = 1, float("inf"), 0.0
        for i in range(1, len(group)):
            run += group[i - 1][1]
            diff = abs(total - 2 * run)
            if diff < best_diff:
                best_i, best_diff = i, diff
        left, right = group[:best_i], group[best_i:]
        frac = sum(v for _, v in left) / total
        if w >= h:
            split(left, x, y, w * frac, h)
            split(right, x + w * frac, y, w * (1 - frac), h)
        else:
            split(left, x, y, w, h * frac)
            split(right, x, y + h * frac, w, h * (1 - frac))

    split(items, 0.0, 0.0, float(CANVAS_W), float(CANVAS_H))
    return rects


def _indian_group(n: int) -> str:
    s = str(n)
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts + [tail])


def inr(n: float) -> str:
    return "₹" + _indian_group(int(round(n)))


def generate_model(profile: dict, today: date | None = None) -> dict:
    """profile keys: name, state, district, land_area, family_members, food_preference,
    farming_goals, livestock_types, raise_livestock, water_bodies, receive_updates"""
    acres = max(0.5, float(profile.get("land_area") or 2))
    goals = profile.get("farming_goals") or []
    organic = "Organic Farming" in goals
    commercial = "Commercial Farming" in goals
    family_only = goals == ["Food for Family"]
    has_water = profile.get("water_bodies") == "Yes"
    animals = [a for a in (profile.get("livestock_types") or []) if a in LIVESTOCK] if profile.get("raise_livestock") == "Yes" else []
    state, district = profile.get("state", ""), profile.get("district", "")
    region = REGIONS.get(state, DEFAULT_REGION)
    season, season_label = current_season(today)

    p = {"family": int(profile.get("family_members") or 4), "food": profile.get("food_preference", "Vegetarian")}
    pct = _allocate(p, has_water, animals, organic, commercial, acres)
    rects = _layout(pct)

    # ---- crops per zone
    field_list = (region["irrigated"] if has_water else region["dryland"])[season]
    crops = {
        "field_crops": field_list,
        "vegetables": region["vegetables"][season],
        "orchard": region["orchard"][:3],
        "kitchen_garden": ["Leafy greens", "Tomato", "Chilli", "Herbs (tulsi, coriander)"],
        "fodder": ["Fodder Maize / Sorghum", "Napier grass (border)"] if "fodder" in pct else [],
        "compost": ["Vermicompost beds", "NADEP / pit compost", "Green manure (Dhaincha / Sunhemp)"],
    }
    notes = {
        "field_crops": "Irrigated rotation with a legume to fix nitrogen." if has_water else "Rain-fed millets, pulses and oilseeds; mulch to hold moisture.",
        "vegetables": "Drip-irrigated beds for steady cash flow." if has_water else "Small mulched beds fed from the farm pond.",
        "orchard": "Plant on borders; fruit starts in year 3-4, full yield by year 6-8.",
        "water": ("Existing source + storage tank for drip." if has_water and "Fish" not in animals
                  else "Pond for irrigation + fish culture." if "Fish" in animals
                  else "Recommended farm pond for rainwater harvesting (dig before monsoon)."),
        "livestock_shed": "Raised, ventilated shed near compost so manure feeds the beds.",
        "fodder": "Feeds livestock and cuts purchased feed cost.",
        "kitchen_garden": f"Sized for a family of {p['family']}.",
        "compost": "Turns farm and animal waste into soil nutrition.",
        "storage": "Produce storage, tools and a cart path.",
    }

    zones = []
    for key, percent in sorted(pct.items(), key=lambda kv: -kv[1]):
        label, color = ZONE_META[key]
        if key == "water":
            label = "Water Source / Pond" if has_water else "Proposed Farm Pond"
        x, y, w, h = rects[key]
        zones.append({
            "key": key, "label": label, "color": color, "percent": percent,
            "acres": round(acres * percent / 100, 2), "crops": crops.get(key, []), "note": notes.get(key, ""),
            "x": round(x, 1), "y": round(y, 1), "w": round(w, 1), "h": round(h, 1),
        })
    z = {r["key"]: r for r in zones}

    # ---- revenue (indicative gross)
    prem = ORGANIC_PREMIUM if organic else 1.0
    breakdown = []
    def add(label, amount):
        if amount > 0:
            breakdown.append({"label": label, "amount": int(round(amount))})
    field_rate = REVENUE_PER_ACRE["field_irrigated" if has_water else "field_dryland"]
    add("Field crops", z["field_crops"]["acres"] * field_rate * prem)
    add("Vegetables", z["vegetables"]["acres"] * REVENUE_PER_ACRE["vegetables"] * prem)
    add("Orchard (steady state)", z["orchard"]["acres"] * REVENUE_PER_ACRE["orchard"] * prem)
    units = max(1, round(acres / 3))
    livestock_lines = []
    for a in animals:
        meta = LIVESTOCK[a]
        n = 1 if a == "Fish" else units
        add(f"{a}", meta["revenue"] * n)
        livestock_lines.append(f"{a} - {n} unit{'s' if n > 1 else ''} ({meta['unit']} each)")
    gross = sum(b["amount"] for b in breakdown)
    if family_only:
        gross *= FAMILY_ONLY_MARKET_SHARE
    total = int(round(gross))

    # ---- text plans (kept compatible with the existing UI cards)
    parts = [f"{z['field_crops']['percent']:g}% field crops ({', '.join(field_list[:3])})"]
    if "vegetables" in z: parts.append(f"{z['vegetables']['percent']:g}% vegetables ({', '.join(crops['vegetables'][:3])})")
    parts.append(f"{z['orchard']['percent']:g}% orchard borders ({', '.join(crops['orchard'][:3])})")
    parts.append(f"{z['kitchen_garden']['percent']:g}% family kitchen garden")
    crop_plan = f"{season_label} plan for {district}, {state}: " + "; ".join(parts) + "."
    if not has_water:
        crop_plan += " Dig a farm pond (about " + f"{z['water']['percent']:g}% of land) to harvest rainwater."

    if animals:
        livestock_plan = ("Integrated closed-loop livestock: " + "; ".join(livestock_lines) +
                          ". Manure feeds the compost pits and crop beds; crop residue and the fodder plot reduce feed purchases.")
    elif p["food"] == "Vegan":
        livestock_plan = "100% plant-powered soil nutrition using green manuring (Dhaincha/Sunhemp), crop-residue mulching and NADEP composting."
    else:
        livestock_plan = "Set up a vermicompost and bio-enzyme pit using farm biomass to steadily build soil organic carbon."

    # ---- IoT sensor plan with map positions
    n_nodes = min(8, max(1, math.ceil(acres / 1.5)))
    targets = [k for k in ("vegetables", "orchard", "field_crops") if k in z]
    assigned = [targets[i] if i < len(targets) else "field_crops" for i in range(n_nodes)]
    nodes, seen = [], {}
    for i, zk in enumerate(assigned):
        seen[zk] = seen.get(zk, 0) + 1
        frac = seen[zk] / (assigned.count(zk) + 1)  # spread nodes evenly across the zone
        zr = z[zk]
        nodes.append({"id": f"node-{i + 1}", "zone": zk, "x": round(zr["x"] + zr["w"] * frac, 1), "y": round(zr["y"] + zr["h"] / 2, 1)})
    valves = 1 + (1 if "vegetables" in z and has_water else 0)
    iot = (f"{n_nodes}x Solar LoRaWAN Soil Moisture & pH/NPK nodes + {valves}x automated solenoid drip valve controller "
           f"(typically cuts water use by ~30-40%)." if acres >= 2 else
           "1x compact solar soil moisture & pH node with SMS/WhatsApp irrigation alerts.")

    # ---- scheme matching (names must match /api/schemes)
    eligible = [{"name": "PM-KISAN Samman Nidhi", "reason": "Income support for farmer families (subject to eligibility checks)."}]
    if has_water or z["vegetables"]["percent"] > 0:
        eligible.append({"name": "PMKSY (Per Drop More Crop)", "reason": "Your plan uses drip irrigation for vegetables and orchard."})
    if organic:
        eligible.append({"name": "Paramparagat Krishi Vikas Yojana (PKVY)", "reason": "You chose Organic Farming."})
    if [a for a in animals if a != "Fish"]:
        eligible.append({"name": "National Livestock Mission", "reason": "Your plan includes poultry/goat/dairy units."})

    assumptions = [
        "Revenue is an indicative gross estimate from typical per-acre values, not a guarantee.",
        "Orchard income is shown at steady state (year 6+).",
        "Confirm crop varieties, sowing dates and animal numbers with your local Krishi Vigyan Kendra (KVK).",
    ]
    if family_only:
        assumptions.append("Only ~60% of output is counted as sold because your goal is family food.")

    title = f"{acres:g}-Acre {'Organic ' if organic else ''}Integrated Sustainable Blueprint"
    return {
        "title": title,
        "farmer": profile.get("name", "").strip(),
        "location": f"{district}, {state}",
        "familySize": str(p["family"]),
        "season": season_label,
        "estimatedRevenue": f"{inr(total)} / year",
        "revenue": {"total": total, "low": int(total * 0.75), "high": int(total * 1.25), "breakdown": breakdown},
        "cropPlan": crop_plan,
        "livestockPlan": livestock_plan,
        "iotRecommendation": iot,
        "canvas": {"width": CANVAS_W, "height": CANVAS_H},
        "zones": zones,
        "iotNodes": nodes,
        "eligibleSchemes": eligible,
        "assumptions": assumptions,
        "receiveUpdates": bool(profile.get("receive_updates", True)),
    }
