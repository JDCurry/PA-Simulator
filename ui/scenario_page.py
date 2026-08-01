"""Scenario setup: applicant, disaster, and the ruleset that governs both."""

from __future__ import annotations

import streamlit as st

from pa.rules import (
    CostShare, DEADLINE_LABELS, NO_EXTENSION_DEADLINES, PRIMARY_CAUSES, RuleSet,
    Thresholds,
)
from .common import date_input_optional, get_scenario, money0, touch


def render() -> None:
    s = get_scenario()
    st.title("Scenario")
    st.write(
        "Everything downstream is computed from what is set here. The thresholds and "
        "cost share in particular are indexed annually and set by the declaration — "
        "carrying last year's numbers into this year's disaster is a real and "
        "expensive mistake."
    )

    s.title = st.text_input("Scenario title", s.title)

    tab_app, tab_dis, tab_rules = st.tabs(
        ["Applicant", "Disaster declaration", "Ruleset"]
    )

    # -- applicant -------------------------------------------------------------
    with tab_app:
        a = s.applicant
        c1, c2 = st.columns(2)
        with c1:
            a.name = st.text_input("Applicant name", a.name)
            a.entity_type = st.selectbox(
                "Entity type",
                ["Local Government", "State Agency", "Tribal Government",
                 "Special District", "Private Non-Profit — critical services",
                 "Private Non-Profit — non-critical essential social services"],
                index=max(0, [
                    "Local Government", "State Agency", "Tribal Government",
                    "Special District", "Private Non-Profit — critical services",
                    "Private Non-Profit — non-critical essential social services",
                ].index(a.entity_type) if a.entity_type in [
                    "Local Government", "State Agency", "Tribal Government",
                    "Special District", "Private Non-Profit — critical services",
                    "Private Non-Profit — non-critical essential social services",
                ] else 0),
            )
            a.county = st.text_input("County", a.county)
            a.state = st.text_input("State", a.state, max_chars=2)
        with c2:
            a.fips = st.text_input(
                "Applicant FIPS", a.fips,
                help="FEMA identifies applicants by FIPS, not by name. Format: "
                     "county-place-suffix, e.g. 061-22640-00.",
            )
            a.primary_contact_role = st.text_input(
                "Primary contact role", a.primary_contact_role,
                help="A role, not a person. This tool deliberately has nowhere to "
                     "store staff names, phone numbers, or email addresses.",
            )
            a.capitalization_level = st.number_input(
                "Equipment capitalization level ($)",
                value=float(a.capitalization_level), min_value=0.0, step=500.0,
                help="Used for the equipment-versus-supply test. FEMA applies the "
                     "LESSER of this figure and $10,000.",
            )

        if a.is_pnp:
            st.info(
                "Private non-profits providing non-critical but essential social "
                "services must apply to the Small Business Administration FIRST for "
                "permanent repairs. PA is available only for what SBA declines."
            )
            if a.is_noncritical_pnp:
                sb1, sb2 = st.columns(2)
                a.sba_application_filed = sb1.checkbox(
                    "SBA application filed", a.sba_application_filed)
                a.sba_declined = sb2.checkbox(
                    "SBA declined or partially declined", a.sba_declined,
                    help="The decline letter is what unlocks PA permanent work "
                         "funding for a non-critical PNP.")

        a.small_impoverished_community = st.checkbox(
            "Qualifies as a small impoverished community",
            a.small_impoverished_community,
            help="Lowers the DRRA Sec. 1219 arbitration threshold from $500,000 to "
                 "$100,000 for disputes.",
        )

        st.markdown("#### Required policies")
        st.caption(
            "FEMA cannot formulate labor or contract costs without these. Every one "
            "of them was an action item at the Recovery Scoping Meeting."
        )
        p1, p2, p3 = st.columns(3)
        a.has_pay_policy = p1.checkbox(
            "Pay policy submitted", a.has_pay_policy,
            help="Establishes straight-time and overtime rates and who is eligible "
                 "for overtime. Without it, force account labor cannot be validated.",
        )
        a.has_procurement_policy = p2.checkbox(
            "Procurement policy submitted", a.has_procurement_policy,
            help="Contract costs cannot be validated without the adopted policy.",
        )
        a.has_insurance_policy = p3.checkbox(
            "Insurance policy submitted", a.has_insurance_policy,
            help="Insurance is the applicant's first means of funding.",
        )

        q1, q2 = st.columns(2)
        a.nfip_participating = q1.checkbox(
            "Participating in the NFIP in good standing", a.nfip_participating,
            help="Communities suspended or sanctioned under the National Flood "
                 "Insurance Program are ineligible for Cat-I funding.",
        )
        a.uses_adopted_equipment_rates = q2.checkbox(
            "Applicant has locally adopted equipment rates",
            a.uses_adopted_equipment_rates,
            help="If adopted, FEMA pays the LESSER of the adopted rate and the FEMA "
                 "schedule rate for the same components.",
        )

        st.markdown("#### Section 428 alternative procedures")
        a.section_428_debris_straight_time = st.checkbox(
            "Elected the Section 428 alternative procedure for debris removal",
            a.section_428_debris_straight_time,
            help="Elected per disaster. Makes straight-time force account labor "
                 "eligible for budgeted employees on eligible Cat-A debris work.",
        )
        st.caption(
            "Emergency Work normally reimburses budgeted employees for overtime only. "
            "Debris removal is the one exception: electing the Section 428 procedure "
            "makes straight time eligible for budgeted employees doing eligible debris "
            "work. The election also opens an increased federal cost share on a sliding "
            "scale for accelerated completion, and lets the applicant retain recycling "
            "revenue. It is a per-disaster decision — evaluate it against your actual "
            "force account hours before the election window closes."
        )

    # -- disaster --------------------------------------------------------------
    with tab_dis:
        d = s.disaster
        c1, c2 = st.columns(2)
        with c1:
            d.number = st.text_input("Disaster number", d.number, placeholder="4906-DR")
            d.name = st.text_input("Incident name", d.name)
            d.state = st.text_input("Declared state", d.state, max_chars=2, key="dis_state")
        with c2:
            d.declaration_date = date_input_optional(
                "Declaration date", d.declaration_date, "decl")
            d.designation_date = date_input_optional(
                "Area designation date", d.designation_date, "desig")
            st.caption(
                "When this applicant's area was designated for PA. Starts the 30-day "
                "RPA clock. Often the declaration date, but a county added later has "
                "its own."
            )

        st.markdown("#### Getting into the program")
        st.caption(
            "The Request for Public Assistance is the first deadline and the one that "
            "ends the process if missed. Nothing downstream of it exists until it is "
            "filed and approved."
        )
        e1, e2, e3 = st.columns(3)
        with e1:
            d.rpa_submitted_date = date_input_optional(
                "RPA submitted", d.rpa_submitted_date, "rpa")
        with e2:
            d.exploratory_call_date = date_input_optional(
                "Exploratory call", d.exploratory_call_date, "explor")
        with e3:
            d.rsm_date = date_input_optional(
                "Recovery Scoping Meeting", d.rsm_date, "rsm")

        st.markdown("#### Incident period")
        st.caption(
            "Damage must have occurred inside this window to be eligible. Repair work "
            "may run well past it — the damage is what has to fall inside."
        )
        c3, c4 = st.columns(2)
        with c3:
            d.incident_start = date_input_optional(
                "Incident start", d.incident_start, "inc_start")
        with c4:
            d.incident_end = date_input_optional(
                "Incident end", d.incident_end, "inc_end")

        d.incident_types = st.multiselect(
            "Declared incident types", list(PRIMARY_CAUSES), d.incident_types,
            help="A site whose primary cause is not among these will be flagged — "
                 "damage must be a direct result of the declared incident.",
        )

        if d.declaration_date:
            st.markdown("#### Resulting deadlines")
            resolved = s.rules.deadlines.resolve(
                d.declaration_date, d.rsm_date, d.designation_date)
            for key, when in sorted(resolved.items(), key=lambda kv: kv[1]):
                st.write(
                    f"**{when:%B %d, %Y}** — {DEADLINE_LABELS.get(key, key)}"
                    + ("  *(no extensions permitted)*"
                       if key in NO_EXTENSION_DEADLINES else "")
                )

        s.description = st.text_area("Scenario description", s.description, height=100)

    # -- ruleset ---------------------------------------------------------------
    with tab_rules:
        r = s.rules
        st.caption(f"Policy basis: {r.name}")
        st.warning(
            "These are the figures that change between disasters. Verify them against "
            "the declaration and the current PAPPG before relying on any number this "
            "tool produces."
        )

        c1, c2 = st.columns(2)
        with c1:
            # Sliders work in whole percent; the ruleset stores fractions.
            federal = st.slider(
                "Federal cost share (%)", 50, 100,
                int(round(r.cost_share.federal * 100)), 5,
                help="75/25 is the Stafford Act default. Declarations can adjust it, "
                     "and some set 100 percent federal for a defined period.",
            ) / 100.0
            st.caption(f"Federal {federal:.0%} / non-federal {1 - federal:.0%}")
            small_min = st.number_input(
                "Small project minimum ($)",
                value=float(r.thresholds.small_project_minimum), step=100.0,
                help="Eligible damage below this cannot be written as a project at all.",
            )
        with c2:
            large = st.number_input(
                "Large project threshold ($)",
                value=float(r.thresholds.large_project_threshold), step=1_000.0,
                help="Above this, payment is on ACTUAL cost with retainage and a final "
                     "inspection. Indexed annually.",
            )
            retainage = st.slider(
                "Large project retainage (%)", 0, 25,
                int(round(r.thresholds.large_project_retainage * 100)), 1,
                help="Withheld from each progress payment and released on FEMA "
                     "approval of the final inspection.",
            ) / 100.0

        st.markdown("#### Procurement thresholds")
        c3, c4 = st.columns(2)
        micro = c3.number_input(
            "Micro-purchase ($)", value=float(r.thresholds.micro_purchase), step=500.0)
        simplified = c4.number_input(
            "Simplified acquisition ($)",
            value=float(r.thresholds.simplified_acquisition), step=5_000.0)

        st.markdown("#### Management costs")
        mgmt = st.slider(
            "Cat-Z cap, as a percent of total obligated", 0.0, 15.0,
            round(r.management.applicant_cap_rate * 100, 1), 0.5,
            help="Direct and indirect costs of administering the PA grant.") / 100.0

        if st.button("Apply ruleset", type="primary"):
            from dataclasses import replace
            s.rules = replace(
                r,
                cost_share=CostShare(federal=federal),
                thresholds=replace(
                    r.thresholds,
                    small_project_minimum=small_min,
                    large_project_threshold=large,
                    large_project_retainage=retainage,
                    micro_purchase=micro,
                    simplified_acquisition=simplified,
                ),
                management=replace(r.management, applicant_cap_rate=mgmt),
            )
            touch()
            st.success("Ruleset applied.")
            st.rerun()

        with st.expander("What each threshold actually changes"):
            st.markdown(f"""
| Figure | Current | What turns on it |
|---|---|---|
| Small project minimum | {money0(r.thresholds.small_project_minimum)} | Below this, there is no project. Sites have to be combined. |
| Large project threshold | {money0(r.thresholds.large_project_threshold)} | Above this: actual-cost payment, progressive draws, {r.thresholds.large_project_retainage:.0%} retainage, final inspection, SOD-FIR at closeout, and Simplified Procedures no longer apply. |
| Micro-purchase | {money0(r.thresholds.micro_purchase)} | Below this, no competitive quotes required. |
| Simplified acquisition | {money0(r.thresholds.simplified_acquisition)} | Above this, formal sealed bid or competitive proposal. |
| Equipment capitalization | {money0(r.thresholds.equipment_capitalization)} | Equipment versus supply, which decides disposition at closeout. |
| Single Audit | {money0(r.thresholds.single_audit)} | Federal funds expended in a fiscal year above this trigger a single audit. |
""")
