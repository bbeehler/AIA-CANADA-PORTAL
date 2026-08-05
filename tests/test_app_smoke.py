from pathlib import Path

from streamlit.testing.v1 import AppTest


APP = Path(__file__).resolve().parents[1] / "app.py"


def portal_radio(app):
    return next(radio for radio in app.radio if "Overview" in radio.options)


def test_demo_member_pages_render_without_exceptions():
    app = AppTest.from_file(APP, default_timeout=30).run()
    next(button for button in app.button if button.label == "View as member").click().run()
    assert not app.exception
    for page in [
        "Benchmark Explorer", "Performance Lab", "Market Demographics", "Resources", "Contribute Data"
    ]:
        portal_radio(app).set_value(page).run()
        assert not app.exception, f"{page}: {[str(error.value) for error in app.exception]}"


def test_demo_admin_centre_renders_without_exceptions():
    app = AppTest.from_file(APP, default_timeout=30).run()
    next(button for button in app.button if button.label == "View as admin").click().run()
    portal_radio(app).set_value("Admin Centre").run()
    assert not app.exception


def test_market_demographics_links_to_benchmark_explorer():
    app = AppTest.from_file(APP, default_timeout=30).run()
    next(button for button in app.button if button.label == "View as member").click().run()
    portal_radio(app).set_value("Market Demographics").run()

    next(
        button for button in app.button
        if button.label == "Open this region in Benchmark Explorer"
    ).click().run()

    assert portal_radio(app).value == "Benchmark Explorer"
    assert not app.exception
    assert any("Linked from Ontario" in item.value for item in app.info)
