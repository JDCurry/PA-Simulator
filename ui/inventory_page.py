"""Impact List: the damage inventory the applicant owes FEMA within 60 days of the RSM."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from pa.export import impact_list_csv
from pa.models import Site
from pa.rules import CATEGORIES, LABOR_TYPES, PRIMARY_CAUSES, PRIORITIES
from .common import get_scenario, money, money_plain, purpose, touch

_GRID_COLUMNS = [
    "Category", "Name", "Address", "City", "State", "Latitude", "Longitude",
    "Primary cause", "Approx. cost", "% complete", "Labor", "Prior PA", "Priority",
]


def _to_frame(sites: list[Site]) -> pd.DataFrame:
    return pd.DataFrame([{
        "Category": s.category,
        "Name": s.name,
        "Address": s.address,
        "City": s.city,
        "State": s.state,
        "Latitude": s.latitude,
        "Longitude": s.longitude,
        "Primary cause": s.primary_cause,
        "Approx. cost": s.approx_cost,
        "% complete": s.percent_complete,
        "Labor": s.labor_type,
        "Prior PA": s.prior_pa_grant,
        "Priority": s.priority,
    } for s in sites], columns=_GRID_COLUMNS)


def render() -> None:
    s = get_scenario()
    st.title("Impact List")
    purpose("Impact List")
    st.write(
        "The impact list is due 60 days after the Recovery Scoping Meeting. It is not "
        "a formality — FEMA formulates projects from these rows, and a site that is "
        "not on the list when the window closes is generally not funded."
    )

    if s.disaster.rsm_date:
        due = s.disaster.rsm_date + pd.Timedelta(
            days=s.rules.deadlines.impact_list_days_from_rsm)
        st.info(f"Impact list due **{due:%B %d, %Y}**.")

    tab_grid, tab_detail, tab_import = st.tabs(
        ["Inventory grid", "Site detail", "Import / export"]
    )

    # -- grid ------------------------------------------------------------------
    with tab_grid:
        if not s.sites:
            st.warning("No sites yet. Add rows below, or import a damage inventory workbook.")

        edited = st.data_editor(
            _to_frame(s.sites),
            num_rows="dynamic",
            use_container_width=True,
            height=440,
            column_config={
                "Category": st.column_config.SelectboxColumn(
                    options=list(CATEGORIES), width="small", required=True),
                "Approx. cost": st.column_config.NumberColumn(format="$%.2f"),
                "% complete": st.column_config.NumberColumn(
                    format="%.0f%%", min_value=0.0, max_value=1.0, step=0.05),
                "Primary cause": st.column_config.SelectboxColumn(
                    options=list(PRIMARY_CAUSES)),
                "Labor": st.column_config.SelectboxColumn(options=list(LABOR_TYPES)),
                "Prior PA": st.column_config.SelectboxColumn(options=["Y", "N", "U"]),
                "Priority": st.column_config.SelectboxColumn(
                    options=[""] + list(PRIORITIES)),
                "Latitude": st.column_config.NumberColumn(format="%.6f"),
                "Longitude": st.column_config.NumberColumn(format="%.6f"),
            },
            key="inventory_grid",
        )

        if st.button("Save grid changes", type="primary"):
            _apply_grid(s, edited)
            touch()
            st.success(f"{len(s.sites)} site(s) saved.")
            st.rerun()

        if s.sites:
            total = sum(x.approx_cost for x in s.sites)
            by_cat: dict[str, float] = {}
            for x in s.sites:
                by_cat[x.category] = by_cat.get(x.category, 0.0) + x.approx_cost

            c1, c2, c3 = st.columns(3)
            c1.metric("Sites", len(s.sites))
            c2.metric("Approximate cost", money_plain(total))
            c3.metric("Categories", ", ".join(sorted(by_cat)) or "—")

            st.bar_chart(
                pd.DataFrame(
                    {"Approximate cost": by_cat}
                ).sort_index(),
                horizontal=True,
            )
            st.caption(
                "These are the applicant's rough order-of-magnitude figures, not "
                "eligible costs. Eligibility is determined on the Cost Buildup page."
            )

    # -- detail ----------------------------------------------------------------
    with tab_detail:
        if not s.sites:
            st.info("Add a site on the grid first.")
        else:
            names = [x.name or x.id for x in s.sites]
            picked = st.selectbox("Site", names, key="site_detail_pick")
            site = s.sites[names.index(picked)]
            _site_detail(site, s)

    # -- import / export -------------------------------------------------------
    with tab_import:
        st.markdown("#### Import a FEMA damage inventory workbook")
        st.caption(
            "Reads the standard damage inventory template your state recipient "
            "distributes. Personnel names, phone numbers, and email addresses in the "
            "header block are not carried into the scenario."
        )
        uploads = st.file_uploader(
            "Damage inventory (.xlsx)", type=["xlsx"], accept_multiple_files=True)
        replace = st.checkbox("Replace the existing impact list", value=False)

        if uploads and st.button("Import", type="primary"):
            import tempfile
            from pathlib import Path
            from pa.importers import read_damage_inventory

            imported: list[Site] = []
            header: dict[str, str] = {}
            for up in uploads:
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".xlsx"
                ) as tmp:
                    tmp.write(up.getvalue())
                    tmp_path = Path(tmp.name)
                try:
                    h, sites = read_damage_inventory(tmp_path)
                    header = {**header, **{k: v for k, v in h.items() if v}}
                    imported.extend(sites)
                finally:
                    tmp_path.unlink(missing_ok=True)

            existing = set() if replace else {
                (x.category, x.name.lower()) for x in s.sites}
            if replace:
                s.sites = []
            added = 0
            for site in imported:
                if (site.category, site.name.lower()) in existing:
                    continue
                existing.add((site.category, site.name.lower()))
                s.sites.append(site)
                added += 1

            if header.get("applicant_name") and not s.applicant.name:
                s.applicant.name = header["applicant_name"]
            if header.get("applicant_fips") and not s.applicant.fips:
                s.applicant.fips = header["applicant_fips"]
            if header.get("disaster_number") and not s.disaster.number:
                s.disaster.number = header["disaster_number"]

            touch()
            st.success(f"Imported {added} site(s).")
            st.rerun()

        st.divider()
        st.download_button(
            "Download impact list (CSV)",
            data=impact_list_csv(s),
            file_name="impact_list.csv",
            mime="text/csv",
        )


def _apply_grid(s, frame: pd.DataFrame) -> None:
    """Rewrite sites from the grid, preserving ids and detail fields by position."""
    old = list(s.sites)
    new: list[Site] = []
    for i, row in frame.iterrows():
        name = str(row.get("Name") or "").strip()
        if not name:
            continue
        base = old[i] if isinstance(i, int) and i < len(old) else Site()
        base.category = str(row.get("Category") or "B").upper()
        base.name = name
        base.address = str(row.get("Address") or "")
        base.city = str(row.get("City") or "")
        base.state = str(row.get("State") or "")
        base.latitude = _f(row.get("Latitude"))
        base.longitude = _f(row.get("Longitude"))
        base.primary_cause = str(row.get("Primary cause") or "")
        base.approx_cost = _f(row.get("Approx. cost")) or 0.0
        base.percent_complete = _f(row.get("% complete")) or 0.0
        base.labor_type = str(row.get("Labor") or "FA")
        base.prior_pa_grant = str(row.get("Prior PA") or "U")
        base.priority = str(row.get("Priority") or "")
        new.append(base)

    kept = {x.id for x in new}
    for p in s.projects:
        p.site_ids = [sid for sid in p.site_ids if sid in kept]
    s.sites = new


def _f(v) -> float | None:
    if v is None or (isinstance(v, float) and pd.isna(v)) or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _site_detail(site: Site, s) -> None:
    """The eligibility and EHP attributes that do not fit on the grid."""
    cat = CATEGORIES.get(site.category.upper())
    if cat:
        st.markdown(f"**{cat.label}** — {cat.work_type.value}")
        if cat.description:
            st.caption(cat.description)

    site.damage_description = st.text_area(
        "Damage description", site.damage_description, height=160,
        help="FEMA writes the Damage, Description and Dimensions from this. State the "
             "damaged component, the causal mechanism tied to the declared incident, "
             "and a quantity or dimension for each.",
    )

    st.markdown("#### Facility eligibility")
    st.caption(
        "All four must hold. A failure on any one of them ends the project regardless "
        "of how well documented the rest of it is."
    )
    c1, c2 = st.columns(2)
    site.in_use_at_time_of_disaster = c1.checkbox(
        "In use at the time of the incident", site.in_use_at_time_of_disaster,
        key=f"use_{site.id}")
    site.applicant_legal_responsibility = c1.checkbox(
        "Applicant's legal responsibility at the time of the incident",
        site.applicant_legal_responsibility, key=f"legal_{site.id}")
    site.within_declared_area = c2.checkbox(
        "Within the declared area", site.within_declared_area, key=f"area_{site.id}")
    site.actively_used_and_maintained = c2.checkbox(
        "Actively used and maintained", site.actively_used_and_maintained,
        key=f"maint_{site.id}")
    site.other_federal_agency_authority = st.checkbox(
        "Work falls under another federal agency's specific authority "
        "(FHWA, NRCS, USACE)",
        site.other_federal_agency_authority, key=f"ofa_{site.id}",
        help="If another federal program has authority, PA is not available and "
             "claiming both is a duplication of benefits.",
    )

    st.markdown("#### Insurance")
    i1, i2, i3 = st.columns(3)
    site.insured = i1.checkbox("Facility insured", site.insured, key=f"ins_{site.id}")
    site.insurance_proceeds = i2.number_input(
        "Proceeds received ($)", value=float(site.insurance_proceeds),
        min_value=0.0, step=1_000.0, key=f"proc_{site.id}")
    site.anticipated_insurance = i3.number_input(
        "Anticipated proceeds ($)", value=float(site.anticipated_insurance),
        min_value=0.0, step=1_000.0, key=f"antic_{site.id}",
        help="FEMA deducts anticipated proceeds whether or not the applicant has "
             "filed the claim.")

    st.markdown("##### Flood exposure and the Section 311 reduction")
    st.caption(
        "If an insurable BUILDING in a Special Flood Hazard Area is damaged by FLOOD "
        "and carried no flood insurance, FEMA must reduce eligible cost by the maximum "
        "proceeds a standard NFIP policy would have paid. The reduction is sized on "
        "policy limits, not on the amount of damage, so it routinely exceeds the whole "
        "project. It is statutory and cannot be appealed away."
    )
    f1, f2 = st.columns(2)
    site.in_special_flood_hazard_area = f1.checkbox(
        "In a Special Flood Hazard Area", site.in_special_flood_hazard_area,
        key=f"sfha_{site.id}")
    site.is_insurable_building = f2.checkbox(
        "Is an insurable building", site.is_insurable_building,
        key=f"bldg_{site.id}",
        help="Roads, levees, and utility lines are not insurable buildings. The "
             "Section 311 reduction applies only to buildings.")

    if site.is_insurable_building and site.in_special_flood_hazard_area:
        g1, g2 = st.columns(2)
        site.sfha_designated_years = g1.number_input(
            "Years the SFHA has been designated",
            value=float(site.sfha_designated_years), min_value=0.0, step=1.0,
            key=f"sfhayr_{site.id}",
            help="The reduction applies only if the area has been identified for "
                 "more than one year.")
        site.flood_insurance_in_force = g2.number_input(
            "Flood insurance coverage carried ($)",
            value=float(site.flood_insurance_in_force), min_value=0.0, step=10_000.0,
            key=f"fic_{site.id}",
            help="Coverage in force, not proceeds received.")
        h1, h2 = st.columns(2)
        site.building_value = h1.number_input(
            "Building value ($)", value=float(site.building_value),
            min_value=0.0, step=10_000.0, key=f"bv_{site.id}")
        site.contents_value = h2.number_input(
            "Contents value ($)", value=float(site.contents_value),
            min_value=0.0, step=10_000.0, key=f"cv_{site.id}")

        ins = s.rules.insurance
        exposure = ins.section_311_reduction(
            site.building_value, site.contents_value, site.flood_insurance_in_force)
        flood = "flood" in (site.primary_cause or "").lower()
        if exposure > 0 and flood and site.sfha_designated_years >= ins.sfha_designated_min_years:
            st.error(
                f"**Section 311 exposure: {money(exposure)}.** Standard NFIP limits are "
                f"{money(ins.nfip_max_building)} building and "
                f"{money(ins.nfip_max_contents)} contents; the reduction is the lesser "
                "of those limits and the actual values, less coverage carried."
            )
        elif exposure > 0 and not flood:
            st.info(
                f"Would face a {money(exposure)} Section 311 reduction if the primary "
                f"cause were flood. It is currently recorded as "
                f"'{site.primary_cause or 'not set'}'."
            )
        elif site.flood_insurance_in_force > 0:
            st.success("Flood coverage is carried; no Section 311 reduction applies.")

        site.obtain_and_maintain_acknowledged = st.checkbox(
            "Obtain-and-maintain requirement acknowledged",
            site.obtain_and_maintain_acknowledged, key=f"onm_{site.id}",
            help="Accepting PA funding obligates the applicant to carry insurance for "
                 "the peril that caused the damage, in at least the amount of the "
                 "damage, for the life of the facility.")

    st.markdown("#### Environmental and historic screening")
    st.caption(
        "Consultation must be complete before work begins. Starting early can void "
        "the entire project."
    )
    flags = dict(site.ehp_flags)
    cols = st.columns(2)
    for i, (key, desc) in enumerate(s.rules.ehp.triggers):
        flags[key] = cols[i % 2].checkbox(
            desc, flags.get(key, False), key=f"ehp_{site.id}_{key}")
    site.ehp_flags = {k: v for k, v in flags.items() if v}

    age = st.number_input(
        "Structure age (years, 0 if not applicable)",
        value=int(site.structure_age_years or 0), min_value=0, step=1,
        key=f"age_{site.id}",
        help=f"At or above {s.rules.ehp.historic_structure_age_years} years, the "
             "structure screens in for NHPA Section 106 review.",
    )
    site.structure_age_years = age or None

    site.ehp_consultation_complete = st.checkbox(
        "EHP consultation and permitting complete",
        site.ehp_consultation_complete, key=f"ehpdone_{site.id}",
        help="Starting work before consultation cannot be undone, but recording that "
             "consultation finished — or the exigency that justified proceeding — is "
             "how the exposure is resolved.")
    if site.ehp_consultation_complete:
        site.ehp_resolution_note = st.text_input(
            "How it was resolved", site.ehp_resolution_note,
            key=f"ehpnote_{site.id}",
            placeholder="e.g. JARPA filed; USFWS concurrence received 2027-05-14")

    if st.button("Save site detail", type="primary", key=f"save_{site.id}"):
        touch()
        st.success("Saved.")
