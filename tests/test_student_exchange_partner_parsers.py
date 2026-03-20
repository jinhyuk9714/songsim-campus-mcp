from __future__ import annotations

import json
from pathlib import Path

import pytest

from songsim_campus.ingest.official_sources import StudentExchangePartnerSource

FIXTURES_DIR = Path(__file__).with_name("fixtures")
LANDING_URL = "https://www.catholic.ac.kr/ko/support/exchange_oversea1.do"
LIST_URL = "https://www.catholic.ac.kr/exchangeOverseaVue/getList.do"


def _fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def test_student_exchange_partner_landing_page_has_app_metadata() -> None:
    html = _fixture("exchange_oversea1_app.html")

    assert 'appKey":"exchange-oversea-vue"' in html
    assert 'pageKind":"APP"' in html


def test_student_exchange_partner_fetch_validates_landing_page_before_list_json(
    monkeypatch,
) -> None:
    calls: list[str] = []

    class DummyResponse:
        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self) -> None:
            return None

    def fake_get(url: str, timeout: int = 20, follow_redirects: bool = False):
        calls.append(url)
        if url == LANDING_URL:
            return DummyResponse(_fixture("exchange_oversea1_app.html"))
        if url == LIST_URL:
            return DummyResponse(_fixture("exchangeOverseaVue_getList.json"))
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("songsim_campus.ingest.official_sources.httpx.get", fake_get)

    source = StudentExchangePartnerSource()
    payload = source.fetch()

    assert json.loads(payload)["list"][0]["schNm"] == "National Central University"
    assert calls == [LANDING_URL, LIST_URL]


def test_student_exchange_partner_fetch_rejects_stale_app_landing_page(monkeypatch):
    class DummyResponse:
        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self) -> None:
            return None

    def fake_get(url: str, timeout: int = 20, follow_redirects: bool = False):
        assert url == LANDING_URL
        return DummyResponse("<html><body>legacy page</body></html>")

    monkeypatch.setattr("songsim_campus.ingest.official_sources.httpx.get", fake_get)

    with pytest.raises(ValueError, match="exchange-oversea-vue"):
        StudentExchangePartnerSource().fetch()


def test_student_exchange_partner_parser_normalizes_json_payload() -> None:
    rows = StudentExchangePartnerSource().parse(
        _fixture("exchangeOverseaVue_getList.json"),
        fetched_at="2026-03-20T00:00:00+09:00",
    )

    assert [row["partner_code"] for row in rows] == [
        "00004",
        "00122",
        "00173",
        "00198",
    ]

    ncu = next(row for row in rows if row["university_name"] == "National Central University")
    assert ncu["country_ko"] == "대만"
    assert ncu["country_en"] == "TAIWAN, PROVINCE OF CHINA"
    assert ncu["continent"] == "ASIA"
    assert ncu["location"] == "Taoyuan"
    assert ncu["agreement_date"] == "2008-07-23"
    assert ncu["homepage_url"] == "http://www.ncu.edu.tw"
    assert ncu["source_url"] == LANDING_URL
    assert ncu["source_tag"] == "cuk_student_exchange_partners"

    utrecht = next(row for row in rows if row["university_name"] == "Utrecht University")
    assert utrecht["homepage_url"] is None
    assert utrecht["location"] is None
    assert utrecht["agreement_date"] is None

    greece = next(
        row for row in rows if row["university_name"] == "The American College of Greece"
    )
    assert greece["continent"] == "EUROPE"
    assert greece["country_ko"] == "그리스"

