"""TMDB HTTP client with bounded retries and normalized results."""

from __future__ import annotations

import re
import threading
import time
import unicodedata
from difflib import SequenceMatcher
from typing import Any

import httpx

TMDB_BASE_URL = "https://api.themoviedb.org/3"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
AUTO_MATCH_THRESHOLD = 0.82
AMBIGUITY_MARGIN = 0.03


class TMDBError(RuntimeError):
    pass


def _normalized_title(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).casefold()
    return re.sub(r"[^a-z0-9]+", "", value)


def _candidate_title(candidate: dict) -> str:
    return candidate.get("title") or candidate.get("name") or ""


def _candidate_year(candidate: dict) -> int | None:
    date = candidate.get("release_date") or candidate.get("first_air_date") or ""
    try:
        return int(date[:4]) if len(date) >= 4 else None
    except ValueError:
        return None


def match_score(name: str, year: int | None, candidate: dict) -> float:
    query_title = _normalized_title(name)
    result_title = _normalized_title(_candidate_title(candidate))
    if not query_title or not result_title:
        return 0.0
    title_score = SequenceMatcher(None, query_title, result_title).ratio()
    result_year = _candidate_year(candidate)
    if year is None or result_year is None:
        year_score = 0.5
    elif year == result_year:
        year_score = 1.0
    elif abs(year - result_year) == 1:
        year_score = 0.5
    else:
        year_score = 0.0
    return round((title_score * 0.8) + (year_score * 0.2), 4)


class TMDBClient:
    def __init__(self, api_key: str, timeout: float = 30.0, max_retries: int = 3):
        self.api_key = api_key.strip()
        self.timeout = timeout
        self.max_retries = max_retries
        self._local = threading.local()

    def _client(self) -> httpx.Client:
        if not hasattr(self._local, "client"):
            self._local.client = httpx.Client(timeout=self.timeout)
        return self._local.client

    def _get(self, path: str, **params: Any) -> dict:
        if not self.api_key:
            raise TMDBError("A TMDB API key is required.")
        params["api_key"] = self.api_key
        for attempt in range(self.max_retries + 1):
            try:
                response = self._client().get(f"{TMDB_BASE_URL}{path}", params=params)
                if (
                    response.status_code in RETRYABLE_STATUS
                    and attempt < self.max_retries
                ):
                    retry_after = response.headers.get("Retry-After")
                    delay = (
                        float(retry_after)
                        if retry_after and retry_after.isdigit()
                        else 0.5 * (2**attempt)
                    )
                    time.sleep(min(delay, 8.0))
                    continue
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt >= self.max_retries:
                    raise TMDBError(f"TMDB network error: {exc}") from exc
                time.sleep(0.5 * (2**attempt))
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in {401, 403}:
                    raise TMDBError("TMDB rejected the API key.") from exc
                raise TMDBError(
                    f"TMDB returned HTTP {exc.response.status_code}."
                ) from exc
        raise TMDBError("TMDB request failed.")

    def validate_key(self) -> bool:
        self._get("/configuration")
        return True

    def _search_movies(self, name: str, year: int | None) -> list[dict]:
        params: dict[str, Any] = {"query": name, "include_adult": "false"}
        if year:
            params["primary_release_year"] = year
        results = self._get("/search/movie", **params).get("results", [])
        if not results and year:
            results = self._get("/search/movie", query=name, include_adult="false").get(
                "results", []
            )
        return results

    def _search_tv(self, name: str, year: int | None) -> list[dict]:
        params: dict[str, Any] = {"query": name, "include_adult": "false"}
        if year:
            params["first_air_date_year"] = year
        results = self._get("/search/tv", **params).get("results", [])
        if not results and year:
            results = self._get("/search/tv", query=name, include_adult="false").get(
                "results", []
            )
        return results

    @staticmethod
    def _rank(
        name: str, year: int | None, results: list[dict], media_type: str
    ) -> list[dict]:
        ranked = []
        for result in results:
            candidate = dict(result)
            candidate["_media_type"] = media_type
            candidate["_match_score"] = match_score(name, year, candidate)
            ranked.append(candidate)
        return sorted(ranked, key=lambda item: item["_match_score"], reverse=True)

    def search_media_candidates(
        self, name: str, year: int | None, limit: int = 10
    ) -> list[dict]:
        movies = self._rank(name, year, self._search_movies(name, year), "movie")
        shows = self._rank(name, year, self._search_tv(name, year), "tv")
        return sorted(
            [*movies, *shows], key=lambda item: item["_match_score"], reverse=True
        )[:limit]

    def search_movies(self, name: str, year: int | None, limit: int = 10) -> list[dict]:
        return self._rank(name, year, self._search_movies(name, year), "movie")[:limit]

    def search_movie(self, name: str, year: int | None) -> dict | None:
        results = self.search_movies(name, year, limit=1)
        return results[0] if results else None

    def movie_details(self, movie_id: int) -> dict:
        return self._get(f"/movie/{movie_id}")

    def movie_credits(self, movie_id: int) -> dict:
        return self._get(f"/movie/{movie_id}/credits")

    def full_movie(self, name: str, year: int | None) -> dict | None:
        return self.full_media(name, year)

    def full_media(self, name: str, year: int | None) -> dict | None:
        movies = self._rank(name, year, self._search_movies(name, year), "movie")
        # A confident movie result avoids an extra TV request for the common path.
        if movies and movies[0]["_match_score"] >= AUTO_MATCH_THRESHOLD:
            candidates = movies
        else:
            shows = self._rank(name, year, self._search_tv(name, year), "tv")
            candidates = sorted(
                [*movies, *shows], key=lambda item: item["_match_score"], reverse=True
            )
        if not candidates or candidates[0]["_match_score"] < AUTO_MATCH_THRESHOLD:
            return None
        if (
            len(candidates) > 1
            and candidates[0]["_match_score"] - candidates[1]["_match_score"]
            < AMBIGUITY_MARGIN
        ):
            return None
        match = candidates[0]
        if not match:
            return None
        movie_id = int(match["id"])
        payload = self.full_movie_by_id(movie_id, match["_media_type"])
        payload["match_confidence"] = match["_match_score"]
        return payload

    def full_movie_by_id(self, movie_id: int, media_type: str = "movie") -> dict:
        if media_type not in {"movie", "tv"}:
            raise ValueError("media_type must be movie or tv")
        details = self._get(f"/{media_type}/{movie_id}")
        credits = self._get(f"/{media_type}/{movie_id}/credits")
        if media_type == "tv":
            details["title"] = details.get("name", details.get("original_name", ""))
            details["release_date"] = details.get("first_air_date", "")
            episode_runtimes = details.get("episode_run_time", [])
            details["runtime"] = episode_runtimes[0] if episode_runtimes else None
        return {"details": details, "credits": credits, "media_type": media_type}
