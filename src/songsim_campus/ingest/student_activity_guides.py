from __future__ import annotations

import re
from html import unescape
from urllib.parse import unquote, urljoin

import httpx
from bs4 import BeautifulSoup

WHITESPACE_PATTERN = re.compile(r"\s+")
IGNORED_LINES = {
    "QUICK MENU",
    "콘텐츠 담당부서",
    "맨위로가기",
}


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


def _dedupe_links(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, str]] = []
    for item in items:
        key = (item["label"], item["url"])
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _extract_links(root, *, base_url: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for anchor in root.select("a[href]"):
        label = _clean_text(anchor.get_text(" ", strip=True))
        href = unquote(unescape(str(anchor.get("href") or "")).strip())
        if not label or not href or href.startswith("javascript:") or href.startswith("#"):
            continue
        items.append({"label": label, "url": urljoin(base_url, href)})
    return _dedupe_links(items)


def _extract_steps(section, *, title: str) -> list[str]:
    clone = BeautifulSoup(str(section), "html.parser")
    for node in clone.select(".link-box, .img-box, img, script, style"):
        node.decompose()

    lines: list[str] = []
    text = clone.get_text("\n", strip=True)
    for raw_line in text.splitlines():
        line = _clean_text(raw_line)
        if not line or line == title or line in IGNORED_LINES:
            continue
        if line.startswith("Image:"):
            continue
        lines.append(line)
    return _unique(lines)


class StudentActivityGuideSourceBase:
    source_tag = "cuk_student_activity_guides"
    topic = ""

    def __init__(self, url: str):
        self.url = url

    def fetch(self) -> str:
        response = httpx.get(self.url, timeout=20, follow_redirects=True)
        response.raise_for_status()
        return response.text


class StudentGovernmentGuideSource(StudentActivityGuideSourceBase):
    topic = "student_government"

    def __init__(
        self,
        url: str = "https://www.catholic.ac.kr/ko/campuslife/student_government.do",
    ):
        super().__init__(url)

    def parse(self, html: str, *, fetched_at: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        root = soup.select_one(".content-box.stu_govm") or soup.select_one(".content-box") or soup
        intro_box = None
        rows: list[dict] = []
        for section in root.find_all("div", class_="con-box", recursive=False):
            heading = section.select_one(".h4-tit01")
            if heading is None:
                if section.select_one(".con-tit"):
                    intro_box = section
                continue

            title = _clean_text(heading.get_text(" ", strip=True))
            steps: list[str] = []
            links: list[dict[str, str]] = []
            if title == "조직구성" and intro_box is not None:
                intro_title = _clean_text(
                    intro_box.select_one(".con-tit").get_text(" ", strip=True)
                )
                if intro_title:
                    steps.append(intro_title)
                links.extend(_extract_links(intro_box, base_url=self.url))
            steps.extend(_extract_steps(section, title=title))
            links.extend(_extract_links(section, base_url=self.url))
            steps = _unique(steps)
            links = _dedupe_links(links)
            rows.append(
                {
                    "topic": self.topic,
                    "title": title,
                    "summary": steps[0] if steps else title,
                    "steps": steps,
                    "links": links,
                    "source_url": self.url,
                    "source_tag": self.source_tag,
                    "last_synced_at": fetched_at,
                }
            )
        return rows


class CampusMediaGuideSource(StudentActivityGuideSourceBase):
    topic = "campus_media"

    def __init__(self, url: str = "https://www.catholic.ac.kr/ko/campuslife/media.do"):
        super().__init__(url)

    def parse(self, html: str, *, fetched_at: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        root = soup.select_one(".content-box") or soup
        rows: list[dict] = []
        for section in root.find_all("div", class_="con-box", recursive=False):
            heading = section.select_one(".h4-tit01")
            if heading is None:
                continue
            title = _clean_text(heading.get_text(" ", strip=True))
            steps = _extract_steps(section, title=title)
            rows.append(
                {
                    "topic": self.topic,
                    "title": title,
                    "summary": steps[0] if steps else title,
                    "steps": steps,
                    "links": _extract_links(section, base_url=self.url),
                    "source_url": self.url,
                    "source_tag": self.source_tag,
                    "last_synced_at": fetched_at,
                }
            )
        return rows


class SocialVolunteeringGuideSource(StudentActivityGuideSourceBase):
    topic = "social_volunteering"

    def __init__(self, url: str = "https://www.catholic.ac.kr/ko/campuslife/volunteer.do"):
        super().__init__(url)

    def parse(self, html: str, *, fetched_at: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        root = soup.select_one(".content-box") or soup
        rows: list[dict] = []
        for section in root.select(".thumb-box .info-box"):
            heading = section.select_one(".h4-tit01")
            if heading is None:
                continue
            title = _clean_text(heading.get_text(" ", strip=True))
            steps = _extract_steps(section, title=title)
            rows.append(
                {
                    "topic": self.topic,
                    "title": title,
                    "summary": steps[0] if steps else title,
                    "steps": steps,
                    "links": _extract_links(section, base_url=self.url),
                    "source_url": self.url,
                    "source_tag": self.source_tag,
                    "last_synced_at": fetched_at,
                }
            )
        return rows


class RotcGuideSource(StudentActivityGuideSourceBase):
    topic = "rotc"

    def __init__(self, url: str = "https://www.catholic.ac.kr/ko/campuslife/rotc.do"):
        super().__init__(url)

    def parse(self, html: str, *, fetched_at: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        root = soup.select_one(".content-box") or soup
        rows: list[dict] = []
        for section in root.select(".thumb-box .info-box"):
            heading = section.select_one(".box-tit") or section.select_one(".h4-tit01")
            if heading is None:
                continue
            title = _clean_text(heading.get_text(" ", strip=True))
            steps = _extract_steps(section, title=title)
            rows.append(
                {
                    "topic": self.topic,
                    "title": title,
                    "summary": steps[0] if steps else title,
                    "steps": steps,
                    "links": _extract_links(section, base_url=self.url),
                    "source_url": self.url,
                    "source_tag": self.source_tag,
                    "last_synced_at": fetched_at,
                }
            )
        return rows
