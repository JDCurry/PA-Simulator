"""Project formulation: turning an Impact List into projects FEMA can obligate.

Grouping is not cosmetic. It decides whether costs clear the $4,100 floor, whether
a project crosses the large-project threshold (and therefore gets paid on actual
cost with retainage instead of on estimate), and whether the work goes on a
Streamlined Project Application.

FEMA's grouping conventions, in the order they bind:

  * Category never mixes. A Cat-A site and a Cat-B site are different projects.
  * Cat-I is a single project, always -- all code enforcement costs, one project.
  * Cat-Z is a single project, always -- one management cost project per applicant.
  * Completed work and work-to-be-completed are formulated separately, because one
    is paid on actual cost and the other on estimate.
  * Emergency work may be combined city- or county-wide; permanent work is grouped
    by facility and logical/geographic proximity.
"""

from __future__ import annotations

from dataclasses import dataclass

from .costing import summarize_project
from .models import CompletionStatus, Project, Scenario, Site
from .rules import CATEGORIES, RuleSet, WorkType


SINGLE_PROJECT_CATEGORIES = ("I", "Z")


@dataclass
class Classification:
    """How a project will be administered, given its net eligible cost."""

    size: str                  # "Large" | "Small" | "Below minimum"
    payment_basis: str
    application_form: str
    closeout_document: str
    simplified_procedures: bool
    notes: list[str]


def classify(project: Project, scenario: Scenario) -> Classification:
    rules = scenario.rules
    cs = summarize_project(project, scenario)
    t = rules.thresholds
    notes: list[str] = []

    sites = scenario.sites_for(project)
    all_complete = bool(sites) and all(s.percent_complete >= 1.0 for s in sites)

    if not cs.meets_minimum:
        # Distinguish "too small to begin with" from "reduced below the floor",
        # because the remedy is completely different.
        reductions = cs.insurance_offset + cs.section_311_reduction
        if reductions > 0 and cs.gross_eligible >= t.small_project_minimum:
            notes = [
                f"Gross eligible cost of ${cs.gross_eligible:,.2f} cleared the "
                f"${t.small_project_minimum:,.0f} minimum, but reductions of "
                f"${reductions:,.2f} pushed net eligible to ${cs.net_eligible:,.2f}. "
                "Grouping more sites will not fix this — the reduction follows the "
                "facility."
            ]
            if cs.section_311_reduction > 0:
                notes.append(
                    f"${cs.section_311_reduction:,.2f} of that is the Stafford Act "
                    "Section 311 mandatory reduction for an uninsured insurable "
                    "building in a Special Flood Hazard Area. It is sized on the "
                    "maximum NFIP proceeds that would have been available, NOT on the "
                    "amount of damage, which is why it can exceed the whole project."
                )
        else:
            notes = [
                f"Net eligible cost ${cs.net_eligible:,.2f} is under the "
                f"${t.small_project_minimum:,.0f} minimum. Combine this work with "
                "other sites in the same category and completion status, or it "
                "cannot be written as a project."
            ]
        return Classification(
            size="Below minimum",
            payment_basis="Not fundable as formulated",
            application_form="—",
            closeout_document="—",
            simplified_procedures=False,
            notes=notes,
        )

    if cs.is_large_project:
        notes.append(
            f"Exceeds the ${t.large_project_threshold:,.0f} large-project threshold. "
            "Payment is based on ACTUAL cost, adjusted from the estimate at "
            "completion, paid progressively as work is completed."
        )
        notes.append(
            f"{t.large_project_retainage:.0%} retainage "
            f"(${cs.retainage_per_payment:,.2f}) is withheld from each payment and "
            "released on FEMA approval of the final inspection."
        )
        notes.append("Simplified Procedures do not apply to large projects.")
        closeout = "Statement of Documentation in Final Inspection Report (SOD-FIR), signed by the applicant agent or alternate"
        payment = "Actual cost, progressive payment with retainage"
        size = "Large"
    else:
        payment = (
            "Actual cost (work already completed)" if all_complete
            else "Approved estimate (work to be completed)"
        )
        notes.append(
            "Small project. Work to be completed is written and paid on estimate; "
            "completed work is paid on actual cost. The applicant keeps the "
            "difference either way, and absorbs an overrun on any single project."
        )
        notes.append(
            "If total costs across ALL small projects overrun the approved estimates, "
            "a Net Small Project Overrun (NSPO) appeal may be filed for additional "
            "funding — based on actual costs for every small project."
        )
        closeout = "Small project certification form or letter, signed by the applicant agent or alternate"
        size = "Small"

    form = (
        "Streamlined Project Application (SPA)"
        if rules.requires_spa(project.category)
        else "Standard project application"
    )
    if rules.requires_spa(project.category):
        notes.append(
            f"Cat-{project.category.upper()} must be submitted on the Streamlined "
            "Project Application."
        )

    return Classification(
        size=size,
        payment_basis=payment,
        application_form=form,
        closeout_document=closeout,
        simplified_procedures=(size == "Small"),
        notes=notes,
    )


# -- automatic grouping --------------------------------------------------------


def _group_key(site: Site, rules: RuleSet) -> tuple:
    code = site.category.upper()
    cat = CATEGORIES.get(code)
    if code in SINGLE_PROJECT_CATEGORIES:
        return (code, "single")
    if cat and cat.work_type is WorkType.EMERGENCY:
        # Emergency work may be combined jurisdiction-wide, but completed and
        # to-be-completed work still separate.
        return (code, site.status.value)
    # Permanent work: separate by completion status and by facility/locality.
    return (code, site.status.value, (site.city or "").strip().lower())


def _title_for(code: str, key: tuple, scenario: Scenario) -> str:
    cat = CATEGORIES[code]
    applicant = scenario.applicant.name or "Applicant"
    if code == "Z":
        return f"{applicant} — Cat-Z Management Costs"
    if code == "I":
        return f"{applicant} — Cat-I Building Code & Floodplain Management Enforcement"
    status = key[1] if len(key) > 1 else ""
    where = f" — {key[2].title()}" if len(key) > 2 and key[2] else ""
    return f"Cat-{code} {cat.name}{where} ({status})"


def auto_group(scenario: Scenario, only_unassigned: bool = True) -> list[Project]:
    """Propose projects from the impact list using FEMA's grouping conventions.

    Returns new Project objects; the caller decides whether to accept them. Grouping
    is a judgement call made with the PDMG, so this is a starting point, not an
    answer.
    """
    pool = scenario.unassigned_sites() if only_unassigned else list(scenario.sites)
    buckets: dict[tuple, list[Site]] = {}
    for site in pool:
        if not site.category:
            continue
        buckets.setdefault(_group_key(site, scenario.rules), []).append(site)

    proposed: list[Project] = []
    for key, sites in sorted(buckets.items(), key=lambda kv: (kv[0][0], str(kv[0][1:]))):
        code = key[0]
        if code not in CATEGORIES:
            continue
        p = Project(
            title=_title_for(code, key, scenario),
            category=code,
            site_ids=[s.id for s in sites],
            estimated_cost=round(sum(s.approx_cost for s in sites), 2),
        )
        p.ddd_damage = "\n\n".join(
            f"[{s.name}] {s.damage_description}".strip()
            for s in sites if s.damage_description
        )
        p.ddd_dimensions = "\n".join(
            f"{s.name}: {s.address or 'address not recorded'}"
            + (f" ({s.latitude}, {s.longitude})" if s.latitude and s.longitude else "")
            for s in sites
        )
        proposed.append(p)
    return proposed


@dataclass
class GroupingIssue:
    severity: str          # "error" | "warning" | "info"
    message: str
    project_id: str = ""


def review_grouping(scenario: Scenario) -> list[GroupingIssue]:
    """Check the current grouping against the conventions above."""
    issues: list[GroupingIssue] = []
    rules = scenario.rules

    for p in scenario.projects:
        sites = scenario.sites_for(p)
        if not sites:
            issues.append(GroupingIssue(
                "warning", f"'{p.title}' has no sites assigned.", p.id))
            continue

        mixed = {s.category.upper() for s in sites if s.category}
        if len(mixed) > 1:
            issues.append(GroupingIssue(
                "error",
                f"'{p.title}' mixes categories {sorted(mixed)}. A project cannot span "
                "work categories — split it.",
                p.id,
            ))
        elif mixed and p.category.upper() not in mixed:
            issues.append(GroupingIssue(
                "error",
                f"'{p.title}' is filed as Cat-{p.category} but its sites are "
                f"Cat-{sorted(mixed)[0]}.",
                p.id,
            ))

        statuses = {s.status for s in sites}
        if CompletionStatus.COMPLETE in statuses and len(statuses) > 1:
            issues.append(GroupingIssue(
                "warning",
                f"'{p.title}' mixes completed work with work to be completed. "
                "Completed work is paid on actual cost and incomplete work on "
                "estimate — FEMA normally formulates these separately.",
                p.id,
            ))

        cls = classify(p, scenario)
        if cls.size == "Below minimum":
            issues.append(GroupingIssue("error", cls.notes[0], p.id))

    for code in SINGLE_PROJECT_CATEGORIES:
        matching = [p for p in scenario.projects if p.category.upper() == code]
        if len(matching) > 1:
            issues.append(GroupingIssue(
                "error",
                f"There are {len(matching)} Cat-{code} projects. All Cat-{code} costs "
                "must be formulated into a single project "
                f"(PAPPG p.{CATEGORIES[code].pappg_page}).",
            ))

    orphans = scenario.unassigned_sites()
    if orphans:
        issues.append(GroupingIssue(
            "warning",
            f"{len(orphans)} site(s) on the impact list are not assigned to any "
            f"project: {', '.join(s.name or s.id for s in orphans[:5])}"
            + (" …" if len(orphans) > 5 else ""),
        ))

    return issues
