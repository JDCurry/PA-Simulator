"""Package assembly: DDD narratives, cost summaries, checklists, and exports."""

from __future__ import annotations

import hashlib

import pandas as pd
import streamlit as st

from pa.costing import summarize_project, summarize_scenario
from pa.export import (
    cost_summary_text, ddd_narrative, documentation_checklist, full_package,
    impact_list_csv, inferred_documentation_items, project_summary_csv,
    reimbursement_request,
)
from pa.formulation import classify
from pa.rules import CATEGORIES
from .common import active_project, get_scenario, money, money_plain, touch


def render() -> None:
    s = get_scenario()
    st.title("Package")

    if not s.projects:
        st.warning("Formulate at least one project first.")
        return

    t = summarize_scenario(s)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Net eligible", money_plain(t.net_eligible))
    c2.metric(f"Federal ({s.rules.cost_share.federal:.0%})", money_plain(t.federal_share))
    c3.metric("Applicant out of pocket", money_plain(t.applicant_out_of_pocket))
    c4.metric("Projects", f"{t.large_projects}L / {t.small_projects}S")

    tab_port, tab_proj, tab_export = st.tabs(
        ["Portfolio", "Project detail", "Export"]
    )

    # -- portfolio -------------------------------------------------------------
    with tab_port:
        if t.by_category:
            rows = [{
                "Category": f"Cat-{code}",
                "Name": CATEGORIES[code].name if code in CATEGORIES else "",
                "Work type": CATEGORIES[code].work_type.value if code in CATEGORIES else "",
                "Net eligible": amount,
            } for code, amount in sorted(t.by_category.items())]
            st.dataframe(
                pd.DataFrame(rows), use_container_width=True, hide_index=True,
                column_config={
                    "Net eligible": st.column_config.NumberColumn(format="$%.2f")},
            )
            st.bar_chart(
                pd.DataFrame({"Net eligible": t.by_category}).sort_index(),
                horizontal=True,
            )

        if t.section_311_reduction > 0:
            st.markdown("#### Section 311 mandatory reduction")
            r1, r2 = st.columns(2)
            r1.metric("Total reduction", money_plain(t.section_311_reduction))
            r2.metric(
                "Share of gross eligible",
                f"{t.section_311_reduction / t.gross_eligible:.1%}"
                if t.gross_eligible else "—")
            st.error(
                f"{money(t.section_311_reduction)} removed before the cost share is "
                "even applied, because insurable buildings in Special Flood Hazard "
                "Areas were damaged by flood without flood coverage. The reduction is "
                "sized on maximum NFIP policy proceeds, not on the damage, and it "
                "recurs in every future flood until the coverage is in place."
            )

        st.markdown("#### Management costs (Cat-Z)")
        c1, c2, c3 = st.columns(3)
        c1.metric(
            f"Applicant cap ({s.rules.management.applicant_cap_rate:.0%})",
            money_plain(t.management_cost_cap))
        c2.metric("Claimed", money_plain(t.management_cost_claimed))
        c3.metric(
            f"State recipient ({s.rules.management.recipient_cap_rate:.0%})",
            money_plain(t.recipient_management_cost_cap))
        st.caption(
            f"DRRA Sec. 1215 sets a combined "
            f"{s.rules.management.combined_cap_rate:.0%} — "
            f"{s.rules.management.recipient_cap_rate:.0%} for the state recipient and "
            f"{s.rules.management.applicant_cap_rate:.0%} for the applicant. The "
            "recipient's portion is not the applicant's money, but it funds the state "
            "PA staff supporting this grant."
        )
        if t.management_cost_claimed == 0 and t.management_cost_cap > 0:
            st.warning(
                f"No management costs claimed. Up to {money(t.management_cost_cap)} is "
                "available for the staff time spent gathering documentation, attending "
                "site visits, submitting for payment, and assembling closeout. Costs "
                "must be actual and auditable, so the time has to be tracked from the "
                "start of the grant rather than reconstructed at the end."
            )
        elif t.management_cost_claimed > t.management_cost_cap:
            st.error(
                f"Claimed {money(t.management_cost_claimed)} against a cap of "
                f"{money(t.management_cost_cap)}. The excess is not reimbursable."
            )

        if t.below_minimum:
            st.error(
                f"{t.below_minimum} project(s) fall below the "
                f"{money(s.rules.thresholds.small_project_minimum)} minimum and cannot "
                "be written as formulated."
            )
        if t.single_audit_triggered:
            st.info(
                f"Federal share of {money(t.federal_share)} meets the Single Audit Act "
                f"threshold of {money(s.rules.thresholds.single_audit)} in federal "
                "funds expended in a fiscal year. A single audit will be required."
            )

        st.text(reimbursement_request(s))

    # -- project detail --------------------------------------------------------
    with tab_proj:
        project = active_project(s, key="package_project")
        if project is None:
            return
        cls = classify(project, s)
        st.markdown(f"**{cls.size} project** — {cls.application_form}")

        st.markdown("#### Damage, Description and Dimensions")
        st.text(ddd_narrative(project, s))

        st.markdown("#### Cost summary")
        st.text(cost_summary_text(project, s))

        st.markdown("#### Documentation checklist")
        items = documentation_checklist(project, s)
        done = sum(1 for _, ok in items if ok)
        st.progress(done / len(items) if items else 0.0,
                    text=f"{done} of {len(items)} satisfied")
        st.caption(
            "Greyed items are determined from the data you entered elsewhere and "
            "cannot be checked here. The rest are records this tool has nowhere to "
            "store — confirm they are in the project file."
        )

        inferred = inferred_documentation_items()
        confirmed = set(project.documentation_confirmed)
        changed = False
        for item, ok in items:
            if item in inferred:
                st.markdown(f"`{'x' if ok else ' '}`  {item}")
                continue
            # Stable key: Python's hash() is salted per process, so it cannot be
            # used to identify a widget across runs.
            slug = hashlib.md5(item.encode("utf-8")).hexdigest()[:10]
            new = st.checkbox(item, value=item in confirmed,
                              key=f"doc_{project.id}_{slug}")
            if new and item not in confirmed:
                confirmed.add(item)
                changed = True
            elif not new and item in confirmed:
                confirmed.discard(item)
                changed = True
        if changed:
            project.documentation_confirmed = sorted(confirmed)
            touch()
            st.rerun()

    # -- export ----------------------------------------------------------------
    with tab_export:
        st.caption(
            "Retain all original documents; provide only copies to FEMA, preferably "
            f"digital. Federal retention is {s.rules.documentation.federal_retention_years} "
            "years from RECIPIENT closeout — not applicant closeout — and Washington "
            f"requires {s.rules.documentation.state_retention_years}."
        )
        name = (s.disaster.number or "disaster").replace("/", "-")

        c1, c2 = st.columns(2)
        c1.download_button(
            "Full package (TXT)", data=full_package(s),
            file_name=f"{name}_pa_package.txt", mime="text/plain",
            use_container_width=True)
        c2.download_button(
            "Reimbursement request (TXT)", data=reimbursement_request(s),
            file_name=f"{name}_reimbursement_request.txt", mime="text/plain",
            use_container_width=True)
        c1.download_button(
            "Project summary (CSV)", data=project_summary_csv(s),
            file_name=f"{name}_projects.csv", mime="text/csv",
            use_container_width=True)
        c2.download_button(
            "Impact list (CSV)", data=impact_list_csv(s),
            file_name=f"{name}_impact_list.csv", mime="text/csv",
            use_container_width=True)

        st.divider()
        st.markdown("#### Conditions of payment")
        st.markdown(f"""
- No reimbursement can be made until the contract between the state military
  department and the applicant has been received and signed by all parties.
- Payment is released on submission of a signed **A-19A Invoice Voucher**, made
  electronically by direct deposit.
- **Large projects** are paid progressively against actual cost, with
  **{s.rules.thresholds.large_project_retainage:.0%} retainage** withheld from each
  payment and released on FEMA approval of the final inspection. Closeout requires a
  signed **SOD-FIR**.
- **Small projects** are paid on the approved estimate for work to be completed and on
  actual cost for work already done. Closeout requires a signed **small project
  certification**.
- If costs across *all* small projects overrun their estimates, a **Net Small Project
  Overrun** appeal may be filed — based on actual costs for every small project.
- Appeals: **{s.rules.appeals.first_appeal_days} days** from receipt of a Determination
  Memo for a first appeal, and another {s.rules.appeals.second_appeal_days} days from
  the first appeal decision for a second.
- **Arbitration** is available in lieu of a second appeal for disputes at or above
  **{money(t.arbitration_threshold)}** (DRRA Sec. 1219).
        """)
