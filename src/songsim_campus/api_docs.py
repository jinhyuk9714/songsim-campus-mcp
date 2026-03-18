from __future__ import annotations

import copy
from typing import Any

from fastapi import FastAPI, Request

GPT_ACTION_PATHS: dict[str, dict[str, str]] = {
    "/places": {
        "operationId": "searchPlaces",
        "summary": "Search campus places",
        "description": (
            "Search Songsim campus places by building name, alias, or facility keyword. "
            "Use this for locations such as 중앙도서관, 베리타스관, or student facilities."
        ),
    },
    "/courses": {
        "operationId": "searchCourses",
        "summary": "Search public course offerings",
        "description": (
            "Search public Songsim course offerings by title and optional year, "
            "semester, or exact period_start."
        ),
    },
    "/academic-calendar": {
        "operationId": "listAcademicCalendar",
        "summary": "List academic calendar events",
        "description": (
            "List public academic calendar events by academic year with optional "
            "month overlap and title substring filters."
        ),
    },
    "/notices": {
        "operationId": "listLatestNotices",
        "summary": "List latest public notices",
        "description": "List the latest public Songsim campus notices.",
    },
    "/certificate-guides": {
        "operationId": "listCertificateGuides",
        "summary": "List certificate issuance guides",
        "description": "List the current Songsim certificate issuance guides and notices.",
    },
    "/leave-of-absence-guides": {
        "operationId": "listLeaveOfAbsenceGuides",
        "summary": "List leave-of-absence guides",
        "description": (
            "List the current Songsim leave-of-absence guidance, submission cases, "
            "and official FAQ or forms links."
        ),
    },
    "/scholarship-guides": {
        "operationId": "listScholarshipGuides",
        "summary": "List scholarship baseline guides",
        "description": (
            "List the current Songsim scholarship baseline guides and official scholarship "
            "document links."
        ),
    },
    "/wifi-guides": {
        "operationId": "listWifiGuides",
        "summary": "List campus wifi guides",
        "description": (
            "List the current Songsim campus wifi SSIDs and building-level connection "
            "guidance."
        ),
    },
    "/notice-categories": {
        "operationId": "listNoticeCategories",
        "summary": "List public notice categories",
        "description": (
            "List the canonical public notice categories and compatibility aliases such "
            "as career -> employment."
        ),
    },
    "/periods": {
        "operationId": "listClassPeriods",
        "summary": "List class periods",
        "description": "List the fixed Songsim class period table.",
    },
    "/library-seats": {
        "operationId": "getLibrarySeatStatus",
        "summary": "Get central-library reading-room seat status",
        "description": (
            "Best-effort realtime central-library reading-room seat status with fresh cache "
            "and stale fallback."
        ),
    },
    "/dining-menus": {
        "operationId": "listDiningMenus",
        "summary": "List current official campus dining menus",
        "description": (
            "List the current official campus dining menus for Buon Pranzo, Café Bona, "
            "and Café Mensa with extracted weekly text and the original PDF link."
        ),
    },
    "/restaurants/nearby": {
        "operationId": "findNearbyRestaurants",
        "summary": "Find nearby restaurants",
        "description": ("Find walkable restaurants near a Songsim campus building or landmark."),
    },
    "/restaurants/search": {
        "operationId": "searchRestaurants",
        "summary": "Search restaurant brands or venue names",
        "description": (
            "Search nearby restaurant or cafe brands directly by venue name. "
            "Use this for questions like 매머드커피 어디 있어 or 이디야 있나."
        ),
    },
    "/transport": {
        "operationId": "listTransportGuides",
        "summary": "List transit guides",
        "description": "List public Songsim campus transit and access guides.",
    },
}

GPT_ACTION_V2_PATHS: dict[str, dict[str, str]] = {
    "/gpt/places": {
        "operationId": "searchPlacesForGpt",
        "summary": "Find campus places with concise summaries",
        "description": (
            "Use when the user asks where a Songsim campus building, landmark, or facility is. "
            "Returns concise names, aliases, short location hints, and coordinates "
            "that are easy to summarize."
        ),
    },
    "/gpt/notices": {
        "operationId": "listLatestNoticesForGpt",
        "summary": "List latest public notices with short previews",
        "description": (
            "Use when the user wants the latest Songsim public notices. "
            "Returns normalized notice categories and short summary previews."
        ),
    },
    "/gpt/notice-categories": {
        "operationId": "listNoticeCategoriesForGpt",
        "summary": "List public notice categories with concise labels",
        "description": (
            "Use when the user asks which public notice categories exist or what "
            "employment vs career means."
        ),
    },
    "/gpt/periods": {
        "operationId": "listPeriodsForGpt",
        "summary": "List class periods with concise timing rows",
        "description": (
            "Use when the user asks what a period number means or needs the class "
            "period table before searching courses."
        ),
    },
    "/gpt/library-seats": {
        "operationId": "getLibrarySeatStatusForGpt",
        "summary": "Get concise central-library reading-room seat status",
        "description": (
            "Use when the user asks whether central-library reading rooms have seats "
            "available. Returns live, stale_cache, or unavailable status."
        ),
    },
    "/gpt/dining-menus": {
        "operationId": "listDiningMenusForGpt",
        "summary": "List official campus dining menus with concise previews",
        "description": (
            "Use when the user asks for this week’s official Songsim campus dining menu. "
            "Returns concise venue names, weekly labels, menu previews, and source links."
        ),
    },
    "/gpt/restaurants/nearby": {
        "operationId": "findNearbyRestaurantsForGpt",
        "summary": "Find nearby restaurants with concise hints",
        "description": (
            "Use when the user asks for nearby food around a Songsim campus location. "
            "Returns concise distance, walk time, price, and location hints."
        ),
    },
    "/gpt/restaurants/search": {
        "operationId": "searchRestaurantsForGpt",
        "summary": "Search restaurant brands with concise hints",
        "description": (
            "Use when the user asks whether a specific brand or venue exists nearby. "
            "Returns concise distance, walk time, price, and location hints."
        ),
    },
    "/gpt/classrooms/empty": {
        "operationId": "listEstimatedEmptyClassroomsForGpt",
        "summary": "Find current empty classrooms in a building",
        "description": (
            "Use when the user asks which classrooms are empty right now in a Songsim "
            "lecture building. Returns official realtime classroom availability when an "
            "official source is available, otherwise falls back to timetable-based estimates."
        ),
    },
}


def build_filtered_openapi(
    app: FastAPI,
    request: Request,
    settings: Any,
    *,
    title: str,
    description: str,
    path_metadata: dict[str, dict[str, str]],
) -> dict[str, object]:
    source_spec = copy.deepcopy(app.openapi())
    public_http_url = settings.public_http_url or str(request.base_url).rstrip("/")
    filtered_paths: dict[str, object] = {}
    for path, metadata in path_metadata.items():
        operation = copy.deepcopy(source_spec["paths"][path]["get"])
        operation["operationId"] = metadata["operationId"]
        operation["summary"] = metadata["summary"]
        operation["description"] = metadata["description"]
        filtered_paths[path] = {"get": operation}
    return {
        "openapi": source_spec["openapi"],
        "info": {
            "title": title,
            "version": source_spec["info"]["version"],
            "description": description,
        },
        "servers": [{"url": public_http_url}],
        "paths": filtered_paths,
        "components": source_spec.get("components", {}),
    }


def build_gpt_actions_openapi(app: FastAPI, request: Request, settings: Any) -> dict[str, object]:
    return build_filtered_openapi(
        app,
        request,
        settings,
        title="Songsim Campus GPT Actions",
        description="Slimmed-down read-only actions schema for ChatGPT GPT Actions.",
        path_metadata=GPT_ACTION_PATHS,
    )


def build_gpt_actions_openapi_v2(
    app: FastAPI,
    request: Request,
    settings: Any,
) -> dict[str, object]:
    return build_filtered_openapi(
        app,
        request,
        settings,
        title="Songsim Campus GPT Actions v2",
        description=(
            "GPT-focused actions schema with concise place, notice, and nearby "
            "restaurant responses."
        ),
        path_metadata=GPT_ACTION_V2_PATHS,
    )
