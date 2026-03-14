from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime

import uvicorn
from fastapi import FastAPI, HTTPException, Query

from .db import connection, init_db
from .schemas import (
    Course,
    MealRecommendationResponse,
    NearbyRestaurant,
    Notice,
    Period,
    Place,
    Profile,
    ProfileCourseRef,
    ProfileCreateRequest,
    ProfileNoticePreferences,
    Restaurant,
    TransportGuide,
)
from .seed import seed_demo
from .services import (
    InvalidRequestError,
    NotFoundError,
    create_profile,
    find_nearby_restaurants,
    get_class_periods,
    get_place,
    get_profile_meal_recommendations,
    get_profile_timetable,
    list_latest_notices,
    list_profile_notices,
    list_restaurants,
    list_transport_guides,
    search_courses,
    search_places,
    set_profile_notice_preferences,
    set_profile_timetable,
    sync_official_snapshot,
)
from .settings import get_settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    settings = get_settings()
    if settings.sync_official_on_start:
        with connection() as conn:
            sync_official_snapshot(conn)
    elif settings.seed_demo_on_start:
        seed_demo(force=False)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    @app.get("/healthz")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/periods", response_model=list[Period])
    def periods() -> list[Period]:
        return get_class_periods()

    @app.get("/places", response_model=list[Place])
    def places(
        query: str = Query(default="", description="건물/시설/도서관 검색어"),
        category: str | None = Query(default=None),
        limit: int = Query(default=10, ge=1, le=50),
    ) -> list[Place]:
        with connection() as conn:
            return search_places(conn, query=query, category=category, limit=limit)

    @app.get("/places/{identifier}", response_model=Place)
    def place_detail(identifier: str) -> Place:
        with connection() as conn:
            try:
                return get_place(conn, identifier)
            except NotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/courses", response_model=list[Course])
    def courses(
        query: str = Query(default=""),
        year: int | None = Query(default=None),
        semester: int | None = Query(default=None),
        limit: int = Query(default=20, ge=1, le=50),
    ) -> list[Course]:
        with connection() as conn:
            return search_courses(conn, query=query, year=year, semester=semester, limit=limit)

    @app.get("/restaurants", response_model=list[Restaurant])
    def restaurants() -> list[Restaurant]:
        with connection() as conn:
            return list_restaurants(conn)

    @app.get("/restaurants/nearby", response_model=list[NearbyRestaurant])
    def restaurants_nearby(
        origin: str = Query(description="출발 건물 slug 또는 이름"),
        category: str | None = Query(default=None),
        budget_max: int | None = Query(default=None, ge=0),
        walk_minutes: int = Query(default=15, ge=1, le=60),
        limit: int = Query(default=10, ge=1, le=50),
    ) -> list[NearbyRestaurant]:
        with connection() as conn:
            try:
                return find_nearby_restaurants(
                    conn,
                    origin=origin,
                    category=category,
                    budget_max=budget_max,
                    walk_minutes=walk_minutes,
                    limit=limit,
                )
            except NotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/notices", response_model=list[Notice])
    def notices(
        category: str | None = Query(default=None),
        limit: int = Query(default=10, ge=1, le=50),
    ) -> list[Notice]:
        with connection() as conn:
            return list_latest_notices(conn, category=category, limit=limit)

    @app.get("/transport", response_model=list[TransportGuide])
    def transport(
        mode: str | None = Query(default=None),
        limit: int = Query(default=20, ge=1, le=50),
    ) -> list[TransportGuide]:
        with connection() as conn:
            return list_transport_guides(conn, mode=mode, limit=limit)

    @app.post("/profiles", response_model=Profile)
    def create_profile_endpoint(payload: ProfileCreateRequest | None = None) -> Profile:
        with connection() as conn:
            return create_profile(conn, display_name=(payload.display_name if payload else ""))

    @app.put("/profiles/{profile_id}/timetable", response_model=list[Course])
    def set_profile_timetable_endpoint(
        profile_id: str,
        courses: list[ProfileCourseRef],
    ) -> list[Course]:
        with connection() as conn:
            try:
                return set_profile_timetable(conn, profile_id, courses)
            except NotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except InvalidRequestError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/profiles/{profile_id}/timetable", response_model=list[Course])
    def get_profile_timetable_endpoint(
        profile_id: str,
        year: int | None = Query(default=None),
        semester: int | None = Query(default=None),
    ) -> list[Course]:
        with connection() as conn:
            try:
                return get_profile_timetable(conn, profile_id, year=year, semester=semester)
            except NotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.put("/profiles/{profile_id}/notice-preferences", response_model=ProfileNoticePreferences)
    def set_profile_notice_preferences_endpoint(
        profile_id: str,
        preferences: ProfileNoticePreferences,
    ) -> ProfileNoticePreferences:
        with connection() as conn:
            try:
                return set_profile_notice_preferences(conn, profile_id, preferences)
            except NotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except InvalidRequestError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/profiles/{profile_id}/notices", response_model=list[Notice])
    def get_profile_notices_endpoint(
        profile_id: str,
        limit: int = Query(default=10, ge=1, le=50),
    ) -> list[Notice]:
        with connection() as conn:
            try:
                return list_profile_notices(conn, profile_id, limit=limit)
            except NotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except InvalidRequestError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(
        "/profiles/{profile_id}/meal-recommendations",
        response_model=MealRecommendationResponse,
    )
    def get_profile_meal_recommendations_endpoint(
        profile_id: str,
        origin: str = Query(description="출발 건물 slug 또는 이름"),
        at: datetime | None = Query(default=None),
        year: int | None = Query(default=None),
        semester: int | None = Query(default=None),
        budget_max: int | None = Query(default=None, ge=0),
        category: str | None = Query(default=None),
        limit: int = Query(default=10, ge=1, le=50),
    ) -> MealRecommendationResponse:
        with connection() as conn:
            try:
                return get_profile_meal_recommendations(
                    conn,
                    profile_id,
                    origin=origin,
                    at=at,
                    year=year,
                    semester=semester,
                    budget_max=budget_max,
                    category=category,
                    limit=limit,
                )
            except NotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except InvalidRequestError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "songsim_campus.api:create_app",
        factory=True,
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
