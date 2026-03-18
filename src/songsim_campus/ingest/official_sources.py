from __future__ import annotations

import json
import re
from datetime import datetime
from html import unescape
from urllib.parse import urlencode, urljoin
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

PLACE_LIST_PATTERN = re.compile(r"\?mode=getPlaceListByCondition&campus=\$\{campus\}")
SCHEDULE_PATTERN = re.compile(
    r"^(?P<day>[월화수목금토일])\s*(?P<start>\d+)(?:\s*[~-]\s*(?P<end>\d+))?(?:\((?P<room>[^)]+)\))?$"
)
WHITESPACE_PATTERN = re.compile(r"\s+")
SEAT_STATUS_INTEGER_PATTERN = re.compile(r"(\d[\d,]*)")
KST = ZoneInfo("Asia/Seoul")


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    text = BeautifulSoup(unescape(value), "html.parser").get_text(" ", strip=True)
    return WHITESPACE_PATTERN.sub(" ", text).strip()


def _compact_text(value: str | None) -> str:
    return re.sub(r"\s+", "", value or "").strip()


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "place"


def _split_parenthetical(value: str) -> tuple[str, list[str]]:
    matches = re.findall(r"\(([^)]+)\)", value)
    outer = re.sub(r"\([^)]*\)", "", value).strip()
    aliases = [item.strip() for item in matches if item.strip()]
    return outer, aliases


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _date_from_epoch_millis(value: int | str | None) -> str | None:
    if value in (None, ""):
        return None
    try:
        timestamp_millis = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(timestamp_millis / 1000, tz=KST).date().isoformat()


def _academic_year_from_date_string(value: str) -> int:
    year = int(value[:4])
    month = int(value[5:7])
    return year if month >= 3 else year - 1


def _extract_table_grid(table) -> list[list[str]]:
    rows: list[list[str]] = []
    active_rowspans: list[tuple[int, str] | None] = []

    for tr in table.select("tr"):
        cells = tr.find_all(["th", "td"], recursive=False)
        row: list[str] = []
        col_idx = 0
        while col_idx < len(active_rowspans) and active_rowspans[col_idx] is not None:
            remaining, value = active_rowspans[col_idx]
            row.append(value)
            remaining -= 1
            active_rowspans[col_idx] = (remaining, value) if remaining > 0 else None
            col_idx += 1
        for cell in cells:
            while col_idx < len(active_rowspans) and active_rowspans[col_idx] is not None:
                remaining, value = active_rowspans[col_idx]
                row.append(value)
                remaining -= 1
                active_rowspans[col_idx] = (remaining, value) if remaining > 0 else None
                col_idx += 1
            text = _clean_text(cell.get_text(" ", strip=True))
            colspan = int(cell.get("colspan", 1))
            rowspan = int(cell.get("rowspan", 1))
            while len(active_rowspans) < col_idx + colspan:
                active_rowspans.append(None)
            for offset in range(colspan):
                row.append(text)
                if rowspan > 1:
                    active_rowspans[col_idx + offset] = (rowspan - 1, text)
            col_idx += colspan
        while col_idx < len(active_rowspans) and active_rowspans[col_idx] is not None:
            remaining, value = active_rowspans[col_idx]
            row.append(value)
            remaining -= 1
            active_rowspans[col_idx] = (remaining, value) if remaining > 0 else None
            col_idx += 1
        if row:
            rows.append(row)
    return rows


def _collect_dl_fields(root) -> dict[str, str]:
    fields: dict[str, str] = {}
    for dl in root.select("dl"):
        label = dl.find("dt")
        value = dl.find("dd")
        if not label or not value:
            continue
        key = _clean_text(label.get_text()).replace(":", "").strip()
        fields[key] = _clean_text(value.get_text(" ", strip=True))
    return fields


def _collect_dl_pairs(root) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for dl in root.select("dl"):
        label = dl.find("dt")
        value = dl.find("dd")
        if not label or not value:
            continue
        key = _clean_text(label.get_text()).replace(":", "").strip()
        normalized = _clean_text(value.get_text(" ", strip=True))
        if key and normalized:
            rows.append((key, normalized))
    return rows


def _normalize_note_text(value: str | None) -> str:
    return _clean_text(value).lstrip("*※ ").strip()


def _extract_table_steps(table) -> list[str]:
    grid = _extract_table_grid(table)
    if len(grid) < 2:
        return []
    headers = [_clean_text(cell) for cell in grid[0]]
    steps: list[str] = []
    for row in grid[1:]:
        normalized_row = [_clean_text(cell) for cell in row]
        nonempty = [cell for cell in normalized_row if cell]
        if not nonempty:
            continue
        unique_nonempty = _unique(nonempty)
        if len(unique_nonempty) == 1:
            note = _normalize_note_text(unique_nonempty[0])
            if note:
                steps.append(note)
            continue
        pairs: list[str] = []
        for idx, header in enumerate(headers[: len(normalized_row)]):
            value = normalized_row[idx]
            if not header or not value:
                continue
            pairs.append(f"{header}: {value}")
        if pairs:
            steps.append(" / ".join(pairs))
    return _unique(steps)


def _extract_link_items(root, *, base_url: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for anchor in root.select("a[href]"):
        label = _clean_text(anchor.get_text(" ", strip=True))
        href = unescape(str(anchor.get("href") or "")).strip()
        if not label or not href:
            continue
        items.append({"label": label, "url": urljoin(base_url, href)})
    return items


def _split_csv_items(value: str | None) -> list[str]:
    if not value:
        return []
    return _unique([_clean_text(item) for item in value.split(",")])


def _flatten_transport_steps(container) -> list[str]:
    steps: list[str] = []
    for item in container.select(".ul-type-dot li"):
        detail = item.select_one(".dl_desc")
        if detail:
            dt = _clean_text(detail.select_one("dt").get_text() if detail.select_one("dt") else "")
            dd = _clean_text(detail.select_one("dd").get_text() if detail.select_one("dd") else "")
            text = " ".join(part for part in [dt, dd] if part)
        else:
            text = _clean_text(item.get_text(" ", strip=True))
        if text:
            steps.append(text)
    return steps


def _normalize_place_slug(name: str, english_name: str, place_id: int) -> str:
    english_base, english_aliases = _split_parenthetical(english_name)
    if any("library" in alias.lower() for alias in english_aliases):
        return _slugify(next(alias for alias in english_aliases if "library" in alias.lower()))
    if english_base:
        return _slugify(english_base)
    return f"place-{place_id}"


def _infer_place_category(name: str, english_name: str, description: str) -> str:
    combined = " ".join([name, english_name, description]).lower()
    if "도서관" in combined or "library" in combined:
        return "library"
    if "정문" in combined or "gate" in combined:
        return "gate"
    if "기숙사" in combined or "dormitory" in combined:
        return "dormitory"
    if "성당" in combined or "chapel" in combined:
        return "chapel"
    if "운동장" in combined or "trail" in combined or "산책로" in combined:
        return "outdoor"
    if "관" in name or "hall" in combined or "center" in combined or "센터" in combined:
        return "building"
    return "facility"


def _normalize_schedule(
    raw_schedule: str | None,
) -> tuple[str | None, int | None, int | None, str | None]:
    if not raw_schedule:
        return None, None, None, None

    normalized = WHITESPACE_PATTERN.sub("", raw_schedule)
    if "," in normalized or "/" in normalized:
        return None, None, None, None

    match = SCHEDULE_PATTERN.match(normalized)
    if not match:
        return None, None, None, None

    start = int(match.group("start"))
    end = int(match.group("end") or start)
    room = match.group("room")
    return match.group("day"), start, end, room


def classify_notice_category(title: str, body: str, board_category: str | None = None) -> str:
    normalized_board_category = _clean_text(board_category or "")
    explicit_category_map = {
        "학사": "academic",
        "장학": "scholarship",
        "취창업": "employment",
    }
    if normalized_board_category in explicit_category_map:
        return explicit_category_map[normalized_board_category]

    text = " ".join(filter(None, [title, body, normalized_board_category])).lower()
    if any(keyword in text for keyword in ["긴급", "중요", "마감", "휴강", "정전", "중단", "폐쇄"]):
        return "urgent"
    if "장학" in text:
        return "scholarship"
    if any(
        keyword in text
        for keyword in ["식당", "학식", "아침밥", "조식", "중식", "석식", "cafeteria"]
    ):
        return "cafeteria"
    if any(keyword in text for keyword in ["도서관", "library"]):
        return "library"
    if any(keyword in text for keyword in ["취업", "진로", "커리어", "자기소개서", "채용"]):
        return "employment"
    if any(keyword in text for keyword in ["행사", "특강", "설명회", "공모전", "축제", "세미나"]):
        return "event"
    if any(
        keyword in text
        for keyword in ["수강", "학사", "성적", "등록", "학기", "시험", "졸업", "강의"]
    ):
        return "academic"
    if board_category:
        return _slugify(board_category).replace("-", "_")
    return "general"


GENERIC_NOTICE_DETAIL_LABELS = {"공지"}


class CampusMapSource:
    """Official Songsim campus map source backed by the public JSON mode."""

    def __init__(self, url: str):
        self.url = url

    def fetch(self) -> str:
        response = httpx.get(self.url, timeout=20)
        response.raise_for_status()
        return response.text

    def discover_place_list_url(self, html: str, *, campus: str = "1") -> str:
        if (
            not PLACE_LIST_PATTERN.search(html)
            and "campus-map" not in html
            and "캠퍼스 안내" not in html
        ):
            raise ValueError("Campus map page no longer exposes the place list endpoint.")
        query = urlencode({"mode": "getPlaceListByCondition", "campus": campus})
        return f"{self.url}?{query}"

    def fetch_place_list(self, *, campus: str = "1") -> str:
        response = httpx.get(self.discover_place_list_url(self.fetch(), campus=campus), timeout=20)
        response.raise_for_status()
        return response.text

    def parse_place_list(self, payload: str, *, fetched_at: str) -> list[dict]:
        data = json.loads(payload)
        rows: list[dict] = []
        seen_slugs: set[str] = set()
        for item in data.get("items", []):
            name = _clean_text(item.get("placeName"))
            english_name = _clean_text(item.get("placeNameEn"))
            description = _clean_text(item.get("description"))
            abbreviation = _clean_text(item.get("abbreviation"))
            name_base, name_aliases = _split_parenthetical(name)
            slug = _normalize_place_slug(name_base or name, english_name, int(item.get("id") or 0))
            if slug in seen_slugs:
                slug = f"{slug}-{item.get('id')}"
            seen_slugs.add(slug)
            aliases = _unique(
                ([name_base] if name_base and name_base != name else [])
                + name_aliases
                + ([abbreviation] if abbreviation else [])
            )
            latitude = item.get("latitude")
            longitude = item.get("longitude")
            rows.append(
                {
                    "slug": slug,
                    "name": name_base or name,
                    "category": _infer_place_category(name, english_name, description),
                    "aliases": aliases,
                    "description": description,
                    "latitude": latitude if latitude not in (0, 0.0, "0", None) else None,
                    "longitude": longitude if longitude not in (0, 0.0, "0", None) else None,
                    "opening_hours": {},
                    "source_tag": "cuk_campus_map",
                    "last_synced_at": fetched_at,
                }
            )
        return rows


class CourseCatalogSource:
    """Official open-course HTML parser."""

    def __init__(self, url: str):
        self.url = url

    def fetch(
        self,
        *,
        year: int,
        semester: int,
        department: str = "ALL",
        completion_type: str = "ALL",
        query: str = "",
        offset: int = 0,
    ) -> str:
        params = {
            "mode": "list",
            "sust": department,
            "pobtFg": completion_type,
            "year": year,
            "openShtm": "10" if semester == 1 else "20",
            "srSearchVal": query,
            "isEngCourses": "N",
            "alignKey": "sbjtNm",
            "article.offset": offset,
        }
        response = httpx.get(self.url, params=params, timeout=20)
        response.raise_for_status()
        return response.text

    def parse(self, html: str, *, fetched_at: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        year = self._parse_year(soup)
        semester = self._parse_semester(soup)
        rows: list[dict] = []
        for tr in soup.select(".b-courses-offered-table tbody tr"):
            cells = tr.find_all("td", recursive=False)
            if len(cells) < 5 or "b-no-post" in cells[0].get("class", []):
                continue
            details = self._parse_detail_fields(cells[4])
            raw_schedule = details.get("시간표") or None
            day_of_week, period_start, period_end, room = _normalize_schedule(raw_schedule)
            rows.append(
                {
                    "year": year,
                    "semester": semester,
                    "code": _clean_text(cells[0].get_text()),
                    "title": _clean_text(cells[1].get_text()),
                    "professor": details.get("담당교수") or None,
                    "department": details.get("개설학과") or None,
                    "section": _clean_text(cells[3].get_text()) or None,
                    "day_of_week": day_of_week,
                    "period_start": period_start,
                    "period_end": period_end,
                    "room": room,
                    "raw_schedule": raw_schedule,
                    "source_tag": "cuk_subject_search",
                    "last_synced_at": fetched_at,
                }
            )
        return rows

    @staticmethod
    def _parse_year(soup: BeautifulSoup) -> int:
        selected = soup.select_one(
            "#year_key option[selected], select[name='year'] option[selected]"
        )
        if selected and selected.get("value", "").isdigit():
            return int(selected["value"])
        current = soup.select_one("#year_key option, select[name='year'] option")
        if current and current.get("value", "").isdigit():
            return int(current["value"])
        raise ValueError("Unable to determine course year from the page.")

    @staticmethod
    def _parse_semester(soup: BeautifulSoup) -> int:
        selected = soup.select_one(
            "#semester_key option[selected], select[name='openShtm'] option[selected]"
        )
        value = selected.get("value") if selected else None
        if value == "10":
            return 1
        if value == "20":
            return 2
        first_option = soup.select_one(
            "#semester_key option[selected], select[name='openShtm'] option"
        )
        value = first_option.get("value") if first_option else None
        if value == "10":
            return 1
        if value == "20":
            return 2
        raise ValueError("Unable to determine course semester from the page.")

    @staticmethod
    def _parse_detail_fields(cell) -> dict[str, str]:
        fields: dict[str, str] = {}
        for item in cell.select(".b-con-list li"):
            label = item.find("p")
            value = item.find("span")
            if not label or not value:
                continue
            key = label.get_text(strip=True).replace(":", "")
            fields[key] = _clean_text(value.get_text())
        return fields


class LibraryHoursSource:
    """Official central-library opening-hours parser."""

    def __init__(self, url: str):
        self.url = url

    def fetch(self) -> str:
        response = httpx.get(self.url, timeout=20)
        response.raise_for_status()
        return response.text

    def parse(self, html: str, *, fetched_at: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        opening_hours: dict[str, str] = {}
        for section in soup.select(".guideContent"):
            title_node = section.select_one(".guideTit1")
            title = _clean_text(title_node.get_text() if title_node else "")
            if title not in {"자료실 이용시간", "열람실 이용시간", "커뮤니티공간 이용시간"}:
                continue
            table = next(
                (
                    candidate
                    for candidate in section.select("table")
                    if candidate.select("tbody tr")
                ),
                None,
            )
            if table is None:
                continue
            grid = _extract_table_grid(table)
            for row in grid[2:]:
                if len(row) < 7:
                    continue
                name = row[0]
                if not name:
                    continue
                time_cells = row[2:6]
                if len(set(time_cells)) == 1:
                    summary = time_cells[0]
                else:
                    summary = (
                        f"학기중 평일 {row[2]} / 토요일 {row[3]} | "
                        f"방학중 평일 {row[4]} / 토요일 {row[5]}"
                    )
                note = row[6]
                if note and note not in {"-", ""}:
                    summary = f"{summary} | {note}"
                opening_hours[name] = summary
        return [
            {
                "place_name": "중앙도서관",
                "opening_hours": opening_hours,
                "source_tag": "cuk_library_hours",
                "last_synced_at": fetched_at,
            }
        ]


class LibrarySeatStatusSource:
    """Best-effort central-library reading-room seat-status parser."""

    def __init__(self, url: str):
        self.url = url

    def fetch(self) -> str:
        response = httpx.get(self.url, timeout=8)
        response.raise_for_status()
        return response.text

    def parse(self, html: str, *, fetched_at: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        rows: list[dict] = []
        seen_rooms: set[str] = set()

        for table in soup.select("table"):
            grid = _extract_table_grid(table)
            if not grid:
                continue
            header_map = self._detect_header_map(grid)
            if header_map is None:
                continue
            header_row_index = int(header_map["_row_index"])
            room_index = int(header_map["room_name"])
            remaining_index = header_map.get("remaining_seats")
            occupied_index = header_map.get("occupied_seats")
            total_index = header_map.get("total_seats")

            for row in grid[header_row_index + 1 :]:
                if len(row) <= room_index:
                    continue
                room_name = _clean_text(row[room_index])
                if not room_name or room_name in seen_rooms or "합계" in room_name:
                    continue
                remaining_seats = self._parse_int_cell(row, remaining_index)
                occupied_seats = self._parse_int_cell(row, occupied_index)
                total_seats = self._parse_int_cell(row, total_index)
                if (
                    remaining_seats is None
                    and occupied_seats is None
                    and total_seats is None
                ):
                    continue
                rows.append(
                    {
                        "room_name": room_name,
                        "remaining_seats": remaining_seats,
                        "occupied_seats": occupied_seats,
                        "total_seats": total_seats,
                        "source_url": self.url,
                        "source_tag": "cuk_library_seat_status",
                        "last_synced_at": fetched_at,
                    }
                )
                seen_rooms.add(room_name)
        return rows

    @staticmethod
    def _parse_int_cell(row: list[str], index: int | None) -> int | None:
        if index is None or index >= len(row):
            return None
        match = SEAT_STATUS_INTEGER_PATTERN.search(row[index] or "")
        if match is None:
            return None
        return int(match.group(1).replace(",", ""))

    @staticmethod
    def _detect_header_map(grid: list[list[str]]) -> dict[str, int] | None:
        for row_index, row in enumerate(grid[:5]):
            normalized = [_compact_text(_clean_text(cell)).lower() for cell in row]
            room_index = next(
                (
                    index
                    for index, cell in enumerate(normalized)
                    if any(keyword in cell for keyword in ("열람실", "실명", "room"))
                ),
                None,
            )
            total_index = next(
                (
                    index
                    for index, cell in enumerate(normalized)
                    if any(keyword in cell for keyword in ("전체", "총", "합계"))
                    and "잔여" not in cell
                    and "사용" not in cell
                ),
                None,
            )
            occupied_index = next(
                (
                    index
                    for index, cell in enumerate(normalized)
                    if any(keyword in cell for keyword in ("사용", "이용", "점유"))
                ),
                None,
            )
            remaining_index = next(
                (
                    index
                    for index, cell in enumerate(normalized)
                    if any(keyword in cell for keyword in ("잔여", "여석", "남은", "빈"))
                ),
                None,
            )
            if room_index is None:
                continue
            if total_index is None and occupied_index is None and remaining_index is None:
                continue
            return {
                "_row_index": row_index,
                "room_name": room_index,
                "total_seats": total_index,
                "occupied_seats": occupied_index,
                "remaining_seats": remaining_index,
            }
        return None


class CampusFacilitiesSource:
    """Official campus restaurants and facilities opening-hours parser."""

    def __init__(self, url: str):
        self.url = url

    def fetch(self) -> str:
        response = httpx.get(self.url, timeout=20)
        response.raise_for_status()
        return response.text

    def fetch_menu_document(self, source_url: str) -> bytes:
        response = httpx.get(source_url, timeout=20)
        response.raise_for_status()
        return response.content

    def parse(self, html: str, *, fetched_at: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        rows: list[dict] = []

        for card in soup.select(".content-box.restaurant .box-wrap.card .border-box"):
            title_node = card.select_one(".box-tit span")
            details = _collect_dl_fields(card)
            facility_name = _clean_text(title_node.get_text() if title_node else "")
            location = details.get("위치", "")
            hours_text = details.get("운영시간", "")
            menu_anchor = next(
                (
                    anchor
                    for anchor in card.select("a[href]")
                    if "메뉴" in _clean_text(anchor.get_text())
                ),
                None,
            )
            contact_value = _normalize_phone(details.get("전화번호"))
            if not facility_name or not location or not hours_text:
                continue
            rows.append(
                {
                    "facility_name": facility_name,
                    "location": location,
                    "hours_text": hours_text,
                    "phone": contact_value,
                    "menu_week_label": (
                        _clean_text(menu_anchor.get_text()) if menu_anchor else None
                    ),
                    "menu_source_url": (
                        urljoin(self.url, unescape(menu_anchor.get("href", "")))
                        if menu_anchor and menu_anchor.get("href")
                        else None
                    ),
                    "category": "식당안내",
                    "source_tag": "cuk_facilities",
                    "last_synced_at": fetched_at,
                }
            )

        table = soup.select_one(".content-box.restaurant .table-wrap table")
        if table is None:
            return rows

        grid = _extract_table_grid(table)
        for row in grid[1:]:
            if len(row) < 5:
                continue
            category = row[0]
            facility_name = row[1]
            phone = _normalize_phone(row[2])
            location = row[3]
            hours_text = row[4]
            rows.append(
                {
                    "facility_name": facility_name,
                    "location": location,
                    "hours_text": hours_text,
                    "phone": phone,
                    "category": category,
                    "source_tag": "cuk_facilities",
                    "last_synced_at": fetched_at,
                }
            )
        return rows


class TransportGuideSource:
    """Official static transport-guide parser for Songsim campus."""

    def __init__(self, url: str):
        self.url = url

    def fetch(self) -> str:
        response = httpx.get(self.url, timeout=20)
        response.raise_for_status()
        return response.text

    def parse(self, html: str, *, fetched_at: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        rows: list[dict] = []

        address = _clean_text(
            soup.select_one(".map-address .addr span").get_text()
            if soup.select_one(".map-address .addr span")
            else ""
        )
        phone = _clean_text(
            soup.select_one(".map-address .tel span").get_text()
            if soup.select_one(".map-address .tel span")
            else ""
        )
        title = _clean_text(
            soup.select_one(".map-title").get_text() if soup.select_one(".map-title") else ""
        )
        if title:
            rows.append(
                {
                    "mode": "campus",
                    "title": title.replace("가톨릭대학교 ", ""),
                    "summary": " / ".join(part for part in [address, phone] if part),
                    "steps": [part for part in [address, phone] if part],
                    "source_url": self.url,
                    "source_tag": "cuk_transport",
                    "last_synced_at": fetched_at,
                }
            )

        for section in soup.select(".con-box02"):
            heading_node = section.select_one(".h5-tit01")
            heading = _clean_text(heading_node.get_text() if heading_node else "")
            mode = "subway" if "지하철" in heading else "bus"
            for box in section.select(".border-box"):
                title_box = box.find("p")
                title_span = title_box.find("span") if title_box else None
                route_title = _clean_text(title_span.get_text() if title_span else "")
                summaries = [
                    _clean_text(item.get_text(" ", strip=True))
                    for item in box.select(".box-tit")
                ]
                if not route_title:
                    continue
                rows.append(
                    {
                        "mode": mode,
                        "title": route_title,
                        "summary": " / ".join(item for item in summaries if item),
                        "steps": _flatten_transport_steps(box),
                        "source_url": self.url,
                        "source_tag": "cuk_transport",
                        "last_synced_at": fetched_at,
                    }
                )
        return rows


class CertificateGuideSource:
    """Official static certificate-guide parser for Songsim campus."""

    def __init__(self, url: str):
        self.url = url

    def fetch(self) -> str:
        response = httpx.get(self.url, timeout=20)
        response.raise_for_status()
        return response.text

    def parse(self, html: str, *, fetched_at: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        root = soup.select_one(".content-box.cert") or soup
        rows: list[dict] = []

        title_node = next(
            (
                node
                for node in root.select(".con-box .h4-tit01")
                if _clean_text(node.get_text()) == "발급증명"
            ),
            None,
        )
        if title_node:
            summary_node = title_node.find_next_sibling("div")
            summary = _clean_text(summary_node.get_text(" ", strip=True) if summary_node else "")
            if summary:
                rows.append(
                    {
                        "title": "발급증명",
                        "summary": summary,
                        "steps": [],
                        "source_url": self.url,
                        "source_tag": "cuk_certificate_guides",
                        "last_synced_at": fetched_at,
                    }
                )

        for box in root.select(".box-wrap .border-box"):
            row = self._parse_simple_box(box, fetched_at=fetched_at)
            if row is not None:
                rows.append(row)

        internet_box = root.select_one(".border-box.box4")
        if internet_box is not None:
            internet_row = self._parse_internet_box(internet_box, fetched_at=fetched_at)
            if internet_row is not None:
                rows.append(internet_row)

            bg_boxes = internet_box.select(".bg-box")
            if len(bg_boxes) > 1:
                stopped_row = self._parse_mail_stop_box(bg_boxes[1], fetched_at=fetched_at)
                if stopped_row is not None:
                    rows.append(stopped_row)
        return rows

    def _parse_simple_box(self, box, *, fetched_at: str) -> dict | None:
        title = _clean_text(
            box.select_one(".box-tit").get_text() if box.select_one(".box-tit") else ""
        )
        if not title:
            return None
        pairs = _collect_dl_pairs(box)
        if not pairs:
            return None
        summary = self._build_summary(title, pairs)
        steps = [f"{label}: {value}" for label, value in pairs]
        steps.extend(
            self._normalize_note(_clean_text(node.get_text(" ", strip=True)))
            for node in box.select(".alert-txt")
            if _clean_text(node.get_text(" ", strip=True))
        )
        return {
            "title": title,
            "summary": summary,
            "steps": steps,
            "source_url": self.url,
            "source_tag": "cuk_certificate_guides",
            "last_synced_at": fetched_at,
        }

    def _parse_internet_box(self, box, *, fetched_at: str) -> dict | None:
        title_wrap = box.find("div", class_="box-tit-wrap")
        title = _clean_text(title_wrap.get_text(" ", strip=True) if title_wrap else "")
        info_box = box.select_one(".bg-box .info-box")
        if not title or info_box is None:
            return None
        pairs = _collect_dl_pairs(info_box)
        summary = next((value for label, value in pairs if label == "신청방법"), "")
        steps = [f"{label}: {value}" for label, value in pairs if label != "신청방법"]
        steps.extend(
            self._normalize_note(_clean_text(node.get_text(" ", strip=True)))
            for node in info_box.select(".alert-txt")
            if _clean_text(node.get_text(" ", strip=True))
        )
        link = info_box.select_one("a[href]")
        source_url = urljoin(self.url, unescape(link.get("href", ""))) if link else self.url
        return {
            "title": title,
            "summary": summary,
            "steps": steps,
            "source_url": source_url,
            "source_tag": "cuk_certificate_guides",
            "last_synced_at": fetched_at,
        }

    def _parse_mail_stop_box(self, box, *, fetched_at: str) -> dict | None:
        title = _clean_text(
            box.select_one(".box-tit").get_text() if box.select_one(".box-tit") else ""
        )
        info_box = box.select_one(".info-box")
        if not title or info_box is None:
            return None
        summary_node = info_box.find("dd")
        summary = _clean_text(summary_node.get_text(" ", strip=True) if summary_node else "")
        pairs = _collect_dl_pairs(info_box)
        steps = [f"{label}: {value}" for label, value in pairs]
        for note in info_box.select(".alert-txt"):
            text = _clean_text(note.get_text(" ", strip=True))
            if not text:
                continue
            if "관련 문의" in text:
                text = text.replace("※ 관련 문의 :", "문의:").replace("※ 관련 문의:", "문의:")
            steps.append(text)
        link = info_box.select_one("a[href]")
        source_url = urljoin(self.url, unescape(link.get("href", ""))) if link else self.url
        return {
            "title": title,
            "summary": summary,
            "steps": steps,
            "source_url": source_url,
            "source_tag": "cuk_certificate_guides",
            "last_synced_at": fetched_at,
        }

    @staticmethod
    def _build_summary(title: str, pairs: list[tuple[str, str]]) -> str:
        field_map = {label: value for label, value in pairs}
        if "발급장소" in field_map and "이용시간" in field_map:
            return f"{field_map['발급장소']} / {field_map['이용시간']}"
        if "신청방법" in field_map:
            return field_map["신청방법"]
        return pairs[0][1] if pairs else title

    @staticmethod
    def _normalize_note(text: str) -> str:
        return text.lstrip("*※ ").strip()


class LeaveOfAbsenceGuideSource:
    """Official static leave-of-absence guide parser for Songsim campus."""

    SECTION_TITLES = (
        "신청방법",
        "휴학상담 안내",
        "다음의 경우 학사지원팀에 직접 방문 제출",
        "휴학 시기에 따른 등록금 반환 기준",
    )

    def __init__(self, url: str):
        self.url = url

    def fetch(self) -> str:
        response = httpx.get(self.url, timeout=20)
        response.raise_for_status()
        return response.text

    def parse(self, html: str, *, fetched_at: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        root = soup.select_one(".content-box.leaveAb") or soup.select_one(".content-box") or soup
        boxes = root.find_all("div", class_="con-box", recursive=False)
        rows_by_title: dict[str, dict] = {}

        for box in boxes:
            title_node = box.select_one(".h4-tit01")
            title = _clean_text(title_node.get_text(" ", strip=True) if title_node else "")
            if not title:
                continue
            if title == "신청방법":
                rows_by_title[title] = self._parse_application_box(box, fetched_at=fetched_at)
            elif title == "휴학상담 안내":
                rows_by_title[title] = self._parse_consultation_box(box, fetched_at=fetched_at)
            elif title == "다음의 경우 학사지원팀에 직접 방문 제출":
                rows_by_title[title] = self._parse_direct_visit_box(box, fetched_at=fetched_at)
            elif title == "휴학 시기에 따른 등록금 반환 기준":
                rows_by_title[title] = self._parse_refund_box(box, fetched_at=fetched_at)

        return [rows_by_title[title] for title in self.SECTION_TITLES if title in rows_by_title]

    def _parse_application_box(self, box, *, fetched_at: str) -> dict:
        step_infos: list[str] = []
        steps: list[str] = []
        for item in box.select(".step-wrap .step-box"):
            step_num = _clean_text(item.select_one(".step-num").get_text(" ", strip=True))
            step_info = _clean_text(item.select_one(".step-info").get_text(" ", strip=True))
            actor_nodes = item.find_all("p", recursive=False)
            actor = _clean_text(actor_nodes[-1].get_text(" ", strip=True) if actor_nodes else "")
            if step_info:
                step_infos.append(step_info)
            if step_num and step_info:
                detail = f"{step_num}: {step_info}"
                if actor:
                    detail += f" ({actor})"
                steps.append(detail)
        return {
            "title": "신청방법",
            "summary": " → ".join(step_infos),
            "steps": steps,
            "links": _extract_link_items(box.select_one(".link-box") or box, base_url=self.url),
            "source_url": self.url,
            "source_tag": "cuk_leave_of_absence_guides",
            "last_synced_at": fetched_at,
        }

    def _parse_consultation_box(self, box, *, fetched_at: str) -> dict:
        steps = self._extract_nested_list_steps(box.select_one(".ul-type-dot"))
        return {
            "title": "휴학상담 안내",
            "summary": (
                "상담을 위한 지도교수 확인과 상담일정 조율 후 휴학관련 문의처를 확인합니다."
            ),
            "steps": steps,
            "links": [],
            "source_url": self.url,
            "source_tag": "cuk_leave_of_absence_guides",
            "last_synced_at": fetched_at,
        }

    def _parse_direct_visit_box(self, box, *, fetched_at: str) -> dict:
        subsection_titles: list[str] = []
        steps: list[str] = []
        for section in box.select(".con-box02"):
            subtitle_node = section.select_one(".h5-tit01")
            subtitle = _clean_text(subtitle_node.get_text(" ", strip=True) if subtitle_node else "")
            if subtitle:
                subsection_titles.append(subtitle)
            for item in self._extract_nested_list_steps(section.select_one(".ul-type-dot")):
                if subtitle:
                    steps.append(f"{subtitle}: {item}")
                else:
                    steps.append(item)
        for note in box.select(".alert-txt li, .alert-txt p"):
            text = _normalize_note_text(note.get_text(" ", strip=True))
            if text and text not in steps:
                steps.append(text)
        title_preview = ", ".join(subsection_titles[:2])
        summary = (
            f"{title_preview} 등 예외적인 경우에는 학사지원팀 방문 제출이 필요합니다."
            if title_preview
            else "예외적인 경우에는 학사지원팀 방문 제출이 필요합니다."
        )
        return {
            "title": "다음의 경우 학사지원팀에 직접 방문 제출",
            "summary": summary,
            "steps": _unique(steps),
            "links": _extract_link_items(box.select_one(".link-box") or box, base_url=self.url),
            "source_url": self.url,
            "source_tag": "cuk_leave_of_absence_guides",
            "last_synced_at": fetched_at,
        }

    def _parse_refund_box(self, box, *, fetched_at: str) -> dict:
        table = box.select_one("table")
        steps = _extract_table_steps(table) if table is not None else []
        return {
            "title": "휴학 시기에 따른 등록금 반환 기준",
            "summary": "휴학 시점에 따라 수업료 전액, 5/6, 2/3 또는 미반환 기준이 적용됩니다.",
            "steps": steps,
            "links": [],
            "source_url": self.url,
            "source_tag": "cuk_leave_of_absence_guides",
            "last_synced_at": fetched_at,
        }

    @staticmethod
    def _extract_nested_list_steps(list_node) -> list[str]:
        if list_node is None:
            return []
        steps: list[str] = []
        for item in list_node.find_all("li", recursive=False):
            main_text = LeaveOfAbsenceGuideSource._direct_list_text(item)
            if main_text:
                steps.append(main_text)
            for nested_list in item.find_all("ul", recursive=False):
                for nested_item in nested_list.find_all("li", recursive=False):
                    nested_text = _normalize_note_text(nested_item.get_text(" ", strip=True))
                    if not nested_text:
                        continue
                    if main_text:
                        steps.append(f"{main_text.rstrip(':')}: {nested_text}")
                    else:
                        steps.append(nested_text)
        return _unique(steps)

    @staticmethod
    def _direct_list_text(item) -> str:
        parts: list[str] = []
        for child in item.contents:
            if getattr(child, "name", None) == "ul":
                continue
            text = _clean_text(
                str(child)
                if isinstance(child, str)
                else child.get_text(" ", strip=True)
            )
            if text:
                parts.append(text)
        return _normalize_note_text(" ".join(parts))


def _extract_alert_steps(box) -> list[str]:
    steps: list[str] = []
    for node in box.select(".alert-txt li, .alert-txt p, p.alert-txt"):
        text = _normalize_note_text(node.get_text(" ", strip=True))
        if text:
            steps.append(text)
    return _unique(steps)


def _extract_con_box_paragraph_steps(box) -> list[str]:
    steps: list[str] = []
    for node in box.find_all(["p", "div"], recursive=False):
        classes = set(node.get("class", []))
        if {"h4-tit01", "h3-tit01"} & classes:
            continue
        if {"alert-txt", "link-box", "table-wrap"} & classes:
            continue
        if node.find("table", recursive=False):
            continue
        text = _normalize_note_text(node.get_text(" ", strip=True))
        if text:
            steps.append(text)
    return _unique(steps)


def _normalize_academic_status_title(title: str) -> str:
    normalized = _clean_text(title)
    if normalized.startswith("자퇴 신청 방법"):
        return "자퇴 신청 방법"
    return normalized


def _parse_academic_status_sections(
    html: str,
    *,
    base_url: str,
    source_tag: str,
    status: str,
    fetched_at: str,
) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(".content-box") or soup
    boxes = root.find_all("div", class_="con-box", recursive=False)
    rows: list[dict] = []
    for box in boxes:
        title_node = box.select_one(".h4-tit01") or box.select_one(".h3-tit01")
        title = _normalize_academic_status_title(
            title_node.get_text(" ", strip=True) if title_node else ""
        )
        if not title:
            continue
        steps = _extract_con_box_paragraph_steps(box)
        steps.extend(LeaveOfAbsenceGuideSource._extract_nested_list_steps(box.select_one("ul")))
        table = box.select_one("table")
        if table is not None:
            steps.extend(_extract_table_steps(table))
        steps.extend(_extract_alert_steps(box))
        steps = _unique(steps)
        summary = steps[0] if steps else ""
        rows.append(
            {
                "status": status,
                "title": title,
                "summary": summary,
                "steps": steps,
                "links": _extract_link_items(box.select_one(".link-box") or box, base_url=base_url),
                "source_url": base_url,
                "source_tag": source_tag,
                "last_synced_at": fetched_at,
            }
        )
    return rows


class AcademicStatusGuideSourceBase:
    """Shared parser for the academic-status guide family."""

    source_tag = "cuk_academic_status_guides"
    status = ""

    def __init__(self, url: str):
        self.url = url

    def fetch(self) -> str:
        response = httpx.get(self.url, timeout=20)
        response.raise_for_status()
        return response.text

    def parse(self, html: str, *, fetched_at: str) -> list[dict]:
        return _parse_academic_status_sections(
            html,
            base_url=self.url,
            source_tag=self.source_tag,
            status=self.status,
            fetched_at=fetched_at,
        )


class ReturnFromLeaveOfAbsenceGuideSource(AcademicStatusGuideSourceBase):
    """Parser for the 복학 안내 page."""

    status = "return_from_leave"

    def __init__(self, url: str = "https://www.catholic.ac.kr/ko/support/return_from_leave_of_absence.do"):
        super().__init__(url)


class DropoutGuideSource(AcademicStatusGuideSourceBase):
    """Parser for the 자퇴 안내 page."""

    status = "dropout"

    def __init__(self, url: str = "https://www.catholic.ac.kr/ko/support/dropout.do"):
        super().__init__(url)


class ReAdmissionGuideSource(AcademicStatusGuideSourceBase):
    """Parser for the 재입학 안내 page."""

    status = "re_admission"

    def __init__(self, url: str = "https://www.catholic.ac.kr/ko/support/re_admission.do"):
        super().__init__(url)


class ScholarshipGuideSource:
    """Official static scholarship-guide parser for Songsim campus."""

    SECTION_TITLES = (
        "장학생 자격",
        "장학생 종류",
        "장학금 신청",
        "장학금 지급",
    )

    def __init__(self, url: str):
        self.url = url

    def fetch(self) -> str:
        response = httpx.get(self.url, timeout=20)
        response.raise_for_status()
        return response.text

    def parse(self, html: str, *, fetched_at: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        root = soup.select_one(".content-box") or soup
        boxes = root.find_all("div", class_="con-box", recursive=False)
        rows_by_title: dict[str, dict] = {}

        for box in boxes:
            title_node = box.select_one(".h4-tit01")
            title = _clean_text(title_node.get_text(" ", strip=True) if title_node else "")
            if title in self.SECTION_TITLES:
                row = self._parse_section_box(box, title=title, fetched_at=fetched_at)
                if row is not None:
                    rows_by_title[row["title"]] = row
            elif title == "장학금 제도보기":
                row = self._parse_document_box(box, fetched_at=fetched_at)
                if row is not None:
                    rows_by_title[row["title"]] = row

        ordered_titles = [*self.SECTION_TITLES, "공식 장학 문서"]
        return [rows_by_title[title] for title in ordered_titles if title in rows_by_title]

    def _parse_section_box(self, box, *, title: str, fetched_at: str) -> dict | None:
        summary = self._section_summary(box, title=title)
        if not summary:
            return None

        steps: list[str] = []
        for table in box.select("table"):
            steps.extend(_extract_table_steps(table))
        for note in box.select(".ul-type-dot li, .ul-type-normal li, .alert-txt"):
            normalized = _normalize_note_text(note.get_text(" ", strip=True))
            if normalized and normalized not in steps and normalized not in summary:
                steps.append(normalized)

        return {
            "title": title,
            "summary": summary,
            "steps": _unique(steps),
            "links": [],
            "source_url": self.url,
            "source_tag": "cuk_scholarship_guides",
            "last_synced_at": fetched_at,
        }

    def _parse_document_box(self, box, *, fetched_at: str) -> dict | None:
        links = _extract_link_items(box, base_url=self.url)
        if not links:
            return None
        return {
            "title": "공식 장학 문서",
            "summary": "장학금 지급 규정과 신입생/재학생 장학제도 공식 문서 링크",
            "steps": [],
            "links": links,
            "source_url": self.url,
            "source_tag": "cuk_scholarship_guides",
            "last_synced_at": fetched_at,
        }

    @staticmethod
    def _section_summary(box, *, title: str) -> str:
        if title == "장학생 종류":
            caption = box.select_one("table caption span")
            return _clean_text(caption.get_text(" ", strip=True) if caption else "")

        summary_node = box.select_one(".con-p")
        if summary_node is None:
            return ""
        if title == "장학금 신청":
            return _clean_text(summary_node.get_text(" ", strip=True))
        return _clean_text(summary_node.get_text(" ", strip=True))


class WifiGuideSource:
    """Official static wifi-guide parser for Songsim campus."""

    def __init__(self, url: str):
        self.url = url

    def fetch(self) -> str:
        response = httpx.get(self.url, timeout=20)
        response.raise_for_status()
        return response.text

    def parse(self, html: str, *, fetched_at: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        root = soup.select_one(".content-box") or soup
        table = root.select_one("table")
        if table is None:
            return []

        rows: list[dict] = []
        shared_steps: list[str] = []
        for tr in table.select("tr"):
            cells = tr.find_all(["th", "td"], recursive=False)
            if len(cells) < 2:
                continue

            building_name = _clean_text(cells[0].get_text(" ", strip=True))
            if not building_name or building_name == "건물명":
                continue

            ssids = _split_csv_items(cells[1].get_text(" ", strip=True))
            if not ssids:
                continue

            steps = self._extract_steps(cells[2]) if len(cells) > 2 else []
            if steps:
                shared_steps = steps
            elif shared_steps:
                steps = list(shared_steps)

            rows.append(
                {
                    "building_name": building_name,
                    "ssids": ssids,
                    "steps": steps,
                    "source_url": self.url,
                    "source_tag": "cuk_wifi_guides",
                    "last_synced_at": fetched_at,
                }
            )
        return rows

    @staticmethod
    def _extract_steps(cell) -> list[str]:
        steps = [
            _normalize_note_text(item.get_text(" ", strip=True))
            for item in cell.select("li")
            if _normalize_note_text(item.get_text(" ", strip=True))
        ]
        if steps:
            return _unique(steps)
        fallback = _normalize_note_text(cell.get_text(" ", strip=True))
        return [fallback] if fallback else []


class AcademicSupportGuideSource:
    """Normalize the 학사지원 업무안내 table into guide rows."""

    def __init__(self, url: str):
        self.url = url

    def fetch(self) -> str:
        response = httpx.get(self.url, timeout=10)
        response.raise_for_status()
        return response.text

    def parse(self, html: str, *, fetched_at: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        table = next(
            (
                candidate
                for candidate in soup.select("table")
                if candidate.select_one("caption strong")
                and "업무안내표" in candidate.select_one("caption strong").get_text()
            ),
            None,
        )
        if table is None:
            return []

        rows: list[dict] = []
        parent_title = ""
        for row in table.select("tbody tr"):
            cells = row.find_all("td")
            if len(cells) < 3:
                continue

            if len(cells) >= 4:
                parent_title = _clean_text(cells[0].get_text(" ", strip=True))
                primary = parent_title
                secondary = _clean_text(cells[1].get_text(" ", strip=True))
                task_cell = cells[2]
                contact_cell = cells[3]
            else:
                primary = _clean_text(cells[0].get_text(" ", strip=True))
                secondary = ""
                if cells[0].get("colspan") == "2":
                    parent_title = ""
                elif parent_title:
                    secondary = primary
                    primary = parent_title
                task_cell = cells[-2]
                contact_cell = cells[-1]

            title = " / ".join(part for part in (primary, secondary) if part)
            if not title:
                continue

            steps = _extract_list_or_text(task_cell)
            rows.append(
                {
                    "title": title,
                    "summary": steps[0] if steps else "",
                    "steps": steps,
                    "contacts": _clean_contact_cell(contact_cell),
                    "source_url": self.url,
                    "source_tag": "cuk_academic_support_guides",
                    "last_synced_at": fetched_at,
                }
            )
        return rows


def _clean_contact_cell(cell) -> list[str]:
    parts: list[str] = []
    for line in cell.get_text("\n", strip=True).splitlines():
        cleaned = _clean_text(line)
        if cleaned:
            parts.append(cleaned)
    return parts


def _normalize_phone(value: str | None) -> str | None:
    if not value:
        return None
    normalized = _clean_text(value)
    if normalized in {"-", ""}:
        return None
    return normalized


def _extract_list_or_text(cell) -> list[str]:
    items = [
        _clean_text(li.get_text(" ", strip=True))
        for li in cell.select("li")
        if _clean_text(li.get_text(" ", strip=True))
    ]
    if items:
        return items
    fallback = _clean_text(cell.get_text(" ", strip=True))
    return [fallback] if fallback else []


class AcademicCalendarSource:
    """Official academic calendar parser backed by the public JSON feed."""

    def __init__(self, url: str, site_id: str = "ko"):
        self.url = url
        self.site_id = site_id

    def fetch_range(self, *, start_date: str, end_date: str) -> str:
        response = httpx.get(
            self.url,
            params={
                "mode": "getCalendarData",
                "siteId": self.site_id,
                "start": start_date,
                "end": end_date,
            },
            timeout=20,
        )
        response.raise_for_status()
        return response.text

    def parse(self, payload: str, *, fetched_at: str) -> list[dict]:
        data = json.loads(payload)
        rows: list[dict] = []
        for item in data.get("data", []):
            title = _clean_text(item.get("content"))
            start_date = _date_from_epoch_millis(item.get("beginDt"))
            end_date = _date_from_epoch_millis(item.get("endDt")) or start_date
            if not title or start_date is None or end_date is None:
                continue
            campuses = _unique(
                [_clean_text(part) for part in str(item.get("campus") or "").split(",")]
            )
            rows.append(
                {
                    "academic_year": _academic_year_from_date_string(start_date),
                    "title": title,
                    "start_date": start_date,
                    "end_date": end_date,
                    "campuses": campuses,
                    "source_url": self.url,
                    "source_tag": "cuk_academic_calendar",
                    "last_synced_at": fetched_at,
                }
            )
        return rows


class NoticeSource:
    """Official notice board list/detail parser."""

    def __init__(self, url: str):
        self.url = url

    def fetch_list(self, *, offset: int = 0, limit: int = 10) -> str:
        response = httpx.get(
            self.url,
            params={"mode": "list", "article.offset": offset, "articleLimit": limit},
            timeout=20,
        )
        response.raise_for_status()
        return response.text

    def fetch_detail(self, article_no: str, *, offset: int = 0, limit: int = 10) -> str:
        response = httpx.get(
            self.url,
            params={
                "mode": "view",
                "articleNo": article_no,
                "article.offset": offset,
                "articleLimit": limit,
            },
            timeout=20,
        )
        response.raise_for_status()
        return response.text

    def parse_list(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        items: list[dict] = []
        for row in soup.select("tbody tr"):
            anchor = row.select_one("a.b-title")
            if not anchor:
                continue
            columns = row.find_all("td", recursive=False)
            fallback_category = row.select_one(".b-cate")
            board_category = (
                _clean_text(columns[1].get_text())
                if len(columns) > 1
                else _clean_text(fallback_category.get_text() if fallback_category else "")
            )
            published_at = None
            if len(columns) >= 4:
                published_at = self._normalize_date(columns[-3].get_text())
            if not published_at:
                date_node = row.select_one(".b-date")
                published_at = self._normalize_date(date_node.get_text() if date_node else "")
            href = anchor.get("href", "")
            items.append(
                {
                    "article_no": anchor.get("data-article-no") or self._extract_article_no(href),
                    "title": _clean_text(anchor.get_text()),
                    "board_category": board_category,
                    "published_at": published_at,
                    "source_url": urljoin(self.url, unescape(href)),
                }
            )
        return items

    def parse_detail(
        self,
        html: str,
        *,
        default_title: str = "",
        default_category: str = "",
    ) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        title = _clean_text(
            soup.select_one(".b-title-box .b-title").get_text()
            if soup.select_one(".b-title-box .b-title")
            else default_title
        )
        detail_board_category = _clean_text(
            soup.select_one(".b-title-box .b-cate").get_text()
            if soup.select_one(".b-title-box .b-cate")
            else default_category
        )
        board_category = (
            default_category
            if default_category and detail_board_category in GENERIC_NOTICE_DETAIL_LABELS
            else detail_board_category or default_category
        )
        published_at = self._normalize_date(
            self._extract_meta_value(soup, label="등록일") or ""
        )
        body_root = soup.select_one(".b-content-box .b-con-box")
        body_text = _clean_text(body_root.get_text(" ", strip=True) if body_root else "")
        summary = body_text[:180].strip()
        return {
            "title": title or default_title,
            "published_at": published_at,
            "summary": summary,
            "labels": _unique([board_category] if board_category else []),
            "category": classify_notice_category(
                title or default_title,
                body_text,
                board_category or default_category,
            ),
        }

    @staticmethod
    def _extract_meta_value(soup: BeautifulSoup, *, label: str) -> str | None:
        for item in soup.select(".b-etc-box li"):
            title = item.select_one(".title")
            value = item.find_all("span")
            if not title or len(value) < 2:
                continue
            if label in title.get_text():
                return value[-1].get_text(strip=True)
        return None

    @staticmethod
    def _extract_article_no(href: str) -> str | None:
        match = re.search(r"articleNo=([^&]+)", href)
        return match.group(1) if match else None

    @staticmethod
    def _normalize_date(value: str) -> str | None:
        match = re.search(r"(\d{4})[./-]\s*(\d{2})[./-]\s*(\d{2})", value)
        if not match:
            return None
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
