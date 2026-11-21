"""Request schemas. Field names match what the React form already sends (camelCase)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

FoodPref = Literal["Vegan", "Vegetarian", "Non-Vegetarian", "Both V & NV"]
Goal = Literal["Food for Family", "Food + Surplus for Market", "Commercial Farming", "Organic Farming"]
Animal = Literal["Poultry", "Cattle", "Goats", "Fish"]


class FarmerProfile(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")

    name: str = Field(min_length=1, max_length=100)
    contact: str = ""
    state: str = Field(min_length=1, max_length=60)
    district: str = Field(min_length=1, max_length=60)
    land_area: float | None = None
    family_members: int = 4
    food_preference: FoodPref = "Vegetarian"
    farming_goals: list[Goal] = Field(default_factory=list, max_length=4)
    raise_livestock: Literal["Yes", "No"] = "No"
    livestock_types: list[Animal] = Field(default_factory=list, max_length=4)
    water_bodies: Literal["Yes", "No"] = "No"
    receive_updates: bool = True

    @field_validator("name", mode="before")
    @classmethod
    def _strip_name(cls, v):
        return v.strip() if isinstance(v, str) else v

    @field_validator("contact", mode="before")
    @classmethod
    def _contact(cls, v):
        v = (v or "").strip() if isinstance(v, str) or v is None else v
        if v and not (isinstance(v, str) and v.isascii() and v.isdigit() and len(v) == 10):
            raise ValueError("Contact must be a valid 10-digit mobile number")
        return v

    @field_validator("land_area", mode="before")
    @classmethod
    def _land(cls, v):
        if v in ("", None):
            return None
        return v

    @field_validator("land_area")
    @classmethod
    def _land_range(cls, v):
        if v is not None and not (0 < v <= 10_000):
            raise ValueError("Land area must be between 0 and 10,000 acres")
        return v

    @field_validator("family_members", mode="before")
    @classmethod
    def _family(cls, v):
        return 4 if v in ("", None) else v

    @field_validator("family_members")
    @classmethod
    def _family_range(cls, v):
        if not (1 <= v <= 50):
            raise ValueError("Family members must be between 1 and 50")
        return v


class ProfileRequest(BaseModel):
    """Body sent by the frontend: {"profile": {...}, "model": {...}}. The client's own
    `model` is ignored on purpose; the server always generates the plan itself."""
    model_config = ConfigDict(extra="ignore")
    profile: FarmerProfile


class IrrigationRequest(BaseModel):
    on: bool
