from __future__ import annotations

import pytest

from songsim_campus.db import connection, init_db
from songsim_campus.ingest.kakao_places import KakaoPlace
from songsim_campus.repo import replace_places
from songsim_campus.seed import seed_demo
from songsim_campus.services import (
    NotFoundError,
    find_nearby_restaurants,
    get_class_periods,
    get_place,
    list_latest_notices,
    list_transport_guides,
    refresh_courses_from_subject_search,
    refresh_facility_hours_from_facilities_page,
    refresh_library_hours_from_library_page,
    refresh_notices_from_notice_board,
    refresh_places_from_campus_map,
    refresh_transport_guides_from_location_page,
    search_courses,
    search_places,
    sync_official_snapshot,
)


def test_get_class_periods_returns_ten_periods(app_env):
    init_db()
    seed_demo(force=True)
    periods = get_class_periods()
    assert len(periods) == 10
    assert periods[0].start == '09:00'
    assert periods[-1].end == '18:50'


def test_search_places_matches_alias(app_env):
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        places = search_places(conn, query='중도')
    assert any(item.name == '중앙도서관' for item in places)


def test_find_nearby_restaurants_sorted(app_env):
    init_db()
    seed_demo(force=True)
    with connection() as conn:
        items = find_nearby_restaurants(conn, origin='central-library', walk_minutes=20)
    assert items
    walk_minutes = [item.estimated_walk_minutes for item in items]
    assert walk_minutes == sorted(walk_minutes)


def test_find_nearby_restaurants_raises_for_unknown_origin(app_env):
    init_db()
    seed_demo(force=True)

    with connection() as conn, pytest.raises(NotFoundError):
        find_nearby_restaurants(conn, origin='unknown-place')


def test_find_nearby_restaurants_raises_when_origin_has_no_coordinates(app_env):
    init_db()
    with connection() as conn:
        replace_places(
            conn,
            [
                {
                    "slug": "mystery-hall",
                    "name": "미스터리관",
                    "category": "building",
                    "aliases": [],
                    "description": "",
                    "latitude": None,
                    "longitude": None,
                    "opening_hours": {},
                    "source_tag": "test",
                    "last_synced_at": "2026-03-13T09:00:00+09:00",
                }
            ],
        )

    with connection() as conn, pytest.raises(NotFoundError):
        find_nearby_restaurants(conn, origin='mystery-hall')


class FakeKakaoClient:
    def search_sync(
        self,
        query: str,
        *,
        x: float | None = None,
        y: float | None = None,
        radius: int = 1000,
    ):
        assert query == '한식'
        assert x is not None and y is not None
        assert radius > 0
        return [
            KakaoPlace(
                name='가톨릭백반',
                category='음식점 > 한식',
                address='경기 부천시 원미구',
                latitude=37.48674,
                longitude=126.80182,
                place_url='https://place.map.kakao.com/1',
            ),
            KakaoPlace(
                name='성심돈까스',
                category='음식점 > 한식',
                address='경기 부천시 원미구',
                latitude=37.48691,
                longitude=126.80114,
                place_url='https://place.map.kakao.com/2',
            ),
        ]


def test_find_nearby_restaurants_can_use_kakao_live_results(app_env):
    init_db()
    seed_demo(force=True)

    with connection() as conn:
        items = find_nearby_restaurants(
            conn,
            origin='central-library',
            category='korean',
            walk_minutes=15,
            kakao_client=FakeKakaoClient(),
        )

    assert [item.name for item in items] == ['가톨릭백반', '성심돈까스']
    assert all(item.source_tag == 'kakao_local' for item in items)
    assert all(item.origin == 'central-library' for item in items)


class FakeCampusMapSource:
    def fetch_place_list(self, *, campus: str = '1'):
        assert campus == '1'
        return 'payload'

    def parse_place_list(self, payload: str, *, fetched_at: str):
        assert payload == 'payload'
        assert fetched_at == '2026-03-13T09:00:00+09:00'
        return [
            {
                'slug': 'central-library',
                'name': '중앙도서관',
                'category': 'library',
                'aliases': ['도서관'],
                'description': '실제 캠퍼스맵 데이터',
                'latitude': 37.486853,
                'longitude': 126.799802,
                'opening_hours': {},
                'source_tag': 'cuk_campus_map',
                'last_synced_at': fetched_at,
            }
        ]


class FakeCourseSource:
    def fetch(
        self,
        *,
        year: int,
        semester: int,
        department: str = 'ALL',
        completion_type: str = 'ALL',
        query: str = '',
    ):
        assert (year, semester, department, completion_type, query) == (2026, 1, 'ALL', 'ALL', '')
        return '<html></html>'

    def parse(self, html: str, *, fetched_at: str):
        assert html == '<html></html>'
        assert fetched_at == '2026-03-13T09:00:00+09:00'
        return [
            {
                'year': 2026,
                'semester': 1,
                'code': '03149',
                'title': '자료구조',
                'professor': '박정흠',
                'department': '컴퓨터정보공학부',
                'section': '01',
                'day_of_week': '화',
                'period_start': 2,
                'period_end': 3,
                'room': 'BA203',
                'raw_schedule': '화2~3(BA203)',
                'source_tag': 'cuk_subject_search',
                'last_synced_at': fetched_at,
            }
        ]


class FakeNoticeSource:
    def fetch_list(self, *, offset: int = 0, limit: int = 10):
        assert offset == 0
        assert limit == 10
        return '<list></list>'

    def parse_list(self, html: str):
        assert html == '<list></list>'
        return [
            {
                'article_no': '1001',
                'title': '2026학년도 1학기 가족장학금 신청 안내',
                'board_category': '장학',
                'published_at': '2026-03-12',
                'source_url': 'https://example.edu/notice/1001',
            }
        ]

    def fetch_detail(self, article_no: str, *, offset: int = 0, limit: int = 10):
        assert article_no == '1001'
        return '<detail></detail>'

    def parse_detail(self, html: str, *, default_title: str = '', default_category: str = ''):
        assert html == '<detail></detail>'
        assert default_title == '2026학년도 1학기 가족장학금 신청 안내'
        assert default_category == '장학'
        return {
            'title': default_title,
            'published_at': '2026-03-12',
            'summary': '가족장학금 신청 안내',
            'labels': ['장학'],
            'category': 'scholarship',
        }


def test_refresh_places_from_campus_map_replaces_place_rows(app_env):
    init_db()

    with connection() as conn:
        refresh_places_from_campus_map(
            conn,
            source=FakeCampusMapSource(),
            fetched_at='2026-03-13T09:00:00+09:00',
        )
        places = search_places(conn, query='중앙')

    assert len(places) == 1
    assert places[0].source_tag == 'cuk_campus_map'


def test_refresh_courses_from_subject_search_replaces_course_rows(app_env):
    init_db()

    with connection() as conn:
        refresh_courses_from_subject_search(
            conn,
            source=FakeCourseSource(),
            year=2026,
            semester=1,
            fetched_at='2026-03-13T09:00:00+09:00',
        )
        courses = search_courses(conn, query='자료')

    assert len(courses) == 1
    assert courses[0].source_tag == 'cuk_subject_search'


def test_refresh_notices_from_notice_board_replaces_notice_rows(app_env):
    init_db()

    with connection() as conn:
        refresh_notices_from_notice_board(
            conn,
            source=FakeNoticeSource(),
            pages=1,
            fetched_at='2026-03-13T09:00:00+09:00',
        )
        notices = list_latest_notices(conn)

    assert len(notices) == 1
    assert notices[0].category == 'scholarship'
    assert notices[0].source_tag == 'cuk_campus_notices'


class FakeLibraryHoursSource:
    def fetch(self):
        return '<library></library>'

    def parse(self, html: str, *, fetched_at: str):
        assert html == '<library></library>'
        assert fetched_at == '2026-03-13T09:00:00+09:00'
        return [
            {
                'place_name': '중앙도서관',
                'opening_hours': {
                    '대출반납실': '학기중 평일 09:00-21:00 / 토요일 09:00-13:00',
                },
                'source_tag': 'cuk_library_hours',
                'last_synced_at': fetched_at,
            }
        ]


class FakeFacilitiesSource:
    def fetch(self):
        return '<facilities></facilities>'

    def parse(self, html: str, *, fetched_at: str):
        assert html == '<facilities></facilities>'
        assert fetched_at == '2026-03-13T09:00:00+09:00'
        return [
            {
                'facility_name': '카페드림',
                'location': '중앙도서관 2층',
                'hours_text': '평일 08:00~19:00 토 10:00~16:00 (일/공휴일휴무)',
                'category': '카페',
                'source_tag': 'cuk_facilities',
                'last_synced_at': fetched_at,
            },
            {
                'facility_name': '매머드커피',
                'location': 'K관 1층',
                'hours_text': '평일 08:00~20:00 주말,공휴일 09:00~17:00',
                'category': '카페',
                'source_tag': 'cuk_facilities',
                'last_synced_at': fetched_at,
            },
            {
                'facility_name': '없는시설',
                'location': '없는관 1층',
                'hours_text': '상시 09:00~18:00',
                'category': '편의점',
                'source_tag': 'cuk_facilities',
                'last_synced_at': fetched_at,
            },
        ]


class FakeTransportSource:
    def fetch(self):
        return '<transport></transport>'

    def parse(self, html: str, *, fetched_at: str):
        assert html == '<transport></transport>'
        assert fetched_at == '2026-03-13T09:00:00+09:00'
        return [
            {
                'mode': 'subway',
                'title': '1호선',
                'summary': '역곡역 2번 출구 또는 소사역 3번 출구에서 도보 10분',
                'steps': ['인천역 ↔ 역곡역 : 35분 소요'],
                'source_url': 'https://www.catholic.ac.kr/ko/about/location_songsim.do',
                'source_tag': 'cuk_transport',
                'last_synced_at': fetched_at,
            }
        ]


def test_refresh_library_hours_merges_opening_hours_into_existing_place(app_env):
    init_db()
    seed_demo(force=True)

    with connection() as conn:
        refresh_library_hours_from_library_page(
            conn,
            source=FakeLibraryHoursSource(),
            fetched_at='2026-03-13T09:00:00+09:00',
        )
        place = get_place(conn, 'central-library')

    assert place.source_tag == 'demo'
    assert place.opening_hours['대출반납실'] == '학기중 평일 09:00-21:00 / 토요일 09:00-13:00'


def test_refresh_facility_hours_merges_by_location_and_skips_unknown_places(app_env):
    init_db()
    seed_demo(force=True)

    with connection() as conn:
        places = refresh_facility_hours_from_facilities_page(
            conn,
            source=FakeFacilitiesSource(),
            fetched_at='2026-03-13T09:00:00+09:00',
        )
        library = get_place(conn, 'central-library')
        hall = get_place(conn, 'kim-soo-hwan-hall')

    assert sorted(item.slug for item in places) == ['central-library', 'kim-soo-hwan-hall']
    assert library.opening_hours['카페드림'] == '평일 08:00~19:00 토 10:00~16:00 (일/공휴일휴무)'
    assert hall.opening_hours['매머드커피'] == '평일 08:00~20:00 주말,공휴일 09:00~17:00'
    assert '없는시설' not in library.opening_hours


def test_refresh_transport_guides_replaces_rows(app_env):
    init_db()

    with connection() as conn:
        refresh_transport_guides_from_location_page(
            conn,
            source=FakeTransportSource(),
            fetched_at='2026-03-13T09:00:00+09:00',
        )
        guides = list_transport_guides(conn)

    assert len(guides) == 1
    assert guides[0].mode == 'subway'
    assert guides[0].title == '1호선'
    assert guides[0].source_tag == 'cuk_transport'


def test_sync_official_snapshot_runs_opening_hours_before_courses_and_transport(
    app_env,
    monkeypatch,
):
    call_order: list[str] = []

    monkeypatch.setattr(
        'songsim_campus.services.refresh_places_from_campus_map',
        lambda conn, campus=None: call_order.append('places') or [],
    )
    monkeypatch.setattr(
        'songsim_campus.services.refresh_library_hours_from_library_page',
        lambda conn: call_order.append('library') or [],
    )
    monkeypatch.setattr(
        'songsim_campus.services.refresh_facility_hours_from_facilities_page',
        lambda conn: call_order.append('facilities') or [],
    )
    monkeypatch.setattr(
        'songsim_campus.services.refresh_courses_from_subject_search',
        lambda conn, year=None, semester=None: call_order.append('courses') or [],
    )
    monkeypatch.setattr(
        'songsim_campus.services.refresh_notices_from_notice_board',
        lambda conn, pages=None: call_order.append('notices') or [],
    )
    monkeypatch.setattr(
        'songsim_campus.services.refresh_transport_guides_from_location_page',
        lambda conn: call_order.append('transport') or [],
    )

    init_db()
    with connection() as conn:
        summary = sync_official_snapshot(conn, year=2026, semester=1, notice_pages=1)

    assert call_order == ['places', 'library', 'facilities', 'courses', 'notices', 'transport']
    assert summary['transport_guides'] == 0
