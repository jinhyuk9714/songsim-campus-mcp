from __future__ import annotations

from typing import Any, Literal

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
    open_now: bool | None = None


class RestaurantSearchResult(Restaurant):
    distance_meters: int | None = None
    estimated_walk_minutes: int | None = None


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


class McpCoordinates(BaseModel):
    latitude: float
    longitude: float


class McpToolError(BaseModel):
    error: str
    type: str
    message: str


class McpPlaceResult(BaseModel):
    slug: str
    name: str
    canonical_name: str
    category: str
    aliases: list[str] = Field(default_factory=list)
    short_location: str | None = None
    coordinates: McpCoordinates | None = None
    highlights: list[str] = Field(default_factory=list)


class McpNoticeResult(BaseModel):
    title: str
    category_display: str
    published_at: str
    summary: str = ""
    source_url: str | None = None


class McpNearbyRestaurantResult(BaseModel):
    name: str
    category_display: str
    distance_meters: int | None = None
    estimated_walk_minutes: int | None = None
    price_hint: str | None = None
    open_now: bool | None = None
    location_hint: str | None = None


class McpRestaurantSearchResult(BaseModel):
    name: str
    category_display: str
    distance_meters: int | None = None
    estimated_walk_minutes: int | None = None
    price_hint: str | None = None
    location_hint: str | None = None


class GptPlaceResult(BaseModel):
    name: str
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    category: str
    short_location: str | None = None
    coordinates: McpCoordinates | None = None
    highlights: list[str] = Field(default_factory=list)


class GptNoticeResult(BaseModel):
    title: str
    category_display: str
    published_at: str
    summary: str = ""
    source_url: str | None = None


class NoticeCategoryInfo(BaseModel):
    category: str
    category_display: str
    aliases: list[str] = Field(default_factory=list)


class GptNoticeCategoryInfo(BaseModel):
    category: str
    category_display: str
    aliases: list[str] = Field(default_factory=list)


class GptNearbyRestaurantResult(BaseModel):
    name: str
    category_display: str
    distance_meters: int | None = None
    estimated_walk_minutes: int | None = None
    price_hint: str | None = None
    open_now: bool | None = None
    location_hint: str | None = None


class GptRestaurantSearchResult(BaseModel):
    name: str
    category_display: str
    distance_meters: int | None = None
    estimated_walk_minutes: int | None = None
    price_hint: str | None = None
    location_hint: str | None = None


class EmptyClassroomBuilding(BaseModel):
    slug: str
    name: str
    canonical_name: str
    category: str
    aliases: list[str] = Field(default_factory=list)


class EstimatedEmptyClassroom(BaseModel):
    room: str
    available_now: bool = True
    availability_mode: Literal["realtime", "estimated"] = "estimated"
    source_observed_at: str | None = None
    next_occupied_at: str | None = None
    next_course_summary: str | None = None


class EstimatedEmptyClassroomResponse(BaseModel):
    building: EmptyClassroomBuilding
    evaluated_at: str
    year: int
    semester: int
    availability_mode: Literal["realtime", "estimated", "mixed"] = "estimated"
    observed_at: str | None = None
    estimate_note: str
    items: list[EstimatedEmptyClassroom] = Field(default_factory=list)


class Profile(BaseModel):
    id: str
    display_name: str = ""
    department: str | None = None
    student_year: int | None = None
    admission_type: str | None = None
    created_at: str
    updated_at: str


class ProfileCreateRequest(BaseModel):
    display_name: str = ""


class ProfileUpdateRequest(BaseModel):
    display_name: str | None = None
    department: str | None = None
    student_year: int | None = None
    admission_type: str | None = None


class ProfileCourseRef(BaseModel):
    year: int
    semester: int
    code: str
    section: str


class ProfileNoticePreferences(BaseModel):
    categories: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class ProfileInterests(BaseModel):
    tags: list[str] = Field(default_factory=list)


class SyncRun(BaseModel):
    id: int
    target: str
    status: str
    trigger: str = "manual"
    params: dict[str, int | str] = Field(default_factory=dict)
    summary: dict[str, int] = Field(default_factory=dict)
    error_text: str | None = None
    started_at: str
    finished_at: str | None = None


class CacheObservability(BaseModel):
    fresh_hit: int = 0
    stale_hit: int = 0
    live_fetch_success: int = 0
    live_fetch_error: int = 0
    local_fallback: int = 0
    restaurant_hours_fresh_hit: int = 0
    restaurant_hours_stale_hit: int = 0
    restaurant_hours_live_fetch_success: int = 0
    restaurant_hours_live_fetch_error: int = 0
    recent_events: list[dict[str, Any]] = Field(default_factory=list)


class SyncObservability(BaseModel):
    recent_events: list[dict[str, Any]] = Field(default_factory=list)
    last_failure_at: str | None = None
    last_failure_message: str | None = None


class AutomationJobObservability(BaseModel):
    name: str
    interval_minutes: int
    last_run_at: str | None = None
    last_status: str | None = None
    next_due_at: str | None = None


class AutomationObservability(BaseModel):
    enabled: bool = False
    leader: bool = False
    jobs: list[AutomationJobObservability] = Field(default_factory=list)


class ObservabilitySnapshot(BaseModel):
    process_started_at: str
    cache: CacheObservability = Field(default_factory=CacheObservability)
    sync: SyncObservability = Field(default_factory=SyncObservability)
    automation: AutomationObservability = Field(default_factory=AutomationObservability)
    datasets: list[dict[str, Any]] = Field(default_factory=list)
    recent_sync_runs: list[SyncRun] = Field(default_factory=list)


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


class MatchedNotice(BaseModel):
    notice: Notice
    matched_reasons: list[str] = Field(default_factory=list)


class MatchedCourse(BaseModel):
    course: Course
    matched_reasons: list[str] = Field(default_factory=list)


class Period(BaseModel):
    period: int
    start: str
    end: str
