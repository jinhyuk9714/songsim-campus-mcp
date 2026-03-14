from __future__ import annotations

from pydantic import BaseModel, Field


class Place(BaseModel):
    id: int
    slug: str
    name: str
    category: str
    aliases: list[str] = Field(default_factory=list)
    description: str = ""
    latitude: float | None = None
    longitude: float | None = None
    opening_hours: dict[str, str] = Field(default_factory=dict)
    source_tag: str = "demo"
    last_synced_at: str


class Course(BaseModel):
    id: int
    year: int
    semester: int
    code: str
    title: str
    professor: str | None = None
    department: str | None = None
    section: str | None = None
    day_of_week: str | None = None
    period_start: int | None = None
    period_end: int | None = None
    room: str | None = None
    raw_schedule: str | None = None
    source_tag: str = "demo"
    last_synced_at: str


class Restaurant(BaseModel):
    id: int
    slug: str
    name: str
    category: str
    min_price: int | None = None
    max_price: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    tags: list[str] = Field(default_factory=list)
    description: str = ""
    source_tag: str = "demo"
    last_synced_at: str


class NearbyRestaurant(Restaurant):
    distance_meters: int | None = None
    estimated_walk_minutes: int | None = None
    origin: str


class Notice(BaseModel):
    id: int
    title: str
    category: str
    published_at: str
    summary: str = ""
    labels: list[str] = Field(default_factory=list)
    source_url: str | None = None
    source_tag: str = "demo"
    last_synced_at: str


class TransportGuide(BaseModel):
    id: int
    mode: str
    title: str
    summary: str = ""
    steps: list[str] = Field(default_factory=list)
    source_url: str | None = None
    source_tag: str = "demo"
    last_synced_at: str


class Profile(BaseModel):
    id: str
    display_name: str = ""
    created_at: str
    updated_at: str


class ProfileCreateRequest(BaseModel):
    display_name: str = ""


class ProfileCourseRef(BaseModel):
    year: int
    semester: int
    code: str
    section: str


class ProfileNoticePreferences(BaseModel):
    categories: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class MealRecommendation(BaseModel):
    restaurant: NearbyRestaurant
    next_course: Course | None = None
    next_place: Place | None = None
    total_estimated_walk_minutes: int | None = None


class MealRecommendationResponse(BaseModel):
    items: list[MealRecommendation] = Field(default_factory=list)
    next_course: Course | None = None
    next_place: Place | None = None
    available_minutes: int | None = None
    reason: str | None = None


class Period(BaseModel):
    period: int
    start: str
    end: str
