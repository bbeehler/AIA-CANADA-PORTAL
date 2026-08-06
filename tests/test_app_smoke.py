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
        "Benchmark Explorer", "Performance Lab", "Member Data Pool", "Market Demographics",
        "Resources", "Contribute Data"
    ]:
        portal_radio(app).set_value(page).run()
        assert not app.exception, f"{page}: {[str(error.value) for error in app.exception]}"


def test_demo_admin_centre_renders_without_exceptions():
    app = AppTest.from_file(APP, default_timeout=30).run()
    next(button for button in app.button if button.label == "View as admin").click().run()
    portal_radio(app).set_value("Admin Centre").run()
    assert not app.exception


def test_demo_admin_can_add_a_valid_manual_dataset_row():
    app = AppTest.from_file(APP, default_timeout=30).run()
    next(button for button in app.button if button.label == "View as admin").click().run()
    portal_radio(app).set_value("Admin Centre").run()

    next(field for field in app.text_input if field.label == "Shop size").set_value("1-3 bays")
    next(field for field in app.text_input if field.label == "Geography").set_value("Ontario")
    next(
        field for field in app.number_input
        if field.label == "Hours sold / technician / day"
    ).set_value(5.2)
    next(button for button in app.button if button.label == "Add validated row").click().run()

    assert not app.exception
    assert any("Row added" in message.value for message in app.success)


def test_demo_member_can_enter_and_submit_shop_data_manually():
    app = AppTest.from_file(APP, default_timeout=30).run()
    next(button for button in app.button if button.label == "View as member").click().run()
    portal_radio(app).set_value("Contribute Data").run()

    next(button for button in app.button if button.label == "Add validated month").click().run()
    assert not app.exception
    assert any("Month added" in message.value for message in app.success)

    next(checkbox for checkbox in app.checkbox if "authorized to submit" in checkbox.label).check()
    next(button for button in app.button if button.label == "Submit for approval").click().run()

    assert not app.exception
    assert any("Submission received" in message.value for message in app.success)


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


def test_best_available_member_data_is_used_across_analytical_pages():
    app = AppTest.from_file(APP, default_timeout=30).run()
    next(button for button in app.button if button.label == "View as member").click().run()

    assert any("Headline indicators use qualified approved member data" in item.value for item in app.success)

    portal_radio(app).set_value("Performance Lab").run()
    next(field for field in app.selectbox if field.label == "Comparison measure").set_value(
        "hours_repair_order"
    ).run()
    assert any("current-member cohort" in item.value for item in app.success)

    portal_radio(app).set_value("Benchmark Explorer").run()
    next(field for field in app.selectbox if field.label == "Measure").set_value(
        "average_hours_repair_order"
    ).run()
    assert any("Current values represent all submitted shop sizes" in item.value for item in app.caption)

    portal_radio(app).set_value("Market Demographics").run()
    assert any("directly linked" in item.value for item in app.success)
