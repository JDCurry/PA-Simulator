"""Domain objects for a Public Assistance reimbursement package.

The hierarchy mirrors how FEMA actually formulates a grant:

    Scenario  -- one disaster declaration, one applicant, one ruleset
      Site    -- a damage location from the applicant's Impact List
      Project -- one or more sites grouped together; the unit that gets obligated
        CostLine -- force account labor, equipment, materials, contract, rental, donated
        Mitigation -- Section 406 proposal attached to a permanent work project
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import date
from enum import Enum
from typing import Any

from .rules import CATEGORIES, RuleSet, DEFAULT_RULES


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


class CostType(str, Enum):
    FORCE_ACCOUNT_LABOR = "Force Account Labor"
    FORCE_ACCOUNT_EQUIPMENT = "Force Account Equipment"
    MATERIALS = "Materials & Supplies"
    CONTRACT = "Contract"
    RENTAL = "Rented Equipment"
    MUTUAL_AID = "Mutual Aid"
    DONATED = "Donated Resources"
    OTHER = "Other Direct Cost"


class EmployeeClass(str, Enum):
    """Drives whether straight time is eligible. See rules.Category."""

    BUDGETED = "Budgeted (regular) employee"
    TEMPORARY = "Temporary / emergency hire"


class CompletionStatus(str, Enum):
    NOT_STARTED = "Work to be completed"
    IN_PROGRESS = "Work in progress"
    COMPLETE = "Work completed"

    @classmethod
    def from_percent(cls, pct: float) -> "CompletionStatus":
        if pct >= 1.0:
            return cls.COMPLETE
        if pct <= 0.0:
            return cls.NOT_STARTED
        return cls.IN_PROGRESS


@dataclass
class Applicant:
    name: str = ""
    fips: str = ""                      # FEMA applicant FIPS, e.g. 061-22640-00
    entity_type: str = "Local Government"
    county: str = ""
    state: str = ""
    #: Policies FEMA requires before it will formulate labor or contract costs.
    has_pay_policy: bool = False
    has_procurement_policy: bool = False
    has_insurance_policy: bool = False
    #: A community suspended or sanctioned under the NFIP is ineligible for Cat-I.
    nfip_participating: bool = True
    #: Applicant's own capitalization level; the equipment/supply test uses the
    #: LESSER of this and the ruleset's $10,000 figure.
    capitalization_level: float = 5_000.0
    #: Applicant's locally adopted equipment rates, if any. FEMA pays the lesser of
    #: the adopted rate and the FEMA schedule rate.
    uses_adopted_equipment_rates: bool = False
    #: Section 428 alternative procedure for DEBRIS REMOVAL. Elected per disaster.
    #: When elected, straight-time force account labor becomes eligible for budgeted
    #: employees conducting eligible Cat-A debris work -- the single largest swing in
    #: emergency work cost, and easy to leave unclaimed.
    section_428_debris_straight_time: bool = False
    #: Private non-profits providing non-critical but essential social services must
    #: apply to the SBA first for PERMANENT work. PA covers only what SBA declines.
    sba_application_filed: bool = False
    sba_declined: bool = False
    #: DRRA Sec. 1219 lowers the arbitration threshold for small impoverished
    #: communities.
    small_impoverished_community: bool = False

    @property
    def is_pnp(self) -> bool:
        return self.entity_type.startswith("Private Non-Profit")

    @property
    def is_noncritical_pnp(self) -> bool:
        return self.is_pnp and "non-critical" in self.entity_type.lower()
    primary_contact_role: str = "Applicant — Office of Emergency Management"


@dataclass
class Disaster:
    number: str = ""                    # e.g. 4906-DR
    name: str = ""
    state: str = ""
    declaration_date: date | None = None
    incident_start: date | None = None
    incident_end: date | None = None
    #: When the applicant's area was designated for PA. Starts the 30-day RPA clock.
    #: Often the declaration date, but a county added later has its own.
    designation_date: date | None = None
    rpa_submitted_date: date | None = None
    exploratory_call_date: date | None = None
    rsm_date: date | None = None        # Recovery Scoping Meeting
    incident_types: list[str] = field(default_factory=list)

    def within_incident_period(self, when: date) -> bool:
        if not (self.incident_start and self.incident_end):
            return True  # unknown period -- do not fail the check, flag it elsewhere
        return self.incident_start <= when <= self.incident_end


@dataclass
class Site:
    """A single entry on the Impact List."""

    id: str = field(default_factory=lambda: _new_id("SITE"))
    category: str = "B"
    name: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    latitude: float | None = None
    longitude: float | None = None
    damage_description: str = ""
    primary_cause: str = ""
    approx_cost: float = 0.0
    percent_complete: float = 0.0
    labor_type: str = "FA"
    prior_pa_grant: str = "U"           # Y / N / U
    priority: str = ""
    #: Facility eligibility attributes -- the "FACILITY" leg of the four-part test.
    in_use_at_time_of_disaster: bool = True
    applicant_legal_responsibility: bool = True
    within_declared_area: bool = True
    actively_used_and_maintained: bool = True
    other_federal_agency_authority: bool = False   # FHWA / NRCS / USACE preempt PA
    #: Insurance
    insured: bool = False
    insurance_proceeds: float = 0.0
    anticipated_insurance: float = 0.0
    in_special_flood_hazard_area: bool = False
    #: Section 311 / NFIP mandatory reduction inputs. The reduction applies to an
    #: INSURABLE BUILDING in an SFHA, damaged by FLOOD, that carried no flood
    #: insurance. These fields size the reduction; without them it cannot be computed.
    is_insurable_building: bool = False
    building_value: float = 0.0
    contents_value: float = 0.0
    flood_insurance_in_force: float = 0.0   # coverage carried, not proceeds received
    sfha_designated_years: float = 0.0      # how long the SFHA has been identified
    #: Obtain-and-maintain: a condition of funding, tracked so closeout can check it.
    obtain_and_maintain_acknowledged: bool = False
    #: EHP screening flags, keyed by EHPTriggers.triggers
    ehp_flags: dict[str, bool] = field(default_factory=dict)
    structure_age_years: int | None = None
    #: Consultation and permitting actually finished. Starting work early cannot be
    #: undone, but documenting completed consultation -- or the exigency that
    #: justified proceeding -- is how the exposure is resolved in practice.
    ehp_consultation_complete: bool = False
    ehp_resolution_note: str = ""
    work_start_date: date | None = None
    notes: str = ""

    @property
    def status(self) -> CompletionStatus:
        return CompletionStatus.from_percent(self.percent_complete)

    @property
    def category_obj(self):
        return CATEGORIES.get(self.category.upper())

    @property
    def total_insurance_offset(self) -> float:
        """Both actual and ANTICIPATED proceeds reduce eligible cost (PAPPG p.220)."""
        return round(self.insurance_proceeds + self.anticipated_insurance, 2)


@dataclass
class LaborLine:
    """One force-account labor entry, split straight time vs. overtime.

    Eligibility of the straight-time portion depends on category and employee class,
    which is exactly the rule that most often costs applicants money on Cat-B.
    """

    id: str = field(default_factory=lambda: _new_id("LAB"))
    description: str = ""
    employee_class: EmployeeClass = EmployeeClass.BUDGETED
    employee_count: int = 1
    straight_time_hours: float = 0.0
    overtime_hours: float = 0.0
    straight_rate: float = 0.0          # base hourly, excluding fringe
    overtime_rate: float = 0.0
    fringe_rate: float = 0.0            # as a fraction of base pay, e.g. 0.32
    work_date: date | None = None


@dataclass
class EquipmentLine:
    """Applicant-owned equipment, billed at the FEMA Schedule of Equipment Rates.

    Standby time is never eligible; only hours in actual operation performing
    eligible work (44 CFR 206.228). Operator labor is billed separately as labor.
    """

    id: str = field(default_factory=lambda: _new_id("EQP"))
    description: str = ""
    fema_cost_code: str = ""
    hours: float = 0.0
    fema_rate: float = 0.0
    unit: str = "Hour"
    adopted_rate: float | None = None   # applicant's own rate, if adopted
    operator_included: bool = False     # if True, this line double-counts labor
    standby_hours: float = 0.0          # tracked so the app can show what is excluded


@dataclass
class SimpleCostLine:
    """Materials, contracts, rentals, mutual aid, and other direct costs."""

    id: str = field(default_factory=lambda: _new_id("CST"))
    cost_type: CostType = CostType.MATERIALS
    description: str = ""
    quantity: float = 1.0
    unit_cost: float = 0.0
    vendor: str = ""
    #: Procurement compliance, checked against the ruleset's thresholds.
    competed: bool = False
    sam_debarment_checked: bool = False
    cost_plus_percentage_of_cost: bool = False   # explicitly prohibited
    prevailing_wage_paid: bool = True
    contract_date: date | None = None

    @property
    def total(self) -> float:
        return round(self.quantity * self.unit_cost, 2)


@dataclass
class DonatedResourceLine:
    """Donated labor, equipment, or materials.

    Donated resources do not add to the eligible project cost. Their value is
    credited against the APPLICANT's non-federal share, capped at that share
    (PAPPG p.105). Simplified Procedures do not apply.
    """

    id: str = field(default_factory=lambda: _new_id("DON"))
    resource_type: str = "Labor"        # Labor | Equipment | Materials
    description: str = ""
    hours_or_quantity: float = 0.0
    valuation_rate: float = 0.0
    donor: str = ""
    #: Donated labor is valued at the rate for equivalent work in the applicant's area.
    rate_basis: str = ""

    @property
    def value(self) -> float:
        return round(self.hours_or_quantity * self.valuation_rate, 2)


@dataclass
class MitigationProposal:
    """A Section 406 hazard mitigation measure attached to a permanent work project."""

    id: str = field(default_factory=lambda: _new_id("HM406"))
    description: str = ""
    proposed_cost: float = 0.0
    on_pappg_list: bool = False
    #: Benefit-cost analysis, required only above the 100% cap.
    bca_benefits: float = 0.0
    bca_performed: bool = False
    directly_related_to_damaged_element: bool = True

    @property
    def bcr(self) -> float:
        if self.proposed_cost <= 0:
            return 0.0
        return round(self.bca_benefits / self.proposed_cost, 3)


@dataclass
class CodeStandard:
    """A code or standard driving an upgrade beyond pre-disaster condition.

    All five criteria must hold for the upgrade cost to be eligible. Failing any one
    of them makes the upgrade the applicant's own expense.
    """

    id: str = field(default_factory=lambda: _new_id("CODE"))
    citation: str = ""                  # e.g. "2021 IBC Sec. 1605, adopted 2022-07-01"
    description: str = ""
    upgrade_cost: float = 0.0
    applies_to_repair_type: bool = False
    appropriate_to_predisaster_use: bool = False
    formally_adopted_before: bool = False
    applied_uniformly: bool = False
    actually_enforced: bool = False

    def failing(self, criteria) -> list[str]:
        return [label for key, label in criteria if not getattr(self, key, False)]

    def eligible(self, criteria) -> bool:
        return not self.failing(criteria)


@dataclass
class Project:
    """The unit FEMA obligates. Sites are grouped into projects by category,
    completion status, and logical/geographic grouping."""

    id: str = field(default_factory=lambda: _new_id("PROJ"))
    number: str = ""                    # FEMA-assigned project number, once issued
    title: str = ""
    category: str = "B"
    site_ids: list[str] = field(default_factory=list)
    #: Damage, Description and Dimensions -- the narrative FEMA writes the scope from.
    ddd_damage: str = ""
    ddd_description: str = ""
    ddd_dimensions: str = ""
    scope_of_work: str = ""
    labor: list[LaborLine] = field(default_factory=list)
    equipment: list[EquipmentLine] = field(default_factory=list)
    costs: list[SimpleCostLine] = field(default_factory=list)
    donated: list[DonatedResourceLine] = field(default_factory=list)
    mitigation: list[MitigationProposal] = field(default_factory=list)
    #: Capped-project options (PAPPG p.183-186). Each requires prior written
    #: approval from the state recipient before work proceeds.
    project_option: str = "Standard"    # Standard | Improved | Alternate | Section 428
    state_written_approval: bool = False
    #: Section 428 permanent work: the applicant accepts a capped, fixed-cost offer
    #: and carries the overrun risk in exchange for scope flexibility.
    fixed_cost_offer: float = 0.0
    fixed_cost_offer_accepted: bool = False
    #: Section 428 debris: when the debris work finished, which sets the sliding-scale
    #: federal share. Left unset, the standard share applies.
    debris_completion_date: date | None = None
    #: Recycling revenue retained under the debris alternative procedures. Recorded
    #: for the file; it does not reduce eligible cost when the election is in effect.
    recycling_revenue: float = 0.0
    codes_and_standards: list[CodeStandard] = field(default_factory=list)
    #: Documentation checklist items the applicant attests are in the project file.
    #: Many required records -- debris monitoring logs, disposal site permits, agency
    #: correspondence -- have no field in this tool to hold them, so the applicant
    #: confirms they exist rather than the engine inferring it.
    documentation_confirmed: list[str] = field(default_factory=list)
    #: Populated during formulation; see formulation.py
    estimated_cost: float = 0.0
    notes: str = ""

    def all_cost_lines(self) -> list[SimpleCostLine]:
        return list(self.costs)

    def contracts(self) -> list[SimpleCostLine]:
        return [c for c in self.costs if c.cost_type is CostType.CONTRACT]


@dataclass
class Scenario:
    """A complete working file: one disaster, one applicant, its sites and projects."""

    title: str = "Untitled Scenario"
    applicant: Applicant = field(default_factory=Applicant)
    disaster: Disaster = field(default_factory=Disaster)
    rules: RuleSet = field(default_factory=lambda: DEFAULT_RULES)
    sites: list[Site] = field(default_factory=list)
    projects: list[Project] = field(default_factory=list)
    #: Free-text provenance so a scenario can carry its own teaching notes.
    description: str = ""
    source_note: str = ""

    def site_by_id(self, site_id: str) -> Site | None:
        return next((s for s in self.sites if s.id == site_id), None)

    def project_by_id(self, project_id: str) -> Project | None:
        return next((p for p in self.projects if p.id == project_id), None)

    def sites_for(self, project: Project) -> list[Site]:
        return [s for s in self.sites if s.id in project.site_ids]

    def unassigned_sites(self) -> list[Site]:
        assigned = {sid for p in self.projects for sid in p.site_ids}
        return [s for s in self.sites if s.id not in assigned]

    def categories_present(self) -> list[str]:
        seen = {s.category.upper() for s in self.sites if s.category}
        return [c for c in CATEGORIES if c in seen]

    def to_dict(self) -> dict[str, Any]:
        from .scenario import scenario_to_dict
        return scenario_to_dict(self)
