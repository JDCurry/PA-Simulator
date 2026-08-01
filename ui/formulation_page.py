"""Project formulation: grouping sites, and what the grouping decides."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from pa.costing import summarize_project
from pa.formulation import auto_group, classify, review_grouping
from pa.models import Project
from pa.rules import CATEGORIES
from .common import get_scenario, md, money, touch



def render() -> None:
    s = get_scenario()
    st.title("Project Formulation")
    st.write(
        "Grouping is a funding decision, not a filing decision. It determines whether "
        "costs clear the minimum, whether a project crosses the large-project "
        "threshold and picks up actual-cost accounting and retainage, and which "
        "application form the work goes on."
    )

    with st.expander("The grouping conventions this follows"):
        st.markdown(f"""
- **Category never mixes.** A Cat-A site and a Cat-B site are separate projects.
- **Cat-I is always one project**, and **Cat-Z is always one project** per applicant.
- **Completed work is separated from work to be completed** — one is paid on actual
  cost, the other on an approved estimate.
- **Emergency work may be combined jurisdiction-wide.** Permanent work is grouped by
  facility and by logical or geographic proximity.
- Anything under **{money(s.rules.thresholds.small_project_minimum)}** is not a
  project at all. Combining sites in the same category and completion status is the
  remedy.
        """)

    unassigned = s.unassigned_sites()
    c1, c2, c3 = st.columns(3)
    c1.metric("Sites on the impact list", len(s.sites))
    c2.metric("Projects formulated", len(s.projects))
    c3.metric("Sites not yet assigned", len(unassigned))

    tab_auto, tab_manage, tab_review = st.tabs(
        ["Propose grouping", "Manage projects", "Review"]
    )

    # -- propose ---------------------------------------------------------------
    with tab_auto:
        if not unassigned:
            st.success("Every site on the impact list is assigned to a project.")
        else:
            st.write(f"{len(unassigned)} unassigned site(s) would group as follows.")
            proposed = auto_group(s)
            for p in proposed:
                sites = [x for x in s.sites if x.id in p.site_ids]
                total = sum(x.approx_cost for x in sites)
                with st.container(border=True):
                    st.markdown(f"**{p.title}** — {len(sites)} site(s), {money(total)}")
                    for x in sites:
                        st.caption(f"• {x.name} — {money(x.approx_cost)}, "
                                   f"{x.percent_complete:.0%} complete")
                    if total < s.rules.thresholds.small_project_minimum:
                        st.warning(
                            f"This group totals less than the "
                            f"{money(s.rules.thresholds.small_project_minimum)} minimum "
                            "and cannot stand as a project."
                        )

            if st.button("Accept proposed grouping", type="primary"):
                s.projects.extend(proposed)
                touch()
                st.success(f"Added {len(proposed)} project(s).")
                st.rerun()

    # -- manage ----------------------------------------------------------------
    with tab_manage:
        if not s.projects:
            st.info("No projects yet. Propose a grouping, or add one below.")

        with st.expander("Add an empty project"):
            c1, c2 = st.columns([3, 1])
            title = c1.text_input("Title", key="new_project_title")
            code = c2.selectbox(
                "Category", list(CATEGORIES), key="new_project_cat",
                format_func=lambda c: f"{c} — {CATEGORIES[c].name}")
            if st.button("Add project") and title:
                s.projects.append(Project(title=title, category=code))
                touch()
                st.rerun()

        for p in list(s.projects):
            cs = summarize_project(p, s)
            cls = classify(p, s)
            with st.expander(
                f"{p.title} — {money(cs.net_eligible)} ({cls.size} project)"
            ):
                c1, c2 = st.columns([3, 1])
                p.title = c1.text_input("Title", p.title, key=f"t_{p.id}")
                p.category = c2.selectbox(
                    "Category", list(CATEGORIES),
                    index=list(CATEGORIES).index(p.category.upper())
                    if p.category.upper() in CATEGORIES else 0,
                    key=f"c_{p.id}")

                options = {x.name or x.id: x.id for x in s.sites}
                current = [n for n, sid in options.items() if sid in p.site_ids]
                chosen = st.multiselect(
                    "Sites in this project", list(options), current, key=f"s_{p.id}")
                p.site_ids = [options[n] for n in chosen]

                p.project_option = st.selectbox(
                    "Project option", ["Standard", "Improved", "Alternate", "Section 428"],
                    index=["Standard", "Improved", "Alternate", "Section 428"].index(
                        p.project_option) if p.project_option in
                    ["Standard", "Improved", "Alternate", "Section 428"] else 0,
                    key=f"opt_{p.id}",
                    help="Improved and Alternate projects cap FEMA funding at the "
                         "estimate to restore pre-disaster design and function, and "
                         "both require written state approval BEFORE work proceeds.",
                )
                if p.project_option in ("Improved", "Alternate"):
                    p.state_written_approval = st.checkbox(
                        "Written approval from the state recipient is on file",
                        p.state_written_approval, key=f"appr_{p.id}")
                    st.caption(
                        "Must be requested in writing within 12 months of the RSM, and "
                        "funding is limited to the approved estimate or the actual "
                        "cost, whichever is less."
                    )

                st.markdown(
                    f"**{cls.size} project** — {cls.payment_basis}  \n"
                    f"Application: {cls.application_form}  \n"
                    f"Closeout: {cls.closeout_document}"
                )
                for note in cls.notes:
                    st.caption(f"• {md(note)}")

                if st.button("Delete project", key=f"d_{p.id}"):
                    s.projects.remove(p)
                    touch()
                    st.rerun()

        if s.projects and st.button("Save changes", type="primary", key="save_formulation"):
            touch()
            st.success("Saved.")
            st.rerun()

    # -- review ----------------------------------------------------------------
    with tab_review:
        issues = review_grouping(s)
        errors = [i for i in issues if i.severity == "error"]
        warnings = [i for i in issues if i.severity == "warning"]

        if not issues:
            st.success("The grouping is consistent with FEMA's conventions.")
        for i in errors:
            st.error(md(i.message))
        for i in warnings:
            st.warning(md(i.message))

        if s.projects:
            st.markdown("#### Portfolio")
            rows = []
            for p in s.projects:
                cs = summarize_project(p, s)
                cls = classify(p, s)
                rows.append({
                    "Project": p.title,
                    "Cat": p.category,
                    "Sites": len(p.site_ids),
                    "Size": cls.size,
                    "Net eligible": cs.net_eligible,
                    "Federal": cs.federal_share,
                    "Applicant": cs.applicant_out_of_pocket,
                    "Form": "SPA" if "Streamlined" in cls.application_form else "Standard",
                })
            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True, hide_index=True,
                column_config={
                    "Net eligible": st.column_config.NumberColumn(format="$%.2f"),
                    "Federal": st.column_config.NumberColumn(format="$%.2f"),
                    "Applicant": st.column_config.NumberColumn(format="$%.2f"),
                },
            )
