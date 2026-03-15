from __future__ import annotations

import json
import re
from html import unescape
from urllib.parse import urlencode, urljoin

import httpx
from bs4 import BeautifulSoup

PLACE_LIST_PATTERN = re.compile(r"\?mode=getPlaceListByCondition&campus=\$\{campus\}")
SCHEDULE_PATTERN = re.compile(
    r"^(?P<day>[월화수목금토일])\s*(?P<start>\d+)(?:\s*[~-]\s*(?P<end>\d+))?(?:\((?P<room>[^)]+)\))?$"
)
WHITESPACE_PATTERN = re.compile(r"\s+")


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    text = BeautifulSoup(unescape(value), "html.parser").get_text(" ", strip=True)
    return WHITESPACE_PATTERN.sub(" ", text).strip()


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


class CampusFacilitiesSource:
    """Official campus restaurants and facilities opening-hours parser."""

    def __init__(self, url: str):
        self.url = url

    def fetch(self) -> str:
        response = httpx.get(self.url, timeout=20)
        response.raise_for_status()
        return response.text

    def parse(self, html: str, *, fetched_at: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        rows: list[dict] = []

        for card in soup.select(".content-box.restaurant .box-wrap.card .border-box"):
            title_node = card.select_one(".box-tit span")
            details = _collect_dl_fields(card)
            facility_name = _clean_text(title_node.get_text() if title_node else "")
            location = details.get("위치", "")
            hours_text = details.get("운영시간", "")
            if not facility_name or not location or not hours_text:
                continue
            rows.append(
                {
                    "facility_name": facility_name,
                    "location": location,
                    "hours_text": hours_text,
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
            category, facility_name, _, location, hours_text = row[:5]
            rows.append(
                {
                    "facility_name": facility_name,
                    "location": location,
                    "hours_text": hours_text,
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
