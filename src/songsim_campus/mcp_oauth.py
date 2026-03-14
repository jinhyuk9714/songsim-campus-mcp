from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings

from .settings import Settings

DEFAULT_SCOPE = "songsim.read"
JWKS_CACHE_TTL_SECONDS = 300


def is_public_mcp_oauth_enabled(settings: Settings) -> bool:
    return settings.app_mode == "public_readonly" and settings.mcp_oauth_enabled


def build_mcp_auth_settings(settings: Settings) -> AuthSettings | None:
    if not is_public_mcp_oauth_enabled(settings):
        return None
    audience = settings.resolved_mcp_oauth_audience
    if audience is None:  # pragma: no cover - guarded by settings validation
        return None
    return AuthSettings(
        issuer_url=settings.mcp_oauth_issuer,
        resource_server_url=audience,
        required_scopes=settings.mcp_oauth_scopes,
    )


def build_mcp_tool_meta(settings: Settings) -> dict[str, Any] | None:
    if not is_public_mcp_oauth_enabled(settings):
        return None
    issuer = (settings.mcp_oauth_issuer or "").rstrip("/")
    scopes = settings.mcp_oauth_scopes or [DEFAULT_SCOPE]
    return {
        "securitySchemes": [
            {
                "type": "oauth2",
                "scopes": scopes,
                "flows": {
                        "authorizationCode": {
                            "authorizationUrl": f"{issuer}/authorize",
                            "tokenUrl": f"{issuer}/oauth/token",
                            "scopes": {
                                scope: (
                                    "Read Songsim campus places, courses, notices, "
                                    "restaurants, and transport."
                                )
                                for scope in scopes
                            },
                        }
                    },
            }
        ]
    }


def build_protected_resource_metadata(settings: Settings) -> dict[str, Any] | None:
    if not is_public_mcp_oauth_enabled(settings):
        return None
    audience = settings.resolved_mcp_oauth_audience
    if audience is None:  # pragma: no cover - guarded by settings validation
        return None
    return {
        "resource": audience,
        "authorization_servers": [settings.mcp_oauth_issuer],
        "scopes_supported": settings.mcp_oauth_scopes,
        "bearer_methods_supported": ["header"],
    }


class Auth0TokenVerifier(TokenVerifier):
    def __init__(
        self,
        *,
        issuer_url: str,
        audience: str,
        required_scopes: list[str],
    ) -> None:
        self.issuer_url = issuer_url
        self.audience = audience
        self.required_scopes = required_scopes
        self._jwks_cache: dict[str, Any] | None = None
        self._jwks_cache_expires_at = 0.0
        self._jwks_uri: str | None = None
        self._lock = asyncio.Lock()

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            if not kid:
                return None
            jwks_document = await self._get_jwks_document()
            public_jwk = next(
                (item for item in jwks_document.get("keys", []) if item.get("kid") == kid),
                None,
            )
            if public_jwk is None:
                return None
            public_key = RSAAlgorithm.from_jwk(json.dumps(public_jwk))
            payload = jwt.decode(
                token,
                key=public_key,
                algorithms=[public_jwk.get("alg", "RS256"), "RS256"],
                audience=self.audience,
                issuer=self.issuer_url,
            )
            scopes = _extract_scopes(payload)
            if any(scope not in scopes for scope in self.required_scopes):
                return None
            return AccessToken(
                token=token,
                client_id=str(
                    payload.get("sub")
                    or payload.get("azp")
                    or payload.get("client_id")
                    or "authenticated-user"
                ),
                scopes=scopes,
                expires_at=int(payload["exp"]) if payload.get("exp") is not None else None,
                resource=self.audience,
            )
        except (jwt.PyJWTError, ValueError, TypeError, httpx.HTTPError):
            return None

    async def _get_jwks_document(self) -> dict[str, Any]:
        now = time.time()
        if self._jwks_cache is not None and now < self._jwks_cache_expires_at:
            return self._jwks_cache
        async with self._lock:
            now = time.time()
            if self._jwks_cache is not None and now < self._jwks_cache_expires_at:
                return self._jwks_cache
            jwks_uri = await self._get_jwks_uri()
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(jwks_uri)
                response.raise_for_status()
                self._jwks_cache = response.json()
                self._jwks_cache_expires_at = now + _parse_cache_ttl(
                    response.headers.get("cache-control")
                )
                return self._jwks_cache

    async def _get_jwks_uri(self) -> str:
        if self._jwks_uri is not None:
            return self._jwks_uri
        discovery_url = f"{self.issuer_url.rstrip('/')}/.well-known/openid-configuration"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(discovery_url)
            response.raise_for_status()
            payload = response.json()
        jwks_uri = payload.get("jwks_uri")
        if not isinstance(jwks_uri, str) or not jwks_uri:
            raise ValueError("OIDC discovery document did not include jwks_uri")
        self._jwks_uri = jwks_uri
        return jwks_uri


def _extract_scopes(payload: dict[str, Any]) -> list[str]:
    scopes: list[str] = []
    raw_scope = payload.get("scope")
    if isinstance(raw_scope, str):
        for item in raw_scope.split():
            if item and item not in scopes:
                scopes.append(item)
    elif isinstance(raw_scope, list):
        for item in raw_scope:
            if isinstance(item, str) and item and item not in scopes:
                scopes.append(item)
    permissions = payload.get("permissions")
    if isinstance(permissions, list):
        for item in permissions:
            if isinstance(item, str) and item and item not in scopes:
                scopes.append(item)
    return scopes


def _parse_cache_ttl(cache_control: str | None) -> int:
    if not cache_control:
        return JWKS_CACHE_TTL_SECONDS
    for part in cache_control.split(","):
        part = part.strip().lower()
        if part.startswith("max-age="):
            try:
                return max(int(part.split("=", 1)[1]), 1)
            except ValueError:
                return JWKS_CACHE_TTL_SECONDS
    return JWKS_CACHE_TTL_SECONDS
