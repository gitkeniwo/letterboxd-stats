"""Shared Letterboxd-inspired presentation helpers."""

from __future__ import annotations

from html import escape

import streamlit as st

ACCENTS = {
    "green": "#00e054",
    "blue": "#40bcf4",
    "orange": "#ff8000",
    "muted": "#9ab",
}


def fa(name: str, *, color: str = "muted") -> str:
    value = ACCENTS.get(color, color)
    return f'<i class="fa-solid fa-{escape(name)}" style="color:{value}"></i>'


def section_header(
    title: str, icon: str, *, color: str = "green", level: int = 2
) -> None:
    st.markdown(
        f'<h{level} class="lb-section-title">{fa(icon, color=color)}'
        f"<span>{escape(title)}</span></h{level}>",
        unsafe_allow_html=True,
    )


def metric_card(
    label: str, value: str | int, icon: str, *, color: str = "green"
) -> None:
    st.markdown(
        '<div class="lb-metric-card">'
        f'<div class="lb-metric-label">{fa(icon, color=color)}<span>{escape(label)}</span></div>'
        f'<div class="lb-metric-value">{escape(str(value))}</div>'
        "</div>",
        unsafe_allow_html=True,
    )


def insight(text: str, icon: str, *, color: str = "muted") -> None:
    st.markdown(
        f'<div class="lb-insight">{fa(icon, color=color)}<span>{text}</span></div>',
        unsafe_allow_html=True,
    )


def star_label(rating: float, label: str) -> None:
    full_stars = int(rating)
    has_half = rating - full_stars >= 0.5
    icons = "".join('<i class="fa-solid fa-star"></i>' for _ in range(full_stars))
    if has_half:
        icons += '<i class="fa-solid fa-star-half-stroke"></i>'
    st.markdown(
        f'<div class="lb-rating-label"><span>{icons}</span>{escape(label)}</div>',
        unsafe_allow_html=True,
    )
