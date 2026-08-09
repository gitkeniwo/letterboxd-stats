from letterboxd_stats.tmdb import TMDBClient, match_score


def test_match_score_uses_title_and_year():
    exact = {"title": "Land of the Lustrous", "release_date": "2017-01-01"}
    wrong_year = {"title": "Land of the Lustrous", "release_date": "1990-01-01"}
    assert match_score("Land of the Lustrous", 2017, exact) == 1.0
    assert match_score("Land of the Lustrous", 2017, wrong_year) == 0.8


def test_full_media_falls_back_to_tv(monkeypatch):
    client = TMDBClient("test-key")

    def fake_get(path, **params):
        if path == "/search/movie":
            return {
                "results": [
                    {"id": 1, "title": "Unrelated", "release_date": "2017-01-01"}
                ]
            }
        if path == "/search/tv":
            return {
                "results": [
                    {
                        "id": 77,
                        "name": "Land of the Lustrous",
                        "first_air_date": "2017-10-07",
                    }
                ]
            }
        if path == "/tv/77":
            return {"id": 77, "name": "Land of the Lustrous", "episode_run_time": [24]}
        if path == "/tv/77/credits":
            return {"crew": [], "cast": []}
        raise AssertionError((path, params))

    monkeypatch.setattr(client, "_get", fake_get)
    payload = client.full_media("Land of the Lustrous", 2017)
    assert payload is not None
    assert payload["media_type"] == "tv"
    assert payload["details"]["runtime"] == 24
    assert payload["match_confidence"] == 1.0
