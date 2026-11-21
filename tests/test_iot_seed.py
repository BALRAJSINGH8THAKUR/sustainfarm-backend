import sys, pathlib, random
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from datetime import datetime, timedelta, timezone
from app.iot import IoTSimulator
from app.seed import relative_time, SCHEMES

def test_moisture_drains_then_rises_with_irrigation_and_stays_clamped():
    t = [0.0]
    sim = IoTSimulator(clock=lambda: t[0], rng=random.Random(1))
    t[0] += 25                      # 10 steps x -0.35
    assert abs(sim.latest()["soilMoisture"] - 58.5) < 0.06
    sim.set_irrigation(True); t[0] += 25   # 10 steps x +1.8
    assert abs(sim.latest()["soilMoisture"] - 76.5) < 0.06
    t[0] += 100_000
    d = sim.latest()
    assert 28 <= d["soilMoisture"] <= 96 and 42 <= d["humidity"] <= 82 and 6.4 <= d["soilPh"] <= 7.2

def test_relative_time_and_scheme_names_match_planner():
    n = datetime.now(timezone.utc)
    assert [relative_time(n - timedelta(minutes=m)) for m in (0, 5, 120, 3000)] == ["Just now", "5m ago", "2h ago", "2d ago"]
    from app.planner import generate_model
    m = generate_model(dict(name="A", state="Punjab", district="Ludhiana", land_area=3, farming_goals=["Organic Farming"],
                            raise_livestock="Yes", livestock_types=["Goats"], water_bodies="Yes"))
    names = {s["name"] for s in SCHEMES}
    assert all(e["name"] in names for e in m["eligibleSchemes"])
