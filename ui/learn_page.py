"""Training mode: scorecard, the PA process end to end, and category reference."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from pa.rules import (
    CATEGORIES, DEADLINE_LABELS, NO_EXTENSION_DEADLINES, WorkType,
)
from pa.scoring import REFLECTION_PROMPTS, score
from .common import get_scenario, md, money

PA_PROCESS = [
    ("Phase 1 — Recovery Scoping Meeting", [
        "Conduct the Recovery Scoping Meeting with the Program Delivery Manager.",
        "Finalize the Impact List within the 60-day window.",
        "Submit pay policy, procurement policy, and insurance policy.",
    ]),
    ("Phase 2 — Project development and field reviews", [
        "Site inspections for work to be completed — in person, or tabletop for minor "
        "damage or work over 90 percent complete.",
        "Gather and organize required information and supporting documentation.",
        "Prepare and review the Damage, Description and Dimensions.",
    ]),
    ("Phase 3 — Scope and cost reviews", [
        "The Consolidated Resource Center drafts or validates the scope of work and costs.",
        "Hazard mitigation proposals are completed or validated.",
        "Insurance and quality control reviews.",
    ]),
    ("Phase 4 — Final reviews and signatures", [
        "Environmental and Historic Preservation review.",
        "Program Delivery Manager, FEMA PA, recipient, and applicant sign off.",
    ]),
    ("Phase 5 — Obligation", [
        "Funds are obligated — transferred to the recipient for management and distribution.",
        "Recovery Transition Meeting once version zero of all projects is obligated.",
    ]),
    ("Phase 6 — Post award", [
        "Project closeout: small project certification, or SOD-FIR for large projects.",
        "Record retention and audit exposure begin at RECIPIENT closeout.",
    ]),
]


def render() -> None:
    s = get_scenario()
    st.title("Training")

    tab_score, tab_process, tab_ref, tab_exercise = st.tabs(
        ["Scorecard", "The PA process", "Category reference", "Exercise"]
    )

    # -- scorecard -------------------------------------------------------------
    with tab_score:
        card = score(s)
        if not card.scorable:
            st.info(
                "Nothing to score yet. Build an impact list and formulate at least "
                "one project, or load the training scenario from the sidebar to work "
                "a package that already has errors in it."
            )
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("Score", f"{card.percent}%")
            c2.metric("Grade", card.grade)
            c3.metric("Points", f"{card.total} / {card.possible}")

            st.progress(min(1.0, card.percent / 100))
            st.caption(
                "Scored against the rules, not against one instructor's answer. A "
                "package that survives the engine is a package that survives a "
                "Consolidated Resource Center review."
            )

            for d in card.dimensions:
                with st.expander(
                    f"**{d.name}** — {d.points} / {d.weight} points",
                    expanded=d.score < 0.8,
                ):
                    st.write(d.detail)
                    if d.misses:
                        st.markdown("**What is costing points:**")
                        for m in d.misses:
                            st.markdown(f"- {md(m)}")
                    else:
                        st.success("Nothing outstanding here.")

            st.dataframe(
                pd.DataFrame([{
                    "Dimension": d.name,
                    "Weight": d.weight,
                    "Earned": d.points,
                } for d in card.dimensions]),
                use_container_width=True, hide_index=True,
            )

    # -- process ---------------------------------------------------------------
    with tab_process:
        st.write(
            "The Public Assistance grant runs six phases from the scoping meeting to "
            "closeout. Most of the applicant's leverage is in phases 1 and 2 — by the "
            "time a project reaches the Consolidated Resource Center, the "
            "documentation either exists or it does not."
        )
        d = s.disaster
        if d.declaration_date:
            resolved = s.rules.deadlines.resolve(
                d.declaration_date, d.rsm_date, d.designation_date)
            st.markdown("#### Your deadlines")
            for key, when in sorted(resolved.items(), key=lambda kv: kv[1]):
                st.write(
                    f"**{when:%B %d, %Y}** — {DEADLINE_LABELS.get(key, key)}"
                    + ("  *(no extensions permitted)*"
                       if key in NO_EXTENSION_DEADLINES else "")
                )

        for phase, steps in PA_PROCESS:
            with st.expander(phase, expanded=phase.startswith("Phase 1")):
                for step in steps:
                    st.markdown(f"- {step}")

        st.markdown("#### Cost share")
        st.markdown(f"""
The Stafford Act default is **{s.rules.cost_share.federal:.0%} federal /
{s.rules.cost_share.non_federal:.0%} applicant**. The applicant's share is real money
that has to come from somewhere — the general fund, a utility fund, a levy, or
donated resources credited against it.
        """)

        st.markdown("#### Project size")
        st.markdown(f"""
| | Small project | Large project |
|---|---|---|
| Threshold | ≥ {money(s.rules.thresholds.small_project_minimum)} | > {money(s.rules.thresholds.large_project_threshold)} |
| Payment | Estimate for work to be completed; actual cost for completed work | Actual cost only |
| Draws | Paid on obligation | Progressive, as work is completed |
| Retainage | None | {s.rules.thresholds.large_project_retainage:.0%} withheld from each payment |
| Closeout | Small project certification | SOD-FIR after final inspection |
| Simplified Procedures | Apply | Do not apply |
| Overrun remedy | Net Small Project Overrun appeal across all small projects | Actual cost is the basis; no NSPO |
        """)

    # -- reference -------------------------------------------------------------
    with tab_ref:
        st.write(
            "The labor column is the one that costs applicants money. **All Emergency "
            "Work — Cat-A debris and Cat-B protective measures — reimburses budgeted "
            "employees for overtime only.** Permanent work reimburses straight time as "
            "well. Temporary and emergency hires are fully eligible everywhere. Debris "
            "is the one category with a way back: electing the Section 428 alternative "
            "procedure makes straight time eligible there."
        )
        rows = []
        for code, cat in CATEGORIES.items():
            if cat.straight_time_eligible:
                st_label = "Eligible"
            elif cat.straight_time_exception:
                st_label = "NOT eligible (unless Section 428 elected)"
            else:
                st_label = "NOT eligible"
            rows.append({
                "Cat": code,
                "Name": cat.name,
                "Work type": cat.work_type.value,
                "Straight time (budgeted staff)": st_label,
                "406 mitigation": "Available" if cat.mitigation_eligible else "—",
                "PAPPG p.": cat.pappg_page,
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        st.markdown("#### Reductions applied before the cost share")
        st.markdown(f"""
| Reduction | When it applies | How it is sized |
|---|---|---|
| **Insurance proceeds** | Any insured facility | Actual **and anticipated** proceeds, whether or not a claim was filed |
| **Section 311 / NFIP** | Insurable **building**, in an SFHA identified over a year, damaged by **flood**, with no flood coverage | Maximum proceeds a standard NFIP policy would have paid — {money(s.rules.insurance.nfip_max_building)} building plus {money(s.rules.insurance.nfip_max_contents)} contents. **Sized on policy limits, not on damage**, so it routinely exceeds the whole project |
| **Codes and standards** | Upgrade driven by a code that fails any of the five criteria | The full upgrade cost becomes the applicant's own expense |
| **Section 428 fixed-cost offer** | Permanent work, offer accepted | Award capped at the offer; applicant carries the overrun |
        """)

        for code, cat in CATEGORIES.items():
            if cat.description:
                with st.expander(cat.label):
                    st.write(cat.description)

        st.markdown("#### Terms worth knowing before the scoping meeting")
        st.markdown("""
| Term | What it is |
|---|---|
| **PDMG** | Program Delivery Manager — the FEMA point of contact who runs the applicant's projects. |
| **RSM** | Recovery Scoping Meeting — starts the 60-day impact list clock. |
| **DDD** | Damage, Description and Dimensions — the narrative FEMA writes the scope of work from. |
| **SOW** | Scope of Work — what FEMA obligates against. Work outside it is not reimbursable. |
| **CRC** | Consolidated Resource Center — drafts and validates scope and cost. |
| **SPA** | Streamlined Project Application — required for emergency work and Cat-I. |
| **EHP** | Environmental and Historic Preservation review. |
| **SOD-FIR** | Statement of Documentation in Final Inspection Report — large project closeout. |
| **NSPO** | Net Small Project Overrun — the appeal route when small projects overrun in aggregate. |
| **RTM** | Recovery Transition Meeting — held once version zero of all projects is obligated. |
| **Force account** | The applicant's own staff and equipment, as opposed to contracted work. |
| **Obligation** | FEMA transferring funds to the recipient. Not the same as the applicant being paid. |
| **RPA** | Request for Public Assistance — the application itself, due 30 days from designation. The first deadline, and the one that ends the process if missed. |
| **Section 311** | The statutory NFIP reduction for an uninsured insurable building in a flood zone. Sized on policy limits, not on damage. |
| **Section 406** | Hazard mitigation funded as part of a permanent work project, to protect the damaged element against the next event. |
| **Section 428** | Alternative Procedures. For debris: straight-time labor, an increased cost share, retained recycling revenue. For permanent work: a fixed-cost offer with scope flexibility. |
| **Section 404 / HMGP** | The Hazard Mitigation Grant Program — statewide, state-administered, and separate from PA. |
| **Recipient / Subrecipient** | The state is the recipient; the applicant is the subrecipient. Deadlines, retention, and management cost caps differ between them. |
        """)

    # -- exercise --------------------------------------------------------------
    with tab_exercise:
        st.write(
            "Load the training scenario from the sidebar and work it as the applicant. "
            "Fix what the compliance review flags, claim what the package leaves on "
            "the table, and watch the scorecard move. The prompts below each map to "
            "something the engine checks, so they can be self-assessed before "
            "submission."
        )
        if not s.projects:
            st.info(
                "No scenario is loaded. Use **Load training scenario** in the sidebar "
                "to start from a package that already contains errors, or build your "
                "own from the Impact List page."
            )
        for i, prompt in enumerate(REFLECTION_PROMPTS, 1):
            with st.container(border=True):
                st.markdown(f"**{i}.** {md(prompt)}")

        st.markdown("#### Suggested assignment structure")
        st.markdown("""
0. **Load the training scenario** from the sidebar.
1. **Read the scenario.** Applicant profile, declaration, incident period, impact list.
2. **Formulate projects.** Group the impact list. Justify every grouping decision that
   moves a project across the minimum or the large-project threshold.
3. **Build costs.** Force account labor and equipment, contracts, materials. Get the
   Cat-B straight-time rule right.
4. **Run compliance.** Clear every blocking finding, and write one paragraph on each
   caution you chose not to clear and why.
5. **Claim what is available.** Cat-Z management costs and Section 406 mitigation.
6. **Assemble and export the package.** Submit the DDD, the cost summary, and the
   documentation checklist.
7. **Reflect.** Answer three of the prompts above in writing.
        """)
