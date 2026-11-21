# Sustainfarm Backend (FastAPI + MongoDB)

Python 3.10+ · FastAPI · Motor (async MongoDB) · simulated IoT sensors · server-side farm model generation.

## Run it
```bash
cd sustainfarm-backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # edit if needed
docker compose up -d                                   # local MongoDB (or use a free MongoDB Atlas cluster and put its URI in .env)
uvicorn app.main:app --reload --port 8000
```
Interactive docs: http://localhost:8000/docs

Then in the React file set `const API_BASE_URL = 'http://localhost:8000';`
(and keep `CORS_ORIGINS` in `.env` equal to your frontend origin, e.g. `http://localhost:5173`).

## Endpoints
| Method | Path | What it does |
|---|---|---|
| GET | `/api/health` | API + database ping |
| POST | `/api/farmer-profiles` | Validate form → **generate farm model** → save → return `{id, createdAt, model}` |
| GET | `/api/farmer-profiles/{id}` | Fetch a saved model (contact number is never returned) |
| GET | `/api/schemes` | Government schemes (seeded in MongoDB on first start) |
| GET | `/api/notifications` | Notifications, newest first |
| POST | `/api/notifications/read` | Mark all as read |
| GET | `/api/iot/latest` | Simulated sensor reading (moisture, pH, temp, humidity, pump state) |
| POST | `/api/iot/irrigation` | `{"on": true}` start/stop the pump (event logged to `iot_events`) |

Collections: `farmer_profiles`, `schemes`, `notifications`, `iot_events`.

## How the farm model is generated (free + visually accurate)
`app/planner.py` is a deterministic rule engine, **not** an image/LLM generator:
- **Free & offline** – no API keys, quotas or per-request cost.
- **Visually accurate** – land is split into zones (field crops, vegetables, orchard, fodder, kitchen garden, pond, shed, compost, storage) and laid out with a slice algorithm, so each drawn block's area is *exactly* its share of the land. Image models can't keep areas to scale; LLMs can invent numbers.
- **Context-aware** – uses state, current season (Kharif/Rabi/Zaid), water availability, goals (organic/commercial/family), livestock, family size and food preference; suggests sensor-node positions and matches eligible schemes.
- **Honest numbers** – revenue is an *indicative* range and the response lists its assumptions.

Tune it by editing `REGIONS` (crops by state/season), `REVENUE_PER_ACRE`, `LIVESTOCK` and the percentages in `_allocate()`.
Have values reviewed by an agronomist / your local KVK before presenting them as advice.

Optional later: add an LLM (e.g. a free-tier Gemini/Groq key) only to *phrase* the advice in the farmer's language; keep the numbers and layout from the rule engine. Check the provider's current free-tier limits and terms first.

## Tests
```bash
pip install -r requirements-dev.txt
python -m pytest -q
```
Covers: percentages sum to 100, drawn areas proportional to land share, no overlapping zones, season logic, scheme matching, INR formatting, sensor simulation.

## Before going to production
- Add authentication (currently open) and a consent/privacy notice: phone numbers are personal data.
- The rate limiter is in-memory (per process); use a gateway/Redis if you run several instances.
- Restrict `CORS_ORIGINS` to your real domain; use a MongoDB user with least privilege.
- Replace `app/iot.py` with real MQTT/LoRaWAN ingestion when hardware is ready (same API shape).
