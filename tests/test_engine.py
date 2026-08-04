"""Rule tests.

These pin the behaviours that cost applicants money when they get them wrong.
Every dollar figure here is traceable to PAPPG V5 Amended or 2 CFR 200.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pa.costing import (
    compute_equipment, compute_labor, summarize_all, summarize_project,
    summarize_scenario,
)
from pa.equipment import is_equipment_not_supply, load_rates, search
from pa.formulation import auto_group, classify, review_grouping
from pa.models import (
    Applicant, CodeStandard, CostType, Disaster, DonatedResourceLine, EmployeeClass,
    EquipmentLine, LaborLine, MitigationProposal, Project, Scenario, SimpleCostLine,
    Site,
)
from pa.rules import CATEGORIES, RuleSet, _add_months
from pa.scenario import scenario_from_dict, scenario_to_dict
from pa.validation import review


# -- fixtures ------------------------------------------------------------------


def make_scenario(**kw) -> Scenario:
    s = Scenario(
        applicant=Applicant(
            name="Test City", fips="061-00000-00",
            has_pay_policy=True, has_procurement_policy=True, has_insurance_policy=True,
        ),
        disaster=Disaster(
            number="9999-DR", name="Test Event", state="WA",
            declaration_date=date(2026, 4, 7),
            incident_start=date(2025, 12, 5),
            incident_end=date(2025, 12, 19),
            rsm_date=date(2026, 6, 24),
            incident_types=["Flood", "Winter Storm"],
        ),
        rules=RuleSet(),
    )
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def a_site(**kw) -> Site:
    kw.setdefault("name", "Test Site")
    kw.setdefault("damage_description", "x" * 60)
    kw.setdefault("primary_cause", "Flood")
    kw.setdefault("state", "WA")
    return Site(**kw)


# -- labor eligibility ---------------------------------------------------------


def test_cat_b_excludes_straight_time_for_budgeted_employees():
    """The single most common Cat-B error. 100 ST hours at $50 must not be paid."""
    line = LaborLine(
        employee_class=EmployeeClass.BUDGETED, employee_count=1,
        straight_time_hours=100, overtime_hours=20,
        straight_rate=50.0, overtime_rate=75.0, fringe_rate=0.0,
    )
    res = compute_labor([line], "B")
    assert res.straight_time_eligible == 0.0
    assert res.straight_time_excluded == 5_000.0
    assert res.overtime == 1_500.0
    assert res.total == 1_500.0
    assert "overtime only" in res.exclusion_reason


def test_cat_a_excludes_straight_time_under_standard_procedures():
    """Debris is Emergency Work. Budgeted employees get overtime only, exactly like
    Cat-B, unless the applicant elects the Section 428 debris procedure."""
    line = LaborLine(
        employee_class=EmployeeClass.BUDGETED, employee_count=1,
        straight_time_hours=100, overtime_hours=20,
        straight_rate=50.0, overtime_rate=75.0, fringe_rate=0.0,
    )
    res = compute_labor([line], "A")
    assert res.straight_time_eligible == 0.0
    assert res.straight_time_excluded == 5_000.0
    assert res.total == 1_500.0
    assert "Section 428" in res.exclusion_reason


def test_section_428_election_makes_debris_straight_time_eligible():
    line = LaborLine(
        employee_class=EmployeeClass.BUDGETED, employee_count=1,
        straight_time_hours=100, overtime_hours=20,
        straight_rate=50.0, overtime_rate=75.0, fringe_rate=0.0,
    )
    res = compute_labor([line], "A", debris_straight_time_elected=True)
    assert res.straight_time_eligible == 5_000.0
    assert res.straight_time_excluded == 0.0
    assert res.total == 6_500.0


def test_section_428_debris_election_does_not_leak_into_cat_b():
    """The election is specific to debris removal. Emergency protective measures are
    unaffected by it."""
    line = LaborLine(
        employee_class=EmployeeClass.BUDGETED, employee_count=1,
        straight_time_hours=100, straight_rate=50.0, fringe_rate=0.0,
    )
    res = compute_labor([line], "B", debris_straight_time_elected=True)
    assert res.straight_time_eligible == 0.0
    assert res.straight_time_excluded == 5_000.0


def test_permanent_work_reimburses_straight_time():
    line = LaborLine(
        employee_class=EmployeeClass.BUDGETED, employee_count=1,
        straight_time_hours=100, overtime_hours=20,
        straight_rate=50.0, overtime_rate=75.0, fringe_rate=0.0,
    )
    for code in ("C", "D", "E", "F", "G"):
        res = compute_labor([line], code)
        assert res.straight_time_eligible == 5_000.0, code
        assert res.straight_time_excluded == 0.0, code


def test_section_428_election_flows_through_the_scenario():
    s = make_scenario()
    site = a_site(category="A")
    s.sites = [site]
    p = Project(title="Debris", category="A", site_ids=[site.id],
                labor=[LaborLine(employee_class=EmployeeClass.BUDGETED,
                                 straight_time_hours=100, straight_rate=50.0)])
    s.projects = [p]
    assert summarize_project(p, s).labor.total == 0.0

    s.applicant.section_428_debris_straight_time = True
    assert summarize_project(p, s).labor.total == 5_000.0


def test_temporary_hires_are_fully_eligible_even_on_cat_b():
    line = LaborLine(
        employee_class=EmployeeClass.TEMPORARY, employee_count=1,
        straight_time_hours=100, overtime_hours=0,
        straight_rate=30.0, fringe_rate=0.0,
    )
    res = compute_labor([line], "B")
    assert res.straight_time_eligible == 3_000.0
    assert res.straight_time_excluded == 0.0


def test_fringe_follows_eligible_base_only():
    """Fringe on excluded straight time is itself excluded."""
    line = LaborLine(
        employee_class=EmployeeClass.BUDGETED, employee_count=1,
        straight_time_hours=100, overtime_hours=100,
        straight_rate=50.0, overtime_rate=75.0, fringe_rate=0.50,
    )
    res = compute_labor([line], "B")
    assert res.overtime == 7_500.0
    assert res.fringe == 3_750.0          # 50% of the OT base only, not of $12,500
    assert res.total == 11_250.0


def test_overtime_rate_defaults_to_time_and_a_half():
    line = LaborLine(
        employee_class=EmployeeClass.BUDGETED, straight_time_hours=0,
        overtime_hours=10, straight_rate=40.0, overtime_rate=0.0,
    )
    assert compute_labor([line], "B").overtime == 600.0


def test_employee_count_multiplies_hours():
    line = LaborLine(
        employee_class=EmployeeClass.TEMPORARY, employee_count=5,
        straight_time_hours=10, straight_rate=20.0,
    )
    assert compute_labor([line], "B").straight_time_eligible == 1_000.0


# -- equipment -----------------------------------------------------------------


def test_standby_hours_are_excluded_from_the_total():
    line = EquipmentLine(hours=10, fema_rate=100.0, standby_hours=4)
    res = compute_equipment([line], uses_adopted_rates=False)
    assert res.total == 1_000.0            # standby is not added
    assert res.standby_excluded == 400.0


def test_fema_pays_the_lesser_of_adopted_and_schedule_rate():
    line = EquipmentLine(hours=10, fema_rate=100.0, adopted_rate=80.0)
    res = compute_equipment([line], uses_adopted_rates=True)
    assert res.total == 800.0
    assert res.rate_reduction == 200.0

    higher = EquipmentLine(hours=10, fema_rate=100.0, adopted_rate=120.0)
    assert compute_equipment([higher], uses_adopted_rates=True).total == 1_000.0


def test_adopted_rate_ignored_when_applicant_has_not_adopted_rates():
    line = EquipmentLine(hours=10, fema_rate=100.0, adopted_rate=80.0)
    assert compute_equipment([line], uses_adopted_rates=False).total == 1_000.0


def test_equipment_rate_schedule_loads():
    rates = load_rates()
    assert len(rates) > 400
    assert all(r.rate > 0 for r in rates)
    assert search("dump truck") or search("truck dump")


def test_equipment_labels_carry_no_replacement_characters():
    """The published schedule contains U+FFFD where upstream lost a glyph. Those
    render as boxes in the picker, so the loader normalizes them away."""
    for r in load_rates():
        assert "�" not in r.label, r.label
        assert "�" not in r.search_text, r.cost_code


def test_equipment_versus_supply_test():
    # Below the applicant's own capitalization level -> supply.
    is_eq, why = is_equipment_not_supply(4_000, 5, capitalization_level=5_000)
    assert not is_eq and "SUPPLY" in why

    # At or above the lesser threshold, useful life over a year -> equipment.
    is_eq, why = is_equipment_not_supply(12_000, 5, capitalization_level=15_000)
    assert is_eq and "EQUIPMENT" in why

    # Useful life of one year or less is a supply regardless of cost.
    is_eq, _ = is_equipment_not_supply(50_000, 1, capitalization_level=5_000)
    assert not is_eq


# -- thresholds and classification ---------------------------------------------


def test_small_project_minimum_blocks_a_tiny_project():
    s = make_scenario()
    site = a_site(category="A", approx_cost=3_000)
    s.sites = [site]
    p = Project(title="Tiny", category="A", site_ids=[site.id],
                costs=[SimpleCostLine(cost_type=CostType.MATERIALS,
                                      quantity=1, unit_cost=3_000)])
    s.projects = [p]
    cls = classify(p, s)
    assert cls.size == "Below minimum"
    assert "4,100" in cls.notes[0]


def test_large_project_threshold_is_exclusive():
    s = make_scenario()
    site = a_site(category="C")
    s.sites = [site]
    threshold = s.rules.thresholds.large_project_threshold

    at = Project(title="At", category="C", site_ids=[site.id],
                 costs=[SimpleCostLine(cost_type=CostType.CONTRACT,
                                       quantity=1, unit_cost=threshold)])
    over = Project(title="Over", category="C", site_ids=[site.id],
                   costs=[SimpleCostLine(cost_type=CostType.CONTRACT,
                                         quantity=1, unit_cost=threshold + 1)])
    s.projects = [at, over]
    assert classify(at, s).size == "Small"        # "must be GREATER than"
    assert classify(over, s).size == "Large"


def test_large_project_carries_retainage_and_actual_cost_basis():
    s = make_scenario()
    site = a_site(category="C")
    s.sites = [site]
    p = Project(title="Big", category="C", site_ids=[site.id],
                costs=[SimpleCostLine(cost_type=CostType.CONTRACT,
                                      quantity=1, unit_cost=2_000_000)])
    s.projects = [p]
    cs = summarize_project(p, s)
    cls = classify(p, s)
    assert cs.is_large_project
    assert cs.retainage_per_payment == round(cs.federal_share * 0.10, 2)
    assert "ACTUAL" in cls.payment_basis.upper()
    assert not cls.simplified_procedures


def test_spa_required_for_emergency_work_and_cat_i():
    rules = RuleSet()
    assert rules.requires_spa("A") and rules.requires_spa("B") and rules.requires_spa("I")
    assert not rules.requires_spa("C")


# -- cost share, insurance, donated resources ----------------------------------


def test_cost_share_is_seventy_five_twenty_five():
    fed, non_fed = RuleSet().cost_share.split(100_000)
    assert (fed, non_fed) == (75_000.0, 25_000.0)


def test_declaration_can_override_the_federal_share():
    fed, non_fed = RuleSet().with_cost_share(0.90).cost_share.split(100_000)
    assert (fed, non_fed) == (90_000.0, 10_000.0)


def test_insurance_reduces_eligible_cost_before_the_share_is_computed():
    s = make_scenario()
    site = a_site(category="C", insured=True,
                  insurance_proceeds=40_000, anticipated_insurance=20_000)
    s.sites = [site]
    p = Project(title="Insured", category="C", site_ids=[site.id],
                costs=[SimpleCostLine(cost_type=CostType.CONTRACT,
                                      quantity=1, unit_cost=200_000)])
    s.projects = [p]
    cs = summarize_project(p, s)
    assert cs.gross_eligible == 200_000.0
    assert cs.insurance_offset == 60_000.0      # actual AND anticipated
    assert cs.net_eligible == 140_000.0
    assert cs.federal_share == 105_000.0
    assert cs.non_federal_share == 35_000.0


def test_donated_resources_offset_only_the_applicant_share():
    s = make_scenario()
    site = a_site(category="B")
    s.sites = [site]
    p = Project(
        title="Donated", category="B", site_ids=[site.id],
        costs=[SimpleCostLine(cost_type=CostType.MATERIALS, quantity=1, unit_cost=100_000)],
        donated=[DonatedResourceLine(hours_or_quantity=100, valuation_rate=100)],
    )
    s.projects = [p]
    cs = summarize_project(p, s)
    assert cs.federal_share == 75_000.0
    assert cs.non_federal_share == 25_000.0
    assert cs.donated_value == 10_000.0
    assert cs.donated_credit_applied == 10_000.0
    assert cs.applicant_out_of_pocket == 15_000.0


def test_donated_credit_is_capped_at_the_applicant_share():
    """Donated value never converts into federal dollars."""
    s = make_scenario()
    site = a_site(category="B")
    s.sites = [site]
    p = Project(
        title="Over-donated", category="B", site_ids=[site.id],
        costs=[SimpleCostLine(cost_type=CostType.MATERIALS, quantity=1, unit_cost=100_000)],
        donated=[DonatedResourceLine(hours_or_quantity=1_000, valuation_rate=100)],
    )
    s.projects = [p]
    cs = summarize_project(p, s)
    assert cs.donated_value == 100_000.0
    assert cs.donated_credit_applied == 25_000.0
    assert cs.donated_credit_unused == 75_000.0
    assert cs.applicant_out_of_pocket == 0.0
    assert cs.federal_share == 75_000.0          # unchanged


# -- Section 406 mitigation ----------------------------------------------------


def test_mitigation_under_fifteen_percent_is_automatically_approvable():
    s = make_scenario()
    site = a_site(category="D")
    s.sites = [site]
    p = Project(
        title="Levee", category="D", site_ids=[site.id],
        costs=[SimpleCostLine(cost_type=CostType.CONTRACT, quantity=1, unit_cost=100_000)],
        mitigation=[MitigationProposal(description="Riprap toe", proposed_cost=14_000)],
    )
    s.projects = [p]
    assert summarize_project(p, s).mitigation == 14_000.0


def test_mitigation_over_fifteen_percent_needs_the_list_or_a_bca():
    s = make_scenario()
    site = a_site(category="D")
    s.sites = [site]
    base = [SimpleCostLine(cost_type=CostType.CONTRACT, quantity=1, unit_cost=100_000)]

    # Over 15%, not on the list, no BCA -> not counted.
    bare = Project(title="Bare", category="D", site_ids=[site.id], costs=list(base),
                   mitigation=[MitigationProposal(description="Armoring",
                                                  proposed_cost=40_000)])
    # Over 15% but on the PAPPG list and within 100% -> approvable.
    listed = Project(title="Listed", category="D", site_ids=[site.id], costs=list(base),
                     mitigation=[MitigationProposal(description="Armoring",
                                                    proposed_cost=40_000,
                                                    on_pappg_list=True)])
    # Over 100% with a favourable BCA -> approvable.
    bca = Project(title="BCA", category="D", site_ids=[site.id], costs=list(base),
                  mitigation=[MitigationProposal(description="Setback levee",
                                                 proposed_cost=150_000,
                                                 bca_performed=True,
                                                 bca_benefits=300_000)])
    s.projects = [bare, listed, bca]
    assert summarize_project(bare, s).mitigation == 0.0
    assert summarize_project(listed, s).mitigation == 40_000.0
    assert summarize_project(bca, s).mitigation == 150_000.0
    assert bca.mitigation[0].bcr == 2.0


def test_mitigation_is_not_available_on_emergency_work():
    s = make_scenario()
    site = a_site(category="B")
    s.sites = [site]
    p = Project(
        title="EPM", category="B", site_ids=[site.id],
        costs=[SimpleCostLine(cost_type=CostType.MATERIALS, quantity=1, unit_cost=100_000)],
        mitigation=[MitigationProposal(description="Permanent floodwall",
                                       proposed_cost=5_000)],
    )
    s.projects = [p]
    assert summarize_project(p, s).mitigation == 0.0
    findings = review(s).findings
    assert any(f.test == "Mitigation" for f in findings)


# -- management costs ----------------------------------------------------------


def test_management_costs_are_capped_at_five_percent_of_obligated():
    s = make_scenario()
    work_site = a_site(category="A")
    z_site = a_site(category="Z", name="Grant administration")
    s.sites = [work_site, z_site]
    work = Project(title="Debris", category="A", site_ids=[work_site.id],
                   costs=[SimpleCostLine(cost_type=CostType.CONTRACT,
                                         quantity=1, unit_cost=1_000_000)])
    mgmt = Project(title="Mgmt", category="Z", site_ids=[z_site.id],
                   costs=[SimpleCostLine(cost_type=CostType.OTHER,
                                         quantity=1, unit_cost=80_000)])
    s.projects = [work, mgmt]
    t = summarize_scenario(s)
    assert t.management_cost_cap == 50_000.0         # 5% of the $1M obligated
    assert t.management_cost_claimed == 80_000.0
    assert t.by_category["Z"] == 50_000.0            # the excess is dropped
    assert t.net_eligible == 1_050_000.0
    assert any(f.severity == "error" and "management costs" in f.message.lower()
               for f in review(s).findings)


# -- formulation ---------------------------------------------------------------


def test_auto_group_never_mixes_categories():
    s = make_scenario()
    s.sites = [
        a_site(category="A", name="Debris 1", approx_cost=10_000, percent_complete=1.0),
        a_site(category="A", name="Debris 2", approx_cost=10_000, percent_complete=1.0),
        a_site(category="B", name="EPM 1", approx_cost=10_000, percent_complete=1.0),
    ]
    proposed = auto_group(s)
    assert len(proposed) == 2
    assert {p.category for p in proposed} == {"A", "B"}
    assert len(next(p for p in proposed if p.category == "A").site_ids) == 2


def test_auto_group_separates_completed_from_incomplete_work():
    s = make_scenario()
    s.sites = [
        a_site(category="A", name="Done", percent_complete=1.0),
        a_site(category="A", name="Pending", percent_complete=0.0),
    ]
    assert len(auto_group(s)) == 2


def test_cat_i_and_cat_z_group_into_a_single_project_each():
    s = make_scenario()
    s.sites = [
        a_site(category="I", name="Inspections north", percent_complete=1.0),
        a_site(category="I", name="Inspections south", percent_complete=0.0),
        a_site(category="Z", name="Admin Q1", percent_complete=1.0),
        a_site(category="Z", name="Admin Q2", percent_complete=0.0),
    ]
    proposed = auto_group(s)
    assert len([p for p in proposed if p.category == "I"]) == 1
    assert len([p for p in proposed if p.category == "Z"]) == 1


def test_review_grouping_flags_mixed_categories_and_duplicate_cat_i():
    s = make_scenario()
    s1 = a_site(category="A", name="A site", approx_cost=50_000)
    s2 = a_site(category="B", name="B site", approx_cost=50_000)
    s.sites = [s1, s2]
    s.projects = [Project(title="Mixed", category="A", site_ids=[s1.id, s2.id])]
    assert any("mixes categories" in i.message for i in review_grouping(s))

    s.projects = [
        Project(title="I-1", category="I", site_ids=[s1.id]),
        Project(title="I-2", category="I", site_ids=[s2.id]),
    ]
    assert any("single project" in i.message for i in review_grouping(s))


# -- deadlines -----------------------------------------------------------------


def test_deadlines_resolve_from_the_declaration_date():
    rules = RuleSet()
    decl, rsm = date(2026, 4, 7), date(2026, 6, 24)
    d = rules.deadlines.resolve(decl, rsm)
    assert d["emergency_work"] == date(2026, 10, 7)      # 6 months
    assert d["permanent_work"] == date(2027, 10, 7)      # 18 months
    assert d["code_enforcement"] == date(2026, 10, 4)    # 180 days
    assert d["impact_list"] == date(2026, 8, 23)         # 60 days from RSM


def test_month_arithmetic_clamps_to_the_end_of_short_months():
    assert _add_months(date(2026, 8, 31), 6) == date(2027, 2, 28)
    assert _add_months(date(2026, 12, 31), 2) == date(2027, 2, 28)


def test_cat_i_deadline_is_not_extendable():
    rules = RuleSet()
    assert "code_enforcement" not in rules.deadlines.extendable
    assert "emergency_work" in rules.deadlines.extendable


def test_category_deadline_routing():
    rules, decl = RuleSet(), date(2026, 4, 7)
    assert rules.deadlines.deadline_for_category("A", decl) == date(2026, 10, 7)
    assert rules.deadlines.deadline_for_category("G", decl) == date(2027, 10, 7)
    assert rules.deadlines.deadline_for_category("I", decl) == date(2026, 10, 4)
    assert rules.deadlines.deadline_for_category("Z", decl) is None


# -- procurement ---------------------------------------------------------------


def test_procurement_method_by_contract_value():
    rules = RuleSet()
    assert "Micro-purchase" in rules.procurement_method(14_999)
    assert "simplified acquisition" in rules.procurement_method(15_000)
    assert "Sealed bid" in rules.procurement_method(350_000)


def test_cost_plus_percentage_of_cost_is_an_error():
    s = make_scenario()
    site = a_site(category="D")
    s.sites = [site]
    s.projects = [Project(
        title="CPPC", category="D", site_ids=[site.id],
        costs=[SimpleCostLine(cost_type=CostType.CONTRACT, description="Repair",
                              quantity=1, unit_cost=500_000, competed=True,
                              sam_debarment_checked=True,
                              cost_plus_percentage_of_cost=True)],
    )]
    findings = review(s).findings
    assert any(f.severity == "error" and "cost-plus-percentage-of-cost" in f.message.lower()
               for f in findings)


def test_uncompeted_contract_over_micro_purchase_is_an_error():
    s = make_scenario()
    site = a_site(category="A")
    s.sites = [site]
    s.projects = [Project(
        title="Uncompeted", category="A", site_ids=[site.id],
        costs=[SimpleCostLine(cost_type=CostType.CONTRACT, description="Hauling",
                              quantity=1, unit_cost=200_000, competed=False,
                              sam_debarment_checked=True)],
    )]
    assert any(f.severity == "error" and "not documented as competed" in f.message
               for f in review(s).findings)


def test_missing_sam_debarment_check_is_an_error():
    s = make_scenario()
    site = a_site(category="A")
    s.sites = [site]
    s.projects = [Project(
        title="No SAM", category="A", site_ids=[site.id],
        costs=[SimpleCostLine(cost_type=CostType.CONTRACT, description="Hauling",
                              quantity=1, unit_cost=5_000, competed=True,
                              sam_debarment_checked=False)],
    )]
    assert any(f.severity == "error" and "debarment" in f.message.lower()
               for f in review(s).findings)


# -- four-part eligibility test ------------------------------------------------


@pytest.mark.parametrize("attr,test_name", [
    ("in_use_at_time_of_disaster", "Facility"),
    ("applicant_legal_responsibility", "Facility"),
    ("within_declared_area", "Facility"),
])
def test_facility_test_failures_are_errors(attr, test_name):
    s = make_scenario()
    site = a_site(category="C")
    setattr(site, attr, False)
    s.sites = [site]
    findings = review(s).findings
    assert any(f.severity == "error" and f.test == test_name for f in findings)


def test_other_federal_agency_authority_blocks_the_work():
    s = make_scenario()
    s.sites = [a_site(category="C", other_federal_agency_authority=True)]
    assert any(f.severity == "error" and "another federal agency" in f.message
               for f in review(s).findings)


def test_missing_applicant_policies_are_errors():
    s = make_scenario()
    s.applicant.has_pay_policy = False
    s.applicant.has_procurement_policy = False
    s.applicant.has_insurance_policy = False
    errors = [f for f in review(s).errors if f.test == "Applicant"]
    assert len(errors) == 3


def test_nfip_suspension_blocks_cat_i():
    s = make_scenario()
    s.applicant.nfip_participating = False
    site = a_site(category="I")
    s.sites = [site]
    s.projects = [Project(title="Code enforcement", category="I", site_ids=[site.id])]
    assert any("National Flood Insurance Program" in f.message for f in review(s).errors)


# -- EHP -----------------------------------------------------------------------


def test_work_started_with_unresolved_ehp_trigger_is_an_error():
    s = make_scenario()
    s.sites = [a_site(category="D", percent_complete=0.25,
                      ehp_flags={"in_or_near_waterway": True})]
    findings = review(s).findings
    assert any(f.severity == "error" and f.test == "EHP" for f in findings)


def test_ehp_trigger_without_work_started_is_only_a_warning():
    s = make_scenario()
    s.sites = [a_site(category="D", percent_complete=0.0,
                      ehp_flags={"in_or_near_waterway": True})]
    ehp = [f for f in review(s).findings if f.test == "EHP"]
    assert ehp and all(f.severity == "warning" for f in ehp)


def test_structure_age_triggers_historic_review():
    s = make_scenario()
    s.sites = [a_site(category="E", structure_age_years=52)]
    assert any(f.test == "EHP" and "NHPA" in f.message for f in review(s).findings)


# -- data quality --------------------------------------------------------------


def test_positive_longitude_in_washington_is_flagged():
    s = make_scenario()
    s.sites = [a_site(category="C", state="WA", longitude=122.19)]
    assert any("longitude" in f.message.lower() for f in review(s).findings)


# -- serialization -------------------------------------------------------------


def test_scenario_round_trips_through_json():
    s = make_scenario()
    site = a_site(category="B", work_start_date=date(2026, 1, 2),
                  ehp_flags={"floodplain": True})
    s.sites = [site]
    s.projects = [Project(
        title="Round trip", category="B", site_ids=[site.id],
        labor=[LaborLine(employee_class=EmployeeClass.TEMPORARY,
                         straight_time_hours=10, straight_rate=25.0)],
        equipment=[EquipmentLine(hours=5, fema_rate=42.11)],
        costs=[SimpleCostLine(cost_type=CostType.CONTRACT, quantity=1, unit_cost=9_000)],
        donated=[DonatedResourceLine(hours_or_quantity=10, valuation_rate=30)],
        mitigation=[MitigationProposal(description="m", proposed_cost=100)],
    )]
    back = scenario_from_dict(scenario_to_dict(s))

    assert back.applicant.name == s.applicant.name
    assert back.disaster.declaration_date == s.disaster.declaration_date
    assert back.sites[0].work_start_date == date(2026, 1, 2)
    assert back.sites[0].ehp_flags == {"floodplain": True}
    assert back.projects[0].labor[0].employee_class is EmployeeClass.TEMPORARY
    assert back.projects[0].costs[0].cost_type is CostType.CONTRACT
    assert summarize_scenario(back).net_eligible == summarize_scenario(s).net_eligible


def test_rules_overrides_survive_a_round_trip():
    s = make_scenario()
    s.rules = RuleSet().with_cost_share(0.90)
    back = scenario_from_dict(scenario_to_dict(s))
    assert back.rules.cost_share.federal == 0.90
    assert back.rules.cost_share.non_federal == 0.10


# -- bundled scenario ----------------------------------------------------------


# -- Section 311 mandatory insurance reduction ---------------------------------


def _flooded_building(**kw) -> Site:
    base = dict(
        category="E", name="City Hall", damage_description="x" * 60,
        primary_cause="Flood", state="WA",
        is_insurable_building=True, in_special_flood_hazard_area=True,
        sfha_designated_years=10, building_value=2_000_000, contents_value=300_000,
        flood_insurance_in_force=0.0,
    )
    base.update(kw)
    return Site(**base)


def _with_site(site: Site, cost: float = 400_000) -> Scenario:
    s = make_scenario()
    s.sites = [site]
    s.projects = [Project(
        title="Repair", category=site.category, site_ids=[site.id],
        costs=[SimpleCostLine(cost_type=CostType.CONTRACT, description="Repair",
                              quantity=1, unit_cost=cost, competed=True,
                              sam_debarment_checked=True)],
    )]
    return s


def test_section_311_reduction_is_capped_by_nfip_policy_limits():
    """The reduction is the max STANDARD POLICY proceeds, not the building's value.
    A $2M building yields $500k, not $2M."""
    s = _with_site(_flooded_building(), cost=1_500_000)
    cs = summarize_project(s.projects[0], s)
    assert cs.section_311_reduction == 800_000.0      # 500k building + 300k contents
    assert cs.net_eligible == 700_000.0
    assert any(f.severity == "error" and "Section 311" in f.message
               for f in review(s).findings)


def test_section_311_can_exceed_the_damage_and_zero_the_project():
    """The reduction is not proportional to damage. This is the case that surprises
    applicants."""
    s = _with_site(_flooded_building(), cost=90_000)
    cs = summarize_project(s.projects[0], s)
    assert cs.section_311_reduction == 800_000.0
    assert cs.net_eligible == 0.0
    assert cs.federal_share == 0.0
    cls = classify(s.projects[0], s)
    assert cls.size == "Below minimum"
    assert any("Section 311" in n for n in cls.notes)


def test_section_311_does_not_apply_when_flood_insurance_is_carried():
    s = _with_site(_flooded_building(flood_insurance_in_force=1_000_000))
    assert summarize_project(s.projects[0], s).section_311_reduction == 0.0


def test_section_311_applies_to_the_shortfall_when_underinsured():
    s = _with_site(_flooded_building(flood_insurance_in_force=300_000))
    assert summarize_project(s.projects[0], s).section_311_reduction == 500_000.0


@pytest.mark.parametrize("field,value", [
    ("is_insurable_building", False),      # not a building
    ("in_special_flood_hazard_area", False),
    ("sfha_designated_years", 0.5),        # designated under a year
    ("primary_cause", "Winter Storm"),     # not flood damage
])
def test_section_311_preconditions_each_defeat_the_reduction(field, value):
    s = _with_site(_flooded_building(**{field: value}))
    assert summarize_project(s.projects[0], s).section_311_reduction == 0.0


def test_section_311_exempts_pnp_in_nonparticipating_community():
    s = _with_site(_flooded_building())
    s.applicant.entity_type = "Private Non-Profit — critical services"
    s.applicant.nfip_participating = False
    cs = summarize_project(s.projects[0], s)
    assert cs.section_311_reduction == 0.0
    assert any("do not participate" in n for n in cs.section_311_notes)


def test_insurance_proceeds_and_section_311_both_reduce_before_cost_share():
    s = _with_site(
        _flooded_building(insured=True, insurance_proceeds=50_000), cost=1_500_000)
    cs = summarize_project(s.projects[0], s)
    assert cs.gross_eligible == 1_500_000.0
    assert cs.insurance_offset == 50_000.0
    assert cs.section_311_reduction == 800_000.0
    assert cs.net_eligible == 650_000.0
    assert cs.federal_share == 487_500.0


# -- Section 428 alternative procedures ----------------------------------------


def test_section_428_debris_sliding_scale_by_completion_speed():
    s = make_scenario()
    s.applicant.section_428_debris_straight_time = True
    site = a_site(category="A")
    s.sites = [site]
    end = s.disaster.incident_end       # 2025-12-19

    cases = {
        None: 0.75,                                  # no date recorded
        end + timedelta(days=20): 0.85,              # inside 30 days
        end + timedelta(days=30): 0.85,              # boundary
        end + timedelta(days=60): 0.80,              # 31-90
        end + timedelta(days=150): 0.75,             # 91-180
        end + timedelta(days=400): 0.75,             # past the scale
    }
    for completion, expected in cases.items():
        p = Project(title="Debris", category="A", site_ids=[site.id],
                    debris_completion_date=completion,
                    costs=[SimpleCostLine(cost_type=CostType.MATERIALS,
                                          quantity=1, unit_cost=100_000)])
        s.projects = [p]
        cs = summarize_project(p, s)
        assert cs.federal_share_rate == expected, completion
        assert cs.federal_share == round(100_000 * expected, 2)


def test_sliding_scale_requires_the_428_election():
    s = make_scenario()
    site = a_site(category="A")
    s.sites = [site]
    p = Project(title="Debris", category="A", site_ids=[site.id],
                debris_completion_date=s.disaster.incident_end + timedelta(days=10),
                costs=[SimpleCostLine(cost_type=CostType.MATERIALS,
                                      quantity=1, unit_cost=100_000)])
    s.projects = [p]
    assert summarize_project(p, s).federal_share_rate == 0.75


def test_sliding_scale_does_not_apply_to_non_debris_categories():
    s = make_scenario()
    s.applicant.section_428_debris_straight_time = True
    site = a_site(category="B")
    s.sites = [site]
    p = Project(title="EPM", category="B", site_ids=[site.id],
                debris_completion_date=s.disaster.incident_end + timedelta(days=5),
                costs=[SimpleCostLine(cost_type=CostType.MATERIALS,
                                      quantity=1, unit_cost=100_000)])
    s.projects = [p]
    assert summarize_project(p, s).federal_share_rate == 0.75


def test_fixed_cost_offer_caps_the_award_only_when_accepted():
    s = make_scenario()
    site = a_site(category="C")
    s.sites = [site]
    base = [SimpleCostLine(cost_type=CostType.CONTRACT, quantity=1, unit_cost=900_000)]

    offered = Project(title="Offered", category="C", site_ids=[site.id],
                      costs=list(base), fixed_cost_offer=800_000)
    accepted = Project(title="Accepted", category="C", site_ids=[site.id],
                       costs=list(base), fixed_cost_offer=800_000,
                       fixed_cost_offer_accepted=True)
    s.projects = [offered, accepted]

    assert summarize_project(offered, s).net_eligible == 900_000.0
    acc = summarize_project(accepted, s)
    assert acc.net_eligible == 800_000.0
    assert acc.fixed_cost_variance == -100_000.0


# -- donated resources: emergency work pools, permanent work does not ----------


def test_emergency_donated_resources_pool_across_cat_a_and_b():
    """Value donated to one flood-fight project can absorb the applicant share on
    another. Capping per project would strand it."""
    s = make_scenario()
    sa, sb = a_site(category="A", name="Debris"), a_site(category="B", name="EPM")
    s.sites = [sa, sb]
    # All the donation sits on the Cat-A project; all the cost sits on Cat-B.
    pa = Project(
        title="Debris", category="A", site_ids=[sa.id],
        costs=[SimpleCostLine(cost_type=CostType.MATERIALS, quantity=1, unit_cost=20_000)],
        donated=[DonatedResourceLine(hours_or_quantity=1, valuation_rate=30_000)],
    )
    pb = Project(
        title="EPM", category="B", site_ids=[sb.id],
        costs=[SimpleCostLine(cost_type=CostType.MATERIALS, quantity=1, unit_cost=400_000)],
    )
    s.projects = [pa, pb]

    summaries = summarize_all(s)
    # Combined non-federal share is 25% of $420,000 = $105,000, so all $30,000
    # of donated value is creditable even though only $5,000 sits on its own project.
    assert summaries[pa.id].donated_scope == "emergency work portfolio"
    total_credit = sum(c.donated_credit_applied for c in summaries.values())
    assert total_credit == 30_000.0
    assert summarize_scenario(s).donated_credit == 30_000.0
    assert summarize_scenario(s).donated_credit_unused == 0.0


def test_emergency_donated_credit_is_still_capped_at_the_combined_share():
    s = make_scenario()
    sa = a_site(category="A")
    s.sites = [sa]
    p = Project(
        title="Debris", category="A", site_ids=[sa.id],
        costs=[SimpleCostLine(cost_type=CostType.MATERIALS, quantity=1, unit_cost=100_000)],
        donated=[DonatedResourceLine(hours_or_quantity=1, valuation_rate=90_000)],
    )
    s.projects = [p]
    t = summarize_scenario(s)
    assert t.donated_credit == 25_000.0          # the whole non-federal share
    assert t.donated_credit_unused == 65_000.0
    assert t.federal_share == 75_000.0           # unchanged
    assert t.applicant_out_of_pocket == 0.0


def test_permanent_work_donated_resources_stay_per_project():
    s = make_scenario()
    s1, s2 = a_site(category="C", name="Road"), a_site(category="G", name="Park")
    s.sites = [s1, s2]
    p1 = Project(
        title="Road", category="C", site_ids=[s1.id],
        costs=[SimpleCostLine(cost_type=CostType.MATERIALS, quantity=1, unit_cost=20_000)],
        donated=[DonatedResourceLine(hours_or_quantity=1, valuation_rate=30_000)],
    )
    p2 = Project(
        title="Park", category="G", site_ids=[s2.id],
        costs=[SimpleCostLine(cost_type=CostType.MATERIALS, quantity=1, unit_cost=400_000)],
    )
    s.projects = [p1, p2]
    summaries = summarize_all(s)
    assert summaries[p1.id].donated_scope == "project"
    # Capped at this project's own $5,000 share; the rest is stranded.
    assert summaries[p1.id].donated_credit_applied == 5_000.0
    assert summaries[p1.id].donated_credit_unused == 25_000.0


# -- codes and standards --------------------------------------------------------


def test_codes_and_standards_requires_all_five_criteria():
    s = make_scenario()
    site = a_site(category="C")
    s.sites = [site]
    good = CodeStandard(
        description="Current design standard", upgrade_cost=50_000,
        applies_to_repair_type=True, appropriate_to_predisaster_use=True,
        formally_adopted_before=True, applied_uniformly=True, actually_enforced=True,
    )
    bad = CodeStandard(
        description="Adopted after the declaration", upgrade_cost=200_000,
        applies_to_repair_type=True, appropriate_to_predisaster_use=True,
        formally_adopted_before=False, applied_uniformly=False, actually_enforced=False,
    )
    p = Project(title="Road", category="C", site_ids=[site.id],
                costs=[SimpleCostLine(cost_type=CostType.CONTRACT,
                                      quantity=1, unit_cost=100_000,
                                      competed=True, sam_debarment_checked=True)],
                codes_and_standards=[good, bad])
    s.projects = [p]
    cs = summarize_project(p, s)
    assert cs.codes_and_standards == 50_000.0
    assert cs.codes_and_standards_excluded == 200_000.0
    assert cs.gross_eligible == 150_000.0
    assert any(f.test == "Codes and Standards" and f.severity == "error"
               for f in review(s).findings)


# -- management costs, RPA, appeals ---------------------------------------------


def test_recipient_and_subrecipient_management_caps():
    rules = RuleSet()
    assert rules.management.applicant_cap_rate == 0.05
    assert rules.management.recipient_cap_rate == 0.07
    assert rules.management.combined_cap_rate == 0.12

    s = make_scenario()
    site = a_site(category="A")
    s.sites = [site]
    s.projects = [Project(title="Debris", category="A", site_ids=[site.id],
                          costs=[SimpleCostLine(cost_type=CostType.CONTRACT,
                                                quantity=1, unit_cost=1_000_000,
                                                competed=True,
                                                sam_debarment_checked=True)])]
    t = summarize_scenario(s)
    assert t.management_cost_cap == 50_000.0
    assert t.recipient_management_cost_cap == 70_000.0


def test_rpa_deadline_is_thirty_days_from_designation():
    s = make_scenario()
    s.disaster.designation_date = date(2026, 4, 7)
    resolved = s.rules.deadlines.resolve(
        s.disaster.declaration_date, s.disaster.rsm_date, s.disaster.designation_date)
    assert resolved["rpa"] == date(2026, 5, 7)

    # Not filed at all -> flagged.
    assert any("Request for Public Assistance" in f.message
               for f in review(s, today=date(2026, 5, 1)).findings)

    # Filed late -> error.
    s.disaster.rpa_submitted_date = date(2026, 6, 1)
    assert any(f.severity == "error" and "after the" in f.message
               for f in review(s).findings if "Public Assistance" in f.message)

    # Filed on time -> no error.
    s.disaster.rpa_submitted_date = date(2026, 4, 20)
    assert not [f for f in review(s).errors if "Request for Public Assistance" in f.message]


def test_arbitration_threshold_drops_for_small_impoverished_communities():
    s = make_scenario()
    assert summarize_scenario(s).arbitration_threshold == 500_000.0
    s.applicant.small_impoverished_community = True
    assert summarize_scenario(s).arbitration_threshold == 100_000.0


def test_noncritical_pnp_must_apply_to_sba_before_permanent_work():
    s = make_scenario()
    s.applicant.entity_type = (
        "Private Non-Profit — non-critical essential social services")
    site = a_site(category="E")
    s.sites = [site]
    s.projects = [Project(title="Building", category="E", site_ids=[site.id])]
    assert any("Small Business Administration" in f.message for f in review(s).errors)

    s.applicant.sba_application_filed = True
    assert not [f for f in review(s).errors if "Small Business Administration" in f.message]
    assert any("decline" in f.message.lower() for f in review(s).warnings)


def test_blank_scenario_is_inert_and_unscorable():
    """The app opens blank. Nothing may crash, and an empty package must NOT score
    well -- every dimension with nothing to evaluate would otherwise return full
    credit, and zero contracts would read as a perfect procurement record."""
    from pa.export import full_package, impact_list_csv, reimbursement_request
    from pa.formulation import auto_group, review_grouping
    from pa.scenario import blank_scenario
    from pa.scoring import score

    s = blank_scenario()
    t = summarize_scenario(s)
    assert t.net_eligible == 0.0 and t.federal_share == 0.0
    assert t.management_cost_cap == 0.0
    assert auto_group(s) == [] and review_grouping(s) == []

    card = score(s)
    assert card.scorable is False
    assert card.dimensions == []

    # Exports must still render rather than raise.
    for fn in (full_package, reimbursement_request, impact_list_csv):
        assert isinstance(fn(s), str)

    # A blank scenario still fails the applicant test -- that is correct, not a crash.
    assert any(f.test == "Applicant" for f in review(s).errors)


def test_scoring_becomes_available_once_a_project_exists():
    from pa.scoring import score

    s = make_scenario()
    site = a_site(category="A")
    s.sites = [site]
    assert score(s).scorable is False
    s.projects = [Project(title="Debris", category="A", site_ids=[site.id],
                          costs=[SimpleCostLine(cost_type=CostType.CONTRACT,
                                                quantity=1, unit_cost=50_000,
                                                competed=True,
                                                sam_debarment_checked=True)])]
    card = score(s)
    assert card.scorable is True and card.dimensions


def test_documentation_attestations_persist_and_count():
    """Records the tool cannot hold -- monitoring logs, disposal permits, agency
    correspondence -- are attested by the applicant. Losing them on save would make
    the exercise uncompletable."""
    from pa.export import documentation_checklist, inferred_documentation_items

    s = make_scenario()
    site = a_site(category="A")
    s.sites = [site]
    p = Project(title="Debris", category="A", site_ids=[site.id])
    s.projects = [p]

    inferred = inferred_documentation_items()
    attestable = [i for i, _ in documentation_checklist(p, s) if i not in inferred]
    assert attestable, "there should be items only the applicant can confirm"

    before = sum(1 for _, ok in documentation_checklist(p, s) if ok)
    p.documentation_confirmed = attestable[:2]
    after = sum(1 for _, ok in documentation_checklist(p, s) if ok)
    assert after == before + 2

    back = scenario_from_dict(scenario_to_dict(s))
    assert back.projects[0].documentation_confirmed == attestable[:2]


def test_ehp_consultation_complete_clears_the_blocking_finding():
    """Starting work early cannot be undone, but recording completed consultation is
    how the exposure is actually resolved -- otherwise the finding is a dead end."""
    s = make_scenario()
    site = a_site(category="D", percent_complete=0.25,
                  ehp_flags={"in_or_near_waterway": True})
    s.sites = [site]
    assert any(f.severity == "error" and f.test == "EHP" for f in review(s).findings)

    site.ehp_consultation_complete = True
    site.ehp_resolution_note = "JARPA filed; USFWS concurrence received"
    findings = [f for f in review(s).findings if f.test == "EHP"]
    assert findings and all(f.severity == "info" for f in findings)
    assert "JARPA" in findings[0].message

    back = scenario_from_dict(scenario_to_dict(s))
    assert back.sites[0].ehp_consultation_complete is True


def test_zero_cost_code_standard_is_not_flagged():
    """An upgrade moved out of the grant should stop generating findings."""
    s = make_scenario()
    site = a_site(category="C")
    s.sites = [site]
    s.projects = [Project(
        title="Road", category="C", site_ids=[site.id],
        codes_and_standards=[CodeStandard(
            description="Retrofit adopted after the declaration", upgrade_cost=0.0,
            formally_adopted_before=False)],
    )]
    assert not [f for f in review(s).findings if f.test == "Codes and Standards"]
    assert summarize_project(s.projects[0], s).codes_and_standards_excluded == 0.0


def test_training_scenario_is_completable_to_a_passing_score():
    """The exercise must be finishable. If the rubric caps below passing, students
    cannot tell a good package from an impossible one."""
    from pa.export import documentation_checklist, inferred_documentation_items
    from pa.scenario import SCENARIO_DIR, load_scenario
    from pa.scoring import score

    path = SCENARIO_DIR / "training_cascade_valley.json"
    if not path.exists():
        pytest.skip("training scenario not built")
    s = load_scenario(path)
    assert score(s).percent < 40          # as delivered

    s.applicant.has_insurance_policy = True
    s.applicant.section_428_debris_straight_time = True
    for site in s.sites:
        if site.longitude and site.longitude > 0:
            site.longitude = -site.longitude
        if site.is_insurable_building and site.flood_insurance_in_force == 0:
            site.flood_insurance_in_force = 1_000_000
            site.obtain_and_maintain_acknowledged = True
        site.ehp_consultation_complete = True
    for p in s.projects:
        for c in p.costs:
            if c.cost_type is CostType.CONTRACT:
                c.competed = c.sam_debarment_checked = True
                c.cost_plus_percentage_of_cost = False
        for cs in p.codes_and_standards:
            if not cs.formally_adopted_before:
                cs.upgrade_cost = 0.0
        if not p.scope_of_work.strip():
            p.scope_of_work = "Restore to pre-disaster design and function."
        inferred = inferred_documentation_items()
        p.documentation_confirmed = sorted(
            {i for i, _ in documentation_checklist(p, s) if i not in inferred})

    card = score(s)
    assert not card.review.errors, [f.message for f in card.review.errors]
    assert card.percent >= 80, card.percent


# -- guidance: where am I, what next -------------------------------------------


def test_blank_scenario_is_not_reported_as_failing():
    """An empty form is not a broken package. Showing four blocking findings before
    the user has typed anything teaches them to ignore the finding count."""
    from pa.guidance import is_untouched, next_action, progress
    from pa.scenario import blank_scenario

    s = blank_scenario()
    assert is_untouched(s) is True
    p = progress(s)
    assert p.completed == 0
    assert p.current is not None and p.current.number == 1
    action = next_action(s)
    assert action.severity == "info"
    assert "training scenario" in action.headline.lower()


def test_scenario_stops_being_untouched_once_work_starts():
    from pa.guidance import is_untouched
    from pa.scenario import blank_scenario

    s = blank_scenario()
    s.applicant.name = "Test City"
    assert is_untouched(s) is False


def test_progress_advances_step_by_step():
    from pa.guidance import progress
    from pa.scenario import blank_scenario

    s = blank_scenario()
    assert progress(s).current.number == 1

    s.applicant.name = "Test City"
    s.disaster.declaration_date = date(2026, 4, 7)
    assert progress(s).current.number == 2          # now needs sites

    site = a_site(category="A")
    s.sites = [site]
    assert progress(s).current.number == 3          # now needs grouping

    p = Project(title="Debris", category="A", site_ids=[site.id])
    s.projects = [p]
    assert progress(s).current.number == 4          # now needs costs

    p.costs = [SimpleCostLine(cost_type=CostType.CONTRACT, description="Haul",
                              quantity=1, unit_cost=50_000,
                              competed=True, sam_debarment_checked=True)]
    assert progress(s).current.number == 5          # now needs compliance work


def test_next_action_points_at_the_page_that_fixes_it():
    """The instruction is only useful if it names where to go."""
    from pa.guidance import FINDING_PAGE, next_action
    from pa.scenario import SCENARIO_DIR, load_scenario

    path = SCENARIO_DIR / "training_cascade_valley.json"
    if not path.exists():
        pytest.skip("training scenario not built")

    s = load_scenario(path)
    action = next_action(s)
    assert action.severity == "blocking"
    assert action.page in ("Scenario", "Impact List", "Cost Buildup", "Package")
    assert action.where and action.headline

    # Every finding category must map to a page, or the user gets sent nowhere.
    from pa.validation import review
    for f in review(s).findings:
        assert f.test in FINDING_PAGE, f"no page mapping for finding test {f.test!r}"


def test_next_action_surfaces_unclaimed_money_once_nothing_is_blocking():
    from pa.guidance import next_action
    s = make_scenario()
    # Without an RPA on file the deadline check blocks, which is correct but is not
    # what this test is about.
    s.disaster.rpa_submitted_date = date(2026, 4, 20)
    site = a_site(category="C")
    s.sites = [site]
    s.projects = [Project(
        title="Road", category="C", site_ids=[site.id],
        scope_of_work="Restore to pre-disaster design.",
        costs=[SimpleCostLine(cost_type=CostType.CONTRACT, description="Repair",
                              quantity=1, unit_cost=500_000,
                              competed=True, sam_debarment_checked=True)],
    )]
    action = next_action(s)
    assert action.severity == "opportunity"
    assert "management cost" in action.headline.lower()


def test_every_page_has_a_plain_english_purpose():
    """A newcomer needs to know what a page is FOR before the expert framing lands."""
    import app
    from pa.guidance import PAGE_PURPOSE

    for key in app.PAGES:
        assert key in PAGE_PURPOSE, f"no plain-English purpose for page {key!r}"
        assert len(PAGE_PURPOSE[key]) > 20


def test_navigation_labels_avoid_markdown_list_syntax():
    """'1. Foo' is an ordered-list item in markdown; Streamlit renders it as one and
    swallows the number, silently destroying the sequence cue."""
    import app
    import re

    for key, (_, label) in app.PAGES.items():
        assert not re.match(r"^\d+[.)]\s", label), (
            f"label {label!r} for {key!r} would render as a markdown list")


def test_only_the_fictional_training_scenario_ships():
    """No real jurisdiction's impact list may be committed to the repository."""
    from pa.scenario import SCENARIO_DIR
    shipped = sorted(p.name for p in SCENARIO_DIR.glob("*.json")
                     if not p.name.endswith(".local.json"))
    assert shipped == ["training_cascade_valley.json"], shipped


def test_training_scenario_loads_and_contains_its_seeded_defects():
    from pa.scenario import SCENARIO_DIR, load_scenario
    path = SCENARIO_DIR / "training_cascade_valley.json"
    if not path.exists():
        pytest.skip("training scenario not built")

    s = load_scenario(path)
    r = review(s)
    messages = " ".join(f.message.lower() for f in r.findings)

    assert len(s.sites) == 15 and len(s.projects) == 8
    assert "cost-plus-percentage-of-cost" in messages
    assert "debarment" in messages
    assert "straight-time labor" in messages
    assert any(f.test == "EHP" and f.severity == "error" for f in r.findings)

    t = summarize_scenario(s)
    assert t.large_projects >= 1
    # The federal share is rounded per PROJECT, because that is the unit FEMA
    # obligates. Summing those gives a portfolio figure that can differ from
    # round(total * 0.75) by a cent per project -- that is correct, not drift.
    assert abs(t.federal_share - t.net_eligible * 0.75) < 0.02 * len(s.projects)
    assert t.management_cost_claimed == 0.0      # the Cat-Z omission

    from pa.scoring import score
    assert score(s).percent < 70                 # the package should not pass as-is
