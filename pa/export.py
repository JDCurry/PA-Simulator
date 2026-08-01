"""Package assembly and export.

Produces the artifacts an applicant actually hands over: the Damage, Description and
Dimensions narrative, a defensible cost summary, a documentation checklist keyed to
what the project actually contains, and a reimbursement request cover.
"""

from __future__ import annotations

import csv
import io
from datetime import date

from .costing import CostSummary, summarize_project, summarize_scenario
from .formulation import classify
from .models import CostType, Project, Scenario
from .rules import CATEGORIES, WorkType


# -- documentation checklists ---------------------------------------------------

#: Keyed to category. These come straight from the RSM "required information"
#: discussion -- what FEMA asks for, per category, to formulate a project.
CATEGORY_DOCS: dict[str, list[str]] = {
    "A": [
        "Detailed description of work activities",
        "Type and quantity of labor resources",
        "Type and quantity of purchased or used equipment, material, and supplies",
        "Quantity of each type of debris and method of removal",
        "Work locations with physical address or GPS coordinates",
        "Timeframe of work performed",
        "Applicable permits and authorizations",
        "Documentation substantiating coordination with regulatory agencies",
        "Temporary and final debris disposal site locations and type",
        "If contracted, name of hauler to the final disposal location",
        "Debris monitoring records",
    ],
    "B": [
        "Detailed description of work activities",
        "Type and quantity of labor resources",
        "Type and quantity of purchased or used equipment, material, and supplies",
        "Work locations with physical address or GPS coordinates",
        "Timeframe of work performed",
        "Documentation for any work on private property requiring FEMA approval",
    ],
    "I": [
        "Areas and locations where code enforcement work occurred",
        "Description of the work conducted",
        "Proof of NFIP participation in good standing",
        "All Cat-I costs consolidated into a SINGLE project",
    ],
    "Z": [
        "Time and effort records for staff administering the grant",
        "Direct and indirect cost documentation — actual and auditable",
        "Records of site visits, payment submissions, and closeout assembly",
    ],
}

PERMANENT_DOCS = [
    "Pre-disaster design, size, and capacity of the facility",
    "Maintenance records showing the facility was actively used and maintained",
    "Applicable codes and standards in force at the time of the disaster",
    "Insurance policy and documentation of actual or anticipated proceeds",
    "Photographs of damage, pre- and post-repair where available",
    "Engineering assessment or damage inspection report",
]

UNIVERSAL_DOCS = [
    "Adopted pay policy establishing straight-time and overtime rates",
    "Adopted procurement policy",
    "Force account labor records: names, dates, hours in/out, work performed, location",
    "Force account equipment records: type, capacity, make, operator, hours per unit",
    "Materials: type, quantity, total cost, and invoices",
    "Contracts: solicitation, bid tabulation, award, SAM.gov debarment check",
    "Environmental and historic preservation permits and correspondence",
]


def documentation_checklist(project: Project, scenario: Scenario) -> list[tuple[str, bool]]:
    """Checklist items paired with a best-effort guess at whether they're satisfied."""
    code = project.category.upper()
    cat = CATEGORIES.get(code)
    items = list(CATEGORY_DOCS.get(code, []))
    if cat and cat.work_type is WorkType.PERMANENT:
        items = PERMANENT_DOCS + items
    items = items + UNIVERSAL_DOCS

    a = scenario.applicant
    sites = scenario.sites_for(project)
    satisfied: dict[str, bool] = {
        "Adopted pay policy establishing straight-time and overtime rates": a.has_pay_policy,
        "Adopted procurement policy": a.has_procurement_policy,
        "Insurance policy and documentation of actual or anticipated proceeds": a.has_insurance_policy,
        "Work locations with physical address or GPS coordinates": all(
            (s.address or (s.latitude and s.longitude)) for s in sites
        ) if sites else False,
        "Type and quantity of labor resources": bool(project.labor),
        "Type and quantity of purchased or used equipment, material, and supplies": bool(
            project.equipment or any(c.cost_type is CostType.MATERIALS for c in project.costs)
        ),
        "Detailed description of work activities": bool(project.scope_of_work.strip()),
        "Contracts: solicitation, bid tabulation, award, SAM.gov debarment check": all(
            c.sam_debarment_checked for c in project.contracts()
        ) if project.contracts() else True,
        "All Cat-I costs consolidated into a SINGLE project": sum(
            1 for p in scenario.projects if p.category.upper() == "I"
        ) <= 1,
    }
    # Items the engine can verify from the data are inferred. Everything else is the
    # applicant's attestation that the record exists in the project file.
    confirmed = set(project.documentation_confirmed)
    seen: set[str] = set()
    out: list[tuple[str, bool]] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append((item, satisfied.get(item, item in confirmed)))
    return out


def inferred_documentation_items() -> set[str]:
    """Checklist items the engine determines itself, which cannot be attested away."""
    return {
        "Adopted pay policy establishing straight-time and overtime rates",
        "Adopted procurement policy",
        "Insurance policy and documentation of actual or anticipated proceeds",
        "Work locations with physical address or GPS coordinates",
        "Type and quantity of labor resources",
        "Type and quantity of purchased or used equipment, material, and supplies",
        "Detailed description of work activities",
        "Contracts: solicitation, bid tabulation, award, SAM.gov debarment check",
        "All Cat-I costs consolidated into a SINGLE project",
    }


# -- narratives -----------------------------------------------------------------


def ddd_narrative(project: Project, scenario: Scenario) -> str:
    """Damage, Description and Dimensions.

    FEMA writes the scope of work from this. Each site needs the damaged component,
    the causal mechanism tied to the declared incident, and a quantified dimension.
    """
    sites = scenario.sites_for(project)
    cat = CATEGORIES.get(project.category.upper())
    d = scenario.disaster

    lines = [
        f"DAMAGE, DESCRIPTION AND DIMENSIONS",
        f"{'=' * 70}",
        f"Disaster:   {d.number} — {d.name}",
        f"Applicant:  {scenario.applicant.name} (FIPS {scenario.applicant.fips})",
        f"Project:    {project.title}",
        f"Category:   {cat.label if cat else project.category}",
        f"Sites:      {len(sites)}",
        "",
        "DAMAGE",
        "-" * 70,
    ]
    if project.ddd_damage.strip():
        lines.append(project.ddd_damage.strip())
    else:
        for s in sites:
            lines.append(f"• {s.name}: {s.damage_description or '[not recorded]'}")
            lines.append(
                f"  Cause: {s.primary_cause or '[not recorded]'} | "
                f"{s.percent_complete:.0%} complete | "
                f"Labor: {s.labor_type}"
            )
            lines.append("")

    lines += ["", "DIMENSIONS", "-" * 70]
    lines.append(project.ddd_dimensions.strip() or "\n".join(
        f"• {s.name} — {s.address or 'address not recorded'}"
        + (f" ({s.latitude}, {s.longitude})" if s.latitude and s.longitude else "")
        for s in sites
    ))

    lines += ["", "SCOPE OF WORK", "-" * 70]
    lines.append(project.scope_of_work.strip() or "[not recorded — FEMA obligates against this text]")

    if project.mitigation:
        lines += ["", "SECTION 406 HAZARD MITIGATION PROPOSED", "-" * 70]
        for m in project.mitigation:
            basis = "PAPPG list" if m.on_pappg_list else "percentage of project"
            if m.bca_performed:
                basis += f"; BCA performed, BCR {m.bcr:.2f}"
            lines.append(f"• {m.description} — ${m.proposed_cost:,.2f} ({basis})")

    return "\n".join(lines)


def cost_summary_text(project: Project, scenario: Scenario) -> str:
    cs = summarize_project(project, scenario)
    cls = classify(project, scenario)
    rules = scenario.rules
    w = 44

    def row(label: str, amount: float) -> str:
        return f"  {label:<{w}} {amount:>15,.2f}"

    lines = [
        "COST SUMMARY",
        "=" * 70,
        f"Project: {project.title}",
        f"Classification: {cls.size} project — {cls.payment_basis}",
        f"Application: {cls.application_form}",
        "",
        "ELIGIBLE COST BUILD",
        "-" * 70,
    ]
    for label, amount in cs.as_rows():
        if amount:
            lines.append(row(label, amount))

    lines += [
        "  " + "-" * (w + 15),
        row("GROSS ELIGIBLE COST", cs.gross_eligible),
    ]
    if cs.insurance_offset:
        lines.append(row("Less: insurance proceeds (actual + anticipated)", -cs.insurance_offset))
    if cs.section_311_reduction:
        lines.append(row("Less: Section 311 mandatory NFIP reduction",
                         -cs.section_311_reduction))
    if cs.fixed_cost_offer:
        lines.append(row("Section 428 fixed-cost offer (capped award)",
                         cs.fixed_cost_offer))
    lines += [
        row("NET ELIGIBLE COST", cs.net_eligible),
        "",
        "COST SHARE",
        "-" * 70,
        row(f"Federal share ({cs.federal_share_rate:.0%})", cs.federal_share),
        row(f"Non-federal share ({1 - cs.federal_share_rate:.0%})", cs.non_federal_share),
    ]
    if cs.cost_share_note:
        lines.append(f"  {cs.cost_share_note}")
    if cs.donated_value:
        lines += [
            row("Donated resource value", cs.donated_value),
            row("  credited against applicant share", -cs.donated_credit_applied),
        ]
        if cs.donated_credit_unused:
            lines.append(row("  in excess of applicant share (not creditable)",
                             cs.donated_credit_unused))
    lines.append(row("APPLICANT OUT OF POCKET", cs.applicant_out_of_pocket))

    if cs.is_large_project:
        lines += [
            "",
            f"  Large project: {rules.thresholds.large_project_retainage:.0%} retainage "
            f"(${cs.retainage_per_payment:,.2f}) withheld from each payment,",
            "  released on FEMA approval of the final inspection.",
        ]

    if cs.section_311_notes:
        lines += ["", "SECTION 311 MANDATORY REDUCTION", "-" * 70]
        for n in cs.section_311_notes:
            lines.append(f"  {n}")

    excluded = []
    if cs.labor.straight_time_excluded:
        excluded.append(("Straight-time labor not eligible in this category",
                         cs.labor.straight_time_excluded))
    if cs.equipment.standby_excluded:
        excluded.append(("Standby equipment time", cs.equipment.standby_excluded))
    if cs.equipment.rate_reduction:
        excluded.append(("Reduction to lesser of adopted / FEMA rate",
                         cs.equipment.rate_reduction))
    if cs.codes_and_standards_excluded:
        excluded.append(("Code upgrades failing the five-part test",
                         cs.codes_and_standards_excluded))
    if excluded:
        lines += ["", "COSTS CLAIMED BUT NOT ELIGIBLE", "-" * 70]
        for label, amount in excluded:
            lines.append(row(label, amount))

    lines += ["", "CLOSEOUT", "-" * 70, f"  {cls.closeout_document}"]
    for n in cls.notes:
        lines.append(f"  • {n}")
    return "\n".join(lines)


def reimbursement_request(scenario: Scenario, as_of: date | None = None) -> str:
    """Cover memo for a payment request, mirroring the A-19A invoice voucher flow."""
    t = summarize_scenario(scenario)
    as_of = as_of or date.today()
    d = scenario.disaster
    a = scenario.applicant

    lines = [
        "REQUEST FOR REIMBURSEMENT",
        "=" * 70,
        f"Date:            {as_of:%B %d, %Y}",
        f"Disaster:        {d.number} — {d.name}",
        f"Declared:        {d.declaration_date:%B %d, %Y}" if d.declaration_date else "Declared:        —",
        f"Applicant:       {a.name}",
        f"Applicant FIPS:  {a.fips}",
        f"Contact:         {a.primary_contact_role}",
        "",
        "PROJECT PORTFOLIO",
        "-" * 70,
        f"  Total projects              {t.projects:>10}",
        f"    Large projects            {t.large_projects:>10}",
        f"    Small projects            {t.small_projects:>10}",
        f"    Below minimum threshold   {t.below_minimum:>10}",
        "",
        "AMOUNTS",
        "-" * 70,
        f"  Gross eligible cost          {t.gross_eligible:>15,.2f}",
        f"  Less insurance proceeds      {-t.insurance_offset:>15,.2f}",
        f"  Less Section 311 reduction   {-t.section_311_reduction:>15,.2f}",
        f"  Net eligible cost            {t.net_eligible:>15,.2f}",
        f"  Federal share                {t.federal_share:>15,.2f}",
        f"  Non-federal share            {t.non_federal_share:>15,.2f}",
        f"  Donated resource credit      {-t.donated_credit:>15,.2f}",
        f"  Applicant out of pocket      {t.applicant_out_of_pocket:>15,.2f}",
        "",
        f"  Section 406 mitigation incl. {t.mitigation:>15,.2f}",
        f"  Cat-Z management cap ({scenario.rules.management.applicant_cap_rate:.0%})   "
        f"{t.management_cost_cap:>15,.2f}",
        f"  Cat-Z claimed                {t.management_cost_claimed:>15,.2f}",
        f"  (State recipient allowance   {t.recipient_management_cost_cap:>15,.2f} "
        f"at {scenario.rules.management.recipient_cap_rate:.0%}, not applicant funds)",
        "",
        "BY CATEGORY",
        "-" * 70,
    ]
    for code in sorted(t.by_category):
        cat = CATEGORIES.get(code)
        lines.append(f"  Cat-{code} {(cat.name if cat else ''):<42} {t.by_category[code]:>15,.2f}")

    lines += [
        "",
        "CONDITIONS OF PAYMENT",
        "-" * 70,
        "  • No reimbursement can be made until the contract between the state",
        "    military department / emergency management division and the applicant",
        "    has been received and signed by all parties.",
        "  • Payment is released on submission of a signed A-19A Invoice Voucher,",
        "    made electronically by direct deposit.",
        "  • Large projects are paid progressively against actual cost, with "
        f"{scenario.rules.thresholds.large_project_retainage:.0%}",
        "    retainage withheld from each payment.",
    ]
    if t.single_audit_triggered:
        lines.append(
            f"  • Federal share exceeds ${scenario.rules.thresholds.single_audit:,.0f} — "
            "a Single Audit will be required."
        )
    return "\n".join(lines)


# -- tabular exports ------------------------------------------------------------


def impact_list_csv(scenario: Scenario) -> str:
    """The Impact List, in the column order of FEMA's damage inventory template."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "Category", "Name of damage/facility", "Address 1", "City", "State", "Zip",
        "Latitude", "Longitude", "Describe Damage", "Primary Cause of Damage",
        "Approx. Cost", "% Work Complete", "Labor Type",
        "Has received PA grant(s) on this facility in the past?", "Applicant priority",
    ])
    for s in scenario.sites:
        w.writerow([
            s.category, s.name, s.address, s.city, s.state, s.zip_code,
            s.latitude if s.latitude is not None else "",
            s.longitude if s.longitude is not None else "",
            s.damage_description, s.primary_cause, f"{s.approx_cost:.2f}",
            f"{s.percent_complete:.2f}", s.labor_type, s.prior_pa_grant, s.priority,
        ])
    return buf.getvalue()


def project_summary_csv(scenario: Scenario) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "Project", "Category", "Sites", "Size", "Application", "Payment basis",
        "Gross eligible", "Insurance offset", "Net eligible",
        "Federal share", "Non-federal share", "Donated credit",
        "Applicant out of pocket", "406 mitigation",
    ])
    for p in scenario.projects:
        cs = summarize_project(p, scenario)
        cls = classify(p, scenario)
        w.writerow([
            p.title, p.category, len(p.site_ids), cls.size, cls.application_form,
            cls.payment_basis, f"{cs.gross_eligible:.2f}", f"{cs.insurance_offset:.2f}",
            f"{cs.net_eligible:.2f}", f"{cs.federal_share:.2f}",
            f"{cs.non_federal_share:.2f}", f"{cs.donated_credit_applied:.2f}",
            f"{cs.applicant_out_of_pocket:.2f}", f"{cs.mitigation:.2f}",
        ])
    return buf.getvalue()


def full_package(scenario: Scenario) -> str:
    """Everything, concatenated — the text an applicant would print and file."""
    parts = [
        reimbursement_request(scenario),
        "",
        "=" * 70,
        "PROJECT DETAIL",
        "=" * 70,
    ]
    for p in scenario.projects:
        parts += ["", ddd_narrative(p, scenario), "", cost_summary_text(p, scenario), ""]
        parts.append("DOCUMENTATION CHECKLIST")
        parts.append("-" * 70)
        for item, ok in documentation_checklist(p, scenario):
            parts.append(f"  [{'x' if ok else ' '}] {item}")
        parts.append("")
        parts.append("=" * 70)
    return "\n".join(parts)
