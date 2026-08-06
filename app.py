from __future__ import annotations

import sys
from datetime import date
from html import escape
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from aia_portal.auth import (  # noqa: E402
    DEMO_USERS,
    PortalUser,
    SessionTokens,
    SupabaseAuth,
    authenticated_client,
)
from aia_portal.analytics import (  # noqa: E402
    CURRENT_METRIC_MAP,
    SOURCE_BEST_AVAILABLE,
    SOURCE_HISTORICAL_ONLY,
    SOURCE_OPTIONS,
    current_explorer_comparison,
    normalize_member_benchmarks,
    select_member_benchmark,
)
from aia_portal.config import load_settings  # noqa: E402
from aia_portal.data import (  # noqa: E402
    METRICS,
    PERFORMANCE_FOCUS_METRICS,
    format_metric,
    read_template_bytes,
)
from aia_portal.dataset_validation import (  # noqa: E402
    DATASET_SEGMENT,
    DATASET_TYPE_LABELS,
    PERFORMANCE_UNITS,
    SEGMENT_METRIC_COLUMNS,
    dataset_template_bytes,
    read_dataset_csv,
    validate_dataset,
    validate_dataset_slug,
)
from aia_portal.exports import csv_bytes, excel_report_bytes, pdf_report_bytes  # noqa: E402
from aia_portal.market import calculate_market_scenario  # noqa: E402
from aia_portal.repository import DemoRepository, SupabaseRepository  # noqa: E402
from aia_portal.resources import (  # noqa: E402
    DELIVERY_EXTERNAL,
    FORMAT_HTML,
    resource_content_format,
    resource_delivery_type,
    sanitize_resource_html,
    validate_external_url,
)
from aia_portal.ui import inject_theme, metric_card, page_intro, source_note  # noqa: E402
from aia_portal.validation import read_uploaded_table, validate_shop_upload  # noqa: E402


AIA_COLOUR_LOGO_URL = "https://www.aiacanada.com/wp-content/uploads/2022/09/AIA-Colour-Logo-72DPI.png"
AIA_WHITE_LOGO_URL = "https://www.aiacanada.com/wp-content/uploads/2022/09/AIA-White-Logo-300DPI.png"

PROVINCE_NAMES = {
    "AB": "Alberta", "BC": "British Columbia", "MB": "Manitoba", "NB": "New Brunswick",
    "NL": "Newfoundland and Labrador", "NS": "Nova Scotia", "NT": "Northwest Territories",
    "NU": "Nunavut", "ON": "Ontario", "PE": "Prince Edward Island", "QC": "Quebec",
    "SK": "Saskatchewan", "YT": "Yukon",
}
DEMOGRAPHIC_LEVELS = {
    "Province or territory": "province",
    "Municipality": "municipality",
    "Postal region (FSA)": "postal_region",
}
AIA_REGION_BY_PROVINCE = {
    "BC": "British Columbia", "AB": "Alberta", "MB": "Prairies", "SK": "Prairies",
    "ON": "Ontario", "QC": "Quebec", "NL": "Atlantic", "PE": "Atlantic",
    "NS": "Atlantic", "NB": "Atlantic",
}


st.set_page_config(
    page_title="AIA Canada Data Portal",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_theme()

try:
    settings = load_settings(st.secrets)
except Exception:
    settings = load_settings()


def plotly_layout(fig: go.Figure, *, height: int = 420) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=16, r=16, t=52, b=16),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font=dict(family="Arial, sans-serif", color="#29495C", size=12),
        title_font=dict(color="#123E5A", size=17),
        legend_title_text="",
        hoverlabel=dict(bgcolor="#123E5A", font_color="white"),
    )
    fig.update_xaxes(showgrid=False, linecolor="#D7E2E8")
    fig.update_yaxes(gridcolor="#E7EEF2", zeroline=False)
    return fig


def chart(fig: go.Figure) -> None:
    st.plotly_chart(
        plotly_layout(fig),
        width="stretch",
        config={
            "displaylogo": False,
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
            "toImageButtonOptions": {"format": "png", "filename": "aia-canada-chart", "scale": 2},
        },
    )


def current_data_enabled() -> bool:
    return st.session_state.get("analytics_source_mode", SOURCE_BEST_AVAILABLE) != SOURCE_HISTORICAL_ONLY


def render_resource_content(content: str, content_format: str) -> None:
    if content_format == FORMAT_HTML:
        safe_html = sanitize_resource_html(content)
        if safe_html:
            st.markdown(safe_html, unsafe_allow_html=True)
        else:
            st.caption("This article has no displayable content.")
        return
    st.markdown(content)


def set_user(user: PortalUser, tokens: SessionTokens | None = None) -> None:
    st.session_state.portal_user = user
    st.session_state.session_tokens = tokens


def clear_user() -> None:
    st.session_state.pop("portal_user", None)
    st.session_state.pop("session_tokens", None)
    st.session_state.pop("repo", None)
    st.session_state.pop("portal_page", None)
    st.session_state.pop("next_portal_page", None)
    st.session_state.pop("market_bridge_context", None)


def login_page() -> None:
    left, right = st.columns([1.15, 0.85], gap="large")
    with left:
        st.image(AIA_COLOUR_LOGO_URL, width=135)
        st.markdown('<div class="aia-eyebrow">Industry Intelligence Portal</div>', unsafe_allow_html=True)
        st.title("The authoritative data hub for Canada’s auto care industry")
        st.markdown(
            '<p class="aia-lead">Explore trusted benchmarks, build reports and contribute secure shop data—all in one member-only workspace.</p>',
            unsafe_allow_html=True,
        )
        st.markdown("### Built for decisions, not just dashboards")
        feature_cols = st.columns(3)
        for column, title, body in zip(
            feature_cols,
            ["Benchmark", "Contribute", "Act"],
            [
                "Compare shop performance by region, size and operating model.",
                "Submit anonymized shop data for AIA Canada review.",
                "Export board-ready tables and reports in seconds.",
            ],
        ):
            with column:
                metric_card(title, "", body)
        st.info(
            "Concept dataset: The View from Here — 2015 Productivity Benchmarks. "
            "All dashboard values are labelled as historical survey benchmarks."
        )

    with right:
        with st.container(border=True):
            st.subheader("Member sign in")
            st.caption("Use the email associated with your AIA Canada membership.")
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="you@organization.ca")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Sign in", type="primary", width="stretch")
            if submitted:
                if not settings.supabase_configured:
                    st.error("Supabase sign-in is not configured. Add Streamlit secrets or use a demo workspace.")
                elif not email or not password:
                    st.error("Enter your email and password.")
                else:
                    try:
                        user, tokens = SupabaseAuth(settings).sign_in(email.strip(), password)
                        set_user(user, tokens)
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Unable to sign in: {exc}")

            if settings.enable_demo_mode:
                st.divider()
                st.caption("Concept review")
                demo_member, demo_admin = st.columns(2)
                if demo_member.button("View as member", width="stretch"):
                    set_user(DEMO_USERS["member"])
                    st.rerun()
                if demo_admin.button("View as admin", width="stretch"):
                    set_user(DEMO_USERS["admin"])
                    st.rerun()
            st.caption(f"Need access? Contact {settings.support_email}")


def get_repository(user: PortalUser):
    if user.demo:
        return DemoRepository(st.session_state)
    tokens = st.session_state.get("session_tokens")
    if not tokens:
        raise RuntimeError("Missing session. Please sign in again.")
    return SupabaseRepository(authenticated_client(settings, tokens))


def portal_sidebar(user: PortalUser) -> str:
    with st.sidebar:
        st.image(AIA_WHITE_LOGO_URL, width=115)
        st.markdown('<div class="aia-logo-sub">Industry Intelligence Portal</div>', unsafe_allow_html=True)
        st.write("")
        pages = [
            "Overview", "Benchmark Explorer", "Performance Lab", "Member Data Pool",
            "Market Demographics", "Resources", "Contribute Data",
        ]
        if user.is_admin:
            pages.append("Admin Centre")
        next_page = st.session_state.pop("next_portal_page", None)
        if next_page in pages:
            st.session_state["portal_page"] = next_page
        if st.session_state.get("portal_page") not in pages:
            st.session_state["portal_page"] = "Overview"
        current = st.radio("Portal", pages, label_visibility="collapsed", key="portal_page")
        st.caption("ANALYTICS SOURCE")
        st.selectbox(
            "Analytics source",
            SOURCE_OPTIONS,
            key="analytics_source_mode",
            label_visibility="collapsed",
            help=(
                "Best available uses qualified current member data first and keeps the 2015 AIA "
                "benchmark as historical context or fallback."
            ),
        )
        st.divider()
        st.markdown(f"**{escape(user.full_name)}**", unsafe_allow_html=True)
        st.caption(user.organization or user.email)
        st.caption("Administrator" if user.is_admin else "Active member")
        if user.demo:
            st.caption("Demo workspace")
        if st.button("Sign out", width="stretch"):
            if not user.demo and settings.supabase_configured:
                try:
                    SupabaseAuth(settings).sign_out()
                except Exception:
                    pass
            clear_user()
            st.rerun()
    return current


def overview_page(repo) -> None:
    page_intro(
        "Industry pulse",
        "A clear view of shop productivity",
        "Start with the newest qualified member benchmarks, with the 2015 AIA report retained as the "
        "historical foundation and fallback.",
    )
    performance = repo.performance_benchmarks()
    mechanical_all = performance[
        (performance["shop_type"] == "Mechanical") & (performance["cohort"] == "All shops")
    ].set_index("metric_code")
    member_data = normalize_member_benchmarks(repo.member_benchmark_aggregates())
    member_selection = select_member_benchmark(member_data, shop_type="Mechanical")
    use_member = current_data_enabled() and member_selection.available

    cards = st.columns(4)
    if use_member:
        current = member_selection.record
        period = pd.to_datetime(current["reporting_month"]).strftime("%B %Y")
        values = [
            ("Current contributors", f"{int(current['contributor_count']):,}", f"Qualified national cohort · {period}"),
            ("Hours / repair order", format_metric(current["hours_per_repair_order"], "hours"), "Approved member data"),
            ("Monthly repair orders", format_metric(current["average_repair_orders"], "count"), "Average submitted shop-month"),
            ("Average monthly sales", format_metric(current["average_total_sales_cad"], "cad"), "Labour, parts and tires"),
        ]
        st.success(
            f"Headline indicators use qualified approved member data for {period}. The historical "
            "benchmark remains below for long-term comparison."
        )
    else:
        values = [
            ("Survey respondents", "572", "Canadian automotive service providers"),
            ("Hours / repair order", format_metric(mechanical_all.loc["hours_repair_order", "value"], "hours"), "Mechanical shop average · 2015"),
            ("Hours / technician / day", format_metric(mechanical_all.loc["hours_technician_day", "value"], "hours"), "Historical daily measure · 2015"),
            ("Hiring intention", "57%", "Planned to hire a technician · 2015"),
        ]
        if current_data_enabled():
            st.info(
                "No national current-member cohort has reached the privacy threshold, so headline "
                "indicators are using the historical AIA benchmark."
            )
    for column, item in zip(cards, values):
        with column:
            metric_card(*item)

    if use_member:
        national_current = member_data[
            (member_data["geography_type"] == "national")
            & (member_data["geography_code"] == "CA")
            & (member_data["shop_type"] == "Mechanical")
        ].sort_values("reporting_month")
        if not national_current.empty:
            current_fig = px.line(
                national_current,
                x="reporting_month",
                y="hours_per_repair_order",
                markers=True,
                title="Current member trend · hours sold per repair order",
                labels={"reporting_month": "Month", "hours_per_repair_order": "Hours"},
            )
            current_fig.update_traces(line_color="#D7263D")
            chart(current_fig)

    st.write("")
    st.subheader("Historical benchmark foundation")
    segment = repo.segment_benchmarks()
    national = segment[
        (segment["geography_type"] == "national")
        & (segment["geography"] == "Canada")
        & (segment["affiliation"] == "All")
    ].copy()
    national["Shop segment"] = national["segment"] + " · " + national["shop_size"]

    left, right = st.columns([1.25, 0.75], gap="large")
    with left:
        fig = px.bar(
            national,
            x="Shop segment",
            y="hours_sold_technician_day",
            color="segment",
            color_discrete_map={"Mechanical": "#1B5B83", "Tire": "#D7263D"},
            text_auto=".1f",
            title="Sold technician hours by shop segment",
            labels={"hours_sold_technician_day": "Hours sold / technician / day"},
        )
        fig.add_hline(y=8, line_dash="dot", line_color="#7A8D98", annotation_text="8-hour workday")
        chart(fig)
    with right:
        st.subheader("What the benchmark says")
        st.markdown(
            '<div class="aia-callout"><strong>The productivity gap is structural.</strong><br>'
            'Mechanical shops sold 4.4 technician hours per day on average, while the productivity-leading cohort sold 7.1.</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="aia-callout"><strong>Ticket size and flow must be managed together.</strong><br>'
            'Ticket-size leaders sold 2.51 hours per repair order—50% above the mechanical-shop average.</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="aia-callout"><strong>Use small samples cautiously.</strong><br>'
            'Regional rows include sample sizes, so filters and exported reports retain context.</div>',
            unsafe_allow_html=True,
        )
    source_note("4, 7–10, 12")

    st.subheader("Regional pattern")
    regional = segment[(segment["segment"] == "Mechanical") & (segment["geography_type"] == "region")]
    heat = regional.pivot(index="geography", columns="shop_size", values="hours_sold_technician_day")
    fig = px.imshow(
        heat,
        text_auto=".1f",
        aspect="auto",
        color_continuous_scale=[[0, "#EAF1F5"], [0.5, "#6F9CB7"], [1, "#123E5A"]],
        title="Hours sold per technician per day · mechanical shops",
        labels={"color": "Hours"},
    )
    chart(fig)
    source_note("7–9")


def explorer_page(repo) -> None:
    page_intro(
        "Benchmark explorer",
        "Slice the industry benchmark your way",
        "Filter dimensions, change the visual and export the result with source context preserved.",
    )
    data = repo.segment_benchmarks()
    bridge = st.session_state.get("market_bridge_context") or {}
    f1, f2, f3, f4 = st.columns([1, 1, 1.25, 1.4])
    with f1:
        segment = st.selectbox("Segment", sorted(data["segment"].dropna().unique()))
    filtered = data[data["segment"] == segment].copy()
    with f2:
        sizes = st.multiselect(
            "Shop size",
            sorted(filtered["shop_size"].dropna().unique()),
            default=sorted(filtered["shop_size"].dropna().unique()),
        )
    filtered = filtered[filtered["shop_size"].isin(sizes)]
    with f3:
        scope_options = ["Regional comparison", "National / affiliation"]
        linked_scope = bridge.get("scope")
        scope_index = scope_options.index(linked_scope) if linked_scope in scope_options else (
            0 if (filtered["geography_type"] == "region").any() else 1
        )
        scope = st.selectbox(
            "View",
            scope_options,
            index=scope_index,
        )
    filtered = filtered[
        filtered["geography_type"] == ("region" if scope == "Regional comparison" else "national")
    ]
    with f4:
        available_metrics = [code for code in METRICS if filtered[code].notna().any()]
        metric = st.selectbox(
            "Measure",
            available_metrics,
            format_func=lambda code: METRICS[code][0],
            index=available_metrics.index("hours_sold_technician_day")
            if "hours_sold_technician_day" in available_metrics else 0,
        )

    selected_regions: list[str] = []
    if scope == "Regional comparison":
        region_options = sorted(filtered["geography"].dropna().unique())
        linked_region = bridge.get("region")
        default_regions = [linked_region] if linked_region in region_options else region_options
        selected_regions = st.multiselect(
            "AIA benchmark regions",
            region_options,
            default=default_regions,
        )
        filtered = filtered[filtered["geography"].isin(selected_regions)]
        if linked_region in region_options:
            st.info(
                f"Linked from {bridge.get('geography', 'Market Demographics')} to the "
                f"historical AIA benchmark region: {linked_region}."
            )
    elif bridge.get("scope") == "National / affiliation":
        st.info(
            f"Linked from {bridge.get('geography', 'Market Demographics')} to the historical "
            "national AIA benchmark because the 2015 report has no separate territory benchmark."
        )

    visual = st.radio("Visualization", ["Bar", "Bubble", "Heatmap", "Table"], horizontal=True)
    label, unit = METRICS[metric]
    if filtered.empty:
        st.warning("No data matches the selected filters.")
        return

    if visual == "Bar":
        x_dimension = "geography" if scope == "Regional comparison" else "affiliation"
        fig = px.bar(
            filtered,
            x=x_dimension,
            y=metric,
            color="shop_size",
            barmode="group",
            text_auto=".2s",
            title=label,
            labels={metric: label, "shop_size": "Shop size", x_dimension: ""},
            color_discrete_sequence=["#123E5A", "#3D789B", "#D7263D", "#E3838F"],
        )
        chart(fig)
    elif visual == "Bubble":
        fig = px.scatter(
            filtered,
            x="average_repair_orders_year",
            y=metric,
            size="sample_size",
            color="shop_size",
            hover_name="geography",
            hover_data=["affiliation", "sample_size", "source_page"],
            title=f"{label} versus annual repair orders",
            labels={"average_repair_orders_year": "Average repair orders / year", metric: label},
            color_discrete_sequence=["#123E5A", "#3D789B", "#D7263D"],
        )
        chart(fig)
    elif visual == "Heatmap":
        row = "geography" if scope == "Regional comparison" else "affiliation"
        matrix = filtered.pivot_table(index=row, columns="shop_size", values=metric, aggfunc="mean")
        fig = px.imshow(
            matrix,
            text_auto=".2g",
            aspect="auto",
            color_continuous_scale=[[0, "#EDF3F6"], [1, "#1B5B83"]],
            title=label,
            labels={"color": label},
        )
        chart(fig)
    else:
        st.dataframe(filtered, hide_index=True, width="stretch")

    current_comparison = pd.DataFrame()
    if current_data_enabled():
        member_data = repo.member_benchmark_aggregates()
        if scope == "Regional comparison":
            province_codes = [
                code
                for code, region in AIA_REGION_BY_PROVINCE.items()
                if region in selected_regions
            ]
            current_comparison = current_explorer_comparison(
                member_data,
                historical_metric_code=metric,
                shop_type=segment,
                geography_type="province",
                province_codes=province_codes,
            )
        else:
            current_comparison = current_explorer_comparison(
                member_data,
                historical_metric_code=metric,
                shop_type=segment,
                geography_type="national",
            )

        st.subheader("Current member-data comparison")
        if metric not in CURRENT_METRIC_MAP:
            st.info(
                "The current contribution contract does not collect a directly compatible measure for "
                f'“{label}.” The historical result above remains the authoritative comparison for this measure.'
            )
        elif current_comparison.empty:
            st.info(
                "No matching current-member cohort has reached the five-contributor privacy threshold. "
                "The historical benchmark remains the best available source."
            )
        else:
            current_comparison["Geography"] = current_comparison["geography_code"].map(
                lambda code: "Canada" if code == "CA" else PROVINCE_NAMES.get(code, code)
            )
            member_fig = px.bar(
                current_comparison,
                x="Geography",
                y="value",
                color="Geography",
                text_auto=".2f",
                title=f"Qualified current member data · {label}",
                labels={"value": label},
                color_discrete_sequence=["#D7263D", "#1B5B83", "#6F9CB7"],
            )
            chart(member_fig)
            st.caption(
                "Current values represent all submitted shop sizes in each qualified cohort. Historical "
                "shop-size and affiliation cuts remain visible above because those dimensions are not "
                "collected in the member contribution contract."
            )

    valid_values = filtered[metric].dropna()
    kpis = st.columns(3)
    with kpis[0]:
        metric_card("Filtered average", format_metric(valid_values.mean(), unit), label)
    with kpis[1]:
        metric_card("Highest result", format_metric(valid_values.max(), unit), "Within the current selection")
    with kpis[2]:
        metric_card("Respondents represented", f"{filtered['sample_size'].sum():,.0f}", "Overlapping cuts are not a unique count")

    st.subheader("Export this view")
    filters = {"Segment": segment, "Shop size": ", ".join(sizes), "View": scope, "Measure": label}
    e1, e2, e3 = st.columns(3)
    with e1:
        st.download_button("Download CSV", csv_bytes(filtered), "aia_benchmark_view.csv", "text/csv", width="stretch")
    with e2:
        st.download_button(
            "Download Excel",
            excel_report_bytes(filtered, title="AIA Canada benchmark view", filters=filters),
            "aia_benchmark_view.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
    with e3:
        st.download_button(
            "Download PDF",
            pdf_report_bytes(filtered, title="AIA Canada benchmark view", filters=filters),
            "aia_benchmark_view.pdf",
            "application/pdf",
            width="stretch",
        )
    if not current_comparison.empty:
        st.download_button(
            "Download current member comparison CSV",
            csv_bytes(current_comparison),
            "aia_current_member_benchmark_comparison.csv",
            "text/csv",
        )
    source_note("7–10")


def performance_page(repo) -> None:
    page_intro(
        "Performance lab",
        "Turn benchmark gaps into operating questions",
        "Compare leading cohorts and estimate the scale of a shop’s ticket-size and productivity opportunity.",
    )
    data = repo.performance_benchmarks()
    shop_type = st.segmented_control("Shop type", ["Mechanical", "Tire"], default="Mechanical")
    member_data = repo.member_benchmark_aggregates()
    member_selection = select_member_benchmark(member_data, shop_type=shop_type)
    use_member = current_data_enabled() and member_selection.available
    scoped = data[data["shop_type"] == shop_type].copy()
    available = scoped[scoped["metric_code"].isin(PERFORMANCE_FOCUS_METRICS)]
    metric_code = st.selectbox(
        "Comparison measure",
        list(dict.fromkeys(available["metric_code"])),
        format_func=lambda code: available.loc[available["metric_code"] == code, "metric_label"].iloc[0],
    )
    comparison = scoped[scoped["metric_code"] == metric_code].copy()
    metric_label = comparison["metric_label"].iloc[0]
    if use_member and metric_code == "hours_repair_order":
        current = member_selection.record
        comparison = pd.concat([
            comparison,
            pd.DataFrame([{
                "shop_type": shop_type,
                "cohort": "Current member pool",
                "metric_code": metric_code,
                "metric_label": metric_label,
                "value": current["hours_per_repair_order"],
            }]),
        ], ignore_index=True)
    fig = px.bar(
        comparison,
        x="cohort",
        y="value",
        color="cohort",
        text_auto=".2f",
        title=f"{shop_type} shops · {metric_label}",
        labels={"value": metric_label, "cohort": ""},
        color_discrete_map={
            "All shops": "#91A7B4",
            "Ticket size leaders": "#1B5B83",
            "Productivity leaders": "#D7263D",
            "Current member pool": "#2B8A66",
        },
    )
    chart(fig)
    if use_member and metric_code == "hours_repair_order":
        current_period = pd.to_datetime(member_selection.record["reporting_month"]).strftime("%B %Y")
        st.success(
            f"The comparison includes the qualified {current_period} current-member cohort "
            f"({int(member_selection.record['contributor_count']):,} contributors)."
        )
    elif current_data_enabled() and metric_code != "hours_repair_order":
        st.info(
            "Current member submissions do not yet collect this measure in a directly compatible daily "
            "or percentage unit, so the historical performance cohorts remain in use."
        )
    source_note("12" if shop_type == "Mechanical" else "15")

    st.subheader("Opportunity calculator")
    st.caption("A directional scenario—not a forecast. Adjust the inputs to match a member shop.")
    current_ticket_default = (
        float(member_selection.record["hours_per_repair_order"])
        if use_member else 1.67
    )
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            repair_orders = st.number_input("Annual repair orders", min_value=1, value=2500, step=100)
            technicians = st.number_input("Paid technicians", min_value=1.0, value=4.0, step=0.5)
        with c2:
            days_open = st.number_input("Days open / year", min_value=1, value=259, step=1)
            door_rate = st.number_input("Labour door rate (CAD)", min_value=1.0, value=110.0, step=5.0)
        with c3:
            current_ticket = st.number_input(
                "Current hours / repair order",
                min_value=0.1,
                value=current_ticket_default,
                step=0.1,
                help=(
                    "Defaults to the latest qualified member benchmark when available; otherwise uses "
                    "the historical mechanical-shop average."
                ),
            )
            current_productivity = st.number_input("Current hours / technician / day", min_value=0.1, value=4.4, step=0.1)

    def benchmark(metric: str, cohort: str) -> float:
        return float(scoped[(scoped["metric_code"] == metric) & (scoped["cohort"] == cohort)]["value"].iloc[0])

    target_ticket = benchmark("hours_repair_order", "Ticket size leaders")
    target_productivity = benchmark("hours_technician_day", "Productivity leaders")
    ticket_gap = max(target_ticket - current_ticket, 0) * repair_orders * door_rate
    productivity_gap = max(target_productivity - current_productivity, 0) * technicians * days_open * door_rate
    annual_labour_sales = repair_orders * current_ticket * door_rate
    c1, c2, c3 = st.columns(3)
    with c1:
        metric_card("Current labour sales lens", f"${annual_labour_sales:,.0f}", "Repair orders × hours / order × door rate")
    with c2:
        metric_card("Ticket-size opportunity", f"${ticket_gap:,.0f}", f"Gap to {target_ticket:.2f} hours / repair order")
    with c3:
        metric_card("Productivity opportunity", f"${productivity_gap:,.0f}", f"Gap to {target_productivity:.1f} hours / technician / day")
    st.warning(
        "The two opportunity lenses can overlap and should not be added together. They are conversation starters for scheduling, inspection, advisor capacity and technician utilization."
    )


def member_data_pool_page(repo) -> None:
    page_intro(
        "Current member benchmarks",
        "Turn approved shop data into industry intelligence",
        "Explore monthly, privacy-safe benchmarks created from validated member submissions. Raw shop "
        "figures remain private and never appear in this view.",
    )
    st.info(
        "Privacy rule: A benchmark is created only when at least five independent contributors are "
        "represented in the same month, geography and shop type. Smaller cohorts are suppressed."
    )
    data = repo.member_benchmark_aggregates()
    if data.empty:
        st.warning(
            "Approved data is entering the governed pool, but no cohort has reached the five-contributor "
            "privacy threshold yet. This page will populate automatically as participation grows."
        )
        return

    numeric_columns = [
        "contributor_count", "submitted_row_count", "average_bay_count",
        "average_technician_count", "average_repair_orders", "average_hours_sold",
        "hours_per_repair_order", "hours_per_technician", "average_labour_sales_cad",
        "average_parts_sales_cad", "average_tire_sales_cad", "average_total_sales_cad",
        "sales_per_repair_order_cad",
    ]
    for column in numeric_columns:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    data["reporting_month"] = pd.to_datetime(data["reporting_month"], errors="coerce")
    data = data.dropna(subset=["reporting_month"]).copy()

    c1, c2, c3 = st.columns(3)
    with c1:
        geography_type = st.segmented_control(
            "Geographic view",
            ["national", "province"],
            default="national",
            format_func=lambda value: value.title(),
            key="member_pool_geography_type",
        )
    geography_options = sorted(
        data.loc[data["geography_type"] == geography_type, "geography_code"].dropna().unique()
    )
    if not geography_options:
        st.warning("No privacy-safe benchmarks are available for that geographic view yet.")
        return
    with c2:
        geography_code = st.selectbox(
            "Geography",
            geography_options,
            format_func=lambda code: "Canada" if code == "CA" else PROVINCE_NAMES.get(code, code),
            key="member_pool_geography",
        )
    shop_options = sorted(
        data.loc[
            (data["geography_type"] == geography_type)
            & (data["geography_code"] == geography_code),
            "shop_type",
        ].dropna().unique()
    )
    with c3:
        shop_type = st.selectbox("Shop type", shop_options, key="member_pool_shop_type")

    scoped = data[
        (data["geography_type"] == geography_type)
        & (data["geography_code"] == geography_code)
        & (data["shop_type"] == shop_type)
    ].sort_values("reporting_month")
    if scoped.empty:
        st.warning("No privacy-safe benchmark rows match that selection.")
        return
    latest = scoped.iloc[-1]
    latest_label = latest["reporting_month"].strftime("%B %Y")

    cards = st.columns(4)
    with cards[0]:
        metric_card(
            "Contributors",
            f"{int(latest['contributor_count']):,}",
            f"Independent contributors · {latest_label}",
        )
    with cards[1]:
        metric_card(
            "Hours / repair order",
            format_metric(latest["hours_per_repair_order"], "hours"),
            "Approved member data",
        )
    with cards[2]:
        metric_card(
            "Average monthly sales",
            format_metric(latest["average_total_sales_cad"], "cad"),
            "Per submitted shop-month row",
        )
    with cards[3]:
        metric_card(
            "Sales / repair order",
            format_metric(latest["sales_per_repair_order_cad"], "cad"),
            "Labour, parts and tire sales",
        )

    historical_performance = repo.performance_benchmarks()
    historical_ticket = historical_performance[
        (historical_performance["shop_type"] == shop_type)
        & (historical_performance["cohort"] == "All shops")
        & (historical_performance["metric_code"] == "hours_repair_order")
    ]
    if not historical_ticket.empty:
        historical_hours = float(historical_ticket.iloc[0]["value"])
        current_hours = float(latest["hours_per_repair_order"])
        change_percent = (
            (current_hours - historical_hours) / historical_hours * 100
            if historical_hours else 0
        )
        st.subheader("Current result versus the historical foundation")
        comparison_cards = st.columns(3)
        with comparison_cards[0]:
            metric_card(
                "Current member cohort",
                format_metric(current_hours, "hours"),
                f"Hours / repair order · {latest_label}",
            )
        with comparison_cards[1]:
            metric_card(
                "Historical AIA benchmark",
                format_metric(historical_hours, "hours"),
                "All shops · 2015",
            )
        with comparison_cards[2]:
            metric_card(
                "Change from foundation",
                f"{change_percent:+.1f}%",
                "Directional comparison of compatible measures",
            )

    trend1, trend2 = st.columns(2)
    with trend1:
        hours_fig = px.line(
            scoped,
            x="reporting_month",
            y="hours_per_repair_order",
            markers=True,
            title="Hours sold per repair order",
            labels={"reporting_month": "Month", "hours_per_repair_order": "Hours"},
        )
        hours_fig.update_traces(line_color="#1B5B83")
        chart(hours_fig)
    with trend2:
        sales_fig = px.bar(
            scoped,
            x="reporting_month",
            y="average_total_sales_cad",
            title="Average monthly sales per submitted row",
            labels={"reporting_month": "Month", "average_total_sales_cad": "CAD"},
            color_discrete_sequence=["#D7263D"],
        )
        chart(sales_fig)

    st.subheader(f"Sales mix · {latest_label}")
    sales_mix = pd.DataFrame({
        "Category": ["Labour", "Parts", "Tires"],
        "Average sales (CAD)": [
            latest["average_labour_sales_cad"],
            latest["average_parts_sales_cad"],
            latest["average_tire_sales_cad"],
        ],
    })
    mix_fig = px.bar(
        sales_mix,
        x="Category",
        y="Average sales (CAD)",
        color="Category",
        text_auto="$.3s",
        color_discrete_sequence=["#123E5A", "#1B5B83", "#D7263D"],
    )
    chart(mix_fig)

    table_columns = [
        "reporting_month", "geography_code", "shop_type", "contributor_count",
        "average_repair_orders", "average_hours_sold", "hours_per_repair_order",
        "average_total_sales_cad", "sales_per_repair_order_cad", "refreshed_at",
    ]
    export_data = scoped[[column for column in table_columns if column in scoped.columns]].copy()
    export_data["reporting_month"] = export_data["reporting_month"].dt.strftime("%Y-%m")
    st.subheader("Privacy-safe aggregate table")
    st.dataframe(export_data, hide_index=True, width="stretch")
    e1, e2 = st.columns(2)
    with e1:
        st.download_button(
            "Download CSV",
            csv_bytes(export_data),
            "aia_member_data_pool.csv",
            "text/csv",
            width="stretch",
        )
    with e2:
        st.download_button(
            "Download Excel",
            excel_report_bytes(
                export_data,
                title="AIA Canada member data pool",
                filters={
                    "Geography": "Canada" if geography_code == "CA" else geography_code,
                    "Shop type": shop_type,
                    "Privacy threshold": "Minimum 5 independent contributors",
                },
            ),
            "aia_member_data_pool.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )


def _demographic_display(item: dict | None) -> str:
    if not item:
        return "—"
    value = float(item["value"])
    unit = item.get("unit")
    if unit == "cad":
        return f"${value:,.0f}"
    if unit == "percent":
        return f"{value:,.1f}%"
    if unit == "years":
        return f"{value:,.1f} years"
    if unit == "people_per_square_km":
        return f"{value:,.1f}/km²"
    if item.get("metric_code") == "average_household_size":
        return f"{value:,.1f}"
    return f"{value:,.0f}"


def _demographic_value(metrics: dict[str, dict], code: str) -> float | None:
    item = metrics.get(code)
    if not item or item.get("value") is None:
        return None
    return float(item["value"])


def demographics_page(repo, user: PortalUser) -> None:
    page_intro(
        "Canadian market context",
        "Connect auto care data to the communities it serves",
        "Explore official population, household, income, age and workforce context by province, municipality and three-character postal region.",
    )
    st.caption(
        "Demographic values are from the 2021 Census Profile. Income measures refer to 2020 and are context—not current consumer spending estimates."
    )

    level_label = st.segmented_control(
        "Geographic level",
        list(DEMOGRAPHIC_LEVELS),
        default="Province or territory",
    )
    geo_level = DEMOGRAPHIC_LEVELS[level_label]
    province_code = None
    search_query = None
    if geo_level == "province":
        geographies = repo.demographic_geographies(geo_level, limit=25)
    else:
        province_code = st.selectbox(
            "Province or territory",
            list(PROVINCE_NAMES),
            format_func=lambda code: PROVINCE_NAMES[code],
        )
        search_label = "Search municipality" if geo_level == "municipality" else "Search postal region"
        search_query = st.text_input(
            search_label,
            placeholder="Start typing Ottawa, Montréal or K1A",
            help="Enter at least two characters. Results are filtered in the database and limited to 100 matches.",
            key=f"demographic_search_{geo_level}",
        ).strip()
        if len(search_query) < 2:
            st.info("Enter at least two characters to search. This replaces the previous long dropdown list.")
            return
        geographies = repo.demographic_geographies(
            geo_level,
            province_code,
            search_query=search_query,
            limit=100,
        )
    if not geographies:
        st.info(
            "No matching geography was found. Check the province and spelling, or try a shorter search."
        )
        if user.is_admin and search_query is None:
            st.code("python scripts/sync_statcan_demographics.py", language="bash")
        return

    if len(geographies) == 100:
        st.caption("Showing the first 100 matches. Add more letters to narrow the results.")

    labels = {
        f"{item.get('geo_name')} · {item.get('geo_code')}": item
        for item in geographies
    }
    selected_label = st.selectbox(
        "Community or region",
        labels,
        help="Postal regions use the first three postal-code characters only; full postal codes are not stored.",
    )
    selected = labels[selected_label]
    observations = repo.demographic_observations(selected["geo_uid"])
    if not observations:
        st.warning("This geography has no loaded observations. Ask an administrator to refresh the source data.")
        return
    metrics = {item["metric_code"]: item for item in observations}

    cards = st.columns(5)
    highlights = [
        ("Population", "population_2021"),
        ("Five-year growth", "population_growth_2016_2021"),
        ("Median age", "median_age"),
        ("After-tax household income", "median_after_tax_household_income"),
        ("Employment rate", "employment_rate"),
    ]
    for column, (label, code) in zip(cards, highlights):
        with column:
            item = metrics.get(code)
            period = item.get("reference_period", "") if item else ""
            metric_card(label, _demographic_display(item), f"Reference period: {period}" if period else "Not available")

    population_codes = ["population_2016", "population_2021"]
    population_rows = [metrics[code] for code in population_codes if code in metrics]
    income_codes = [
        "median_household_income",
        "median_after_tax_household_income",
        "average_after_tax_household_income",
    ]
    income_rows = [metrics[code] for code in income_codes if code in metrics]
    left, right = st.columns(2, gap="large")
    with left:
        if population_rows:
            population = pd.DataFrame(population_rows)
            fig = px.bar(
                population,
                x="reference_period",
                y="value",
                text_auto=",.0f",
                title="Population change",
                labels={"reference_period": "Census year", "value": "Population"},
                color_discrete_sequence=["#1B5B83"],
            )
            chart(fig)
    with right:
        if income_rows:
            income = pd.DataFrame(income_rows)
            fig = px.bar(
                income,
                x="label",
                y="value",
                text_auto=",.0f",
                title="Household income context",
                labels={"label": "", "value": "2020 dollars"},
                color="metric_code",
                color_discrete_sequence=["#123E5A", "#D7263D"],
            )
            fig.update_traces(texttemplate="$%{y:,.0f}")
            chart(fig)

    age = pd.DataFrame([
        metrics[code]
        for code in ["age_0_14", "age_15_64", "age_65_plus"]
        if code in metrics
    ])
    if not age.empty:
        total_age_population = age["value"].sum()
        age["share"] = age["value"] / total_age_population * 100
        fig = px.bar(
            age,
            x="label",
            y="share",
            text_auto=".1f",
            title="Age composition",
            labels={"label": "", "share": "Share of population (%)"},
            color="metric_code",
            color_discrete_sequence=["#6F9CB7", "#1B5B83", "#D7263D"],
        )
        fig.update_traces(texttemplate="%{y:.1f}%")
        chart(fig)

    workforce = pd.DataFrame([
        metrics[code]
        for code in ["participation_rate", "employment_rate", "unemployment_rate"]
        if code in metrics
    ])
    if not workforce.empty:
        fig = px.bar(
            workforce,
            x="label",
            y="value",
            text_auto=".1f",
            title="Workforce indicators",
            labels={"label": "", "value": "Percent"},
            color="metric_code",
            color_discrete_sequence=["#1B5B83", "#3D789B", "#D7263D"],
        )
        chart(fig)

    st.subheader("Linked auto care market view")
    auto_shop_type = st.selectbox(
        "Auto care shop type",
        ["Mechanical", "Tire"],
        key="demographic_auto_shop_type",
    )
    aia_region = AIA_REGION_BY_PROVINCE.get(selected["province_code"], "Canada")
    member_selection = select_member_benchmark(
        repo.member_benchmark_aggregates(),
        province_code=selected["province_code"],
        shop_type=auto_shop_type,
    )
    current_auto_record = (
        member_selection.record
        if current_data_enabled() and member_selection.available
        else None
    )
    if current_auto_record is not None:
        current_period = pd.to_datetime(current_auto_record["reporting_month"]).strftime("%B %Y")
        member_scope = (
            "Canada fallback"
            if member_selection.used_national_fallback
            else PROVINCE_NAMES[selected["province_code"]]
        )
        st.markdown("#### Best available current auto care context")
        current_cards = st.columns(5)
        current_values = [
            ("Contributors", f"{int(current_auto_record['contributor_count']):,}"),
            ("Repair orders / month", format_metric(current_auto_record["average_repair_orders"], "count")),
            ("Hours / repair order", format_metric(current_auto_record["hours_per_repair_order"], "hours")),
            ("Average monthly sales", format_metric(current_auto_record["average_total_sales_cad"], "cad")),
            ("Sales / repair order", format_metric(current_auto_record["sales_per_repair_order_cad"], "cad")),
        ]
        for column, (label, value) in zip(current_cards, current_values):
            with column:
                metric_card(label, value, f"{member_scope} · {current_period}")
        if member_selection.used_national_fallback:
            st.info(
                f"No {PROVINCE_NAMES[selected['province_code']]} cohort has reached the privacy "
                "threshold, so the qualified national member cohort is used as the current fallback."
            )
        else:
            st.success(
                f"This demographic selection is directly linked to the qualified "
                f"{PROVINCE_NAMES[selected['province_code']]} member cohort."
            )
    elif current_data_enabled():
        st.info(
            "No matching current-member cohort has reached the privacy threshold. The historical AIA "
            "regional benchmark below is the best available auto care source for this selection."
        )

    st.markdown("#### Historical benchmark foundation")
    benchmark = repo.segment_benchmarks()
    geography_type = "national" if aia_region == "Canada" else "region"
    scoped = benchmark[
        (benchmark["geography_type"] == geography_type)
        & (benchmark["geography"] == aia_region)
        & (benchmark["segment"] == auto_shop_type)
        & (benchmark["affiliation"] == "All")
    ]
    st.caption(
        f"{selected['geo_name']} maps to the {aia_region} AIA benchmark region through "
        f"{PROVINCE_NAMES[selected['province_code']]}. Municipality and FSA selections inherit the "
        "provincial region; the AIA values are not local estimates."
    )
    linked_benchmark = None
    if not scoped.empty:
        shop_sizes = list(dict.fromkeys(scoped["shop_size"].dropna()))
        shop_size = st.selectbox("Historical AIA shop-size cohort", shop_sizes)
        linked_benchmark = scoped[scoped["shop_size"] == shop_size].iloc[0]
        benchmark_cards = st.columns(5)
        benchmark_values = [
            ("Repair orders / year", f"{linked_benchmark['average_repair_orders_year']:,.0f}"),
            ("Hours / repair order", f"{linked_benchmark['average_hours_repair_order']:.1f}"),
            ("Hours sold / tech / day", f"{linked_benchmark['hours_sold_technician_day']:.1f}"),
            ("Service advisor", f"{linked_benchmark['percentage_with_service_advisor']:.0f}%"),
            ("Regional sample", f"{linked_benchmark['sample_size']:,.0f}"),
        ]
        for column, (label, value) in zip(benchmark_cards, benchmark_values):
            with column:
                metric_card(label, value, f"{aia_region} · {shop_size} · 2015")
        st.caption(
            "Direct AIA linkage: observed historical regional benchmark values from the 2015 survey. "
            "They provide comparison context, not a current local-market forecast."
        )
        if st.button("Open this region in Benchmark Explorer", type="primary"):
            st.session_state["market_bridge_context"] = {
                "region": aia_region,
                "geography": selected["geo_name"],
                "province_code": selected["province_code"],
                "scope": "National / affiliation" if aia_region == "Canada" else "Regional comparison",
            }
            st.session_state["next_portal_page"] = "Benchmark Explorer"
            st.rerun()

    occupied_households = _demographic_value(metrics, "occupied_private_dwellings")
    population_growth = _demographic_value(metrics, "population_growth_2016_2021")
    age_65_plus = _demographic_value(metrics, "age_65_plus")
    population = _demographic_value(metrics, "population_2021")
    if occupied_households is not None:
        st.subheader("Auto care demand scenario")
        st.warning(
            "Directional scenario only—not a forecast. Occupied households come from the 2021 Census; "
            "vehicle ownership, annual spending, shop count and target share are user-controlled assumptions."
        )
        with st.container(border=True):
            a1, a2, a3, a4 = st.columns(4)
            with a1:
                vehicles_per_household = st.number_input(
                    "Vehicles / household (assumption)",
                    min_value=0.0,
                    max_value=5.0,
                    value=1.5,
                    step=0.1,
                )
            with a2:
                annual_spend_per_vehicle = st.number_input(
                    "Annual auto care / vehicle (assumption)",
                    min_value=0.0,
                    value=1200.0,
                    step=100.0,
                    format="%.0f",
                )
            with a3:
                shops_serving_market = st.number_input(
                    "Shops serving market (assumption)",
                    min_value=1,
                    value=25,
                    step=1,
                )
            with a4:
                target_share_percent = st.number_input(
                    "Target market share (assumption)",
                    min_value=0.0,
                    max_value=100.0,
                    value=2.0,
                    step=0.5,
                )

        scenario = calculate_market_scenario(
            occupied_households=occupied_households,
            vehicles_per_household=vehicles_per_household,
            annual_spend_per_vehicle=annual_spend_per_vehicle,
            shops_serving_market=int(shops_serving_market),
            target_share_percent=target_share_percent,
        )
        scenario_values = [
            ("Estimated vehicle base", f"{scenario.estimated_vehicles:,.0f}", "Households × vehicles assumption"),
            ("Annual auto care pool", f"${scenario.annual_auto_care_pool:,.0f}", "Vehicles × spending assumption"),
            ("Pool / serving shop", f"${scenario.annual_pool_per_shop:,.0f}", "Scenario pool ÷ assumed shops"),
            ("Revenue at target share", f"${scenario.target_share_revenue:,.0f}", "Scenario pool × target share"),
        ]
        if current_auto_record is not None:
            scenario_values.append((
                "Current annualized shop sales",
                f"${float(current_auto_record['average_total_sales_cad']) * 12:,.0f}",
                "Qualified monthly member average × 12",
            ))
        scenario_cards = st.columns(len(scenario_values))
        for column, values in zip(scenario_cards, scenario_values):
            with column:
                metric_card(*values)

        signals = [f"The scenario starts with {occupied_households:,.0f} occupied households (2021)."]
        if population_growth is not None:
            signals.append(
                f"Population changed {population_growth:+.1f}% from 2016 to 2021; use this as historical "
                "growth context, not a current projection."
            )
        if age_65_plus is not None and population:
            signals.append(
                f"Residents aged 65+ represented {age_65_plus / population * 100:.1f}% of the 2021 population; "
                "this is planning context, not a vehicle-ownership proxy."
            )
        if current_auto_record is not None:
            annualized_member_sales = float(current_auto_record["average_total_sales_cad"]) * 12
            signals.append(
                f"The latest qualified member cohort annualizes to ${annualized_member_sales:,.0f} "
                "in average shop sales; compare it with the scenario pool per serving shop without "
                "treating either value as a forecast."
            )
        st.markdown("#### Planning signals\n\n" + "\n".join(f"- {signal}" for signal in signals))

        export_rows = [
            {"basis": "Statistics Canada 2021", "measure": "Occupied households", "value": occupied_households},
            {"basis": "User assumption", "measure": "Vehicles per household", "value": vehicles_per_household},
            {"basis": "User assumption", "measure": "Annual auto care per vehicle (CAD)", "value": annual_spend_per_vehicle},
            {"basis": "User assumption", "measure": "Shops serving market", "value": shops_serving_market},
            {"basis": "User assumption", "measure": "Target market share (%)", "value": target_share_percent},
            {"basis": "Calculated scenario", "measure": "Estimated vehicle base", "value": scenario.estimated_vehicles},
            {"basis": "Calculated scenario", "measure": "Annual auto care pool (CAD)", "value": scenario.annual_auto_care_pool},
            {"basis": "Calculated scenario", "measure": "Pool per serving shop (CAD)", "value": scenario.annual_pool_per_shop},
            {"basis": "Calculated scenario", "measure": "Revenue at target share (CAD)", "value": scenario.target_share_revenue},
        ]
        if linked_benchmark is not None:
            export_rows.extend([
                {"basis": f"AIA 2015 · {aia_region}", "measure": "Repair orders per year", "value": linked_benchmark["average_repair_orders_year"]},
                {"basis": f"AIA 2015 · {aia_region}", "measure": "Hours per repair order", "value": linked_benchmark["average_hours_repair_order"]},
                {"basis": f"AIA 2015 · {aia_region}", "measure": "Hours sold per technician per day", "value": linked_benchmark["hours_sold_technician_day"]},
            ])
        if current_auto_record is not None:
            member_basis = (
                f"Approved member data · {member_selection.geography_label} · "
                f"{pd.to_datetime(current_auto_record['reporting_month']).strftime('%Y-%m')}"
            )
            export_rows.extend([
                {"basis": member_basis, "measure": "Contributors", "value": current_auto_record["contributor_count"]},
                {"basis": member_basis, "measure": "Average monthly repair orders", "value": current_auto_record["average_repair_orders"]},
                {"basis": member_basis, "measure": "Hours per repair order", "value": current_auto_record["hours_per_repair_order"]},
                {"basis": member_basis, "measure": "Average monthly sales (CAD)", "value": current_auto_record["average_total_sales_cad"]},
                {"basis": member_basis, "measure": "Sales per repair order (CAD)", "value": current_auto_record["sales_per_repair_order_cad"]},
            ])
        st.download_button(
            "Download linked market scenario",
            csv_bytes(pd.DataFrame(export_rows)),
            file_name=f"aia_linked_market_scenario_{selected['geo_code']}.csv",
            mime="text/csv",
        )

    detail = pd.DataFrame(observations)[
        ["category", "label", "value", "unit", "reference_period", "source_characteristic_name"]
    ]
    st.subheader("All demographic measures")
    st.dataframe(detail, hide_index=True, width="stretch")
    st.download_button(
        "Download demographic CSV",
        csv_bytes(detail),
        file_name=f"aia_demographics_{selected['geo_code']}.csv",
        mime="text/csv",
    )
    retrieved = max((item.get("retrieved_at", "") for item in observations), default="")
    st.caption(
        f"Source: Statistics Canada, 2021 Census Profile · Flow {selected['source_flow']}"
        + (f" · Retrieved {retrieved[:10]}" if retrieved else "")
    )
    st.link_button(
        "View Statistics Canada Census Profile methodology",
        "https://www12.statcan.gc.ca/wds-sdw/2021profile-profil2021-eng.cfm",
    )


def resources_page(repo, user: PortalUser) -> None:
    page_intro(
        "Member resources",
        "Research and guidance in one place",
        "A CMS-managed library for reports, methodology notes, data definitions and member tools.",
    )
    resources = repo.resources(include_unpublished=False)
    sections = ["All"] + sorted({item.get("section", "Other") for item in resources})
    section = st.selectbox("Section", sections, label_visibility="collapsed")
    visible = resources if section == "All" else [item for item in resources if item.get("section") == section]
    if not visible:
        st.info("No published resources are available in this section.")
        return
    for index in range(0, len(visible), 3):
        columns = st.columns(3)
        for column, item in zip(columns, visible[index:index + 3]):
            with column:
                with st.container(border=True):
                    st.caption(item.get("section", "Resource").upper())
                    st.subheader(item.get("title", "Untitled"))
                    st.write(item.get("summary", ""))
                    st.caption(item.get("resource_type", "Resource"))
                    delivery_type = resource_delivery_type(item)
                    url = str(item.get("external_url") or "").strip()
                    content = str(item.get("content") or "").strip()
                    if delivery_type == DELIVERY_EXTERNAL and url:
                        try:
                            safe_url = validate_external_url(url)
                        except ValueError:
                            st.caption("This external resource link needs administrator review.")
                        else:
                            st.link_button("Open external resource", safe_url, width="stretch")
                    elif content:
                        with st.popover("Read in portal", width="stretch"):
                            render_resource_content(content, resource_content_format(item))
                    else:
                        st.caption("Resource details are being prepared by AIA Canada.")


def show_shop_validation(result) -> None:
    for error in result.errors:
        st.error(error)
    for warning in result.warnings:
        st.warning(warning)
    if result.valid:
        st.success(f"Validation passed · {len(result.data):,} row(s)")


def shop_contribution_form(
    repo,
    user: PortalUser,
    data: pd.DataFrame,
    *,
    filename: str,
    form_key: str,
    clear_manual_draft: bool = False,
) -> None:
    period_start = pd.to_datetime(data["reporting_month"].min()).date().replace(day=1)
    period_end = (pd.to_datetime(data["reporting_month"].max()) + pd.offsets.MonthEnd(0)).date()
    st.caption(f"Reporting period: {period_start:%B %Y} to {period_end:%B %Y}")
    with st.form(form_key):
        organization = st.text_input(
            "Contributing organization",
            value=user.organization,
            key=f"{form_key}_organization",
        )
        notes = st.text_area(
            "Notes for the AIA Canada reviewer",
            placeholder="Optional context, exclusions or corrections",
            key=f"{form_key}_notes",
        )
        attest = st.checkbox(
            "I confirm this submission contains no customer, employee, vehicle or invoice-level "
            "identifiers and I am authorized to submit it.",
            key=f"{form_key}_attest",
        )
        submit = st.form_submit_button("Submit for approval", type="primary")
    if not submit:
        return
    if not organization.strip():
        st.error("Enter the contributing organization.")
        return
    if not attest:
        st.error("Confirm the data and authorization statement before submitting.")
        return
    try:
        normalized_payload = csv_bytes(data)
        record = repo.submit_contribution(
            user=user,
            organization=organization.strip(),
            period_start=period_start,
            period_end=period_end,
            filename=filename,
            payload=normalized_payload,
            row_count=len(data),
            notes=notes.strip(),
        )
        if clear_manual_draft:
            st.session_state["member_manual_shop_rows"] = []
        st.success(f"Submission received · reference {record['id']}")
        st.info("Status: Submitted. The data remains private until reviewed by AIA Canada.")
    except Exception as exc:
        st.error(f"The submission could not be saved: {exc}")


def manual_shop_row_form(user: PortalUser) -> tuple[bool, dict[str, object]]:
    default_province = user.province if user.province in PROVINCE_NAMES else "ON"
    province_options = list(PROVINCE_NAMES)
    with st.form("manual_shop_row_form"):
        st.markdown("#### Add one reporting month")
        st.caption("Add more months to the draft before submitting if needed.")
        c1, c2, c3 = st.columns(3)
        with c1:
            reporting_month = st.date_input(
                "Reporting month",
                value=date.today().replace(day=1),
                max_value=date.today(),
                key="manual_reporting_month",
            )
            province = st.selectbox(
                "Province or territory",
                province_options,
                index=province_options.index(default_province),
                format_func=lambda code: f"{code} · {PROVINCE_NAMES[code]}",
                key="manual_province",
            )
            shop_type = st.selectbox(
                "Shop type",
                ["Mechanical", "Tire", "Collision", "Other"],
                key="manual_shop_type",
            )
        with c2:
            municipality = st.text_input(
                "Municipality (optional)",
                max_chars=100,
                key="manual_municipality",
            )
            forward_sortation_area = st.text_input(
                "Postal region / FSA (optional)",
                max_chars=3,
                placeholder="K1A",
                help="Enter only the first three postal-code characters—never a full postal code.",
                key="manual_fsa",
            )
            bay_count = st.number_input(
                "Service bays",
                min_value=1,
                value=1,
                step=1,
                key="manual_bay_count",
            )
        with c3:
            technician_count = st.number_input(
                "Technicians",
                min_value=0.1,
                value=1.0,
                step=0.5,
                key="manual_technician_count",
            )
            repair_orders = st.number_input(
                "Repair orders",
                min_value=0,
                value=0,
                step=1,
                key="manual_repair_orders",
            )
            hours_sold = st.number_input(
                "Hours sold",
                min_value=0.0,
                value=0.0,
                step=0.5,
                key="manual_hours_sold",
            )

        sales = st.columns(3)
        with sales[0]:
            labour_sales_cad = st.number_input(
                "Labour sales (CAD)", min_value=0.0, value=0.0, step=100.0,
                key="manual_labour_sales",
            )
        with sales[1]:
            parts_sales_cad = st.number_input(
                "Parts sales (CAD)", min_value=0.0, value=0.0, step=100.0,
                key="manual_parts_sales",
            )
        with sales[2]:
            tire_sales_cad = st.number_input(
                "Tire sales (CAD)", min_value=0.0, value=0.0, step=100.0,
                key="manual_tire_sales",
            )
        add_month = st.form_submit_button("Add validated month", type="primary")

    return add_month, {
        "reporting_month": reporting_month.strftime("%Y-%m"),
        "province": province,
        "shop_type": shop_type,
        "bay_count": bay_count,
        "technician_count": technician_count,
        "repair_orders": repair_orders,
        "hours_sold": hours_sold,
        "labour_sales_cad": labour_sales_cad,
        "parts_sales_cad": parts_sales_cad,
        "tire_sales_cad": tire_sales_cad,
        "municipality": municipality.strip(),
        "forward_sortation_area": forward_sortation_area.strip().upper(),
    }


def contribute_page(repo, user: PortalUser) -> None:
    page_intro(
        "Member contribution",
        "Contribute shop data securely",
        "Upload the standard template or enter monthly shop data manually. AIA Canada reviews every "
        "submission before any data is approved for aggregation.",
    )
    s1, s2, s3 = st.columns(3)
    with s1:
        metric_card("1 · Prepare", "Anonymize", "No customer, employee, vehicle or invoice identifiers")
    with s2:
        metric_card("2 · Validate", "Automatic", "Structure, date, province and numeric checks")
    with s3:
        metric_card("3 · Review", "AIA Canada", "Submitted data is not published automatically")

    st.subheader("Download the standard template")
    template = pd.read_csv(PROJECT_ROOT / "data" / "member_shop_upload_template.csv")
    d1, d2 = st.columns(2)
    with d1:
        st.download_button(
            "CSV template", read_template_bytes(), "aia_member_shop_template.csv", "text/csv",
            width="stretch",
        )
    with d2:
        st.download_button(
            "Excel template",
            excel_report_bytes(template, title="AIA Canada member shop upload template"),
            "aia_member_shop_template.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )

    upload_tab, manual_tab = st.tabs(["Upload CSV or Excel", "Enter data manually"])
    with upload_tab:
        st.markdown("#### Validate and submit a file")
        upload = st.file_uploader(
            "Shop data file",
            type=["csv", "xlsx"],
            help=f"Maximum {settings.max_upload_mb} MB",
            key="member_shop_upload",
        )
        if upload:
            payload = upload.getvalue()
            if len(payload) > settings.max_upload_mb * 1024 * 1024:
                st.error(f"The file exceeds the {settings.max_upload_mb} MB limit.")
            else:
                try:
                    frame = read_uploaded_table(payload, upload.name)
                    result = validate_shop_upload(frame)
                except Exception as exc:
                    st.error(f"Could not read the file: {exc}")
                else:
                    show_shop_validation(result)
                    if result.valid:
                        assert result.data is not None
                        st.dataframe(result.data.head(20), hide_index=True, width="stretch")
                        shop_contribution_form(
                            repo,
                            user,
                            result.data,
                            filename=f"{Path(upload.name).stem}_validated.csv",
                            form_key="upload_contribution_form",
                        )

    with manual_tab:
        manual_rows = st.session_state.setdefault("member_manual_shop_rows", [])
        add_month, manual_row = manual_shop_row_form(user)
        if add_month:
            row_result = validate_shop_upload(pd.DataFrame([manual_row]))
            show_shop_validation(row_result)
            if row_result.valid:
                assert row_result.data is not None
                manual_rows.append(row_result.data.iloc[0].to_dict())
                st.success(f"Month added · {len(manual_rows):,} month(s) in the current draft.")

        if manual_rows:
            manual_result = validate_shop_upload(pd.DataFrame(manual_rows))
            st.markdown("#### Current manual submission")
            show_shop_validation(manual_result)
            if manual_result.valid:
                assert manual_result.data is not None
                st.dataframe(manual_result.data, hide_index=True, width="stretch")
                st.download_button(
                    "Download current draft CSV",
                    csv_bytes(manual_result.data),
                    file_name="aia_manual_shop_data_draft.csv",
                    mime="text/csv",
                    width="stretch",
                )
                edit1, edit2 = st.columns(2)
                if edit1.button("Remove last month", width="stretch"):
                    manual_rows.pop()
                    st.rerun()
                if edit2.button("Clear draft", width="stretch"):
                    st.session_state["member_manual_shop_rows"] = []
                    st.rerun()
                shop_contribution_form(
                    repo,
                    user,
                    manual_result.data,
                    filename="aia_manual_shop_submission.csv",
                    form_key="manual_contribution_form",
                    clear_manual_draft=True,
                )
        else:
            st.info("Add a reporting month above to begin a manual submission.")

    own = repo.contributions(user)
    if own:
        st.subheader("Your recent submissions")
        st.dataframe(pd.DataFrame(own), hide_index=True, width="stretch")


def dataset_metadata_fields(prefix: str) -> dict[str, object]:
    c1, c2 = st.columns(2)
    with c1:
        title = st.text_input("Dataset title", key=f"{prefix}_title")
        slug = st.text_input(
            "Slug",
            placeholder="2026-shop-productivity",
            help="Lowercase letters, numbers and hyphens only. Each dataset needs a unique slug.",
            key=f"{prefix}_slug",
        )
    with c2:
        data_year = st.number_input(
            "Data year",
            min_value=1900,
            max_value=date.today().year,
            value=date.today().year,
            key=f"{prefix}_data_year",
        )
    description = st.text_area(
        "Source and methodology description",
        help="Identify the source, population, collection period and important limitations.",
        key=f"{prefix}_description",
    )
    return {
        "title": title.strip(),
        "slug": slug.strip(),
        "data_year": int(data_year),
        "description": description.strip(),
    }


def show_dataset_validation(result) -> None:
    for error in result.errors:
        st.error(error)
    for warning in result.warnings:
        st.warning(warning)
    if result.valid:
        st.success(f"Validation passed · {len(result.data):,} row(s) are ready to stage.")


def manual_segment_row_form() -> tuple[bool, dict[str, object]]:
    with st.form("manual_segment_row_form"):
        st.markdown("#### Add a regional or shop-size benchmark row")
        c1, c2, c3 = st.columns(3)
        with c1:
            segment = st.selectbox("Segment", ["Mechanical", "Tire"])
            shop_size = st.text_input("Shop size", placeholder="1-3 bays")
        with c2:
            geography_type = st.selectbox("Geography type", ["region", "national"])
            geography = st.text_input("Geography", placeholder="Ontario or Canada")
        with c3:
            affiliation = st.text_input("Affiliation", value="All")
            sample_size = st.number_input("Sample size", min_value=0, value=None, step=1)

        values: dict[str, object] = {}
        metric_columns = st.columns(3)
        for index, metric_code in enumerate(SEGMENT_METRIC_COLUMNS):
            label, unit = METRICS[metric_code]
            options: dict[str, object] = {"value": None, "step": 1.0 if unit == "percent" else 0.1}
            if unit == "percent":
                options.update({"min_value": 0.0, "max_value": 100.0})
            else:
                options.update({"min_value": 0.0})
            with metric_columns[index % 3]:
                values[metric_code] = st.number_input(label, key=f"manual_{metric_code}", **options)

        source_page = st.number_input(
            "Source page (optional)", min_value=1, value=None, step=1, key="manual_segment_source_page"
        )
        add_row = st.form_submit_button("Add validated row", type="primary")

    row = {
        "segment": segment,
        "shop_size": shop_size,
        "geography_type": geography_type,
        "geography": geography,
        "affiliation": affiliation,
        "sample_size": sample_size,
        **values,
        "source_page": source_page,
    }
    return add_row, row


def manual_performance_row_form() -> tuple[bool, dict[str, object]]:
    with st.form("manual_performance_row_form"):
        st.markdown("#### Add a performance cohort benchmark row")
        c1, c2 = st.columns(2)
        with c1:
            shop_type = st.selectbox("Shop type", ["Mechanical", "Tire"])
            cohort = st.text_input("Cohort", placeholder="All shops")
            metric_code = st.text_input("Metric code", placeholder="hours_repair_order")
            metric_label = st.text_input("Metric label", placeholder="Hours sold per repair order")
        with c2:
            value = st.number_input("Value", min_value=0.0, value=0.0, step=0.1)
            unit = st.selectbox("Unit", PERFORMANCE_UNITS)
            sort_order = st.number_input("Sort order", min_value=0, value=10, step=10)
            source_page = st.number_input(
                "Source page (optional)", min_value=1, value=None, step=1,
                key="manual_performance_source_page",
            )
        add_row = st.form_submit_button("Add validated row", type="primary")

    return add_row, {
        "shop_type": shop_type,
        "cohort": cohort,
        "metric_code": metric_code,
        "metric_label": metric_label,
        "value": value,
        "unit": unit,
        "sort_order": sort_order,
        "source_page": source_page,
    }


def admin_page(repo, user: PortalUser) -> None:
    page_intro(
        "Administration",
        "Govern the portal from one workspace",
        "Manage member access, review contributions, control dataset lifecycle and publish resources.",
    )
    profiles = repo.profiles()
    contributions = repo.contributions(user, include_all=True)
    a1, a2, a3, a4 = st.columns(4)
    with a1:
        metric_card("Members", str(len(profiles)), "All portal profiles")
    with a2:
        pending_members = sum(profile.get("membership_status") == "pending" for profile in profiles)
        metric_card("Pending access", str(pending_members), "Require AIA Canada review")
    with a3:
        pending_data = sum(item.get("status") == "submitted" for item in contributions)
        metric_card("Data queue", str(pending_data), "Member submissions awaiting review")
    with a4:
        metric_card("Published datasets", "1", "Historical productivity benchmark")

    users_tab, submissions_tab, datasets_tab, cms_tab = st.tabs([
        "Users & access", "Contribution queue", "Datasets", "Content CMS"
    ])
    with users_tab:
        st.subheader("Member directory")
        user_notice = st.session_state.pop("admin_user_notice", None)
        if user_notice:
            st.success(user_notice)

        with st.expander("Add user", expanded=not profiles):
            st.caption(
                "Create a Supabase login with a temporary password. Share it through an approved "
                "secure channel and have the user replace it as soon as password reset is available."
            )
            with st.form("create_user_form", clear_on_submit=True):
                new_email = st.text_input("Email", key="new_user_email")
                new_full_name = st.text_input("Full name", key="new_user_full_name")
                create1, create2 = st.columns(2)
                with create1:
                    new_organization = st.text_input("Organization", key="new_user_organization")
                    new_province = st.text_input("Province / territory", key="new_user_province")
                    new_role = st.selectbox(
                        "Portal role", ["member", "analyst", "admin"], key="new_user_role"
                    )
                with create2:
                    new_status = st.selectbox(
                        "Membership status", ["pending", "active", "suspended"],
                        key="new_user_status",
                    )
                    new_password = st.text_input(
                        "Temporary password", type="password", key="new_user_password",
                        help="Use 10 to 128 characters and share it only through a secure channel.",
                    )
                    confirm_password = st.text_input(
                        "Confirm temporary password", type="password", key="confirm_new_user_password"
                    )
                create_user = st.form_submit_button("Create user", type="primary")

            if create_user:
                if not new_email.strip() or not new_full_name.strip():
                    st.error("Email and full name are required.")
                elif len(new_password) < 10 or len(new_password) > 128:
                    st.error("Temporary password must be 10 to 128 characters.")
                elif new_password != confirm_password:
                    st.error("Temporary passwords do not match.")
                else:
                    try:
                        repo.create_user(
                            email=new_email.strip(),
                            password=new_password,
                            full_name=new_full_name.strip(),
                            organization=new_organization.strip(),
                            province=new_province.strip(),
                            membership_status=new_status,
                            role=new_role,
                        )
                        st.session_state.admin_user_notice = (
                            f"{new_full_name.strip()} was created. Share the temporary password securely."
                        )
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not create the user: {exc}")

        st.dataframe(pd.DataFrame(profiles), hide_index=True, width="stretch")
        if profiles:
            labels = {
                f"{p.get('full_name') or p.get('email') or 'Unnamed user'} · "
                f"{p.get('email') or p.get('id')}": p
                for p in profiles
            }
            selected_label = st.selectbox("User", labels)
            selected = labels[selected_label]
            editing_self = selected["id"] == user.id
            with st.form("user_admin_form"):
                email = st.text_input("Email", value=selected.get("email", ""))
                full_name = st.text_input("Full name", value=selected.get("full_name", ""))
                c1, c2 = st.columns(2)
                with c1:
                    organization = st.text_input("Organization", value=selected.get("organization", ""))
                    membership_status = st.selectbox(
                        "Membership status", ["pending", "active", "suspended"],
                        index=["pending", "active", "suspended"].index(selected.get("membership_status", "pending")),
                        disabled=editing_self,
                    )
                with c2:
                    province = st.text_input("Province / territory", value=selected.get("province", ""))
                    role = st.selectbox(
                        "Portal role", ["member", "analyst", "admin"],
                        index=["member", "analyst", "admin"].index(selected.get("role", "member")),
                        disabled=editing_self,
                    )
                if editing_self:
                    st.caption("For safety, you cannot demote or suspend your own administrator account.")
                save = st.form_submit_button("Save user", type="primary")
            if save:
                try:
                    repo.update_user(
                        selected["id"],
                        email=email.strip(),
                        full_name=full_name.strip(),
                        organization=organization.strip(),
                        province=province.strip(),
                        membership_status=membership_status,
                        role=role,
                    )
                    st.session_state.admin_user_notice = "User details and access were updated."
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not update the user: {exc}")

            with st.expander("Delete user permanently"):
                st.warning(
                    "This permanently removes the Supabase login, portal profile, private contributions "
                    "and uploaded contribution files. This cannot be undone."
                )
                if editing_self:
                    st.info("You cannot delete the account you are currently using.")
                confirmation = st.text_input(
                    "Type DELETE to confirm",
                    key=f"delete_user_confirmation_{selected['id']}",
                    disabled=editing_self,
                )
                delete_user = st.button(
                    "Permanently delete user",
                    key=f"delete_user_{selected['id']}",
                    disabled=editing_self,
                )
                if delete_user:
                    if confirmation != "DELETE":
                        st.error("Type DELETE exactly before continuing.")
                    else:
                        try:
                            deleted_name = selected.get("full_name") or selected.get("email") or "User"
                            repo.delete_user(selected["id"])
                            st.session_state.admin_user_notice = f"{deleted_name} was permanently deleted."
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Could not delete the user: {exc}")

    with submissions_tab:
        st.subheader("Private review queue")
        if not contributions:
            st.info("No member contributions have been submitted yet.")
        else:
            table = pd.DataFrame(contributions)
            visible_columns = [column for column in [
                "id", "organization", "original_filename", "row_count", "status",
                "ingested_row_count", "ingested_at", "submitted_at", "admin_notes"
            ] if column in table.columns]
            st.dataframe(table[visible_columns], hide_index=True, width="stretch")
            labels = {f"{item.get('organization')} · {item.get('original_filename')} · {item.get('id')}": item for item in contributions}
            with st.form("review_submission_form"):
                selected_label = st.selectbox("Submission", labels)
                selected = labels[selected_label]
                decision = st.selectbox("Decision", ["in_review", "approved", "rejected", "archived"])
                admin_notes = st.text_area("Reviewer notes", value=selected.get("admin_notes", ""))
                review = st.form_submit_button("Save review", type="primary")
            if review:
                try:
                    review_result = repo.review_contribution(
                        selected["id"], decision, admin_notes.strip()
                    )
                    if decision == "approved":
                        st.success(
                            f"Contribution approved and {review_result['ingested_row_count']:,} validated "
                            "row(s) added to the governed data pool."
                        )
                        if review_result["aggregate_count"]:
                            st.info(
                                f"Privacy-safe member benchmarks refreshed · "
                                f"{review_result['aggregate_count']:,} aggregate cohort(s) available."
                            )
                        else:
                            st.info(
                                "The contribution is in the pool. Its cohorts remain suppressed until at "
                                "least five independent contributors are represented."
                            )
                    else:
                        st.success("Contribution status updated and member aggregates refreshed.")
                except Exception as exc:
                    st.error(f"Could not save the review: {exc}")
            try:
                st.download_button(
                    "Download selected private file",
                    repo.download_contribution(selected),
                    file_name=selected.get("original_filename", "member-contribution.csv"),
                    mime="application/octet-stream",
                    help="Use only for AIA Canada’s authorized review process.",
                )
            except Exception as exc:
                st.error(f"The private file could not be retrieved: {exc}")

    with datasets_tab:
        dataset_notice = st.session_state.pop("admin_dataset_notice", None)
        if dataset_notice:
            st.success(dataset_notice)
        st.subheader("Dataset lifecycle")
        datasets = repo.datasets()
        st.dataframe(pd.DataFrame(datasets), hide_index=True, width="stretch")
        st.caption(
            "Archive is the default removal action so provenance and audit history remain intact. "
            "New source files are stored privately as validated drafts."
        )
        if datasets:
            labels = {f"{item.get('title')} · {item.get('status')} · {item.get('id')}": item for item in datasets}
            with st.form("dataset_status_form"):
                dataset_label = st.selectbox("Dataset", labels)
                dataset_status = st.selectbox("Lifecycle status", ["draft", "published", "archived"])
                dataset_submit = st.form_submit_button("Update dataset status")
            if dataset_submit:
                try:
                    repo.set_dataset_status(labels[dataset_label]["id"], dataset_status)
                    st.success("Dataset lifecycle updated.")
                except Exception as exc:
                    st.error(f"Could not update the dataset: {exc}")

        st.subheader("Add a governed benchmark dataset")
        st.caption(
            "Uploaded and manually entered rows use the same validation rules. Valid records are staged as drafts "
            "for AIA Canada review."
        )
        upload_dataset_tab, manual_dataset_tab = st.tabs(["Upload validated CSV", "Enter rows manually"])

        with upload_dataset_tab:
            upload_type = st.selectbox(
                "Dataset type",
                list(DATASET_TYPE_LABELS),
                format_func=DATASET_TYPE_LABELS.get,
                key="admin_upload_dataset_type",
            )
            template_filename = f"{upload_type}_benchmark_upload_template.csv"
            st.download_button(
                "Download CSV template",
                dataset_template_bytes(upload_type),
                file_name=template_filename,
                mime="text/csv",
            )
            st.caption("The template contains one example row. Replace or remove it before uploading your data.")
            dataset_file = st.file_uploader(
                "Completed CSV template", type=["csv"], key="admin_dataset_file"
            )
            upload_validation = None
            if dataset_file:
                payload = dataset_file.getvalue()
                if len(payload) > 25 * 1024 * 1024:
                    st.error("The dataset exceeds the 25 MB administrator upload limit.")
                else:
                    try:
                        upload_frame = read_dataset_csv(payload)
                        upload_validation = validate_dataset(upload_frame, upload_type)
                        show_dataset_validation(upload_validation)
                        if upload_validation.valid:
                            st.dataframe(upload_validation.data.head(100), hide_index=True, width="stretch")
                            if len(upload_validation.data) > 100:
                                st.caption("Preview is limited to the first 100 rows.")
                    except ValueError as exc:
                        st.error(str(exc))

            if upload_validation and upload_validation.valid:
                with st.form("upload_dataset_metadata_form"):
                    upload_metadata = dataset_metadata_fields("upload_dataset")
                    stage_upload = st.form_submit_button("Stage validated CSV as draft", type="primary")
                if stage_upload:
                    if not all([
                        upload_metadata["title"], upload_metadata["slug"], upload_metadata["description"]
                    ]):
                        st.error("Title, slug and source/methodology description are required.")
                    else:
                        try:
                            validated_slug = validate_dataset_slug(str(upload_metadata["slug"]))
                            repo.stage_dataset(
                                title=str(upload_metadata["title"]),
                                slug=validated_slug,
                                data_year=int(upload_metadata["data_year"]),
                                dataset_type=upload_type,
                                description=str(upload_metadata["description"]),
                                filename=dataset_file.name,
                                payload=csv_bytes(upload_validation.data),
                                created_by=user.id,
                            )
                            st.session_state.admin_dataset_notice = (
                                f"Validated dataset staged as draft · {len(upload_validation.data):,} row(s)."
                            )
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Could not stage the dataset: {exc}")

        with manual_dataset_tab:
            manual_type = st.selectbox(
                "Dataset type",
                list(DATASET_TYPE_LABELS),
                format_func=DATASET_TYPE_LABELS.get,
                key="admin_manual_dataset_type",
            )
            manual_rows_key = f"admin_manual_rows_{manual_type}"
            manual_rows = st.session_state.setdefault(manual_rows_key, [])
            if manual_type == DATASET_SEGMENT:
                add_manual_row, manual_row = manual_segment_row_form()
            else:
                add_manual_row, manual_row = manual_performance_row_form()

            if add_manual_row:
                row_validation = validate_dataset(pd.DataFrame([manual_row]), manual_type)
                show_dataset_validation(row_validation)
                if row_validation.valid:
                    manual_rows.append(row_validation.data.iloc[0].to_dict())
                    st.success(f"Row added · {len(manual_rows):,} row(s) in the current draft.")

            if manual_rows:
                manual_frame = pd.DataFrame(manual_rows)
                manual_validation = validate_dataset(manual_frame, manual_type)
                st.markdown("#### Current manual draft")
                show_dataset_validation(manual_validation)
                if manual_validation.valid:
                    st.dataframe(manual_validation.data, hide_index=True, width="stretch")
                    st.download_button(
                        "Download current draft CSV",
                        csv_bytes(manual_validation.data),
                        file_name=f"manual_{manual_type}_draft.csv",
                        mime="text/csv",
                    )
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("Remove last row", width="stretch"):
                        manual_rows.pop()
                        st.rerun()
                with b2:
                    if st.button("Clear manual draft", width="stretch"):
                        manual_rows.clear()
                        st.rerun()

                if manual_validation.valid:
                    with st.form("manual_dataset_metadata_form"):
                        manual_metadata = dataset_metadata_fields("manual_dataset")
                        stage_manual = st.form_submit_button("Stage manual dataset as draft", type="primary")
                    if stage_manual:
                        if not all([
                            manual_metadata["title"],
                            manual_metadata["slug"],
                            manual_metadata["description"],
                        ]):
                            st.error("Title, slug and source/methodology description are required.")
                        else:
                            try:
                                validated_slug = validate_dataset_slug(str(manual_metadata["slug"]))
                                repo.stage_dataset(
                                    title=str(manual_metadata["title"]),
                                    slug=validated_slug,
                                    data_year=int(manual_metadata["data_year"]),
                                    dataset_type=manual_type,
                                    description=str(manual_metadata["description"]),
                                    filename=f"{validated_slug}.csv",
                                    payload=csv_bytes(manual_validation.data),
                                    created_by=user.id,
                                )
                                manual_rows.clear()
                                st.session_state.admin_dataset_notice = (
                                    f"Manual dataset staged as draft · {len(manual_validation.data):,} row(s)."
                                )
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Could not stage the manual dataset: {exc}")
            else:
                st.info("Add at least one valid row to build a manual dataset draft.")

        st.subheader("Statistics Canada demographic sync")
        sync_runs = repo.demographic_sync_runs()
        if sync_runs:
            st.dataframe(pd.DataFrame(sync_runs), hide_index=True, width="stretch")
        else:
            st.info("No demographic synchronization run has been recorded yet.")
        st.caption(
            "Run the trusted operator script from Codespaces with a temporary Supabase secret-key environment variable. "
            "Never add the secret key to Streamlit."
        )
        st.code("python scripts/sync_statcan_demographics.py", language="bash")

    with cms_tab:
        resource_notice = st.session_state.pop("admin_resource_notice", None)
        if resource_notice:
            st.success(resource_notice)
        st.subheader("Resource library")
        resources = repo.resources(include_unpublished=True)
        resource_table = pd.DataFrame(resources)
        visible_resource_columns = [column for column in [
            "section", "title", "resource_type", "delivery_type", "content_format", "status", "sort_order",
        ] if column in resource_table.columns]
        st.dataframe(resource_table[visible_resource_columns], hide_index=True, width="stretch")
        if resources:
            resource_labels = {
                f"{item.get('title')} · {item.get('status')} · {item.get('id')}": item
                for item in resources
            }
            with st.form("resource_status_form"):
                resource_label = st.selectbox("Existing resource", resource_labels)
                resource_status = st.selectbox("Update lifecycle", ["draft", "published", "archived"])
                update_resource = st.form_submit_button("Update resource status")
            if update_resource:
                try:
                    repo.set_resource_status(resource_labels[resource_label]["id"], resource_status)
                    st.success("Resource lifecycle updated.")
                except Exception as exc:
                    st.error(f"Could not update the resource: {exc}")

        st.subheader("Add a resource")
        st.caption("Choose whether members will read the resource inside the portal or open a trusted external website.")
        article_tab, external_tab = st.tabs(["In-portal article", "External link"])

        with article_tab:
            with st.form("internal_resource_form"):
                c1, c2 = st.columns(2)
                with c1:
                    article_section = st.text_input("Section", value="Member guidance", key="article_section")
                    article_title = st.text_input("Title", key="article_title")
                    article_type = st.selectbox(
                        "Resource type",
                        ["Research report", "Methodology", "Data definition", "Tool", "News"],
                        key="article_type",
                    )
                with c2:
                    article_format_label = st.selectbox(
                        "Content format", ["Markdown", "HTML"], key="article_format"
                    )
                    article_status = st.selectbox(
                        "Status", ["draft", "published", "archived"], key="article_status"
                    )
                    article_sort_order = st.number_input(
                        "Sort order", min_value=0, value=10, step=10, key="article_sort_order"
                    )
                article_summary = st.text_area("Summary", key="article_summary")
                article_content = st.text_area(
                    "Article content",
                    height=320,
                    key="article_content",
                    help=(
                        "Markdown is easiest for headings, lists and links. HTML supports a safe subset of text, "
                        "table and link tags; scripts, forms, iframes, styles and unsafe URLs are removed."
                    ),
                )
                preview_article = st.form_submit_button("Preview article")
                save_article = st.form_submit_button("Save in-portal article", type="primary")

            article_format = article_format_label.lower()
            if preview_article:
                st.markdown("#### Article preview")
                if article_content.strip():
                    render_resource_content(article_content, article_format)
                else:
                    st.info("Add article content to preview it.")
            if save_article:
                if not article_section.strip() or not article_title.strip() or not article_summary.strip():
                    st.error("Section, title and summary are required.")
                elif article_status == "published" and not article_content.strip():
                    st.error("A published in-portal article needs content.")
                else:
                    stored_content = article_content.strip()
                    if article_format == FORMAT_HTML:
                        stored_content = sanitize_resource_html(stored_content)
                    if article_status == "published" and not stored_content:
                        st.error("The HTML contains no safe displayable content.")
                    else:
                        try:
                            repo.save_resource({
                                "section": article_section.strip(),
                                "title": article_title.strip(),
                                "summary": article_summary.strip(),
                                "resource_type": article_type,
                                "delivery_type": "internal",
                                "content_format": article_format,
                                "external_url": None,
                                "content": stored_content,
                                "status": article_status,
                                "sort_order": int(article_sort_order),
                                "published_at": date.today().isoformat() if article_status == "published" else None,
                                "created_by": user.id,
                            })
                            st.session_state.admin_resource_notice = "In-portal article saved."
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Could not save the article: {exc}")

        with external_tab:
            with st.form("external_resource_form"):
                c1, c2 = st.columns(2)
                with c1:
                    link_section = st.text_input("Section", value="Featured research", key="link_section")
                    link_title = st.text_input("Title", key="link_title")
                    link_type = st.selectbox(
                        "Resource type",
                        ["Research report", "Methodology", "Data definition", "Tool", "News"],
                        key="link_type",
                    )
                with c2:
                    link_url = st.text_input(
                        "External HTTPS URL", placeholder="https://", key="link_url"
                    )
                    link_status = st.selectbox(
                        "Status", ["draft", "published", "archived"], key="link_status"
                    )
                    link_sort_order = st.number_input(
                        "Sort order", min_value=0, value=10, step=10, key="link_sort_order"
                    )
                link_summary = st.text_area("Summary", key="link_summary")
                test_link = st.form_submit_button("Test link")
                save_link = st.form_submit_button("Save external link", type="primary")

            checked_link = None
            if test_link or save_link:
                if link_url.strip():
                    try:
                        checked_link = validate_external_url(link_url)
                    except ValueError as exc:
                        st.error(str(exc))
                elif test_link or link_status == "published":
                    st.error("Enter the external resource URL.")
            if test_link and checked_link:
                st.link_button("Open link in a new tab", checked_link)
            if save_link:
                if not link_section.strip() or not link_title.strip() or not link_summary.strip():
                    st.error("Section, title and summary are required.")
                elif link_status == "published" and not checked_link:
                    st.error("A published external resource needs a valid HTTPS URL.")
                elif link_url.strip() and not checked_link:
                    pass
                else:
                    try:
                        repo.save_resource({
                            "section": link_section.strip(),
                            "title": link_title.strip(),
                            "summary": link_summary.strip(),
                            "resource_type": link_type,
                            "delivery_type": "external",
                            "content_format": "markdown",
                            "external_url": checked_link,
                            "content": "",
                            "status": link_status,
                            "sort_order": int(link_sort_order),
                            "published_at": date.today().isoformat() if link_status == "published" else None,
                            "created_by": user.id,
                        })
                        st.session_state.admin_resource_notice = "External resource link saved."
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not save the external link: {exc}")


user = st.session_state.get("portal_user")
if not user:
    login_page()
    st.stop()

if not user.can_access_portal:
    page_intro(
        "Access review",
        "Your portal access is pending",
        "Your account is authenticated, but AIA Canada must confirm active membership before industry data is available.",
    )
    st.info(f"Current status: {user.membership_status}. Contact {settings.support_email} if this is unexpected.")
    if st.button("Sign out"):
        clear_user()
        st.rerun()
    st.stop()

try:
    repository = get_repository(user)
except Exception as exc:
    st.error(f"Could not connect to the portal data service: {exc}")
    if st.button("Return to sign in"):
        clear_user()
        st.rerun()
    st.stop()

page = portal_sidebar(user)
if page == "Overview":
    overview_page(repository)
elif page == "Benchmark Explorer":
    explorer_page(repository)
elif page == "Performance Lab":
    performance_page(repository)
elif page == "Member Data Pool":
    member_data_pool_page(repository)
elif page == "Market Demographics":
    demographics_page(repository, user)
elif page == "Resources":
    resources_page(repository, user)
elif page == "Contribute Data":
    contribute_page(repository, user)
elif page == "Admin Centre" and user.is_admin:
    admin_page(repository, user)
