from __future__ import annotations

import json
import re
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

from .schemas import RestaurantSearchResult

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
RESTAURANT_SEARCH_ALIASES_PATH = DATA_DIR / "restaurant_search_aliases.json"
RESTAURANT_SEARCH_NOISE_TERMS_PATH = DATA_DIR / "restaurant_search_noise_terms.json"


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _collapse_whitespace(value: str) -> str:
    return " ".join(value.split())


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", "", value).strip()


def _normalized_query_variants(value: str | None) -> tuple[str | None, str | None]:
    cleaned = _normalize_optional_text(value)
    if cleaned is None:
        return None, None
    collapsed = _collapse_whitespace(cleaned)
    compacted = _compact_text(cleaned)
    return collapsed, compacted or None


def _matches_exact_text_candidate(
    text: str | None,
    *,
    collapsed_query: str,
    compact_query: str | None,
) -> bool:
    cleaned = _normalize_optional_text(text)
    if cleaned is None:
        return False
    collapsed_text = _collapse_whitespace(cleaned).lower()
    if collapsed_text == collapsed_query.lower():
        return True
    if compact_query is None:
        return False
    return _compact_text(cleaned).lower() == compact_query.lower()


def _matches_partial_text_candidate(
    text: str | None,
    *,
    collapsed_query: str,
    compact_query: str | None,
) -> bool:
    cleaned = _normalize_optional_text(text)
    if cleaned is None:
        return False
    collapsed_text = _collapse_whitespace(cleaned).lower()
    if collapsed_query.lower() in collapsed_text:
        return True
    if compact_query is None:
        return False
    compact_text = _compact_text(cleaned).lower()
    return bool(compact_query) and compact_query.lower() in compact_text


def _unique_stripped(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _unique_lower_stripped(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = value.strip().lower()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _normalize_facility_name(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"\([^)]*\)", "", normalized)
    for token in ("가톨릭대학교", "가톨릭대", "성심교정"):
        normalized = normalized.replace(token, "")
    normalized = "".join(char for char in normalized if not char.isspace())
    if normalized.endswith("점"):
        normalized = normalized[:-1]
    return normalized


def _parse_restaurant_search_aliases(payload: Any) -> dict[str, list[str]]:
    if not isinstance(payload, dict):
        raise ValueError("restaurant search aliases must be a JSON object keyed by brand token")

    aliases: dict[str, list[str]] = {}
    for raw_brand, raw_aliases in payload.items():
        if not isinstance(raw_brand, str) or not raw_brand.strip():
            raise ValueError("restaurant search alias key must be a non-empty string")
        if not isinstance(raw_aliases, list) or any(
            not isinstance(item, str) for item in raw_aliases
        ):
            raise ValueError("restaurant search alias entries must be a list of strings")
        aliases[raw_brand.strip()] = _unique_stripped(list(raw_aliases))
    return aliases


@lru_cache(maxsize=1)
def _load_restaurant_search_aliases() -> dict[str, list[str]]:
    payload = json.loads(RESTAURANT_SEARCH_ALIASES_PATH.read_text(encoding="utf-8"))
    return _parse_restaurant_search_aliases(payload)


def _parse_restaurant_search_noise_terms(payload: Any) -> dict[str, list[str]]:
    if not isinstance(payload, dict):
        raise ValueError("restaurant search noise terms must be a JSON object")
    allowed_keys = {"name_terms", "tag_terms", "description_terms"}
    unknown_keys = set(payload) - allowed_keys
    if unknown_keys:
        raise ValueError(
            "restaurant search noise terms only support name_terms, tag_terms, "
            "and description_terms"
        )

    parsed: dict[str, list[str]] = {}
    for key in allowed_keys:
        raw_values = payload.get(key, [])
        if not isinstance(raw_values, list) or any(
            not isinstance(item, str) for item in raw_values
        ):
            raise ValueError(f"restaurant search noise terms {key} must be a list of strings")
        parsed[key] = _unique_stripped(list(raw_values))
    return parsed


@lru_cache(maxsize=1)
def _load_restaurant_search_noise_terms() -> dict[str, list[str]]:
    payload = json.loads(RESTAURANT_SEARCH_NOISE_TERMS_PATH.read_text(encoding="utf-8"))
    return _parse_restaurant_search_noise_terms(payload)


def _restaurant_brand_aliases_for_row(item: dict[str, Any]) -> list[str]:
    normalized_targets = {
        _normalize_facility_name(str(item.get("name") or "")),
        *[_normalize_facility_name(str(tag)) for tag in item.get("tags", [])],
    }
    aliases: list[str] = []
    for canonical_brand, brand_aliases in _load_restaurant_search_aliases().items():
        normalized_brand = _normalize_facility_name(canonical_brand)
        if normalized_brand and any(
            normalized_brand in target for target in normalized_targets if target
        ):
            aliases.extend(brand_aliases)
    return _unique_stripped(aliases)


def resolve_restaurant_brand_query_token(query: str) -> str:
    collapsed_query, _ = _normalized_query_variants(query)
    normalized_query = _normalize_facility_name(query)
    for canonical_brand, brand_aliases in _load_restaurant_search_aliases().items():
        for candidate in [canonical_brand, *brand_aliases]:
            if _normalize_facility_name(candidate) == normalized_query:
                return canonical_brand
    if collapsed_query is not None:
        return collapsed_query
    return query.strip()


def _restaurant_brand_exactness(
    item: dict[str, Any],
    *,
    canonical_query: str | None,
) -> int:
    if canonical_query is None:
        return 0

    normalized_brand_terms = _unique_lower_stripped(
        [canonical_query, *(_load_restaurant_search_aliases().get(canonical_query, []))]
    )
    if not normalized_brand_terms:
        return 2

    tag_targets = [_normalize_facility_name(str(tag)) for tag in item.get("tags", [])]
    name_target = _normalize_facility_name(str(item.get("name") or ""))

    if any(target == term for term in normalized_brand_terms for target in tag_targets if target):
        return 0
    if any(target == term for term in normalized_brand_terms for target in [name_target] if target):
        return 0
    if any(term in target for term in normalized_brand_terms for target in tag_targets if target):
        return 1
    if any(term in name_target for term in normalized_brand_terms if term and name_target):
        return 1
    return 2


def _restaurant_search_text_contains_noise(value: str | None, terms: list[str]) -> bool:
    normalized_value = _normalize_facility_name(value or "")
    if not normalized_value:
        return False
    return any(
        normalized_term in normalized_value
        for normalized_term in (_normalize_facility_name(term) for term in terms)
        if normalized_term
    )


def _is_restaurant_search_noise_candidate(item: dict[str, Any]) -> bool:
    noise_terms = _load_restaurant_search_noise_terms()
    if _restaurant_search_text_contains_noise(item.get("name"), noise_terms["name_terms"]):
        return True
    if any(
        _restaurant_search_text_contains_noise(str(tag), noise_terms["tag_terms"])
        for tag in item.get("tags", [])
    ):
        return True
    if _restaurant_search_text_contains_noise(
        item.get("description"),
        noise_terms["description_terms"],
    ):
        return True
    return False


def _rank_restaurant_search_candidate(
    item: dict[str, Any],
    *,
    collapsed_query: str,
    compact_query: str | None,
) -> int | None:
    name = str(item.get("name") or "")
    aliases = _restaurant_brand_aliases_for_row(item)
    tags = [str(tag) for tag in item.get("tags", [])]

    if any(
        _matches_exact_text_candidate(
            alias,
            collapsed_query=collapsed_query,
            compact_query=compact_query,
        )
        for alias in aliases
    ):
        return 0
    if _matches_exact_text_candidate(
        name,
        collapsed_query=collapsed_query,
        compact_query=compact_query,
    ):
        return 1
    if any(
        _matches_partial_text_candidate(
            alias,
            collapsed_query=collapsed_query,
            compact_query=compact_query,
        )
        for alias in aliases
    ):
        return 2
    if _matches_partial_text_candidate(
        name,
        collapsed_query=collapsed_query,
        compact_query=compact_query,
    ):
        return 3
    if any(
        _matches_partial_text_candidate(
            tag,
            collapsed_query=collapsed_query,
            compact_query=compact_query,
        )
        for tag in tags
    ):
        return 4
    return None


def rank_restaurant_search_results(
    rows: list[dict[str, Any]],
    *,
    collapsed_query: str | None,
    compact_query: str | None,
    canonical_brand_query: str | None,
    ranking_origin_place: dict[str, Any] | None,
    origin_place: dict[str, Any] | None,
    limit: int,
    estimate_distance_meters: Callable[[dict[str, Any], dict[str, Any]], int | None],
    estimate_walk_minutes: Callable[[dict[str, Any], dict[str, Any]], int | None],
) -> list[RestaurantSearchResult]:
    ranked: list[
        tuple[
            int,
            int,
            int,
            int,
            int,
            str,
            dict[str, Any],
            int | None,
            int | None,
        ]
    ] = []
    for item in rows:
        if _is_restaurant_search_noise_candidate(item):
            continue
        if collapsed_query is None:
            rank = 0
        else:
            rank = _rank_restaurant_search_candidate(
                item,
                collapsed_query=collapsed_query,
                compact_query=compact_query,
            )
            if rank is None:
                continue
        brand_exactness = _restaurant_brand_exactness(
            item,
            canonical_query=canonical_brand_query,
        )

        hidden_distance_meters: int | None = None
        hidden_walk_minutes: int | None = None
        distance_meters: int | None = None
        estimated_walk_minutes: int | None = None
        if (
            ranking_origin_place is not None
            and item.get("latitude") is not None
            and item.get("longitude") is not None
        ):
            hidden_distance_meters = estimate_distance_meters(ranking_origin_place, item)
            hidden_walk_minutes = estimate_walk_minutes(ranking_origin_place, item)
            if origin_place is not None:
                distance_meters = hidden_distance_meters
                estimated_walk_minutes = hidden_walk_minutes

        campus_bucket = 0
        if origin_place is None:
            campus_bucket = (
                0
                if hidden_walk_minutes is not None and hidden_walk_minutes <= 15
                else 1
            )

        ranked.append(
            (
                rank,
                brand_exactness,
                campus_bucket,
                hidden_walk_minutes if hidden_walk_minutes is not None else 999,
                hidden_distance_meters if hidden_distance_meters is not None else 999999,
                str(item.get("name") or ""),
                item,
                distance_meters,
                estimated_walk_minutes,
            )
        )

    ranked.sort(key=lambda item: (item[0], item[1], item[2], item[3], item[4], item[5]))
    return [
        RestaurantSearchResult.model_validate(
            {
                **item,
                "distance_meters": distance_meters,
                "estimated_walk_minutes": estimated_walk_minutes,
            }
        )
        for _, _, _, _, _, _, item, distance_meters, estimated_walk_minutes in ranked[:limit]
    ]
