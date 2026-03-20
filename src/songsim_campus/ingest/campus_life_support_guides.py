from __future__ import annotations

import re
from html import unescape
from urllib.parse import unquote, urljoin

import httpx
from bs4 import BeautifulSoup

WHITESPACE_PATTERN = re.compile(r"\s+")


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    text = BeautifulSoup(unescape(value), "html.parser").get_text(" ", strip=True)
    return WHITESPACE_PATTERN.sub(" ", text).strip()


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = _clean_text(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _collect_text_lines(root, *, skip_exact: set[str] | None = None) -> list[str]:
    skip_exact = skip_exact or set()
    text = root.get_text("\n", strip=True)
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = _clean_text(raw_line)
        if not line:
            continue
        if line in skip_exact:
            continue
        if line.startswith("Image:"):
            continue
        lines.append(line)
    return lines


def _pair_label_value_lines(lines: list[str]) -> list[str]:
    paired: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.rstrip(":").strip()
        if line.endswith(":") and index + 1 < len(lines):
            value = lines[index + 1]
            if value and not value.endswith(":"):
                paired.append(f"{stripped}: {value}")
                index += 2
                continue
        paired.append(line)
        index += 1
    return _unique(paired)


def _extract_links(root, *, base_url: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for anchor in root.select("a[href]"):
        label = _clean_text(anchor.get_text(" ", strip=True))
        href = unquote(unescape(str(anchor.get("href") or "")).strip())
        if not label or not href or href.startswith("javascript:"):
            continue
        items.append({"label": label, "url": urljoin(base_url, href)})
    return _dedupe_link_items(items)


def _dedupe_link_items(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, str]] = []
    for item in items:
        key = (item["label"], item["url"])
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _extract_table_rows(table) -> list[str]:
    rows: list[str] = []
    header_cells = [
        _clean_text(cell.get_text(" ", strip=True))
        for cell in table.select_one("thead tr").find_all(["th", "td"], recursive=False)
    ] if table.select_one("thead tr") else []

    for tr in table.select("tbody tr"):
        cells = [
            _clean_text(cell.get_text(" ", strip=True))
            for cell in tr.find_all(["th", "td"], recursive=False)
        ]
        if not cells:
            continue
        if header_cells and len(header_cells) == len(cells):
            parts = [
                f"{header}: {cell}"
                for header, cell in zip(header_cells, cells, strict=False)
                if header and cell
            ]
            if parts:
                rows.append(" / ".join(parts))
                continue
        rows.append(" / ".join(cell for cell in cells if cell))
    return _unique(rows)


def _extract_section_steps(
    section,
    *,
    title: str | None = None,
    extra_skip: set[str] | None = None,
) -> list[str]:
    skip_exact = set(extra_skip or set())
    if title:
        skip_exact.add(title)
    lines = _collect_text_lines(section, skip_exact=skip_exact)
    steps = _pair_label_value_lines(lines)
    for table in section.select("table"):
        steps.extend(_extract_table_rows(table))
    return _unique(steps)


def _find_con_box_by_h4_title(root, title: str):
    target = _clean_text(title)
    for section in root.find_all("div", class_="con-box", recursive=False):
        heading = section.select_one(".h4-tit01")
        if heading and _clean_text(heading.get_text(" ", strip=True)) == target:
            return section
    return None


def _extract_hospital_links(root, *, base_url: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for anchor in root.select("a[href]"):
        label = _clean_text(anchor.get_text(" ", strip=True))
        href = unquote(unescape(str(anchor.get("href") or "")).strip())
        if not label or not href:
            continue
        if not re.search(r"/hospital[2-9]\.do$", href):
            continue
        items.append({"label": label, "url": urljoin(base_url, href)})
    return _dedupe_link_items(items)


class CampusLifeSupportGuideSourceBase:
    source_tag = "cuk_campus_life_support_guides"
    topic = ""

    def __init__(self, url: str):
        self.url = url

    def fetch(self) -> str:
        response = httpx.get(self.url, timeout=20, follow_redirects=True)
        response.raise_for_status()
        return response.text


class StudentCounselingGuideSource(CampusLifeSupportGuideSourceBase):
    topic = "student_counseling"

    def __init__(self, url: str = "https://www.catholic.ac.kr/ko/campuslife/counsel.do"):
        super().__init__(url)

    def parse(self, html: str, *, fetched_at: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        root = soup.select_one(".content-box") or soup
        rows: list[dict] = []
        for thumb in root.select(".thumb-box"):
            title_node = thumb.select_one(".box-tit")
            title = _clean_text(title_node.get_text(" ", strip=True) if title_node else "")
            if not title:
                continue
            steps = _extract_section_steps(thumb, title=title, extra_skip={"홈페이지 바로가기"})
            rows.append(
                {
                    "topic": self.topic,
                    "title": title,
                    "summary": steps[0] if steps else title,
                    "steps": steps,
                    "links": _extract_links(thumb, base_url=self.url),
                    "source_url": self.url,
                    "source_tag": self.source_tag,
                    "last_synced_at": fetched_at,
                }
            )
        return rows


class DisabilitySupportGuideSource(CampusLifeSupportGuideSourceBase):
    topic = "disability_support"

    def __init__(self, url: str = "https://www.catholic.ac.kr/ko/campuslife/disability_service.do"):
        super().__init__(url)

    def parse(self, html: str, *, fetched_at: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        root = soup.select_one(".content-box") or soup
        rows: list[dict] = []
        title = "장애학생지원센터"
        steps: list[str] = []
        links: list[dict[str, str]] = []
        for index, box in enumerate(root.find_all("div", class_="con-box", recursive=False)):
            section_title_node = box.select_one(".h4-tit01") or box.select_one(".box-tit")
            section_title = _clean_text(
                section_title_node.get_text(" ", strip=True) if section_title_node else ""
            )
            if not section_title:
                continue
            if index == 0:
                title = section_title
                links = _extract_links(box, base_url=self.url)
            elif section_title != title:
                steps.append(section_title)
            steps.extend(
                _extract_section_steps(
                    box,
                    title=section_title,
                    extra_skip={"홈페이지 바로가기"},
                )
            )
        steps = _unique(steps)
        summary = next(
            (step for step in steps if step.startswith("장애학생지원센터에서는")),
            steps[0] if steps else title,
        )
        rows.append(
            {
                "topic": self.topic,
                "title": title,
                "summary": summary,
                "steps": steps,
                "links": links,
                "source_url": self.url,
                "source_tag": self.source_tag,
                "last_synced_at": fetched_at,
            }
        )
        return rows


class StudentReservistGuideSource(CampusLifeSupportGuideSourceBase):
    topic = "student_reservist"

    def __init__(self, url: str = "https://www.catholic.ac.kr/ko/campuslife/student_reservist.do"):
        super().__init__(url)

    def parse(self, html: str, *, fetched_at: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        root = soup.select_one(".content-box") or soup
        rows: list[dict] = []
        title = "직장예비군 가톨릭대학교 대대"
        steps: list[str] = []
        links: list[dict[str, str]] = []
        for index, box in enumerate(root.find_all("div", class_="con-box", recursive=False)):
            section_title_node = box.select_one(".h4-tit01") or box.select_one(".box-tit")
            section_title = _clean_text(
                section_title_node.get_text(" ", strip=True) if section_title_node else ""
            )
            if not section_title:
                continue
            if index == 0:
                title = section_title
                links = _extract_links(box, base_url=self.url)
            elif section_title != title:
                steps.append(section_title)
            steps.extend(
                _extract_section_steps(
                    box,
                    title=section_title,
                    extra_skip={"예비군대대 홈페이지 바로가기", "홈페이지 바로가기"},
                )
            )
        steps = _unique(steps)
        rows.append(
            {
                "topic": self.topic,
                "title": "직장예비군 가톨릭대학교 대대",
                "summary": title,
                "steps": steps,
                "links": links,
                "source_url": self.url,
                "source_tag": self.source_tag,
                "last_synced_at": fetched_at,
            }
        )
        return rows


class HospitalUseGuideSource(CampusLifeSupportGuideSourceBase):
    topic = "hospital_use"

    def __init__(self, url: str = "https://www.catholic.ac.kr/ko/campuslife/hospital1.do"):
        super().__init__(url)

    def parse(self, html: str, *, fetched_at: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        root = soup.select_one(".content-box") or soup
        thumb = root.select_one(".thumb-box") or root
        steps = _extract_section_steps(
            thumb,
            title="가톨릭중앙의료원",
            extra_skip={"병원아이콘", "홈페이지 바로가기"},
        )
        steps = [
            step.replace("병원아이콘 ", "", 1) if step.startswith("병원아이콘 ") else step
            for step in steps
        ]
        rows = [
            {
                "topic": self.topic,
                "title": "부속병원이용",
                "summary": steps[0] if steps else "부속병원이용",
                "steps": steps,
                "links": _extract_hospital_links(root, base_url=self.url),
                "source_url": self.url,
                "source_tag": self.source_tag,
                "last_synced_at": fetched_at,
            }
        ]
        return rows


class HealthCenterGuideSource(CampusLifeSupportGuideSourceBase):
    topic = "health_center"

    def __init__(self, url: str = "https://www.catholic.ac.kr/ko/campuslife/health.do"):
        super().__init__(url)

    def parse(self, html: str, *, fetched_at: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        root = (
            soup.select_one(".content-box.conv.health")
            or soup.select_one(".content-box")
            or soup
        )
        sections = root.find_all("div", class_="con-box", recursive=False) or [root]

        steps: list[str] = []
        links: list[dict[str, str]] = []
        title = "보건실"

        for index, section in enumerate(sections):
            section_title_node = section.select_one(".box-tit") or section.select_one(".h4-tit01")
            section_title = _clean_text(
                section_title_node.get_text(" ", strip=True) if section_title_node else ""
            )
            if index == 0 and section_title:
                title = section_title
            section_steps = _extract_section_steps(section, title=section_title or None)
            if section_title and section_title != title:
                steps.append(section_title)
            steps.extend(section_steps)
            links.extend(_extract_links(section, base_url=self.url))

        steps = _unique(steps)
        summary = next(
            (step for step in steps if "학생과 교직원의 건강" in step),
            steps[0] if steps else title,
        )
        return [
            {
                "topic": self.topic,
                "title": title,
                "summary": summary,
                "steps": steps,
                "links": links,
                "source_url": self.url,
                "source_tag": self.source_tag,
                "last_synced_at": fetched_at,
            }
        ]


class LostFoundGuideSource(CampusLifeSupportGuideSourceBase):
    topic = "lost_found"

    def __init__(self, url: str = "https://www.catholic.ac.kr/ko/campuslife/find.do"):
        super().__init__(url)

    def parse(self, html: str, *, fetched_at: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        root = (
            soup.select_one(".sub-content.cms-sub-content .border-box.mg-b40")
            or soup.select_one(".border-box.mg-b40")
            or soup
        )
        title = "유실물 찾기"
        steps = _extract_section_steps(root, title=title, extra_skip={"NOTICE"})
        summary = steps[0] if steps else title
        return [
            {
                "topic": self.topic,
                "title": title,
                "summary": summary,
                "steps": steps,
                "links": _extract_links(root, base_url=self.url),
                "source_url": self.url,
                "source_tag": self.source_tag,
                "last_synced_at": fetched_at,
            }
        ]


class ParkingGuideSource(CampusLifeSupportGuideSourceBase):
    topic = "parking"

    def __init__(self, url: str = "https://www.catholic.ac.kr/ko/about/location_songsim.do"):
        super().__init__(url)

    def parse(self, html: str, *, fetched_at: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        root = soup.select_one(".content-box") or soup
        section = _find_con_box_by_h4_title(root, "주차요금안내") or root

        steps: list[str] = []
        title = "주차요금안내"

        section_title_node = section.select_one(".h4-tit01") or section.select_one(".box-tit")
        section_title = _clean_text(
            section_title_node.get_text(" ", strip=True) if section_title_node else ""
        )
        if section_title:
            title = section_title

        for sub_section in section.select(".con-box02"):
            sub_title_node = (
                sub_section.select_one(".h5-tit01")
                or sub_section.select_one(".h6-tit01")
                or sub_section.select_one(".box-tit")
            )
            sub_title = _clean_text(
                sub_title_node.get_text(" ", strip=True) if sub_title_node else ""
            )
            section_steps = _extract_section_steps(
                sub_section,
                title=sub_title or None,
            )
            if sub_title:
                steps.append(sub_title)
            steps.extend(section_steps)

        for alert in section.select(".alert-txt"):
            steps.append(_clean_text(alert.get_text(" ", strip=True)))

        steps = _unique(steps)
        summary = next(
            (step for step in steps if "교직원, 학생(학부, 대학원생)" in step),
            steps[0] if steps else title,
        )
        return [
            {
                "topic": self.topic,
                "title": title,
                "summary": summary,
                "steps": steps,
                "links": _extract_links(section, base_url=self.url),
                "source_url": self.url,
                "source_tag": self.source_tag,
                "last_synced_at": fetched_at,
            }
        ]
