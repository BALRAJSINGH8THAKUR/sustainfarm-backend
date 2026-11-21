import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from datetime import date
from app.planner import generate_model, current_season, CANVAS_W, CANVAS_H, inr

BASE = dict(name="Ramesh", state="Maharashtra", district="Nanded", land_area=2, family_members=4,
            food_preference="Vegetarian", farming_goals=["Food + Surplus for Market"],
            raise_livestock="Yes", livestock_types=["Poultry", "Goats"], water_bodies="Yes", receive_updates=True)
TODAY = date(2026, 11, 20)

def variants():
    yield BASE
    yield {**BASE, "water_bodies": "No"}
    yield {**BASE, "land_area": 0.5, "livestock_types": ["Poultry", "Goats", "Cattle", "Fish"], "family_members": 12}
    yield {**BASE, "farming_goals": ["Organic Farming", "Commercial Farming"], "food_preference": "Vegan", "raise_livestock": "No"}
    yield {**BASE, "state": "Kerala", "district": "X", "land_area": 25}  # unknown state -> default crops
    yield {**BASE, "farming_goals": ["Food for Family"], "land_area": None}

def test_percentages_sum_to_100_and_field_crops_dominant_enough():
    for v in variants():
        m = generate_model(v, TODAY)
        assert abs(sum(z["percent"] for z in m["zones"]) - 100) < 0.05
        fc = next(z for z in m["zones"] if z["key"] == "field_crops")
        assert fc["percent"] >= 29.9  # never squeezed out

def test_drawn_area_is_proportional_to_land_share():
    for v in variants():
        m = generate_model(v, TODAY)
        for z in m["zones"]:
            drawn = z["w"] * z["h"] / (CANVAS_W * CANVAS_H) * 100
            assert abs(drawn - z["percent"]) < 0.3, (z["key"], drawn, z["percent"])

def test_zones_do_not_overlap_and_stay_in_canvas():
    for v in variants():
        zs = generate_model(v, TODAY)["zones"]
        for z in zs:
            assert z["x"] >= -0.2 and z["y"] >= -0.2 and z["x"] + z["w"] <= CANVAS_W + 0.5 and z["y"] + z["h"] <= CANVAS_H + 0.5
        for i, a in enumerate(zs):
            for b in zs[i + 1:]:
                ox = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
                oy = min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"])
                assert not (ox > 0.5 and oy > 0.5), (a["key"], b["key"])

def test_no_water_proposes_pond_and_uses_dryland_crops():
    m = generate_model({**BASE, "water_bodies": "No"}, TODAY)
    assert any(z["key"] == "water" and z["label"] == "Proposed Farm Pond" for z in m["zones"])
    assert "farm pond" in m["cropPlan"].lower()
    fc = next(z for z in m["zones"] if z["key"] == "field_crops")
    assert "Wheat" not in fc["crops"]

def test_livestock_zones_only_when_selected():
    m = generate_model({**BASE, "raise_livestock": "No"}, TODAY)
    keys = {z["key"] for z in m["zones"]}
    assert "livestock_shed" not in keys and "fodder" not in keys
    assert "livestock_shed" in {z["key"] for z in generate_model(BASE, TODAY)["zones"]}

def test_season_and_schemes():
    assert current_season(date(2026, 11, 20))[0] == "rabi"
    assert current_season(date(2027, 2, 1)) == ("rabi", "Rabi 2026-27")
    assert current_season(date(2026, 7, 1))[0] == "kharif"
    assert current_season(date(2026, 4, 15))[0] == "zaid"
    names = [s["name"] for s in generate_model({**BASE, "farming_goals": ["Organic Farming"]}, TODAY)["eligibleSchemes"]]
    assert "Paramparagat Krishi Vikas Yojana (PKVY)" in names and "National Livestock Mission" in names

def test_revenue_and_formatting():
    m = generate_model(BASE, TODAY)
    assert m["revenue"]["low"] < m["revenue"]["total"] < m["revenue"]["high"]
    assert m["estimatedRevenue"].startswith("₹")
    assert inr(205850) == "₹2,05,850" and inr(1234567) == "₹12,34,567" and inr(999) == "₹999"

def test_iot_nodes_inside_their_zone():
    m = generate_model({**BASE, "land_area": 10}, TODAY)
    zones = {z["key"]: z for z in m["zones"]}
    assert 1 <= len(m["iotNodes"]) <= 8
    for n in m["iotNodes"]:
        z = zones[n["zone"]]
        assert z["x"] <= n["x"] <= z["x"] + z["w"] and z["y"] <= n["y"] <= z["y"] + z["h"]
