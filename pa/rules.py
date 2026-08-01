"""Declarative, versioned FEMA Public Assistance rules.

Everything that changes between disasters, fiscal years, or policy revisions lives
here as data -- not as branches scattered through the costing and validation code.
A new disaster is a new ``RuleSet``, not a new code path.

Primary source: FEMA Public Assistance Program and Policy Guide (PAPPG) V5 Amended,
January 2025, and FEMA Policy FP-104-23-001 (Public Assistance Simplified
Procedures), January 2023. Page citations refer to PAPPG V5 Amended.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from enum import Enum


class WorkType(str, Enum):
    EMERGENCY = "Emergency Work"
    PERMANENT = "Permanent Work"
    CODE_ENFORCEMENT = "Building Code & Floodplain Management Enforcement"
    MANAGEMENT = "Management Costs"


@dataclass(frozen=True)
class Category:
    """A PA work category (A-G, I, Z)."""

    code: str
    name: str
    work_type: WorkType
    pappg_page: int
    # Force-account labor eligibility for the applicant's own budgeted employees.
    # ALL Emergency Work (A and B) and Code Enforcement (I) reimburse overtime only.
    # Only Permanent Work and Management Costs reimburse straight time outright.
    straight_time_eligible: bool
    overtime_eligible: bool = True
    # Temporary//emergency hires are fully eligible in every category.
    temp_hire_fully_eligible: bool = True
    mitigation_eligible: bool = False  # Section 406 is Cat C-G only
    #: Where an opt-in procedure can make straight time eligible after all. Cat-A is
    #: the only category with one -- the Section 428 debris straight-time election.
    straight_time_exception: str = ""
    description: str = ""

    @property
    def label(self) -> str:
        return f"Cat-{self.code} — {self.name}"


#: The nine PA categories. Note the labor asymmetry between A and B -- it is the
#: single most common source of de-obligation on emergency work.
CATEGORIES: dict[str, Category] = {
    "A": Category(
        "A", "Debris Removal", WorkType.EMERGENCY, 117,
        straight_time_eligible=False,
        straight_time_exception="section_428_debris_straight_time",
        description=(
            "Eliminating immediate threats to lives, public health and safety; "
            "eliminating significant damage to public or private improved property; "
            "ensuring economic recovery of the affected community. As Emergency Work, "
            "only OVERTIME is eligible for budgeted employees — UNLESS the applicant "
            "opts into the Section 428 alternative procedure for debris removal, which "
            "makes straight time eligible for budgeted employees conducting eligible "
            "debris work. Temporary hires are fully eligible either way."
        ),
    ),
    "B": Category(
        "B", "Emergency Protective Measures", WorkType.EMERGENCY, 130,
        straight_time_eligible=False,
        description=(
            "Eliminating or lessening an immediate threat to life, public health and "
            "safety, or an immediate threat of significant additional damage. For "
            "budgeted (regular) employees only OVERTIME and fringe are eligible; "
            "straight time is not. Temporary hires are fully eligible."
        ),
    ),
    "C": Category(
        "C", "Roads and Bridges", WorkType.PERMANENT, 186,
        straight_time_eligible=True, mitigation_eligible=True,
    ),
    "D": Category(
        "D", "Water Control Facilities", WorkType.PERMANENT, 194,
        straight_time_eligible=True, mitigation_eligible=True,
    ),
    "E": Category(
        "E", "Buildings and Equipment", WorkType.PERMANENT, 195,
        straight_time_eligible=True, mitigation_eligible=True,
    ),
    "F": Category(
        "F", "Utilities", WorkType.PERMANENT, 201,
        straight_time_eligible=True, mitigation_eligible=True,
    ),
    "G": Category(
        "G", "Parks, Recreational, and Other Facilities", WorkType.PERMANENT, 204,
        straight_time_eligible=True, mitigation_eligible=True,
    ),
    "I": Category(
        "I", "Building Code and Floodplain Management Enforcement",
        WorkType.CODE_ENFORCEMENT, 221,
        straight_time_eligible=False,
        description=(
            "Administering and enforcing building codes and floodplain management "
            "ordinances in areas related to the disaster. ALL eligible costs under "
            "this category must be formulated into a SINGLE project. Communities "
            "suspended or sanctioned under the NFIP are ineligible."
        ),
    ),
    "Z": Category(
        "Z", "Management Costs", WorkType.MANAGEMENT, 74,
        straight_time_eligible=True,
        description=(
            "Direct and indirect costs of administering the PA grant. Costs must be "
            "actual and auditable. Capped at a percentage of the applicant's total "
            "obligated amount."
        ),
    ),
}

PERMANENT_WORK_CODES = ("C", "D", "E", "F", "G")
EMERGENCY_WORK_CODES = ("A", "B")


@dataclass(frozen=True)
class Deadlines:
    """Regulatory deadlines, expressed as offsets so any disaster can reuse them."""

    #: The FIRST deadline, and the one that ends the process if missed. An applicant
    #: has 30 days from the date its area is designated to file the Request for
    #: Public Assistance. Everything downstream presumes an approved RPA.
    rpa_days_from_designation: int = 30          # 44 CFR 206.202(c)
    impact_list_days_from_rsm: int = 60          # PAPPG p.70
    emergency_work_months: int = 6               # Cat A-B, from declaration
    permanent_work_months: int = 18              # Cat C-G, from declaration
    code_enforcement_days: int = 180             # Cat I, from declaration
    appeal_days: int = 60                        # PAPPG p.42, 254
    improved_alternate_request_months: int = 12  # from RSM
    #: Cat-I is the one deadline FEMA will not extend (PAPPG p.221, 247).
    extendable: tuple[str, ...] = ("emergency_work", "permanent_work")

    def resolve(
        self,
        declaration_date: date,
        rsm_date: date | None,
        designation_date: date | None = None,
    ) -> dict[str, date]:
        out = {
            "emergency_work": _add_months(declaration_date, self.emergency_work_months),
            "permanent_work": _add_months(declaration_date, self.permanent_work_months),
            "code_enforcement": declaration_date + timedelta(days=self.code_enforcement_days),
        }
        # Areas are often designated on the declaration date; fall back to it.
        out["rpa"] = (designation_date or declaration_date) + timedelta(
            days=self.rpa_days_from_designation
        )
        if rsm_date:
            out["impact_list"] = rsm_date + timedelta(days=self.impact_list_days_from_rsm)
            out["improved_alternate_request"] = _add_months(
                rsm_date, self.improved_alternate_request_months
            )
        return out

    def deadline_for_category(
        self, code: str, declaration_date: date, rsm_date: date | None = None
    ) -> date | None:
        resolved = self.resolve(declaration_date, rsm_date)
        cat = CATEGORIES.get(code.upper())
        if cat is None:
            return None
        if cat.work_type is WorkType.EMERGENCY:
            return resolved["emergency_work"]
        if cat.work_type is WorkType.PERMANENT:
            return resolved["permanent_work"]
        if cat.work_type is WorkType.CODE_ENFORCEMENT:
            return resolved["code_enforcement"]
        return None  # Cat-Z tracks the grant, not a work deadline


def _add_months(d: date, months: int) -> date:
    """Calendar-month offset, clamped to the last valid day of the target month."""
    total = d.month - 1 + months
    year = d.year + total // 12
    month = total % 12 + 1
    day = min(d.day, _days_in_month(year, month))
    return date(year, month, day)


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        return 31
    return (date(year + (month // 12), month % 12 + 1, 1) - timedelta(days=1)).day


@dataclass(frozen=True)
class Thresholds:
    """Dollar thresholds. These are indexed annually -- always set them per disaster."""

    #: Minimum eligible damage for a project to exist at all (all sites combined).
    small_project_minimum: float = 4_100.0
    #: Above this a project is a LARGE project: paid on actual cost, with retainage,
    #: progressive payment, and a final inspection. Simplified Procedures do not apply.
    large_project_threshold: float = 1_093_800.0
    #: Federal procurement thresholds (2 CFR 200 / 41 USC 1908, adjusted 2025-10-01).
    micro_purchase: float = 15_000.0
    simplified_acquisition: float = 350_000.0
    #: Equipment vs. supply. Equipment has a useful life > 1 year AND a per-unit cost
    #: at or above the LESSER of the applicant's capitalization level or this figure.
    equipment_capitalization: float = 10_000.0
    #: Disposition: on large projects, retained equipment at or above this fair market
    #: value requires compensating FEMA (PAPPG p.89).
    disposition_fmv: float = 10_000.0
    #: Aggregate unused supplies below this are not deducted on small projects (p.91).
    supply_disposition_floor: float = 10_000.0
    #: Single Audit Act trigger -- total federal awards expended in a fiscal year.
    single_audit: float = 1_000_000.0
    #: Retainage withheld from each large-project progress payment.
    large_project_retainage: float = 0.10


@dataclass(frozen=True)
class CostShare:
    """Federal / non-federal split. 75/25 is the Stafford Act default; declarations
    can and do adjust it (90/10, or 100% federal for a defined period)."""

    federal: float = 0.75

    @property
    def non_federal(self) -> float:
        return round(1.0 - self.federal, 6)

    def split(self, eligible: float) -> tuple[float, float]:
        fed = round(eligible * self.federal, 2)
        return fed, round(eligible - fed, 2)


@dataclass(frozen=True)
class MitigationRules:
    """Section 406 hazard mitigation -- funded as part of a permanent work project.

    Distinct from the Section 404 Hazard Mitigation Grant Program, which is
    state-administered and not disaster-project-specific.
    """

    #: Tier 1: mitigation up to this fraction of the eligible repair cost is
    #: approved without further justification.
    percent_of_project_auto: float = 0.15
    #: Tier 2: measures on the PAPPG list are eligible up to 100% of eligible repair.
    pappg_list_cap: float = 1.00
    #: Tier 3: anything above the cap requires a favorable Benefit-Cost Analysis.
    bca_required_above: float = 1.00
    minimum_bcr: float = 1.0
    eligible_categories: tuple[str, ...] = PERMANENT_WORK_CODES


@dataclass(frozen=True)
class ManagementCostRules:
    """Cat-Z. DRRA Sec. 1215 and FEMA policy FP 104-11-2 (PAPPG p.74).

    Section 1215 sets a combined 12 percent: up to 7 percent for the RECIPIENT (the
    state) and up to 5 percent for the SUBRECIPIENT (the applicant). An applicant
    sees only its own 5 percent, but the recipient's 7 percent is what funds the
    state PA staff the applicant works with, so the split is worth understanding.
    """

    applicant_cap_rate: float = 0.05   # subrecipient, of its total obligated amount
    recipient_cap_rate: float = 0.07   # state recipient
    requires_actual_auditable_costs: bool = True

    @property
    def combined_cap_rate(self) -> float:
        return round(self.applicant_cap_rate + self.recipient_cap_rate, 4)


@dataclass(frozen=True)
class InsuranceRules:
    """Stafford Act Sec. 311 and 44 CFR 206.252-253.

    The reduction that catches applicants by surprise: an insurable building in a
    Special Flood Hazard Area, damaged by flood, that was NOT insured for flood, has
    its eligible cost reduced by the maximum proceeds a standard NFIP policy WOULD
    have paid -- whether or not the applicant ever bought one. It is not a penalty
    that can be appealed away, and it can exceed the value of the project.
    """

    #: Standard NFIP policy limits for non-residential structures, which is what
    #: public facilities are. Residential limits are lower and not modeled here.
    nfip_max_building: float = 500_000.0
    nfip_max_contents: float = 500_000.0
    #: The SFHA must have been identified for at least this long before the incident.
    sfha_designated_min_years: int = 1
    #: FEMA does not apply the reduction to PNP facilities in communities that do not
    #: participate in the NFIP.
    exempt_pnp_in_nonparticipating_community: bool = True

    @property
    def max_available_proceeds(self) -> float:
        return self.nfip_max_building + self.nfip_max_contents

    def section_311_reduction(
        self, building_value: float, contents_value: float,
        flood_insurance_in_force: float = 0.0,
    ) -> float:
        """Maximum NFIP proceeds that would have been available, less any coverage
        actually carried. Capped by the actual value of the building and contents --
        FEMA cannot deduct more than the facility was worth."""
        available = min(
            self.nfip_max_building, max(0.0, building_value)
        ) + min(self.nfip_max_contents, max(0.0, contents_value))
        return round(max(0.0, available - max(0.0, flood_insurance_in_force)), 2)


@dataclass(frozen=True)
class Section428Rules:
    """PA Alternative Procedures, Stafford Act Sec. 428 (PAPPG p.160, Appendix G).

    Two distinct programs share the section number:

      DEBRIS REMOVAL -- an election that makes straight-time force account labor
      eligible for budgeted employees, pays an increased federal share on a sliding
      scale for accelerated completion, and lets the applicant keep recycling revenue.

      PERMANENT WORK -- a fixed-cost offer. The applicant accepts a capped amount,
      takes on the overrun risk, and in exchange is freed from rebuilding to
      pre-disaster design and may move funds across its alternative-procedures
      projects.
    """

    #: Sliding scale for debris, as (days after the end of the incident period, share).
    #: FEMA pays the higher share on costs INCURRED inside each window, so debris that
    #: spans windows is normally formulated as separate projects per window.
    debris_cost_share_tiers: tuple[tuple[int, float], ...] = (
        (30, 0.85), (90, 0.80), (180, 0.75),
    )
    #: Past the last tier there is no reimbursement without an approved extension.
    debris_deadline_days: int = 180
    recycling_revenue_retained: bool = True
    #: Permanent work fixed-cost offers are subject to acceptance, and excess funds
    #: may be retained for limited purposes.
    permanent_work_fixed_cost_offer: bool = True

    def debris_federal_share(
        self, days_after_incident_end: int | None, standard_share: float
    ) -> tuple[float, str]:
        """Return (federal share, explanation) for debris completed at that point."""
        if days_after_incident_end is None:
            return standard_share, (
                "No debris completion date recorded, so the standard cost share "
                "applies. Recording the date is what unlocks the sliding scale."
            )
        previous = 0
        for cutoff, share in self.debris_cost_share_tiers:
            if days_after_incident_end <= cutoff:
                if share <= standard_share:
                    return standard_share, (
                        f"Completed {days_after_incident_end} days after the incident "
                        f"period ended, which falls in the {previous}-{cutoff} day "
                        f"window at {share:.0%}. That is not better than the standard "
                        f"{standard_share:.0%}, so the standard share applies."
                    )
                return share, (
                    f"Completed {days_after_incident_end} days after the incident "
                    f"period ended. Costs incurred within {previous}-{cutoff} days "
                    f"earn an increased federal share of {share:.0%} instead of "
                    f"{standard_share:.0%}."
                )
            previous = cutoff
        return standard_share, (
            f"Completed {days_after_incident_end} days after the incident period "
            f"ended, past the {self.debris_deadline_days}-day sliding scale. No "
            "increase applies, and reimbursement past the deadline requires an "
            "approved time extension."
        )


@dataclass(frozen=True)
class CodesAndStandardsRules:
    """The five-part test for whether an upgrade required by a code is eligible
    (PAPPG p.168, 44 CFR 206.226(d))."""

    criteria: tuple[tuple[str, str], ...] = (
        ("applies_to_repair_type",
         "Applies to the type of repair required"),
        ("appropriate_to_predisaster_use",
         "Appropriate to the pre-disaster use of the facility"),
        ("formally_adopted_before",
         "Formally adopted and implemented before the declaration, or a post-disaster "
         "consensus-based code adopted under the DRRA"),
        ("applied_uniformly",
         "Applies uniformly to all similar facilities in the jurisdiction, not only "
         "to those damaged by the incident"),
        ("actually_enforced",
         "Was actually enforced during the time it was in effect"),
    )


@dataclass(frozen=True)
class AppealRules:
    """PAPPG p.42, 254; DRRA Sec. 1219 arbitration."""

    first_appeal_days: int = 60
    second_appeal_days: int = 60
    #: DRRA Sec. 1219 allows arbitration in lieu of a second appeal above a threshold.
    arbitration_minimum: float = 500_000.0
    arbitration_minimum_small_impoverished: float = 100_000.0


@dataclass(frozen=True)
class DocumentationRules:
    federal_retention_years: int = 3   # from RECIPIENT closeout, 2 CFR 200.334
    state_retention_years: int = 6     # Washington adds three years
    originals_retained_by_applicant: bool = True


@dataclass(frozen=True)
class EHPTriggers:
    """Screening questions that route a project into environmental / historic review."""

    historic_structure_age_years: int = 45  # DAHP screening age for NRHP eligibility
    triggers: tuple[tuple[str, str], ...] = (
        ("undisturbed_ground", "Work in previously undisturbed areas — NEPA + NHPA review"),
        ("in_or_near_waterway", "Work in or near waterways — NEPA/NHPA, likely ESA + MSA"),
        ("listed_species_present", "Potential listed species — ESA/MSA consultation"),
        ("critical_habitat", "Removal of critical habitat — NEPA/NHPA, likely ESA/MSA"),
        ("historic_structure", "Structure at or over screening age — NHPA Section 106"),
        ("floodplain", "Facility in a floodplain — Executive Order 11988"),
        ("wetland", "Facility in wetlands — Executive Order 11990"),
        ("footprint_change", "Change to facility footprint — full EHP review"),
        ("tribal_land", "Work on tribal lands — tribal consultation required"),
        ("ground_disturbance", "Ground disturbance — archaeological review"),
    )


@dataclass(frozen=True)
class RuleSet:
    """A complete, versioned policy configuration for one disaster."""

    name: str = "PAPPG V5 Amended (Jan 2025) + FP-104-23-001"
    policy_version: str = "V5-Amended-2025-01"
    thresholds: Thresholds = field(default_factory=Thresholds)
    cost_share: CostShare = field(default_factory=CostShare)
    deadlines: Deadlines = field(default_factory=Deadlines)
    mitigation: MitigationRules = field(default_factory=MitigationRules)
    management: ManagementCostRules = field(default_factory=ManagementCostRules)
    documentation: DocumentationRules = field(default_factory=DocumentationRules)
    ehp: EHPTriggers = field(default_factory=EHPTriggers)
    insurance: InsuranceRules = field(default_factory=InsuranceRules)
    section_428: Section428Rules = field(default_factory=Section428Rules)
    codes_and_standards: CodesAndStandardsRules = field(
        default_factory=CodesAndStandardsRules)
    appeals: AppealRules = field(default_factory=AppealRules)
    #: Emergency Work and Cat-I must be submitted on the Streamlined Project
    #: Application rather than a standard project application.
    spa_required_categories: tuple[str, ...] = ("A", "B", "I")
    #: Simplified Procedures never apply to large projects or to donated resources.
    simplified_procedures_excluded: tuple[str, ...] = ("large_project", "donated_resources")

    # -- convenience -----------------------------------------------------------

    def is_large_project(self, eligible_cost: float) -> bool:
        return eligible_cost > self.thresholds.large_project_threshold

    def meets_minimum(self, eligible_cost: float) -> bool:
        return eligible_cost >= self.thresholds.small_project_minimum

    def requires_spa(self, category_code: str) -> bool:
        return category_code.upper() in self.spa_required_categories

    def procurement_method(self, contract_value: float) -> str:
        t = self.thresholds
        if contract_value < t.micro_purchase:
            return "Micro-purchase (no competitive quotes required; distribute equitably)"
        if contract_value < t.simplified_acquisition:
            return "Small purchase / simplified acquisition (rate or price quotes required)"
        return "Sealed bid or competitive proposal (formal advertisement required)"

    def with_cost_share(self, federal: float) -> "RuleSet":
        return replace(self, cost_share=CostShare(federal=federal))


#: The default ruleset used when a scenario does not override anything.
DEFAULT_RULES = RuleSet()


#: Labor types recognized on a damage inventory (matches the FEMA inventory template).
LABOR_TYPES: dict[str, str] = {
    "FA": "Force Account",
    "C": "Contract",
    "FA/C": "Force Account & Contract",
    "MAA": "Mutual Aid Agreement",
    "MOU": "Memorandum of Understanding",
    "MA": "Mission Assigned",
    "DR": "Donated Resource",
}

PRIMARY_CAUSES = (
    "Earthquake", "Fire", "Flood", "Hurricane", "Severe Storm",
    "Tornado", "Tsunami", "Volcanic Eruption", "Wind", "Winter Storm",
)

PRIORITIES = ("Low", "Medium", "High", "Urgent")

#: Human labels for the keys ``Deadlines.resolve`` returns, so every surface names
#: them the same way.
DEADLINE_LABELS: dict[str, str] = {
    "rpa": "Request for Public Assistance (30 days from designation)",
    "impact_list": "Impact List (60 days from the Recovery Scoping Meeting)",
    "code_enforcement": "Cat-I Building Code and Floodplain Management Enforcement",
    "emergency_work": "Emergency Work, Cat A-B (6 months from declaration)",
    "improved_alternate_request":
        "Improved / Alternate Project written request (12 months from RSM)",
    "permanent_work": "Permanent Work, Cat C-G (18 months from declaration)",
}

#: Deadlines FEMA will not extend under any circumstances. Distinct from
#: ``Deadlines.extendable``, which lists the work deadlines that CAN be extended --
#: the other keys are procedural milestones, not work completion deadlines.
NO_EXTENSION_DEADLINES: tuple[str, ...] = ("code_enforcement",)
