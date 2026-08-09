from visualizations import overview


def test_missing_poster_renders_actionable_placeholder(monkeypatch):
    rendered = {}

    def capture(body, **kwargs):
        rendered["body"] = body
        rendered.update(kwargs)

    monkeypatch.setattr(overview.st, "markdown", capture)
    overview.render_missing_poster_card(
        {
            "name": "Land of the Lustrous",
            "tmdb_id": None,
            "enrichment_status": "no_match",
        }
    )
    assert "Land of the Lustrous" in rendered["body"]
    assert "Needs TMDB match" in rendered["body"]
    assert rendered["unsafe_allow_html"] is True
