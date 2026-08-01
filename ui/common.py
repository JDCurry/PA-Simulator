"""Shared UI state and formatting helpers."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import streamlit as st

from pa.models import Project, Scenario
from pa.scenario import (
    SCENARIO_DIR, blank_scenario, load_scenario, scenario_from_dict,
    scenario_to_dict,
)

SEVERITY_LABEL = {"error": "BLOCKING", "warning": "CAUTION", "info": "NOTE"}

#: The bundled training scenario, loadable on demand from the sidebar.
TRAINING_SCENARIO = "training_cascade_valley.json"


def get_scenario() -> Scenario:
    """The app opens on an empty scenario. A jurisdiction starts from its own impact
    list, not from someone else's disaster."""
    if "scenario" not in st.session_state:
        st.session_state.scenario = blank_scenario()
    return st.session_state.scenario


def set_scenario(scenario: Scenario) -> None:
    st.session_state.scenario = scenario
    st.session_state.pop("active_project", None)


def touch() -> None:
    """Mark the scenario dirty so downstream caches recompute."""
    st.session_state["revision"] = st.session_state.get("revision", 0) + 1


def md(text: str) -> str:
    """Escape dollar signs so Streamlit's markdown does not parse them as LaTeX.

    Two unescaped ``$`` in one block make everything between them render as math,
    which silently mangles any sentence quoting two figures. Engine-generated text
    is full of them, so it is escaped at the display boundary rather than at the
    source -- the engine's strings stay usable in a terminal, a CSV, or a report.
    """
    return text.replace("$", r"\$")


def money(v: float) -> str:
    """Currency for markdown contexts: st.markdown, captions, expander labels,
    st.info/warning/error. Pre-escaped."""
    return rf"\${v:,.2f}"


def money0(v: float) -> str:
    return rf"\${v:,.0f}"


def money_plain(v: float) -> str:
    """Currency for contexts that do NOT render markdown: st.metric, dataframes,
    st.text, download filenames."""
    return f"${v:,.2f}"


def money0_plain(v: float) -> str:
    return f"${v:,.0f}"


def active_project(scenario: Scenario, key: str = "active_project") -> Project | None:
    """Project picker that survives reruns and project deletion."""
    if not scenario.projects:
        return None
    titles = [p.title or p.id for p in scenario.projects]
    stored = st.session_state.get(key)
    index = next((i for i, p in enumerate(scenario.projects) if p.id == stored), 0)
    chosen = st.selectbox("Project", titles, index=index, key=f"{key}_select")
    project = scenario.projects[titles.index(chosen)]
    st.session_state[key] = project.id
    return project


def finding_block(findings, empty_message: str = "Nothing flagged.") -> None:
    """Render validation findings grouped by the test that produced them."""
    if not findings:
        st.success(empty_message)
        return
    for f in findings:
        label = SEVERITY_LABEL.get(f.severity, "NOTE")
        subject = f.subject or f.test
        with st.container(border=True):
            st.caption(label)
            st.markdown(f"**{md(subject)}**")
            st.write(md(f.message))
            meta = []
            if f.citation:
                meta.append(f"*{md(f.citation)}*")
            if f.remedy:
                meta.append(f"**What to do:** {md(f.remedy)}")
            if meta:
                st.caption("  \n".join(meta))


def scenario_picker() -> None:
    """Sidebar controls for saving, uploading, and resetting the working file."""
    import json

    scenario = get_scenario()
    training_path = SCENARIO_DIR / TRAINING_SCENARIO

    with st.sidebar:
        st.markdown("### Scenario")

        st.download_button(
            "Save working file",
            data=json.dumps(scenario_to_dict(scenario), indent=2),
            file_name=f"{_slug(scenario.title)}.json",
            mime="application/json",
            use_container_width=True,
            help="Downloads the scenario as JSON. Nothing is stored on the server.",
        )

        uploaded = st.file_uploader("Open a saved file (.json)", type=["json"])
        if uploaded is not None and st.button("Open", use_container_width=True):
            set_scenario(scenario_from_dict(json.loads(uploaded.getvalue())))
            st.rerun()

        st.divider()

        if training_path.exists() and st.button(
            "Load training scenario", use_container_width=True,
            help="A fictional declaration seeded with errors to find and correct.",
        ):
            set_scenario(load_scenario(training_path))
            st.rerun()

        if st.button("Clear and start over", use_container_width=True):
            set_scenario(blank_scenario())
            st.rerun()


def _slug(text: str) -> str:
    keep = [c.lower() if c.isalnum() else "_" for c in text]
    return "".join(keep).strip("_")[:60] or "scenario"


def header(scenario: Scenario) -> None:
    d = scenario.disaster
    bits = [scenario.applicant.name or "No applicant set"]
    if d.number:
        bits.append(d.number)
    if d.declaration_date:
        bits.append(f"declared {d.declaration_date:%b %d, %Y}")
    st.caption(" • ".join(bits))


def date_input_optional(label: str, value: date | None, key: str) -> date | None:
    """A date input that genuinely allows 'not set'."""
    col_a, col_b = st.columns([3, 1])
    with col_b:
        unset = st.checkbox("Not set", value=value is None, key=f"{key}_unset")
    with col_a:
        picked = st.date_input(
            label, value=value or date.today(), key=f"{key}_value",
            disabled=unset, format="MM/DD/YYYY",
        )
    return None if unset else picked
