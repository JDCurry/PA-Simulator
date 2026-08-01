"""Public Assistance Workbench.

A FEMA Public Assistance reimbursement workbench and training simulator.

Run locally:      streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from pa import __version__
from pa.costing import summarize_scenario
from pa.validation import review
from ui import (
    common, compliance_page, costing_page, formulation_page, inventory_page,
    learn_page, manual_page, package_page, scenario_page,
)

st.set_page_config(
    page_title="Public Assistance Workbench",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

PAGES = {
    "Scenario": scenario_page,
    "Impact List": inventory_page,
    "Formulation": formulation_page,
    "Cost Buildup": costing_page,
    "Compliance": compliance_page,
    "Package": package_page,
    "Training": learn_page,
    "Manual": manual_page,
}


def main() -> None:
    scenario = common.get_scenario()

    with st.sidebar:
        st.markdown("### Public Assistance Workbench")
        st.caption("FEMA PA project formulation, cost buildup, and closeout")
        st.divider()
        choice = st.radio("Section", list(PAGES), label_visibility="collapsed")

        st.divider()
        totals = summarize_scenario(scenario)
        result = review(scenario)
        st.metric("Net eligible", common.money0_plain(totals.net_eligible))
        st.metric(
            f"Federal share ({scenario.rules.cost_share.federal:.0%})",
            common.money0_plain(totals.federal_share),
        )
        st.metric("Applicant share",
                  common.money0_plain(totals.applicant_out_of_pocket))
        if result.errors:
            st.error(f"{len(result.errors)} blocking finding(s)")
        elif result.warnings:
            st.warning(f"{len(result.warnings)} caution(s)")
        else:
            st.success("No findings")

        st.divider()
        common.scenario_picker()

        st.divider()
        st.caption(
            f"v{__version__} • Rules: {scenario.rules.policy_version}  \n"
            "Not affiliated with FEMA. A planning and training aid — verify every "
            "figure against the current PAPPG and your award before relying on it."
        )

    common.header(scenario)
    PAGES[choice].render()


if __name__ == "__main__":
    main()
