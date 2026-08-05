from __future__ import annotations

from html import escape

import streamlit as st


AIA_NAVY = "#123E5A"
AIA_BLUE = "#1B5B83"
AIA_RED = "#D7263D"


def inject_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
          --aia-navy: #123E5A;
          --aia-blue: #1B5B83;
          --aia-red: #D7263D;
          --aia-ink: #173044;
          --aia-muted: #627887;
          --aia-mist: #EDF3F6;
        }
        .stApp { background: #F7F9FA; color: var(--aia-ink); }
        [data-testid="stHeader"] { background: rgba(247,249,250,.85); }
        [data-testid="stSidebar"] { background: var(--aia-navy); }
        [data-testid="stSidebar"] * { color: #F5FAFC; }
        [data-testid="stSidebar"] .stRadio label { padding: .28rem 0; }
        [data-testid="stSidebar"] hr { border-color: rgba(255,255,255,.14); }
        .block-container { padding-top: 1.55rem; padding-bottom: 3rem; max-width: 1280px; }
        h1, h2, h3 { color: var(--aia-navy); letter-spacing: -.025em; }
        h1 { font-size: 2.05rem !important; }
        h2 { font-size: 1.35rem !important; }
        .aia-logo { font-size: 1.25rem; font-weight: 800; color: white; line-height: 1; }
        .aia-logo span { color: #FF5265; }
        .aia-logo-sub { color: #B9CDD9 !important; font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; }
        .aia-eyebrow { color: var(--aia-red); font-weight: 800; font-size: .76rem; letter-spacing: .11em; text-transform: uppercase; margin-bottom: .2rem; }
        .aia-lead { color: var(--aia-muted); font-size: 1.05rem; max-width: 780px; margin-top: -.55rem; }
        .aia-card { background: white; border: 1px solid #DCE6EB; border-radius: 14px; padding: 1.05rem 1.15rem; min-height: 122px; box-shadow: 0 4px 18px rgba(18,62,90,.05); }
        .aia-card-label { color: var(--aia-muted); font-size: .76rem; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }
        .aia-card-value { color: var(--aia-navy); font-size: 1.72rem; font-weight: 800; line-height: 1.2; margin: .18rem 0; }
        .aia-card-note { color: var(--aia-muted); font-size: .81rem; }
        .aia-callout { border-left: 4px solid var(--aia-red); background: white; border-radius: 0 12px 12px 0; padding: .9rem 1rem; margin: .5rem 0 1rem; }
        .aia-status { display: inline-block; border-radius: 999px; padding: .2rem .6rem; font-size: .72rem; font-weight: 800; text-transform: uppercase; letter-spacing: .04em; }
        .aia-status-published, .aia-status-approved, .aia-status-active { background: #DDF3E8; color: #18704A; }
        .aia-status-submitted, .aia-status-pending, .aia-status-review { background: #FFF0CC; color: #875E00; }
        .aia-status-rejected, .aia-status-suspended { background: #FDE3E7; color: #A3192E; }
        div.stButton > button[kind="primary"] { background: var(--aia-red); border-color: var(--aia-red); }
        div.stButton > button { border-radius: 9px; font-weight: 700; }
        [data-testid="stMetric"] { background: white; border: 1px solid #DCE6EB; border-radius: 12px; padding: .9rem; }
        [data-testid="stDataFrame"] { border: 1px solid #DCE6EB; border-radius: 12px; overflow: hidden; }
        .aia-source { color: var(--aia-muted); font-size: .76rem; margin-top: .4rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_intro(eyebrow: str, title: str, lead: str) -> None:
    st.markdown(
        f'<div class="aia-eyebrow">{escape(eyebrow)}</div>'
        f'<h1>{escape(title)}</h1><p class="aia-lead">{escape(lead)}</p>',
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str, note: str = "") -> None:
    st.markdown(
        '<div class="aia-card">'
        f'<div class="aia-card-label">{escape(label)}</div>'
        f'<div class="aia-card-value">{escape(value)}</div>'
        f'<div class="aia-card-note">{escape(note)}</div>'
        "</div>",
        unsafe_allow_html=True,
    )


def source_note(pages: str) -> None:
    st.markdown(
        f'<div class="aia-source">Source: AIA Canada, <em>The View from Here: 2015 Productivity Benchmarks</em>, pages {escape(pages)}. Historical survey data (n=572); not a current market estimate.</div>',
        unsafe_allow_html=True,
    )


def status_badge(status: str) -> str:
    safe = escape(status.lower())
    return f'<span class="aia-status aia-status-{safe}">{escape(status)}</span>'
