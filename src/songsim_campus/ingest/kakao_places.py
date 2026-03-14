from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(slots=True)
class KakaoPlace:
    name: str
    category: str
    address: str
    latitude: float
    longitude: float
    place_url: str


class KakaoLocalClient:
    BASE_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"KakaoAK {self.api_key}"}

    @staticmethod
    def _params(
        query: str,
        *,
        x: float | None = None,
        y: float | None = None,
        radius: int = 1000,
    ) -> dict[str, str | int | float]:
        params: dict[str, str | int | float] = {"query": query, "radius": radius}
        if x is not None and y is not None:
            params.update({"x": x, "y": y})
        return params

    @staticmethod
    def _parse_places(data: dict) -> list[KakaoPlace]:
        places: list[KakaoPlace] = []
        for item in data.get("documents", []):
            places.append(
                KakaoPlace(
                    name=item.get("place_name", ""),
                    category=item.get("category_name", ""),
                    address=item.get("road_address_name") or item.get("address_name", ""),
                    latitude=float(item["y"]),
                    longitude=float(item["x"]),
                    place_url=item.get("place_url", ""),
                )
            )
        return places

    async def search(
        self,
        query: str,
        *,
        x: float | None = None,
        y: float | None = None,
        radius: int = 1000,
    ) -> list[KakaoPlace]:
        params = self._params(query, x=x, y=y, radius=radius)
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(self.BASE_URL, headers=self._headers(), params=params)
            response.raise_for_status()
            data = response.json()
        return self._parse_places(data)

    def search_sync(
        self,
        query: str,
        *,
        x: float | None = None,
        y: float | None = None,
        radius: int = 1000,
    ) -> list[KakaoPlace]:
        params = self._params(query, x=x, y=y, radius=radius)
        with httpx.Client(timeout=20) as client:
            response = client.get(self.BASE_URL, headers=self._headers(), params=params)
            response.raise_for_status()
            data = response.json()
        return self._parse_places(data)
