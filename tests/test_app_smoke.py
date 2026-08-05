from pathlib import Path

from streamlit.testing.v1 import AppTest


APP = Path(__file__).resolve().parents[1] / "app.py"


def portal_radio(app):
    return next(radio for radio in app.radio if "Overview" in radio.options)


def test_demo_member_pages_render_without_exceptions():
    app = AppTest.from_file(APP, default_timeout=30).run()
    next(button for button in app.button if button.label == "View as member").click().run()
    assert not app.exception
    for page in ["Benchmark Explorer", "Performance Lab", "Resources", "Contribute Data"]:
        portal_radio(app).set_value(page).run()
        assert not app.exception, f"{page}: {[str(error.value) for error in app.exception]}"


def test_demo_admin_centre_renders_without_exceptions():
    app = AppTest.from_file(APP, default_timeout=30).run()
    next(button for button in app.button if button.label == "View as admin").click().run()
    portal_radio(app).set_value("Admin Centre").run()
    assert not app.exception
