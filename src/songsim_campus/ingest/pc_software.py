from __future__ import annotations

import re
from html import unescape
from typing import Any

import httpx
from bs4 import BeautifulSoup

OFFICIAL_PC_SOFTWARE_URL = "https://www.catholic.ac.kr/ko/campuslife/pc.do"
PC_SOFTWARE_SOURCE_TAG = "cuk_pc_software"
_WORD_PATTERN = re.compile(r"[0-9A-Za-z가-힣]+")
_VERSION_SUFFIX_PATTERN = re.compile(
    r"(?:\s+(?:\d+(?:\.\d+)*|cs\d+|cc\d+|dc))+$",
    re.IGNORECASE,
)

_SOFTWARE_TRANSLATION_ALIASES = {
    "포토샵": ["photoshop"],
    "일러스트레이터": ["illustrator"],
    "한글": ["hangul"],
    "ms-office": ["msoffice", "ms office"],
    "ms office": ["msoffice", "ms-office"],
    "visual studio": ["visualstudio", "visual studio"],
    "spss": ["spss"],
    "sas": ["sas"],
    "acrobat reader": ["acrobatreader", "acrobat reader"],
    "sap": ["sap"],
}


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    text = BeautifulSoup(unescape(value), "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_search_text(value: str | None) -> str:
    return re.sub(r"\W+", "", _clean_text(value).casefold())


def _split_software_items(value: str | None) -> list[str]:
    if not value:
        return []
    return [item for item in (_clean_text(part) for part in value.split(",")) if item]


def _software_aliases(value: str) -> set[str]:
    aliases = {_normalize_search_text(value)}
    normalized = _clean_text(value).casefold()
    stripped = _VERSION_SUFFIX_PATTERN.sub("", _clean_text(value)).strip()
    if stripped and stripped != _clean_text(value):
        aliases.add(_normalize_search_text(stripped))

    for token in _WORD_PATTERN.findall(_clean_text(value)):
        aliases.add(_normalize_search_text(token))

    for needle, mapped_aliases in _SOFTWARE_TRANSLATION_ALIASES.items():
        if needle in normalized:
            for alias in mapped_aliases:
                aliases.add(_normalize_search_text(alias))

    return {alias for alias in aliases if alias}


def _room_aliases(value: str) -> set[str]:
    aliases = {_normalize_search_text(value)}
    aliases.update(
        {
            _normalize_search_text(token)
            for token in _WORD_PATTERN.findall(_clean_text(value))
        }
    )
    return {alias for alias in aliases if alias}


def _room_prefix(section_title: str) -> str:
    prefix = _clean_text(section_title)
    prefix = prefix.removesuffix(" PC사양").strip()
    prefix = prefix.removesuffix(" 실습실").strip()
    return prefix


def _match_rank(entry: dict[str, Any], query: str | None) -> int | None:
    if query is None:
        return 0
    normalized_query = _normalize_search_text(query)
    if not normalized_query:
        return 0

    for software in entry.get("software_list", []):
        aliases = _software_aliases(str(software))
        if normalized_query in aliases:
            return 0
    for software in entry.get("software_list", []):
        aliases = _software_aliases(str(software))
        if any(normalized_query in alias for alias in aliases):
            return 1

    room_aliases = _room_aliases(str(entry.get("room") or ""))
    if normalized_query in room_aliases:
        return 2
    if any(normalized_query in alias for alias in room_aliases):
        return 3
    return None


def search_pc_software_entries(
    rows: list[dict[str, Any]],
    *,
    query: str | None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    ranked: list[tuple[int, str, int, dict[str, Any]]] = []
    for index, row in enumerate(rows):
        rank = _match_rank(row, query)
        if rank is None:
            continue
        ranked.append((rank, _clean_text(str(row.get("room") or "")).casefold(), index, row))
    ranked.sort(key=lambda item: (item[0], item[1], item[2]))
    return [item[3] for item in ranked[:limit]]


class PCSoftwareSource:
    """Parser for the official PC/software usage page."""

    source_tag = PC_SOFTWARE_SOURCE_TAG

    def __init__(self, url: str = OFFICIAL_PC_SOFTWARE_URL):
        self.url = url

    def fetch(self) -> str:
        response = httpx.get(self.url, timeout=20)
        response.raise_for_status()
        return response.text

    def parse(self, html: str, *, fetched_at: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        rows: list[dict[str, Any]] = []
        for block in soup.select(".content-box.ITserv .con-box"):
            section_title_node = block.select_one(".h4-tit01")
            section_title = _clean_text(
                section_title_node.get_text(" ", strip=True) if section_title_node else ""
            )
            if section_title != "실습실 이용안내":
                continue
            for sub_block in block.select(".con-box02"):
                sub_title_node = sub_block.select_one(".h5-tit01")
                room_prefix = _room_prefix(
                    _clean_text(sub_title_node.get_text(" ", strip=True) if sub_title_node else "")
                )
                table = sub_block.select_one("table")
                if table is None:
                    continue
                rows.extend(
                    self._parse_table(
                        table,
                        room_prefix=room_prefix,
                        fetched_at=fetched_at,
                    )
                )
        return rows

    def _parse_table(
        self,
        table,
        *,
        room_prefix: str,
        fetched_at: str,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for tr in table.select("tbody tr"):
            cells = tr.find_all("td", recursive=False)
            if len(cells) < 7:
                continue
            room_cell = _clean_text(cells[0].get_text(" ", strip=True))
            room = " ".join(part for part in [room_prefix, room_cell] if part)
            pc_count_text = _clean_text(cells[1].get_text(" ", strip=True))
            try:
                pc_count = int(re.sub(r"[^\d]", "", pc_count_text))
            except ValueError:
                pc_count = None
            software_list = _split_software_items(cells[-1].get_text(" ", strip=True))
            rows.append(
                {
                    "room": room,
                    "pc_count": pc_count,
                    "software_list": software_list,
                    "source_url": self.url,
                    "source_tag": self.source_tag,
                    "last_synced_at": fetched_at,
                }
            )
        return rows
