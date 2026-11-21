"""Sustainfarm API  (FastAPI + MongoDB via Motor)."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import create_client, init_db
from .iot import IoTSimulator
from .planner import generate_model
from .schemas import IrrigationRequest, ProfileRequest
from .seed import relative_time


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = create_client()
    app.state.client = client
    app.state.db = client[settings.mongodb_db]
    app.state.iot = IoTSimulator()
    app.state.hits = defaultdict(deque)
    await init_db(app.state.db)
    yield
    client.close()


app = FastAPI(title="Sustainfarm API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def get_db(request: Request):
    return request.app.state.db


def rate_limit(request: Request) -> None:
    """Tiny in-memory sliding window (per client IP). Use Redis/gateway limits if you scale out."""
    ip = request.client.host if request.client else "unknown"
    q = request.app.state.hits[ip]
    now = time.monotonic()
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= settings.profile_rate_limit_per_minute:
        raise HTTPException(429, "Too many requests. Please wait a minute and try again.")
    q.append(now)


# ----------------------------------------------------------------- health
@app.get("/api/health")
async def health(db=Depends(get_db)):
    try:
        await db.command("ping")
        return {"status": "ok", "db": True}
    except Exception:
        raise HTTPException(503, "Database unavailable")


# -------------------------------------------------------- farmer profiles
@app.post("/api/farmer-profiles", status_code=201)
async def create_profile(body: ProfileRequest, request: Request, db=Depends(get_db)):
    rate_limit(request)
    profile = body.profile.model_dump()
    model = generate_model(profile)
    now = datetime.now(timezone.utc)
    res = await db.farmer_profiles.insert_one({"profile": profile, "model": model, "created_at": now})
    return {"id": str(res.inserted_id), "createdAt": now.isoformat(), "model": model}


@app.get("/api/farmer-profiles/{profile_id}")
async def get_profile(profile_id: str, db=Depends(get_db)):
    if not ObjectId.is_valid(profile_id):
        raise HTTPException(404, "Profile not found")
    doc = await db.farmer_profiles.find_one({"_id": ObjectId(profile_id)})
    if not doc:
        raise HTTPException(404, "Profile not found")
    # contact number is personal data: never returned by this endpoint
    return {"id": profile_id, "createdAt": doc["created_at"].isoformat(), "model": doc["model"]}


# ---------------------------------------------------------------- schemes
@app.get("/api/schemes")
async def list_schemes(db=Depends(get_db)):
    docs = await db.schemes.find({}, {"_id": 0}).to_list(length=100)
    return docs


# ---------------------------------------------------------- notifications
@app.get("/api/notifications")
async def list_notifications(db=Depends(get_db)):
    docs = await db.notifications.find({}).sort("created_at", -1).to_list(length=50)
    return [
        {"id": str(d["_id"]), "title": d["title"], "detail": d["detail"],
         "time": relative_time(d["created_at"]), "unread": d.get("unread", False)}
        for d in docs
    ]


@app.post("/api/notifications/read")
async def mark_notifications_read(db=Depends(get_db)):
    res = await db.notifications.update_many({"unread": True}, {"$set": {"unread": False}})
    return {"updated": res.modified_count}


# ------------------------------------------------------------ IoT (simulated)
@app.get("/api/iot/latest")
async def iot_latest(request: Request):
    return request.app.state.iot.latest()


@app.post("/api/iot/irrigation")
async def iot_irrigation(body: IrrigationRequest, request: Request, db=Depends(get_db)):
    iot: IoTSimulator = request.app.state.iot
    iot.set_irrigation(body.on)
    await db.iot_events.insert_one({"type": "irrigation", "on": body.on, "at": datetime.now(timezone.utc)})
    return iot.latest()
