from __future__ import annotations

from songsim_campus.db import connection
from songsim_campus.services import (
    refresh_facility_hours_from_facilities_page,
    refresh_transport_guides_from_location_page,
)


def test_healthz(client):
    response = client.get('/healthz')
    assert response.status_code == 200
    assert response.json() == {'ok': True}


def test_places_query_returns_library(client):
    response = client.get('/places', params={'query': '도서관'})
    assert response.status_code == 200
    names = [item['name'] for item in response.json()]
    assert '중앙도서관' in names


def test_courses_query_returns_expected_course(client):
    response = client.get('/courses', params={'query': '객체지향', 'year': 2026, 'semester': 1})
    assert response.status_code == 200
    items = response.json()
    assert items
    assert items[0]['title'] == '객체지향프로그래밍설계'


def test_nearby_restaurants_uses_origin(client):
    response = client.get(
        '/restaurants/nearby',
        params={'origin': 'central-library', 'budget_max': 10000, 'walk_minutes': 15},
    )
    assert response.status_code == 200
    items = response.json()
    assert items
    assert all(item['estimated_walk_minutes'] <= 15 for item in items)


def test_place_detail_returns_404_for_missing_place(client):
    response = client.get('/places/does-not-exist')

    assert response.status_code == 404


def test_nearby_restaurants_returns_404_for_missing_origin(client):
    response = client.get('/restaurants/nearby', params={'origin': 'does-not-exist'})

    assert response.status_code == 404


class ApiFacilitiesSource:
    def fetch(self):
        return '<facilities></facilities>'

    def parse(self, html: str, *, fetched_at: str):
        assert html == '<facilities></facilities>'
        return [
            {
                'facility_name': '카페드림',
                'location': '중앙도서관 2층',
                'hours_text': '평일 08:00~19:00 토 10:00~16:00 (일/공휴일휴무)',
                'category': '카페',
                'source_tag': 'cuk_facilities',
                'last_synced_at': fetched_at,
            }
        ]


class ApiTransportSource:
    def fetch(self):
        return '<transport></transport>'

    def parse(self, html: str, *, fetched_at: str):
        assert html == '<transport></transport>'
        return [
            {
                'mode': 'bus',
                'title': '마을버스',
                'summary': '51번, 51-1번, 51-2번 버스',
                'steps': ['[가톨릭대학교, 역곡도서관] 정류장 하차'],
                'source_url': 'https://www.catholic.ac.kr/ko/about/location_songsim.do',
                'source_tag': 'cuk_transport',
                'last_synced_at': fetched_at,
            }
        ]


def test_place_detail_returns_merged_opening_hours(client):
    with connection() as conn:
        refresh_facility_hours_from_facilities_page(conn, source=ApiFacilitiesSource())

    response = client.get('/places/central-library')
    payload = response.json()

    assert response.status_code == 200
    assert (
        payload['opening_hours']['카페드림']
        == '평일 08:00~19:00 토 10:00~16:00 (일/공휴일휴무)'
    )


def test_transport_endpoint_returns_guides(client):
    with connection() as conn:
        refresh_transport_guides_from_location_page(conn, source=ApiTransportSource())

    response = client.get('/transport', params={'mode': 'bus'})
    items = response.json()

    assert response.status_code == 200
    assert items == [
        {
            'id': 1,
            'mode': 'bus',
            'title': '마을버스',
            'summary': '51번, 51-1번, 51-2번 버스',
            'steps': ['[가톨릭대학교, 역곡도서관] 정류장 하차'],
            'source_url': 'https://www.catholic.ac.kr/ko/about/location_songsim.do',
            'source_tag': 'cuk_transport',
            'last_synced_at': items[0]['last_synced_at'],
        }
    ]
