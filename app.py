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
from aia_portal.config import load_settings  # noqa: E402
from aia_portal.data import (  # noqa: E402
    METRICS,
    PERFORMANCE_FOCUS_METRICS,
    format_metric,
    read_template_bytes,
)
from aia_portal.exports import csv_bytes, excel_report_bytes, pdf_report_bytes  # noqa: E402
from aia_portal.repository import DemoRepository, SupabaseRepository  # noqa: E402
from aia_portal.ui import inject_theme, metric_card, page_intro, source_note  # noqa: E402
from aia_portal.validation import read_uploaded_table, validate_shop_upload  # noqa: E402


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


def set_user(user: PortalUser, tokens: SessionTokens | None = None) -> None:
    st.session_state.portal_user = user
    st.session_state.session_tokens = tokens


def clear_user() -> None:
    st.session_state.pop("portal_user", None)
    st.session_state.pop("session_tokens", None)
    st.session_state.pop("repo", None)


def login_page() -> None:
    left, right = st.columns([1.15, 0.85], gap="large")
    with left:
        st.markdown('<div class="aia-eyebrow">Member intelligence platform</div>', unsafe_allow_html=True)
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
        st.markdown('<div class="aia-logo">aia <span>Canada</span></div>', unsafe_allow_html=True)
        st.markdown('<div class="aia-logo-sub">Data Portal</div>', unsafe_allow_html=True)
        st.write("")
        pages = ["Overview", "Benchmark Explorer", "Performance Lab", "Resources", "Contribute Data"]
        if user.is_admin:
            pages.append("Admin Centre")
        current = st.radio("Portal", pages, label_visibility="collapsed")
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
        "Start with national benchmarks, then move from signal to detail using the explorer and performance lab.",
    )
    performance = repo.performance_benchmarks()
    mechanical_all = performance[
        (performance["shop_type"] == "Mechanical") & (performance["cohort"] == "All shops")
    ].set_index("metric_code")

    cards = st.columns(4)
    values = [
        ("Survey respondents", "572", "Canadian automotive service providers"),
        ("Hours / repair order", format_metric(mechanical_all.loc["hours_repair_order", "value"], "hours"), "Mechanical shop average"),
        ("Hours / technician / day", format_metric(mechanical_all.loc["hours_technician_day", "value"], "hours"), "55% of an eight-hour day"),
        ("Hiring intention", "57%", "Planned to hire a technician"),
    ]
    for column, item in zip(cards, values):
        with column:
            metric_card(*item)

    st.write("")
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
        scope = st.selectbox(
            "View",
            ["Regional comparison", "National / affiliation"],
            index=0 if (filtered["geography_type"] == "region").any() else 1,
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
    source_note("7–10")


def performance_page(repo) -> None:
    page_intro(
        "Performance lab",
        "Turn benchmark gaps into operating questions",
        "Compare leading cohorts and estimate the scale of a shop’s ticket-size and productivity opportunity.",
    )
    data = repo.performance_benchmarks()
    shop_type = st.segmented_control("Shop type", ["Mechanical", "Tire"], default="Mechanical")
    scoped = data[data["shop_type"] == shop_type].copy()
    available = scoped[scoped["metric_code"].isin(PERFORMANCE_FOCUS_METRICS)]
    metric_code = st.selectbox(
        "Comparison measure",
        list(dict.fromkeys(available["metric_code"])),
        format_func=lambda code: available.loc[available["metric_code"] == code, "metric_label"].iloc[0],
    )
    comparison = scoped[scoped["metric_code"] == metric_code]
    metric_label = comparison["metric_label"].iloc[0]
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
        },
    )
    chart(fig)
    source_note("12" if shop_type == "Mechanical" else "15")

    st.subheader("Opportunity calculator")
    st.caption("A directional scenario—not a forecast. Adjust the inputs to match a member shop.")
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            repair_orders = st.number_input("Annual repair orders", min_value=1, value=2500, step=100)
            technicians = st.number_input("Paid technicians", min_value=1.0, value=4.0, step=0.5)
        with c2:
            days_open = st.number_input("Days open / year", min_value=1, value=259, step=1)
            door_rate = st.number_input("Labour door rate (CAD)", min_value=1.0, value=110.0, step=5.0)
        with c3:
            current_ticket = st.number_input("Current hours / repair order", min_value=0.1, value=1.67, step=0.1)
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
                    url = item.get("external_url")
                    if url:
                        st.link_button("Open resource", url, width="stretch")
                    else:
                        st.button("Available in portal", key=f"resource-{item.get('id')}", disabled=True, width="stretch")


def contribute_page(repo, user: PortalUser) -> None:
    page_intro(
        "Member contribution",
        "Contribute shop data securely",
        "Use the standard template. AIA Canada reviews every submission before any data is approved for aggregation.",
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
        st.download_button("CSV template", read_template_bytes(), "aia_member_shop_template.csv", "text/csv", width="stretch")
    with d2:
        st.download_button(
            "Excel template",
            excel_report_bytes(template, title="AIA Canada member shop upload template"),
            "aia_member_shop_template.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )

    st.subheader("Validate and submit")
    upload = st.file_uploader("Shop data file", type=["csv", "xlsx"], help=f"Maximum {settings.max_upload_mb} MB")
    if not upload:
        own = repo.contributions(user)
        if own:
            st.subheader("Your recent submissions")
            st.dataframe(pd.DataFrame(own), hide_index=True, width="stretch")
        return
    payload = upload.getvalue()
    if len(payload) > settings.max_upload_mb * 1024 * 1024:
        st.error(f"The file exceeds the {settings.max_upload_mb} MB limit.")
        return
    try:
        frame = read_uploaded_table(payload, upload.name)
        result = validate_shop_upload(frame)
    except Exception as exc:
        st.error(f"Could not read the file: {exc}")
        return
    for error in result.errors:
        st.error(error)
    for warning in result.warnings:
        st.warning(warning)
    if not result.valid:
        return
    assert result.data is not None
    st.success(f"Validation passed · {len(result.data):,} row(s)")
    st.dataframe(result.data.head(20), hide_index=True, width="stretch")

    default_start = pd.to_datetime(result.data["reporting_month"].min()).date().replace(day=1)
    default_end = (pd.to_datetime(result.data["reporting_month"].max()) + pd.offsets.MonthEnd(0)).date()
    with st.form("contribution_form"):
        c1, c2 = st.columns(2)
        with c1:
            organization = st.text_input("Contributing organization", value=user.organization)
            period_start = st.date_input("Reporting period starts", value=default_start)
        with c2:
            period_end = st.date_input("Reporting period ends", value=default_end)
            notes = st.text_area("Notes for the AIA Canada reviewer", placeholder="Optional context, exclusions or corrections")
        attest = st.checkbox(
            "I confirm this file contains no customer, employee, vehicle or invoice-level identifiers and I am authorized to submit it."
        )
        submit = st.form_submit_button("Submit for approval", type="primary")
    if submit:
        if not organization.strip():
            st.error("Enter the contributing organization.")
        elif period_end < period_start:
            st.error("The reporting period end must be on or after the start.")
        elif not attest:
            st.error("Confirm the data and authorization statement before submitting.")
        else:
            try:
                record = repo.submit_contribution(
                    user=user,
                    organization=organization.strip(),
                    period_start=period_start,
                    period_end=period_end,
                    filename=upload.name,
                    payload=payload,
                    row_count=len(result.data),
                    notes=notes.strip(),
                )
                st.success(f"Submission received · reference {record['id']}")
                st.info("Status: Submitted. The file remains private until reviewed by AIA Canada.")
            except Exception as exc:
                st.error(f"The submission could not be saved: {exc}")


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
                "id", "organization", "original_filename", "row_count", "status", "submitted_at", "admin_notes"
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
                    repo.review_contribution(selected["id"], decision, admin_notes.strip())
                    st.success("Contribution status updated. Approval does not automatically publish raw shop data.")
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
        st.subheader("Dataset lifecycle")
        datasets = repo.datasets()
        st.dataframe(pd.DataFrame(datasets), hide_index=True, width="stretch")
        st.caption("Archive is the default removal action so provenance and audit history remain intact.")
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
        with st.expander("Stage a new dataset file"):
            with st.form("new_dataset_form"):
                title = st.text_input("Dataset title")
                slug = st.text_input("Slug", placeholder="2026-shop-productivity")
                data_year = st.number_input("Data year", min_value=2000, max_value=date.today().year, value=date.today().year)
                description = st.text_area("Description")
                dataset_file = st.file_uploader("Curated CSV", type=["csv"], key="admin_dataset_file")
                stage = st.form_submit_button("Stage as draft", type="primary")
            if stage:
                if not title or not slug or not dataset_file:
                    st.error("Title, slug and a curated CSV are required.")
                else:
                    try:
                        repo.stage_dataset(
                            title=title.strip(), slug=slug.strip(), data_year=int(data_year),
                            description=description.strip(), filename=dataset_file.name,
                            payload=dataset_file.getvalue(), created_by=user.id,
                        )
                        st.success("Dataset staged as draft. Validate and publish only after review.")
                    except Exception as exc:
                        st.error(f"Could not stage the dataset: {exc}")

    with cms_tab:
        st.subheader("Published resources")
        resources = repo.resources(include_unpublished=True)
        st.dataframe(pd.DataFrame(resources), hide_index=True, width="stretch")
        if resources:
            resource_labels = {f"{item.get('title')} · {item.get('status')}": item for item in resources}
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
        with st.form("resource_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                section = st.text_input("Section", value="Featured research")
                title = st.text_input("Title")
                resource_type = st.selectbox("Resource type", ["Research report", "Methodology", "Data definition", "Tool", "News"])
            with c2:
                external_url = st.text_input("External URL", placeholder="https://")
                status = st.selectbox("Status", ["draft", "published", "archived"])
                sort_order = st.number_input("Sort order", min_value=0, value=10, step=10)
            summary = st.text_area("Summary")
            save_resource = st.form_submit_button("Save resource", type="primary")
        if save_resource:
            if not title.strip() or not summary.strip():
                st.error("Title and summary are required.")
            else:
                try:
                    repo.save_resource({
                        "section": section.strip(), "title": title.strip(), "summary": summary.strip(),
                        "resource_type": resource_type, "external_url": external_url.strip() or None,
                        "status": status, "sort_order": int(sort_order),
                    })
                    st.success("Resource saved.")
                except Exception as exc:
                    st.error(f"Could not save the resource: {exc}")


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
elif page == "Resources":
    resources_page(repository, user)
elif page == "Contribute Data":
    contribute_page(repository, user)
elif page == "Admin Centre" and user.is_admin:
    admin_page(repository, user)
