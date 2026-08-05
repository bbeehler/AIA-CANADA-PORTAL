from aia_portal.data import load_performance_benchmarks, load_segment_benchmarks, national_segment_snapshot


def test_seed_row_counts_and_provenance():
    segment = load_segment_benchmarks()
    performance = load_performance_benchmarks()
    assert len(segment) == 30
    assert len(performance) == 84
    assert segment["source_page"].notna().all()
    assert performance["source_page"].notna().all()


def test_known_report_values_are_preserved():
    performance = load_performance_benchmarks()
    value = performance.loc[
        (performance["shop_type"] == "Mechanical")
        & (performance["cohort"] == "Ticket size leaders")
        & (performance["metric_code"] == "hours_repair_order"),
        "value",
    ].iloc[0]
    assert value == 2.51

    snapshot = national_segment_snapshot()
    small = snapshot[(snapshot["segment"] == "Mechanical") & (snapshot["shop_size"] == "1-3 bays")]
    assert small["hours_sold_technician_day"].iloc[0] == 5.1
