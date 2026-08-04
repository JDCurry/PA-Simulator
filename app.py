"""Public Assistance Workbench.

A FEMA Public Assistance reimbursement workbench and training simulator.

Run locally:      streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from pa import __version__
from pa.costing import summarize_scenario
from pa.guidance import PAGE_PURPOSE, is_untouched, next_action, progress
from pa.validation import review
from ui import (
    common, compliance_page, costing_page, formulation_page, inventory_page,
    learn_page, manual_page, package_page, scenario_page, start_page,
)

st.set_page_config(
    page_title="Public Assistance Workbench",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

#: page key -> (module, sidebar label). The label leads with the task, because the
#: FEMA term means nothing until you have done this once. The term itself stays
#: visible in the page purpose line and in the Start page step list.
PAGES: dict[str, tuple[object, str]] = {
    "Start": (start_page, "Start here"),
    "Scenario": (scenario_page, "1 · Set up the disaster"),
    "Impact List": (inventory_page, "2 · List the damage"),
    "Formulation": (formulation_page, "3 · Group into projects"),
    "Cost Buildup": (costing_page, "4 · Price the work"),
    "Compliance": (compliance_page, "5 · Fix what FEMA would reject"),
    "Package": (package_page, "6 · Assemble the package"),
    "Training": (learn_page, "How am I doing?"),
    "Manual": (manual_page, "User manual"),
}


def main() -> None:
    scenario = common.get_scenario()
    keys = list(PAGES)

    # Pages navigate by setting st.session_state["nav"]; the radio reads it back.
    if st.session_state.get("nav") in PAGES:
        st.session_state["nav_radio"] = st.session_state.pop("nav")

    with st.sidebar:
        st.markdown("### Public Assistance Workbench")
        st.caption("FEMA reimbursement, worked end to end")
        st.divider()

        choice = st.radio(
            "Section", keys,
            format_func=lambda k: PAGES[k][1],
            label_visibility="collapsed",
            key="nav_radio",
        )

        st.divider()
        fresh = is_untouched(scenario)
        action = next_action(scenario)

        st.caption("DO THIS NEXT")
        st.markdown(f"**{common.md(action.headline)}**")
        st.caption(common.md(action.where))

        if not fresh:
            prog = progress(scenario)
            st.progress(prog.fraction,
                        text=f"Step {min(prog.completed + 1, prog.total)} of {prog.total}")

            st.divider()
            totals = summarize_scenario(scenario)
            st.metric("Net eligible", common.money0_plain(totals.net_eligible))
            st.metric(
                f"FEMA pays ({scenario.rules.cost_share.federal:.0%})",
                common.money0_plain(totals.federal_share),
            )
            st.metric("You pay",
                      common.money0_plain(totals.applicant_out_of_pocket))

            result = review(scenario)
            if result.errors:
                st.error(f"{len(result.errors)} blocking finding(s)")
            elif result.warnings:
                st.warning(f"{len(result.warnings)} caution(s)")
            else:
                st.success("Nothing blocking")

        st.divider()
        common.scenario_picker()

        st.divider()
        st.caption(
            f"v{__version__} • Rules: {scenario.rules.policy_version}  \n"
            "Not affiliated with FEMA. A planning and training aid — verify every "
            "figure against the current PAPPG and your award before relying on it."
        )

    module, _ = PAGES[choice]
    if choice != "Start":
        common.header(scenario)
    module.render()

    if choice not in ("Start", "Manual"):
        common.next_step_footer(scenario, choice)


if __name__ == "__main__":
    main()
