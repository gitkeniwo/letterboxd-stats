from streamlit.testing.v1 import AppTest


def _has_setup_heading(app: AppTest) -> bool:
    return any("Set up Letterboxd Stats" in item.value for item in app.markdown)


def test_first_launch_renders_setup(tmp_path, monkeypatch):
    monkeypatch.setenv("LETTERBOXD_STATS_DATA_DIR", str(tmp_path))
    app = AppTest.from_file("app.py")
    app.run(timeout=10)
    assert not app.exception
    assert _has_setup_heading(app)


def test_packaged_streamlit_entrypoint_has_package_imports(tmp_path, monkeypatch):
    monkeypatch.setenv("LETTERBOXD_STATS_DATA_DIR", str(tmp_path))
    app = AppTest.from_file("letterboxd_stats/streamlit_app.py")
    app.run(timeout=10)
    assert not app.exception
    assert _has_setup_heading(app)
