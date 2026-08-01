"""Cost buildup: force account labor and equipment, contracts, donated resources,
and Section 406 mitigation, for one project at a time."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from pa.costing import (
    eligible_codes_and_standards, eligible_mitigation, summarize_project,
)
from pa.equipment import by_cost_code, is_equipment_not_supply, search
from pa.formulation import classify
from pa.models import (
    CodeStandard, CostType, DonatedResourceLine, EmployeeClass, EquipmentLine,
    LaborLine, MitigationProposal, SimpleCostLine,
)
from pa.rules import CATEGORIES
from .common import (
    active_project, date_input_optional, get_scenario, md, money, money_plain, touch,
)


def render() -> None:
    s = get_scenario()
    st.title("Cost Buildup")

    if not s.projects:
        st.warning("Formulate at least one project first.")
        return

    project = active_project(s)
    if project is None:
        return

    cat = CATEGORIES.get(project.category.upper())
    cs = summarize_project(project, s)
    cls = classify(project, s)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Net eligible", money_plain(cs.net_eligible))
    c2.metric(f"Federal ({s.rules.cost_share.federal:.0%})", money_plain(cs.federal_share))
    c3.metric("Applicant out of pocket", money_plain(cs.applicant_out_of_pocket))
    c4.metric("Classification", cls.size)

    if cat:
        st.caption(f"**{cat.label}** — {cat.work_type.value}. {cat.description}")

    if cs.cost_share_note:
        st.info(cs.cost_share_note)

    tabs = st.tabs([
        "Labor", "Equipment", "Contracts & materials", "Donated resources",
        "406 Mitigation", "Codes & standards", "Section 428", "Summary",
    ])

    with tabs[0]:
        _labor(project, s, cat)
    with tabs[1]:
        _equipment(project, s)
    with tabs[2]:
        _costs(project, s)
    with tabs[3]:
        _donated(project, s)
    with tabs[4]:
        _mitigation(project, s)
    with tabs[5]:
        _codes_and_standards(project, s)
    with tabs[6]:
        _section_428(project, s)
    with tabs[7]:
        _summary(project, s)


# -- codes and standards -------------------------------------------------------


def _codes_and_standards(project, s) -> None:
    criteria = s.rules.codes_and_standards.criteria
    st.caption(
        "FEMA funds restoration to pre-disaster design in conformity with current "
        "applicable codes and standards. An upgrade driven by a code is eligible only "
        "if the code satisfies ALL FIVE criteria below. Failing any one of them makes "
        "the upgrade the applicant's own expense."
    )
    for _, label in criteria:
        st.markdown(f"- {label}")

    frame = pd.DataFrame([{
        "Citation": c.citation,
        "Description": c.description,
        "Upgrade cost": c.upgrade_cost,
        **{label: getattr(c, key) for key, label in criteria},
    } for c in project.codes_and_standards], columns=[
        "Citation", "Description", "Upgrade cost", *[l for _, l in criteria],
    ])

    edited = st.data_editor(
        frame, num_rows="dynamic", use_container_width=True,
        column_config={
            "Upgrade cost": st.column_config.NumberColumn(format="$%.2f"),
            **{label: st.column_config.CheckboxColumn(width="small")
               for _, label in criteria},
        },
        key=f"codes_{project.id}",
    )

    if st.button("Save codes and standards", type="primary", key=f"savecs_{project.id}"):
        project.codes_and_standards = [
            CodeStandard(
                citation=str(r.get("Citation") or ""),
                description=str(r.get("Description") or ""),
                upgrade_cost=float(r.get("Upgrade cost") or 0),
                **{key: bool(r.get(label)) for key, label in criteria},
            )
            for _, r in edited.iterrows()
            if str(r.get("Description") or r.get("Citation") or "").strip()
        ]
        touch()
        st.rerun()

    if project.codes_and_standards:
        eligible, excluded, notes = eligible_codes_and_standards(project, s.rules)
        c1, c2 = st.columns(2)
        c1.metric("Eligible upgrade cost", money_plain(eligible))
        c2.metric("Not eligible", money_plain(excluded))
        for n in notes:
            (st.error if "not eligible" in n else st.success)(md(n))


# -- Section 428 ---------------------------------------------------------------


def _section_428(project, s) -> None:
    code = project.category.upper()
    cat = CATEGORIES.get(code)
    elected = s.applicant.section_428_debris_straight_time
    rules = s.rules.section_428

    if code == "A":
        st.markdown("#### Debris removal alternative procedures")
        if not elected:
            st.warning(
                "The Section 428 debris election has not been made. Elect it on the "
                "Scenario page to make straight-time force account labor eligible for "
                "budgeted employees, unlock the increased federal cost share below, "
                "and retain recycling revenue."
            )
        else:
            st.success("Section 428 debris procedures elected for this disaster.")

        tiers = " | ".join(
            f"within {days} days: {share:.0%}"
            for days, share in rules.debris_cost_share_tiers
        )
        st.caption(
            f"Increased federal cost share for accelerated completion, measured from "
            f"the END of the incident period — {tiers}. Past "
            f"{rules.debris_deadline_days} days there is no reimbursement without an "
            "approved time extension. FEMA applies the scale to costs INCURRED inside "
            "each window, so debris spanning windows is normally formulated as "
            "separate projects per window."
        )

        project.debris_completion_date = date_input_optional(
            "Debris work completed", project.debris_completion_date,
            f"debris_{project.id}")

        project.recycling_revenue = st.number_input(
            "Recycling revenue retained ($)", value=float(project.recycling_revenue),
            min_value=0.0, step=1_000.0, key=f"recyc_{project.id}",
            help="Under the election the applicant keeps recycling income rather than "
                 "offsetting it against eligible cost. Recorded for the file.")

        cs = summarize_project(project, s)
        c1, c2 = st.columns(2)
        c1.metric("Federal share applied", f"{cs.federal_share_rate:.0%}")
        c2.metric("Federal share", money_plain(cs.federal_share))
        if cs.cost_share_note:
            st.info(md(cs.cost_share_note))

    elif cat and cat.work_type.value == "Permanent Work":
        st.markdown("#### Permanent work fixed-cost offer")
        st.caption(
            "Under Section 428 the applicant may accept a fixed-cost offer. In "
            "exchange for capping the award and taking on the overrun risk, the "
            "applicant is freed from rebuilding to pre-disaster design and may move "
            "funds across all of its alternative procedures projects. Excess funds may "
            "be retained for limited purposes. The offer is subject to acceptance."
        )
        project.fixed_cost_offer = st.number_input(
            "Fixed-cost offer ($)", value=float(project.fixed_cost_offer),
            min_value=0.0, step=10_000.0, key=f"fco_{project.id}")
        project.fixed_cost_offer_accepted = st.checkbox(
            "Offer accepted", project.fixed_cost_offer_accepted,
            key=f"fcoa_{project.id}")

        cs = summarize_project(project, s)
        if project.fixed_cost_offer_accepted and project.fixed_cost_offer > 0:
            c1, c2 = st.columns(2)
            c1.metric("Award (capped)", money_plain(cs.net_eligible))
            c2.metric("Variance vs. estimate", money_plain(cs.fixed_cost_variance))
            if cs.fixed_cost_variance < 0:
                st.warning(
                    f"The offer is {money(abs(cs.fixed_cost_variance))} BELOW the "
                    "estimated eligible cost. Accepting means absorbing that "
                    "difference."
                )
            elif cs.fixed_cost_variance > 0:
                st.success(
                    f"The offer is {money(cs.fixed_cost_variance)} above the estimated "
                    "eligible cost. Excess funds may be retained for limited purposes."
                )
    else:
        st.info(
            f"Section 428 alternative procedures apply to debris removal (Cat-A) and "
            f"to permanent work (Cat-C through G). This is a Cat-{code} project."
        )


# -- labor ---------------------------------------------------------------------


def _labor(project, s, cat) -> None:
    elected = (
        cat is not None
        and cat.straight_time_exception == "section_428_debris_straight_time"
        and s.applicant.section_428_debris_straight_time
    )

    if cat and elected:
        st.info(
            f"**Cat-{cat.code} with the Section 428 debris procedure elected.** "
            "Straight time IS eligible for budgeted employees on eligible debris work "
            "because of the election. Without it, only overtime would count."
        )
    elif cat and not cat.straight_time_eligible:
        msg = (
            f"**Cat-{cat.code} reimburses budgeted employees for overtime only.** "
            "Straight time for regular staff is not eligible here — those hours are "
            "part of what the jurisdiction was already paying for. Temporary and "
            "emergency hires are fully eligible, straight time included. "
            f"(PAPPG V5 p.{cat.pappg_page})"
        )
        if cat.straight_time_exception == "section_428_debris_straight_time":
            msg += (
                "  \n\nDebris is the one category with an exception: electing the "
                "**Section 428 alternative procedure** on the Scenario page makes "
                "straight time eligible for budgeted employees here."
            )
        st.warning(msg)
    elif cat:
        st.info(
            f"Cat-{cat.code} reimburses all force account labor and fringe benefits, "
            "straight time included."
        )

    frame = pd.DataFrame([{
        "Description": l.description,
        "Class": l.employee_class.value,
        "Staff": l.employee_count,
        "ST hours": l.straight_time_hours,
        "OT hours": l.overtime_hours,
        "ST rate": l.straight_rate,
        "OT rate": l.overtime_rate,
        "Fringe %": l.fringe_rate,
    } for l in project.labor], columns=[
        "Description", "Class", "Staff", "ST hours", "OT hours",
        "ST rate", "OT rate", "Fringe %",
    ])

    edited = st.data_editor(
        frame, num_rows="dynamic", use_container_width=True,
        column_config={
            "Class": st.column_config.SelectboxColumn(
                options=[e.value for e in EmployeeClass], width="medium"),
            "Staff": st.column_config.NumberColumn(min_value=1, step=1),
            "ST rate": st.column_config.NumberColumn(format="$%.2f"),
            "OT rate": st.column_config.NumberColumn(
                format="$%.2f", help="Leave at 0 to default to time and a half."),
            "Fringe %": st.column_config.NumberColumn(
                format="%.2f", help="As a fraction of base pay, e.g. 0.34 for 34%."),
        },
        key=f"labor_{project.id}",
    )

    if st.button("Save labor", type="primary", key=f"savelab_{project.id}"):
        project.labor = [
            LaborLine(
                description=str(r.get("Description") or ""),
                employee_class=EmployeeClass(r.get("Class") or EmployeeClass.BUDGETED.value),
                employee_count=int(r.get("Staff") or 1),
                straight_time_hours=float(r.get("ST hours") or 0),
                overtime_hours=float(r.get("OT hours") or 0),
                straight_rate=float(r.get("ST rate") or 0),
                overtime_rate=float(r.get("OT rate") or 0),
                fringe_rate=float(r.get("Fringe %") or 0),
            )
            for _, r in edited.iterrows()
            if str(r.get("Description") or "").strip()
        ]
        touch()
        st.rerun()

    cs = summarize_project(project, s)
    L = cs.labor
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Straight time eligible", money_plain(L.straight_time_eligible))
    c2.metric("Overtime", money_plain(L.overtime))
    c3.metric("Fringe", money_plain(L.fringe))
    c4.metric("Labor total", money_plain(L.total))

    if L.straight_time_excluded:
        st.error(
            f"**{money(L.straight_time_excluded)} of straight-time labor is not "
            f"eligible.** {md(L.exclusion_reason)}"
        )

    st.caption(
        "Records FEMA will ask for: names, dates, time in and out, work performed, "
        "and location — per employee, per day."
    )


# -- equipment -----------------------------------------------------------------


def _equipment(project, s) -> None:
    st.caption(
        "Applicant-owned equipment is billed at the FEMA Schedule of Equipment Rates, "
        "which already covers depreciation, overhead, maintenance, fuel, and tires. "
        "Operator labor is **not** in the rate — claim it separately on the Labor tab. "
        "Standby time is never eligible."
    )

    with st.expander("Look up a FEMA rate", expanded=not project.equipment):
        query = st.text_input(
            "Search the schedule", key=f"eqsearch_{project.id}",
            placeholder="dump truck, excavator, generator, pump, sweeper…")
        results = search(query, limit=25) if query else []
        if query and not results:
            st.info("No match. Try a broader term — the schedule names equipment by type.")
        for r in results[:12]:
            c1, c2 = st.columns([5, 1])
            detail = r.capacity or r.specification or r.manufacturer
            meta = " • ".join(x for x in (f"Code {r.cost_code}", r.notes) if x)
            c1.markdown(
                f"**{r.equipment}**" + (f" — {detail}" if detail else "")
                + f"  \n<small>{meta}</small>",
                unsafe_allow_html=True,
            )
            c2.markdown(
                md(f"**{money_plain(r.rate)}**") + f"  \n<small>per {r.unit.lower()}</small>",
                unsafe_allow_html=True,
            )
            if c2.button("Add", key=f"add_{project.id}_{r.cost_code}"):
                project.equipment.append(EquipmentLine(
                    description=f"{r.equipment} — {r.capacity or r.specification}".strip(" —"),
                    fema_cost_code=r.cost_code, fema_rate=r.rate, unit=r.unit, hours=0.0,
                ))
                touch()
                st.rerun()

    frame = pd.DataFrame([{
        "Description": e.description,
        "Code": e.fema_cost_code,
        "Hours": e.hours,
        "FEMA rate": e.fema_rate,
        "Adopted rate": e.adopted_rate,
        "Standby hours": e.standby_hours,
    } for e in project.equipment], columns=[
        "Description", "Code", "Hours", "FEMA rate", "Adopted rate", "Standby hours",
    ])

    edited = st.data_editor(
        frame, num_rows="dynamic", use_container_width=True,
        column_config={
            "FEMA rate": st.column_config.NumberColumn(format="$%.2f"),
            "Adopted rate": st.column_config.NumberColumn(
                format="$%.2f",
                help="Only used if the applicant has locally adopted rates. FEMA pays "
                     "the lesser of the two."),
            "Standby hours": st.column_config.NumberColumn(
                help="Recorded for the file. Never reimbursable."),
        },
        key=f"equip_{project.id}",
    )

    if st.button("Save equipment", type="primary", key=f"saveeq_{project.id}"):
        lines = []
        for _, r in edited.iterrows():
            desc = str(r.get("Description") or "").strip()
            code = str(r.get("Code") or "").strip()
            if not desc and not code:
                continue
            rate = float(r.get("FEMA rate") or 0)
            if not rate and code:
                match = by_cost_code(code)
                rate = match.rate if match else 0.0
            adopted = r.get("Adopted rate")
            lines.append(EquipmentLine(
                description=desc, fema_cost_code=code,
                hours=float(r.get("Hours") or 0), fema_rate=rate,
                adopted_rate=None if adopted in (None, "") or pd.isna(adopted)
                else float(adopted),
                standby_hours=float(r.get("Standby hours") or 0),
            ))
        project.equipment = lines
        touch()
        st.rerun()

    cs = summarize_project(project, s)
    c1, c2, c3 = st.columns(3)
    c1.metric("Equipment total", money_plain(cs.equipment.total))
    c2.metric("Standby excluded", money_plain(cs.equipment.standby_excluded))
    c3.metric("Rate reduction", money_plain(cs.equipment.rate_reduction))
    for n in cs.equipment.notes:
        st.info(md(n))

    with st.expander("Equipment or supply? (it matters at closeout)"):
        st.caption(md(
            "Equipment has a useful life over one year AND a per-unit cost at or above "
            "the lesser of the applicant's capitalization level and $10,000. On a large "
            "project, retained equipment worth $10,000 or more at the work completion "
            "deadline means compensating FEMA."
        ))
        c1, c2 = st.columns(2)
        cost = c1.number_input("Per-unit acquisition cost ($)", value=0.0, step=500.0,
                               key=f"eqtest_cost_{project.id}")
        life = c2.number_input("Useful life (years)", value=0.0, step=0.5,
                               key=f"eqtest_life_{project.id}")
        if cost or life:
            _, why = is_equipment_not_supply(
                cost, life, s.applicant.capitalization_level,
                s.rules.thresholds.equipment_capitalization)
            st.write(md(why))


# -- contracts and materials ---------------------------------------------------


def _costs(project, s) -> None:
    st.caption(
        "Procurement is where otherwise-eligible work gets de-obligated. The method "
        "required scales with the contract value, and the file has to show it."
    )
    t = s.rules.thresholds
    st.markdown(
        f"Under **{money(t.micro_purchase)}**: micro-purchase, no quotes required. "
        f"Up to **{money(t.simplified_acquisition)}**: rate or price quotes. "
        f"At or above **{money(t.simplified_acquisition)}**: sealed bid or competitive "
        "proposal."
    )

    frame = pd.DataFrame([{
        "Type": c.cost_type.value,
        "Description": c.description,
        "Vendor": c.vendor,
        "Qty": c.quantity,
        "Unit cost": c.unit_cost,
        "Competed": c.competed,
        "SAM checked": c.sam_debarment_checked,
        "CPPC": c.cost_plus_percentage_of_cost,
        "Prevailing wage": c.prevailing_wage_paid,
    } for c in project.costs], columns=[
        "Type", "Description", "Vendor", "Qty", "Unit cost",
        "Competed", "SAM checked", "CPPC", "Prevailing wage",
    ])

    edited = st.data_editor(
        frame, num_rows="dynamic", use_container_width=True,
        column_config={
            "Type": st.column_config.SelectboxColumn(
                options=[c.value for c in CostType], width="medium"),
            "Unit cost": st.column_config.NumberColumn(format="$%.2f"),
            "Competed": st.column_config.CheckboxColumn(
                help="Solicitation, bid tabulation, and award in the file."),
            "SAM checked": st.column_config.CheckboxColumn(
                help="Contractor confirmed not debarred at sam.gov, documented."),
            "CPPC": st.column_config.CheckboxColumn(
                help="Cost-plus-percentage-of-cost — prohibited outright for "
                     "non-state entities."),
        },
        key=f"costs_{project.id}",
    )

    if st.button("Save costs", type="primary", key=f"savecost_{project.id}"):
        project.costs = [
            SimpleCostLine(
                cost_type=CostType(r.get("Type") or CostType.MATERIALS.value),
                description=str(r.get("Description") or ""),
                vendor=str(r.get("Vendor") or ""),
                quantity=float(r.get("Qty") or 0),
                unit_cost=float(r.get("Unit cost") or 0),
                competed=bool(r.get("Competed")),
                sam_debarment_checked=bool(r.get("SAM checked")),
                cost_plus_percentage_of_cost=bool(r.get("CPPC")),
                prevailing_wage_paid=bool(r.get("Prevailing wage")),
            )
            for _, r in edited.iterrows()
            if str(r.get("Description") or "").strip()
        ]
        touch()
        st.rerun()

    for c in project.contracts():
        label = c.description or c.vendor or c.id
        method = s.rules.procurement_method(c.total)
        if c.cost_plus_percentage_of_cost:
            st.error(f"**{label}** — cost-plus-percentage-of-cost contracts are "
                     "prohibited. These costs are ineligible.")
        elif not c.competed and c.total >= t.micro_purchase:
            st.error(f"**{label}** ({money(c.total)}) — not documented as competed. "
                     f"Required: {method}.")
        else:
            st.caption(f"**{label}** ({money(c.total)}) — {method}")
        if not c.sam_debarment_checked:
            st.warning(f"**{label}** — no documented SAM.gov debarment check.")


# -- donated -------------------------------------------------------------------


def _donated(project, s) -> None:
    st.caption(
        "Donated labor, equipment, and materials do **not** add to the project cost. "
        "Their value is credited against the applicant's non-federal share, capped at "
        "that share. They never increase the federal contribution, and Simplified "
        "Procedures do not apply to them."
    )

    frame = pd.DataFrame([{
        "Type": d.resource_type,
        "Description": d.description,
        "Donor": d.donor,
        "Hours / Qty": d.hours_or_quantity,
        "Rate": d.valuation_rate,
        "Valuation basis": d.rate_basis,
    } for d in project.donated], columns=[
        "Type", "Description", "Donor", "Hours / Qty", "Rate", "Valuation basis",
    ])

    edited = st.data_editor(
        frame, num_rows="dynamic", use_container_width=True,
        column_config={
            "Type": st.column_config.SelectboxColumn(
                options=["Labor", "Equipment", "Materials"]),
            "Rate": st.column_config.NumberColumn(format="$%.2f"),
            "Valuation basis": st.column_config.TextColumn(
                help="Donated labor is valued at the rate for equivalent work in the "
                     "applicant's area. The basis has to be in the file."),
        },
        key=f"donated_{project.id}",
    )

    if st.button("Save donated resources", type="primary", key=f"savedon_{project.id}"):
        project.donated = [
            DonatedResourceLine(
                resource_type=str(r.get("Type") or "Labor"),
                description=str(r.get("Description") or ""),
                donor=str(r.get("Donor") or ""),
                hours_or_quantity=float(r.get("Hours / Qty") or 0),
                valuation_rate=float(r.get("Rate") or 0),
                rate_basis=str(r.get("Valuation basis") or ""),
            )
            for _, r in edited.iterrows()
            if str(r.get("Description") or "").strip()
        ]
        touch()
        st.rerun()

    cs = summarize_project(project, s)
    c1, c2, c3 = st.columns(3)
    c1.metric("Donated value", money_plain(cs.donated_value))
    c2.metric("Credited to applicant share", money_plain(cs.donated_credit_applied))
    c3.metric("Applicant out of pocket", money_plain(cs.applicant_out_of_pocket))

    if cs.donated_credit_unused:
        st.warning(
            f"{money(cs.donated_credit_unused)} of donated value exceeds the "
            f"{money(cs.non_federal_share)} applicant share on this project and is "
            "stranded. Donated resources credit against the applicant share only. "
            "Emergency work donated resources are normally held until the Cat-A and "
            "Cat-B projects obligate, then applied against the applicant's share; on "
            "permanent work they are applied project by project."
        )
    st.caption(
        "Records FEMA will ask for — labor: names, dates, time in and out, work "
        "performed, location. Equipment: type, capacity, make, operator, hours per "
        "unit. Materials: donor, item, quantity, and what it would have cost."
    )


# -- mitigation ----------------------------------------------------------------


def _mitigation(project, s) -> None:
    m = s.rules.mitigation
    code = project.category.upper()
    eligible = code in m.eligible_categories

    if not eligible:
        st.warning(
            f"Section 406 mitigation is available only on permanent work "
            f"(Cat-{', '.join(m.eligible_categories)}). This is a Cat-{code} project. "
            "For mitigation on emergency work, look to the Section 404 Hazard "
            "Mitigation Grant Program — statewide, state-administered, and not tied "
            "to this declaration."
        )
    else:
        st.info(
            f"Mitigation protects the damaged element against the next event. Three "
            f"routes: up to **{m.percent_of_project_auto:.0%}** of the eligible repair "
            "cost is approvable without further justification; measures on the PAPPG "
            "list are approvable up to **100%** of eligible repair; anything above that "
            f"needs a favorable Benefit-Cost Analysis (BCR ≥ {m.minimum_bcr:.1f})."
        )

    frame = pd.DataFrame([{
        "Description": p.description,
        "Cost": p.proposed_cost,
        "On PAPPG list": p.on_pappg_list,
        "BCA performed": p.bca_performed,
        "BCA benefits": p.bca_benefits,
        "Related to damaged element": p.directly_related_to_damaged_element,
    } for p in project.mitigation], columns=[
        "Description", "Cost", "On PAPPG list", "BCA performed", "BCA benefits",
        "Related to damaged element",
    ])

    edited = st.data_editor(
        frame, num_rows="dynamic", use_container_width=True,
        column_config={
            "Cost": st.column_config.NumberColumn(format="$%.2f"),
            "BCA benefits": st.column_config.NumberColumn(
                format="$%.2f",
                help="Present value of avoided future losses. BCR is benefits / cost."),
        },
        key=f"mit_{project.id}",
    )

    if st.button("Save mitigation", type="primary", key=f"savemit_{project.id}"):
        project.mitigation = [
            MitigationProposal(
                description=str(r.get("Description") or ""),
                proposed_cost=float(r.get("Cost") or 0),
                on_pappg_list=bool(r.get("On PAPPG list")),
                bca_performed=bool(r.get("BCA performed")),
                bca_benefits=float(r.get("BCA benefits") or 0),
                directly_related_to_damaged_element=bool(
                    r.get("Related to damaged element", True)),
            )
            for _, r in edited.iterrows()
            if str(r.get("Description") or "").strip()
        ]
        touch()
        st.rerun()

    if project.mitigation:
        cs = summarize_project(project, s)
        repair = cs.gross_eligible - cs.mitigation
        approved, notes = eligible_mitigation(project, repair, s.rules)
        c1, c2, c3 = st.columns(3)
        c1.metric("Eligible repair cost", money_plain(repair))
        c2.metric("Mitigation proposed",
                  money_plain(sum(p.proposed_cost for p in project.mitigation)))
        c3.metric("Mitigation approvable", money_plain(approved))
        for n in notes:
            st.caption(f"• {md(n)}")


# -- summary -------------------------------------------------------------------


def _summary(project, s) -> None:
    cs = summarize_project(project, s)
    cls = classify(project, s)

    rows = [{"Line": label, "Amount": amount}
            for label, amount in cs.as_rows() if amount]
    rows.append({"Line": "— Gross eligible cost", "Amount": cs.gross_eligible})
    if cs.insurance_offset:
        rows.append({"Line": "Less: insurance (actual + anticipated)",
                     "Amount": -cs.insurance_offset})
    if cs.section_311_reduction:
        rows.append({"Line": "Less: Section 311 mandatory NFIP reduction",
                     "Amount": -cs.section_311_reduction})
    if cs.fixed_cost_offer:
        rows.append({"Line": "Section 428 fixed-cost offer (capped award)",
                     "Amount": cs.fixed_cost_offer})
    rows.append({"Line": "— Net eligible cost", "Amount": cs.net_eligible})
    rows.append({"Line": f"Federal share ({cs.federal_share_rate:.0%})",
                 "Amount": cs.federal_share})
    rows.append({"Line": f"Non-federal share ({1 - cs.federal_share_rate:.0%})",
                 "Amount": cs.non_federal_share})
    if cs.donated_credit_applied:
        rows.append({"Line": "Less: donated resource credit",
                     "Amount": -cs.donated_credit_applied})
    rows.append({"Line": "— Applicant out of pocket",
                 "Amount": cs.applicant_out_of_pocket})

    st.dataframe(
        pd.DataFrame(rows), use_container_width=True, hide_index=True,
        column_config={"Amount": st.column_config.NumberColumn(format="$%.2f")},
    )

    st.markdown(f"**{cls.size} project.** {cls.payment_basis}")
    st.markdown(f"Application: {cls.application_form}")
    st.markdown(f"Closeout: {cls.closeout_document}")
    for n in cls.notes:
        st.caption(f"• {md(n)}")

    if cs.section_311_notes:
        st.markdown("#### Section 311 mandatory reduction")
        for n in cs.section_311_notes:
            (st.error if "MANDATORY" in n else st.info)(md(n))

    excluded = []
    if cs.labor.straight_time_excluded:
        excluded.append(("Straight-time labor, not eligible in this category",
                         cs.labor.straight_time_excluded))
    if cs.equipment.standby_excluded:
        excluded.append(("Standby equipment time", cs.equipment.standby_excluded))
    if cs.codes_and_standards_excluded:
        excluded.append(("Code upgrades failing the five-part test",
                         cs.codes_and_standards_excluded))
    if cs.donated_credit_unused:
        excluded.append((
            f"Donated value beyond the applicant share ({cs.donated_scope} cap)",
            cs.donated_credit_unused))
    if excluded:
        st.markdown("#### Claimed but not payable")
        for label, amount in excluded:
            st.write(f"• {label} — **{money(amount)}**")
