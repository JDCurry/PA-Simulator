"""The landing page: what this is, where to begin, and what to do next.

The rest of the app assumes you know what a Public Assistance grant is. This page
does not.
"""

from __future__ import annotations

import streamlit as st

from pa.costing import summarize_scenario
from pa.guidance import is_untouched, next_action, progress
from pa.scenario import SCENARIO_DIR, blank_scenario, load_scenario
from .common import TRAINING_SCENARIO, md, money_plain, set_scenario

_STATUS_LABEL = {"done": "Done", "current": "You are here", "todo": "Not started"}


def render() -> None:
    s = st.session_state.scenario
    fresh = is_untouched(s)

    st.title("Public Assistance Workbench")

    if fresh:
        _welcome()
    else:
        _dashboard(s)


def _welcome() -> None:
    st.markdown(
        "#### After a declared disaster, a city or county can be reimbursed by FEMA "
        "for what the disaster cost it. Getting that money is a long, rule-bound "
        "process, and most of the ways it goes wrong are avoidable."
    )
    st.write(
        "This tool lets you work that process end to end as the **applicant** — the "
        "local government doing the claiming. You list the damage, group it into "
        "projects, price the work, and assemble a submission. As you go, it checks "
        "your package the way a FEMA reviewer would and tells you what would be "
        "rejected and why, with a citation for each finding."
    )
    st.write("**You do not need to know anything about the program to start.**")

    st.divider()
    st.markdown("### Pick a starting point")

    c1, c2 = st.columns(2)

    with c1:
        with st.container(border=True):
            st.markdown("#### Learn with a worked example")
            st.write(
                "Loads a fictional city that has just been through a flood. Its "
                "reimbursement package is already built — and deliberately full of "
                "mistakes. Your job is to find and fix them."
            )
            st.caption(
                "Recommended if you have not done this before. It opens at a failing "
                "grade with about 20 blocking problems, and the tool walks you "
                "through them one at a time."
            )
            path = SCENARIO_DIR / TRAINING_SCENARIO
            if st.button("Start the worked example", type="primary",
                         use_container_width=True, disabled=not path.exists()):
                set_scenario(load_scenario(path))
                st.session_state["nav"] = "Compliance"
                st.rerun()

    with c2:
        with st.container(border=True):
            st.markdown("#### Work my own disaster")
            st.write(
                "Start from an empty file and enter your own applicant, declaration, "
                "and damage. You can also import the damage inventory workbook your "
                "state recipient sent you."
            )
            st.caption(
                "Nothing you enter is stored on the server. Save your working file "
                "before you close the tab."
            )
            if st.button("Set up my disaster", use_container_width=True):
                set_scenario(blank_scenario())
                st.session_state.scenario.title = "My Disaster"
                st.session_state["nav"] = "Scenario"
                st.rerun()

    st.divider()
    _primer()


def _primer() -> None:
    with st.expander("How the program works, in about a minute"):
        st.markdown(r"""
**Who pays.** FEMA pays **75 percent** of eligible costs. Your jurisdiction pays the
other 25 percent, out of real money — a general fund, a utility fund, a levy.

**What counts.** FEMA tests four things separately: are **you** an eligible applicant,
was the damaged thing an eligible **facility**, is the **work** required because of
this disaster, and is the **cost** documented and reasonable. Failing any one of the
four ends the project, no matter how good the other three are.

**Work is sorted into categories, and the category changes the rules.** Debris removal
and emergency protective measures are *emergency work*. Roads, water control,
buildings, utilities and parks are *permanent work*. The most expensive thing people
get wrong: on emergency work, your regular employees are reimbursed for **overtime
only** — their normal salary is not eligible, because you were already paying it.

**Size matters more than you would expect.** Under about **\$4,100** there is no project
at all. Over about **\$1.09 million** it becomes a *large* project, paid on actual cost
with money held back, a final inspection, and two years of different paperwork.

**The clock is real.** You have 30 days from designation to apply at all, 60 days from
your scoping meeting to list every damaged site, six months to finish emergency work,
and eighteen for permanent work.
        """)
        st.caption(
            "The Manual page covers all of this properly, and the Training page has a "
            "glossary. Neither is required reading before you start."
        )


def _dashboard(s) -> None:
    prog = progress(s)
    action = next_action(s)
    totals = summarize_scenario(s)

    st.caption(s.title)

    c1, c2, c3 = st.columns(3)
    c1.metric("Progress", f"{prog.completed} of {prog.total} steps")
    c2.metric("FEMA would pay", money_plain(totals.federal_share))
    c3.metric("Your share", money_plain(totals.applicant_out_of_pocket))

    st.divider()

    st.markdown("### Do this next")
    box = {"blocking": st.error, "opportunity": st.warning}.get(
        action.severity, st.info)
    box(f"**{md(action.headline)}**\n\n{md(action.why)}")
    cols = st.columns([1, 3])
    if cols[0].button(f"Go to {action.page}", type="primary",
                      use_container_width=True):
        st.session_state["nav"] = action.page
        st.rerun()
    cols[1].caption(f"Where: {action.where}")

    st.divider()
    st.markdown("### The six steps")
    st.caption(
        "This is the order the work actually happens in. Each one has a page in the "
        "sidebar."
    )

    for step in prog.steps:
        with st.container(border=True):
            head, right = st.columns([5, 1])
            head.markdown(f"**{step.label}**")
            right.caption(_STATUS_LABEL[step.status])
            st.caption(f"{step.purpose}  \n**{step.detail}**  \n"
                       f"*FEMA calls this: {step.fema_term}*")
            if step.status == "current":
                if st.button(f"Open {step.page}", key=f"go_{step.number}"):
                    st.session_state["nav"] = step.page
                    st.rerun()

    st.divider()
    with st.expander("Start over, or switch to the worked example"):
        c1, c2 = st.columns(2)
        path = SCENARIO_DIR / TRAINING_SCENARIO
        if c1.button("Load the worked example", use_container_width=True,
                     disabled=not path.exists()):
            set_scenario(load_scenario(path))
            st.rerun()
        if c2.button("Clear everything and start fresh", use_container_width=True):
            set_scenario(blank_scenario())
            st.rerun()
    _primer()
