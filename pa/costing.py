"""Cost buildup and cost-share math for a PA project.

The ordering below is not arbitrary -- it is the order FEMA applies reductions:

    1. Build gross eligible cost from labor, equipment, materials, and contracts,
       dropping ineligible components (straight time on emergency work, standby
       equipment, code upgrades that fail the five-part test).
    2. Add any approved Section 406 mitigation.
    3. Subtract insurance proceeds, actual and anticipated. Insurance is the
       applicant's FIRST means of funding (PAPPG p.220).
    4. Subtract the Stafford Act Sec. 311 mandatory reduction for an uninsured
       insurable building in a Special Flood Hazard Area damaged by flood.
    5. Apply any Section 428 fixed-cost offer, which caps the award.
    6. Split at the applicable federal share -- normally the declaration's, but the
       Section 428 debris sliding scale can raise it.
    7. Credit donated resources against the APPLICANT's non-federal share only.
       Emergency work pools that credit across all Cat-A and Cat-B projects;
       permanent work caps it per project. Donated value never increases the
       federal contribution.

Step 7 is why per-project summarization is not sufficient on its own -- use
``summarize_all`` when you need the whole portfolio, which is what
``summarize_project`` does internally.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import (
    CostType,
    DonatedResourceLine,
    EmployeeClass,
    EquipmentLine,
    LaborLine,
    Project,
    Scenario,
    SimpleCostLine,
    Site,
)
from .rules import CATEGORIES, RuleSet, WorkType


@dataclass
class LaborResult:
    straight_time_eligible: float = 0.0
    straight_time_excluded: float = 0.0
    overtime: float = 0.0
    fringe: float = 0.0
    total: float = 0.0
    exclusion_reason: str = ""


@dataclass
class EquipmentResult:
    total: float = 0.0
    standby_excluded: float = 0.0
    rate_reduction: float = 0.0     # where an adopted rate undercut the FEMA rate
    notes: list[str] = field(default_factory=list)


@dataclass
class CostSummary:
    """Everything the UI and the export need to show a defensible cost build."""

    labor: LaborResult = field(default_factory=LaborResult)
    equipment: EquipmentResult = field(default_factory=EquipmentResult)
    materials: float = 0.0
    contract: float = 0.0
    rental: float = 0.0
    mutual_aid: float = 0.0
    other: float = 0.0
    mitigation: float = 0.0
    codes_and_standards: float = 0.0
    codes_and_standards_excluded: float = 0.0

    gross_eligible: float = 0.0
    insurance_offset: float = 0.0
    #: Stafford Act Sec. 311 mandatory reduction for an uninsured insurable building
    #: in a Special Flood Hazard Area damaged by flood.
    section_311_reduction: float = 0.0
    section_311_notes: list[str] = field(default_factory=list)
    net_eligible: float = 0.0

    #: The share actually applied, which the Section 428 debris sliding scale can
    #: raise above the declaration's standard share.
    federal_share_rate: float = 0.75
    cost_share_note: str = ""
    federal_share: float = 0.0
    non_federal_share: float = 0.0
    donated_value: float = 0.0
    donated_credit_applied: float = 0.0
    donated_credit_unused: float = 0.0
    #: "project" for permanent work, "emergency work portfolio" for Cat A and B --
    #: emergency donated resources are capped against the COMBINED non-federal share
    #: of all Cat-A and Cat-B projects, not project by project.
    donated_scope: str = "project"
    applicant_out_of_pocket: float = 0.0

    #: Section 428 permanent work fixed-cost offer.
    fixed_cost_offer: float = 0.0
    fixed_cost_variance: float = 0.0

    is_large_project: bool = False
    meets_minimum: bool = False
    retainage_per_payment: float = 0.0

    def as_rows(self) -> list[tuple[str, float]]:
        return [
            ("Force account labor", self.labor.total),
            ("Force account equipment", self.equipment.total),
            ("Materials & supplies", self.materials),
            ("Contract", self.contract),
            ("Rented equipment", self.rental),
            ("Mutual aid", self.mutual_aid),
            ("Other direct costs", self.other),
            ("Codes and standards upgrades", self.codes_and_standards),
            ("Section 406 mitigation", self.mitigation),
        ]


# -- labor ---------------------------------------------------------------------


def compute_labor(
    lines: list[LaborLine],
    category_code: str,
    debris_straight_time_elected: bool = False,
) -> LaborResult:
    """Apply the straight-time eligibility rule for the category.

    ALL Emergency Work (Cat-A debris and Cat-B protective measures) and Cat-I code
    enforcement reimburse budgeted employees for OVERTIME ONLY. Permanent Work and
    Cat-Z reimburse straight time as well. Temporary and emergency hires are fully
    eligible in every category.

    The one exception: an applicant that elects the Section 428 alternative procedure
    for debris removal makes straight time eligible for budgeted employees doing
    eligible Cat-A work.
    """
    cat = CATEGORIES.get(category_code.upper())
    res = LaborResult()
    if cat is None:
        return res

    elected = (
        debris_straight_time_elected
        and cat.straight_time_exception == "section_428_debris_straight_time"
    )

    for ln in lines:
        n = max(1, ln.employee_count)
        st_base = ln.straight_time_hours * ln.straight_rate * n
        ot_rate = ln.overtime_rate or (ln.straight_rate * 1.5)
        ot_base = ln.overtime_hours * ot_rate * n

        temp = ln.employee_class is EmployeeClass.TEMPORARY
        st_ok = (
            cat.straight_time_eligible
            or elected
            or (temp and cat.temp_hire_fully_eligible)
        )

        if st_ok:
            res.straight_time_eligible += st_base
        else:
            res.straight_time_excluded += st_base

        if cat.overtime_eligible:
            res.overtime += ot_base

        eligible_base = (st_base if st_ok else 0.0) + ot_base
        res.fringe += eligible_base * ln.fringe_rate

    if res.straight_time_excluded > 0:
        res.exclusion_reason = (
            f"Cat-{cat.code} is Emergency Work, which reimburses budgeted employees "
            f"for overtime only; straight time is not eligible "
            f"(PAPPG p.{cat.pappg_page}). Reclassify as a temporary hire only if that "
            "is factually correct."
        )
        if cat.straight_time_exception == "section_428_debris_straight_time":
            res.exclusion_reason += (
                " This is the one category with a way back: electing the Section 428 "
                "alternative procedure for debris removal makes straight time eligible "
                "for budgeted employees on eligible debris work. The election is made "
                "per disaster and is worth evaluating before the deadline."
            )

    res.straight_time_eligible = round(res.straight_time_eligible, 2)
    res.straight_time_excluded = round(res.straight_time_excluded, 2)
    res.overtime = round(res.overtime, 2)
    res.fringe = round(res.fringe, 2)
    res.total = round(res.straight_time_eligible + res.overtime + res.fringe, 2)
    return res


# -- equipment -----------------------------------------------------------------


def compute_equipment(lines: list[EquipmentLine], uses_adopted_rates: bool) -> EquipmentResult:
    """Bill operating hours at the lesser of the FEMA rate and any adopted rate.

    Standby hours are excluded outright -- equipment must be in actual operation
    performing eligible work.
    """
    res = EquipmentResult()
    for ln in lines:
        rate = ln.fema_rate
        if uses_adopted_rates and ln.adopted_rate is not None:
            chosen = min(ln.fema_rate, ln.adopted_rate)
            if chosen < ln.fema_rate:
                res.rate_reduction += (ln.fema_rate - chosen) * ln.hours
                res.notes.append(
                    f"{ln.description or ln.fema_cost_code}: adopted rate "
                    f"${chosen:,.2f} is lower than the FEMA schedule rate "
                    f"${ln.fema_rate:,.2f}; FEMA pays the lesser."
                )
            rate = chosen
        res.total += ln.hours * rate
        if ln.standby_hours:
            res.standby_excluded += ln.standby_hours * rate
        if ln.operator_included:
            res.notes.append(
                f"{ln.description or ln.fema_cost_code}: operator labor is NOT included "
                "in the FEMA equipment rate and must be claimed as a separate labor "
                "line. Verify this is not double-counted."
            )
    res.total = round(res.total, 2)
    res.standby_excluded = round(res.standby_excluded, 2)
    res.rate_reduction = round(res.rate_reduction, 2)
    return res


# -- simple lines --------------------------------------------------------------


def _sum_by_type(costs: list[SimpleCostLine], ctype: CostType) -> float:
    return round(sum(c.total for c in costs if c.cost_type is ctype), 2)


# -- mitigation ----------------------------------------------------------------


def eligible_mitigation(project: Project, repair_cost: float, rules: RuleSet) -> tuple[float, list[str]]:
    """Return the approvable 406 mitigation amount and the reasoning behind it."""
    m = rules.mitigation
    cat = CATEGORIES.get(project.category.upper())
    notes: list[str] = []

    if cat is None or project.category.upper() not in m.eligible_categories:
        if project.mitigation:
            notes.append(
                f"Section 406 mitigation is available only on permanent work "
                f"(Cat-{'/'.join(m.eligible_categories)}). Cat-{project.category} "
                "proposals cannot be funded here; consider the Section 404 Hazard "
                "Mitigation Grant Program, which is state-administered and separate."
            )
        return 0.0, notes

    approved = 0.0
    auto_cap = repair_cost * m.percent_of_project_auto
    list_cap = repair_cost * m.pappg_list_cap

    for prop in project.mitigation:
        if not prop.directly_related_to_damaged_element:
            notes.append(
                f"'{prop.description}': mitigation must be directly related to the "
                "eligible damaged element. Not counted."
            )
            continue

        running = approved + prop.proposed_cost
        if running <= auto_cap:
            approved = running
            notes.append(
                f"'{prop.description}': within {m.percent_of_project_auto:.0%} of the "
                f"eligible repair cost — approvable without further justification."
            )
        elif prop.on_pappg_list and running <= list_cap:
            approved = running
            notes.append(
                f"'{prop.description}': on the PAPPG mitigation list and within 100% "
                "of eligible repair cost — approvable."
            )
        elif prop.bca_performed and prop.bcr >= m.minimum_bcr:
            approved = running
            notes.append(
                f"'{prop.description}': exceeds the 100% cap but carries a favorable "
                f"BCA (BCR {prop.bcr:.2f} ≥ {m.minimum_bcr:.1f}) — approvable."
            )
        else:
            need = "a favorable Benefit-Cost Analysis (BCR ≥ 1.0)"
            if not prop.on_pappg_list and running <= list_cap:
                need = "either placement on the PAPPG list or " + need
            notes.append(
                f"'{prop.description}': ${prop.proposed_cost:,.2f} pushes mitigation to "
                f"${running:,.2f} against ${repair_cost:,.2f} of eligible repair. "
                f"Requires {need}. Not counted."
            )

    return round(approved, 2), notes


# -- codes and standards -------------------------------------------------------


def eligible_codes_and_standards(
    project: Project, rules: RuleSet
) -> tuple[float, float, list[str]]:
    """Return (eligible, excluded, notes) for code-driven upgrade costs.

    All five criteria must hold. An upgrade that fails any one of them is the
    applicant's own expense, not a disaster cost.
    """
    criteria = rules.codes_and_standards.criteria
    eligible = excluded = 0.0
    notes: list[str] = []

    for cs in project.codes_and_standards:
        if cs.upgrade_cost <= 0:
            continue        # nothing claimed, nothing to test
        failing = cs.failing(criteria)
        label = cs.description or cs.citation or cs.id
        if failing:
            excluded += cs.upgrade_cost
            notes.append(
                f"'{label}': ${cs.upgrade_cost:,.2f} not eligible. Fails "
                f"{len(failing)} of the five criteria — {'; '.join(failing)}."
            )
        else:
            eligible += cs.upgrade_cost
            notes.append(
                f"'{label}': ${cs.upgrade_cost:,.2f} eligible. Meets all five criteria."
            )
    return round(eligible, 2), round(excluded, 2), notes


# -- Section 311 mandatory insurance reduction ---------------------------------


def section_311_reduction(
    sites: list[Site], scenario: Scenario
) -> tuple[float, list[str]]:
    """The NFIP mandatory reduction (Stafford Act Sec. 311, 44 CFR 206.252).

    Applies to an insurable BUILDING, in a Special Flood Hazard Area identified for
    more than a year, damaged by FLOOD, that carried no flood insurance. FEMA reduces
    eligible cost by the maximum proceeds a standard NFIP policy would have paid.
    """
    rules = scenario.rules.insurance
    applicant = scenario.applicant
    total = 0.0
    notes: list[str] = []

    exempt_pnp = (
        rules.exempt_pnp_in_nonparticipating_community
        and applicant.is_pnp
        and not applicant.nfip_participating
    )

    for site in sites:
        if not site.is_insurable_building:
            continue
        if not site.in_special_flood_hazard_area:
            continue
        if site.sfha_designated_years < rules.sfha_designated_min_years:
            continue
        if "flood" not in (site.primary_cause or "").lower():
            continue

        reduction = rules.section_311_reduction(
            site.building_value, site.contents_value, site.flood_insurance_in_force
        )
        if reduction <= 0:
            continue

        if exempt_pnp:
            notes.append(
                f"{site.name}: would face a ${reduction:,.2f} Section 311 reduction, "
                "but FEMA does not apply it to private non-profit facilities in "
                "communities that do not participate in the NFIP."
            )
            continue

        total += reduction
        notes.append(
            f"{site.name}: ${reduction:,.2f} MANDATORY reduction. This is an insurable "
            f"building in a Special Flood Hazard Area identified for "
            f"{site.sfha_designated_years:g} year(s), damaged by flood, carrying "
            f"${site.flood_insurance_in_force:,.2f} of flood coverage. FEMA reduces "
            "eligible cost by the maximum proceeds a standard NFIP policy would have "
            "paid, whether or not the policy was ever purchased."
        )
    return round(total, 2), notes


# -- top level -----------------------------------------------------------------


def _project_federal_rate(project: Project, scenario: Scenario) -> tuple[float, str]:
    """The federal share for this project.

    Normally the declaration's share. Debris under the Section 428 election earns an
    increased share on a sliding scale keyed to how quickly the work finished.
    """
    rules = scenario.rules
    standard = rules.cost_share.federal
    if project.category.upper() != "A":
        return standard, ""
    if not scenario.applicant.section_428_debris_straight_time:
        return standard, ""

    end = scenario.disaster.incident_end
    days = (
        (project.debris_completion_date - end).days
        if project.debris_completion_date and end
        else None
    )
    return rules.section_428.debris_federal_share(days, standard)


def _base_summary(project: Project, scenario: Scenario) -> CostSummary:
    """Everything except the donated-resource credit, which needs portfolio context."""
    rules = scenario.rules
    s = CostSummary()

    s.labor = compute_labor(
        project.labor, project.category,
        debris_straight_time_elected=scenario.applicant.section_428_debris_straight_time,
    )
    s.equipment = compute_equipment(
        project.equipment, scenario.applicant.uses_adopted_equipment_rates
    )
    s.materials = _sum_by_type(project.costs, CostType.MATERIALS)
    s.contract = _sum_by_type(project.costs, CostType.CONTRACT)
    s.rental = _sum_by_type(project.costs, CostType.RENTAL)
    s.mutual_aid = _sum_by_type(project.costs, CostType.MUTUAL_AID)
    s.other = _sum_by_type(project.costs, CostType.OTHER)

    s.codes_and_standards, s.codes_and_standards_excluded, _ = (
        eligible_codes_and_standards(project, rules)
    )

    repair_cost = round(
        s.labor.total + s.equipment.total + s.materials + s.contract
        + s.rental + s.mutual_aid + s.other + s.codes_and_standards,
        2,
    )
    s.mitigation, _ = eligible_mitigation(project, repair_cost, rules)
    s.gross_eligible = round(repair_cost + s.mitigation, 2)

    sites = scenario.sites_for(project)

    # Reductions, in FEMA's order: insurance proceeds first, then the Section 311
    # mandatory reduction for an uninsured insurable building in an SFHA.
    s.insurance_offset = round(
        sum(site.total_insurance_offset for site in sites), 2
    )
    s.section_311_reduction, s.section_311_notes = section_311_reduction(sites, scenario)

    s.net_eligible = round(
        max(0.0, s.gross_eligible - s.insurance_offset - s.section_311_reduction), 2
    )

    # Section 428 permanent work: the fixed-cost offer caps the award.
    if project.fixed_cost_offer_accepted and project.fixed_cost_offer > 0:
        s.fixed_cost_offer = round(project.fixed_cost_offer, 2)
        s.fixed_cost_variance = round(s.fixed_cost_offer - s.net_eligible, 2)
        s.net_eligible = s.fixed_cost_offer

    s.federal_share_rate, s.cost_share_note = _project_federal_rate(project, scenario)
    s.federal_share = round(s.net_eligible * s.federal_share_rate, 2)
    s.non_federal_share = round(s.net_eligible - s.federal_share, 2)

    s.donated_value = round(sum(d.value for d in project.donated), 2)
    s.applicant_out_of_pocket = s.non_federal_share

    s.is_large_project = rules.is_large_project(s.net_eligible)
    s.meets_minimum = rules.meets_minimum(s.net_eligible)
    if s.is_large_project:
        s.retainage_per_payment = round(
            s.federal_share * rules.thresholds.large_project_retainage, 2
        )
    return s


def summarize_all(scenario: Scenario) -> dict[str, CostSummary]:
    """Every project's cost summary, with donated resources allocated correctly.

    Donated resources offset the APPLICANT's share and never increase the federal
    contribution. The cap differs by work type:

      Emergency Work  -- capped against the COMBINED non-federal share of all Cat-A
                         and Cat-B projects. Value donated to one flood-fight site
                         can therefore absorb the applicant's share on another, which
                         is why FEMA holds the emergency donated-resource project
                         until the Cat-A and Cat-B projects obligate.
      Permanent Work  -- capped per project.
    """
    summaries = {p.id: _base_summary(p, scenario) for p in scenario.projects}

    emergency = [
        p for p in scenario.projects
        if (CATEGORIES.get(p.category.upper()) or None)
        and CATEGORIES[p.category.upper()].work_type is WorkType.EMERGENCY
    ]

    # Emergency work: pool the donated value and the applicant share, then allocate.
    pool = round(sum(summaries[p.id].donated_value for p in emergency), 2)
    capacity = round(sum(summaries[p.id].non_federal_share for p in emergency), 2)
    applied_total = round(min(pool, capacity), 2)
    remaining = applied_total

    for i, p in enumerate(emergency):
        cs = summaries[p.id]
        cs.donated_scope = "emergency work portfolio"
        if capacity <= 0:
            cs.donated_credit_applied = 0.0
        elif i == len(emergency) - 1:
            cs.donated_credit_applied = round(remaining, 2)   # absorb rounding
        else:
            share = cs.non_federal_share / capacity
            cs.donated_credit_applied = round(applied_total * share, 2)
            remaining = round(remaining - cs.donated_credit_applied, 2)
        cs.applicant_out_of_pocket = round(
            cs.non_federal_share - cs.donated_credit_applied, 2
        )

    if emergency:
        unused = round(pool - applied_total, 2)
        first = summaries[emergency[0].id]
        first.donated_credit_unused = unused

    # Permanent work and everything else: per project.
    for p in scenario.projects:
        if p in emergency:
            continue
        cs = summaries[p.id]
        cs.donated_scope = "project"
        cs.donated_credit_applied = round(
            min(cs.donated_value, cs.non_federal_share), 2
        )
        cs.donated_credit_unused = round(
            cs.donated_value - cs.donated_credit_applied, 2
        )
        cs.applicant_out_of_pocket = round(
            cs.non_federal_share - cs.donated_credit_applied, 2
        )

    return summaries


def summarize_project(project: Project, scenario: Scenario) -> CostSummary:
    """Full cost build for one project, in FEMA's order of operations."""
    summaries = summarize_all(scenario)
    if project.id in summaries:
        return summaries[project.id]
    # A project not attached to the scenario still summarizes, minus pooling.
    return _base_summary(project, scenario)


@dataclass
class ScenarioTotals:
    projects: int = 0
    large_projects: int = 0
    small_projects: int = 0
    below_minimum: int = 0
    gross_eligible: float = 0.0
    insurance_offset: float = 0.0
    section_311_reduction: float = 0.0
    codes_and_standards_excluded: float = 0.0
    net_eligible: float = 0.0
    federal_share: float = 0.0
    non_federal_share: float = 0.0
    donated_value: float = 0.0
    donated_credit: float = 0.0
    donated_credit_unused: float = 0.0
    applicant_out_of_pocket: float = 0.0
    mitigation: float = 0.0
    by_category: dict[str, float] = field(default_factory=dict)
    management_cost_cap: float = 0.0
    management_cost_claimed: float = 0.0
    #: The state recipient's separate Cat-Z allowance. Not the applicant's money, but
    #: it is what funds the state PA staff the applicant works with.
    recipient_management_cost_cap: float = 0.0
    single_audit_triggered: bool = False
    #: DRRA Sec. 1219: arbitration is available in lieu of a second appeal above this.
    arbitration_threshold: float = 0.0


def summarize_scenario(scenario: Scenario) -> ScenarioTotals:
    """Roll every project up, then apply the Cat-Z cap against the total obligated."""
    rules = scenario.rules
    t = ScenarioTotals()
    mgmt_projects: list[tuple[Project, CostSummary]] = []
    summaries = summarize_all(scenario)

    for p in scenario.projects:
        cs = summaries[p.id]
        code = p.category.upper()
        if code == "Z":
            mgmt_projects.append((p, cs))
            continue

        t.projects += 1
        if cs.is_large_project:
            t.large_projects += 1
        elif cs.meets_minimum:
            t.small_projects += 1
        else:
            t.below_minimum += 1

        t.gross_eligible += cs.gross_eligible
        t.insurance_offset += cs.insurance_offset
        t.section_311_reduction += cs.section_311_reduction
        t.codes_and_standards_excluded += cs.codes_and_standards_excluded
        t.net_eligible += cs.net_eligible
        t.federal_share += cs.federal_share
        t.non_federal_share += cs.non_federal_share
        t.donated_value += cs.donated_value
        t.donated_credit += cs.donated_credit_applied
        t.donated_credit_unused += cs.donated_credit_unused
        t.applicant_out_of_pocket += cs.applicant_out_of_pocket
        t.mitigation += cs.mitigation
        t.by_category[code] = round(t.by_category.get(code, 0.0) + cs.net_eligible, 2)

    # Cat-Z is capped at a percentage of the applicant's TOTAL OBLIGATED amount,
    # so it can only be computed once every other project is rolled up.
    t.management_cost_cap = round(t.net_eligible * rules.management.applicant_cap_rate, 2)
    t.recipient_management_cost_cap = round(
        t.net_eligible * rules.management.recipient_cap_rate, 2
    )
    claimed = sum(cs.gross_eligible for _, cs in mgmt_projects)
    t.management_cost_claimed = round(claimed, 2)
    allowed_mgmt = min(claimed, t.management_cost_cap)

    if allowed_mgmt:
        t.projects += len(mgmt_projects)
        fed, non_fed = rules.cost_share.split(allowed_mgmt)
        t.net_eligible += allowed_mgmt
        t.gross_eligible += allowed_mgmt
        t.federal_share += fed
        t.non_federal_share += non_fed
        t.applicant_out_of_pocket += non_fed
        t.by_category["Z"] = round(allowed_mgmt, 2)

    for attr in (
        "gross_eligible", "insurance_offset", "section_311_reduction",
        "codes_and_standards_excluded", "net_eligible", "federal_share",
        "non_federal_share", "donated_value", "donated_credit",
        "donated_credit_unused", "applicant_out_of_pocket", "mitigation",
    ):
        setattr(t, attr, round(getattr(t, attr), 2))

    t.single_audit_triggered = t.federal_share >= rules.thresholds.single_audit
    t.arbitration_threshold = (
        rules.appeals.arbitration_minimum_small_impoverished
        if scenario.applicant.small_impoverished_community
        else rules.appeals.arbitration_minimum
    )
    return t
