"""Generate the bundled training scenario.

Cascade Valley is invented. Its impact list is structured like a real one and its
dollar magnitudes are realistic for a mid-size city on a winter storm and flood
declaration, but no part of it describes an actual jurisdiction or event.

The scenario is seeded with defects on purpose. Each one maps to a rule the engine
checks, so a student who works the package cleanly will watch the scorecard move:

  * straight-time labor claimed on Cat-B for budgeted employees
  * a $290,000 contract with no competition and no SAM.gov debarment check
  * a cost-plus-percentage-of-cost contract, which is prohibited outright
  * work underway on a levee with unresolved ESA and waterway EHP triggers
  * a 52-year-old community center, over the NHPA screening age
  * that same community center uninsured for flood inside a Special Flood Hazard
    Area, which triggers the Stafford Act Sec. 311 mandatory reduction -- the animal
    shelter is the deliberate contrast case, same exposure but coverage carried
  * the Section 428 debris election left unmade, stranding straight-time debris labour
  * a code-driven seismic upgrade that fails the five-part codes and standards test
  * a donated equipment line with no documented valuation basis
  * a debris site too small to stand as its own project
  * a longitude keyed without its sign
  * no Cat-Z management cost project at all
  * no Section 406 mitigation on any permanent work project
  * the applicant's insurance policy not yet submitted

Usage:
    python tools/build_training_scenario.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pa.models import (                                      # noqa: E402
    Applicant, CodeStandard, CostType, Disaster, DonatedResourceLine,
    EmployeeClass, EquipmentLine, LaborLine, MitigationProposal, Project,
    Scenario, SimpleCostLine, Site,
)
from pa.rules import RuleSet                                 # noqa: E402
from pa.scenario import SCENARIO_DIR, save_scenario          # noqa: E402

OUT = SCENARIO_DIR / "training_cascade_valley.json"

DECL = date(2027, 2, 15)
RSM = date(2027, 4, 20)


def site(**kw) -> Site:
    kw.setdefault("city", "Cascade Valley")
    kw.setdefault("state", "WA")
    return Site(**kw)


def build() -> Scenario:
    s = Scenario(
        title="DR-4988-WA — City of Cascade Valley (training scenario)",
        description=(
            "A mid-size Washington city on a winter storm, flooding, and landslide "
            "declaration. Emergency work is largely complete; permanent work on the "
            "levee, a bridge, a signalized intersection, and the water transmission "
            "corridor is outstanding. The package as delivered contains errors."
        ),
        source_note=(
            "Fictional. Invented jurisdiction, invented sites, invented costs. "
            "Structured to match FEMA's damage inventory template and PAPPG V5 "
            "Amended so the exercise transfers to a real declaration."
        ),
        applicant=Applicant(
            name="City of Cascade Valley",
            fips="061-09915-00",
            entity_type="Local Government",
            county="Cascade",
            state="WA",
            has_pay_policy=True,
            has_procurement_policy=True,
            has_insurance_policy=False,      # DEFECT: not yet submitted
            nfip_participating=True,
            capitalization_level=5_000.0,
            uses_adopted_equipment_rates=False,
            primary_contact_role="Applicant — Office of Emergency Management",
        ),
        disaster=Disaster(
            number="4988-DR",
            name="Severe Winter Storms, Flooding, Landslides, and Mudslides",
            state="WA",
            declaration_date=DECL,
            incident_start=date(2026, 12, 28),
            incident_end=date(2027, 1, 11),
            designation_date=DECL,
            rpa_submitted_date=date(2027, 3, 4),
            exploratory_call_date=date(2027, 3, 25),
            rsm_date=RSM,
            incident_types=["Winter Storm", "Flood", "Severe Storm", "Wind"],
        ),
        rules=RuleSet(),
    )

    # -- Category A: debris removal --------------------------------------------
    a1 = site(
        category="A", name="Citywide Vegetative Debris Removal",
        address="Public rights-of-way, citywide", zip_code="98288",
        latitude=47.8412, longitude=-121.7734,
        damage_description=(
            "Storm winds and saturated soils brought down vegetation across the public "
            "right-of-way. Street crews swept 138 miles of roadway, removed 24 downed "
            "trees and 61 downed limbs, and collected 187 cubic yards of vegetative "
            "debris, of which 94 cubic yards were chipped on site and the balance "
            "hauled to the county transfer station."
        ),
        primary_cause="Winter Storm", approx_cost=88_400, percent_complete=1.0,
        labor_type="FA", prior_pa_grant="N", priority="High",
        work_start_date=date(2026, 12, 29),
    )
    a2 = site(
        category="A", name="River Road Sediment and Debris Removal",
        address="River Road between Mill Street and the county line",
        latitude=47.8266, longitude=-121.8051,
        damage_description=(
            "Floodwaters deposited an estimated 310 cubic yards of silt and mixed "
            "construction debris, including approximately 90 creosote-treated railroad "
            "ties transported from an upstream staging area, across 1.2 miles of River "
            "Road and the adjacent maintained shoulder."
        ),
        primary_cause="Flood", approx_cost=22_150, percent_complete=1.0,
        labor_type="FA/C", prior_pa_grant="N", priority="Medium",
        work_start_date=date(2027, 1, 4),
    )
    # DEFECT: below the $4,100 minimum if formulated alone.
    a3 = site(
        category="A", name="Water Filtration Plant Access Road Clearing",
        address="18400 Cascade Ridge Road", zip_code="98288",
        latitude=47.8901, longitude=-121.6620,
        damage_description=(
            "Downed trees blocked the single access road to the water filtration plant, "
            "restricting access to critical drinking water infrastructure for 31 hours."
        ),
        primary_cause="Winter Storm", approx_cost=3_100, percent_complete=1.0,
        labor_type="FA", prior_pa_grant="N", priority="Urgent",
        work_start_date=date(2026, 12, 28),
    )

    # -- Category B: emergency protective measures ------------------------------
    b1 = site(
        category="B", name="Levee District 3 Emergency Berm and Sandbagging",
        address="Levee District 3, north bank of the Cascade River",
        latitude=47.8515, longitude=-121.7902,
        damage_description=(
            "Rising river stage threatened the wastewater treatment plant and 340 acres "
            "of improved property behind the Levee District 3 embankment. The City "
            "constructed approximately 18,600 linear feet of temporary berm on the "
            "existing levee crest and placed approximately 11,000 sandbags around plant "
            "structures. Berm material and sandbags were removed after the river fell "
            "below flood stage."
        ),
        primary_cause="Flood", approx_cost=412_000, percent_complete=1.0,
        labor_type="FA/C", prior_pa_grant="U", priority="Urgent",
        work_start_date=date(2026, 12, 30),
        in_special_flood_hazard_area=True,
        ehp_flags={"in_or_near_waterway": True, "floodplain": True},
    )
    b2 = site(
        category="B", name="Emergency Operations Center Activation",
        address="900 Cascade Avenue, Suite 200", zip_code="98288",
        latitude=47.8377, longitude=-121.7688,
        damage_description=(
            "The City activated its Emergency Operations Center to Level 2 for 11 "
            "operational periods to coordinate flood fight, evacuation messaging, and "
            "damage assessment. Staff from public works, police, fire, communications, "
            "and administration were assigned to EOC positions."
        ),
        primary_cause="Flood", approx_cost=34_600, percent_complete=1.0,
        labor_type="FA", prior_pa_grant="N", priority="High",
        work_start_date=date(2026, 12, 29),
    )
    b3 = site(
        category="B", name="Lift Station Emergency Generator Operations",
        address="Lift stations 4, 9, 11, and 16",
        latitude=47.8340, longitude=-121.7820,
        damage_description=(
            "Four wastewater lift stations lost commercial power for periods ranging "
            "from 9 to 52 hours. Portable and permanent standby generators were operated "
            "to maintain pumping capacity and prevent sanitary sewer overflow."
        ),
        primary_cause="Winter Storm", approx_cost=6_900, percent_complete=1.0,
        labor_type="FA", prior_pa_grant="N", priority="High",
    )
    b4 = site(
        category="B", name="Animal Shelter Evacuation and Relocation",
        address="1450 Smith Island Road",
        latitude=47.8602, longitude=-121.8110,
        damage_description=(
            "The municipal animal shelter was evacuated ahead of forecast inundation. "
            "Approximately 95 animals were relocated to a partner facility, building "
            "systems were shut down, and medical equipment, sensitive electronics, and "
            "feed stores were moved above the projected flood elevation."
        ),
        primary_cause="Flood", approx_cost=12_300, percent_complete=1.0,
        labor_type="FA/C", prior_pa_grant="N", priority="Medium",
        # The contrast case: same exposure, but coverage was carried, so no
        # Section 311 reduction applies.
        is_insurable_building=True,
        in_special_flood_hazard_area=True,
        sfha_designated_years=14,
        building_value=780_000,
        contents_value=95_000,
        flood_insurance_in_force=1_000_000.0,
        obtain_and_maintain_acknowledged=True,
    )
    b5 = site(
        category="B", name="Police Impound Lot Relocation and Aerial Reconnaissance",
        address="2200 Industrial Way",
        latitude=47.8215, longitude=-121.7455,
        damage_description=(
            "Vehicles held at the police impound lot inside the mapped flood zone were "
            "relocated to higher ground. Department unmanned aircraft crews flew 14 "
            "sorties over the inundated area to provide situational awareness to the EOC."
        ),
        primary_cause="Flood", approx_cost=9_850, percent_complete=1.0,
        labor_type="FA", prior_pa_grant="N", priority="Medium",
    )

    # -- Category C: roads and bridges ------------------------------------------
    c1 = site(
        category="C", name="Signalized Intersection — Main Street and 3rd Avenue",
        address="Intersection of Main Street and 3rd Avenue", zip_code="98288",
        latitude=47.8391, longitude=-121.7701,
        damage_description=(
            "Floodwater inundated the traffic signal controller cabinet and its internal "
            "components, rendering the intersection dark. Damaged components include one "
            "M60 controller, 12 LED vehicle signal modules, 7 pedestrian signal modules, "
            "one three-section vehicle head, approximately 50 feet of 7-conductor cable, "
            "8 pedestrian push buttons, and the grounding circuit at the northeast "
            "corner pole. Arc and burn marks were observed on conductors at all four "
            "corners."
        ),
        primary_cause="Flood", approx_cost=566_000, percent_complete=0.0,
        labor_type="C", prior_pa_grant="N", priority="High",
    )
    c2 = site(
        category="C", name="Mill Creek Bridge Scour Repair",
        address="Mill Creek Bridge, Bridge No. CV-118, Mill Street",
        latitude=47.8298,
        longitude=121.7912,           # DEFECT: sign dropped in transcription
        damage_description=(
            "Prolonged high flow scoured the streambed at both bridge abutments and "
            "undermined the north wingwall. Post-event inspection measured 4.2 feet of "
            "scour at the north abutment and 2.8 feet at the south, with loss of "
            "approximately 190 cubic yards of embankment and riprap. The structure is "
            "posted and restricted to a single lane pending repair."
        ),
        primary_cause="Flood", approx_cost=1_240_000, percent_complete=0.0,
        labor_type="C", prior_pa_grant="Y", priority="Urgent",
        insured=True, insurance_proceeds=0.0, anticipated_insurance=95_000.0,
        in_special_flood_hazard_area=True,
        ehp_flags={"in_or_near_waterway": True, "listed_species_present": True,
                   "ground_disturbance": True, "floodplain": True},
    )

    # -- Category D: water control ----------------------------------------------
    d1 = site(
        category="D", name="Levee District 3 Scour Repair — 13 Locations",
        address="Levee District 3, stations 12+00 through 96+00",
        latitude=47.8534, longitude=-121.7845,
        damage_description=(
            "Overtopping and receding flow caused scour damage at 13 discrete locations "
            "along the Levee District 3 embankment, ranging from 15 to 140 linear feet "
            "each, with an aggregate loss of approximately 2,100 cubic yards of "
            "embankment material. Emergency stabilization was completed at the two most "
            "significant locations; the remaining 11 are unrepaired."
        ),
        primary_cause="Flood", approx_cost=845_000,
        percent_complete=0.25,        # DEFECT: work underway with EHP unresolved
        labor_type="C", prior_pa_grant="U", priority="Urgent",
        in_special_flood_hazard_area=True,
        ehp_flags={"in_or_near_waterway": True, "listed_species_present": True,
                   "ground_disturbance": True, "floodplain": True,
                   "undisturbed_ground": True},
    )

    # -- Category F: utilities ---------------------------------------------------
    f1 = site(
        category="F", name="Transmission Main No. 4 — Air Valve and Blowoff Structures",
        address="South transmission corridor, stations 40+00 through 118+00",
        latitude=47.8447, longitude=-121.8003,
        damage_description=(
            "Floodwater submerged nine air valve and blowoff vaults on Transmission Main "
            "No. 4, the potable water conveyance serving approximately 70 percent of the "
            "service area. Vault interiors, valve actuators, and the protective coating "
            "on exposed pipe were exposed to prolonged submergence and floodborne debris. "
            "Portions of the corridor remain inundated and a complete assessment is not "
            "yet possible."
        ),
        primary_cause="Flood", approx_cost=71_500, percent_complete=0.0,
        labor_type="FA/C", prior_pa_grant="U", priority="High",
        ehp_flags={"in_or_near_waterway": True},
    )
    f2 = site(
        category="F", name="Cathodic Protection Rectifier — Lowell River Road",
        address="2500 block of Lowell River Road",
        latitude=47.8362, longitude=-121.8140,
        damage_description=(
            "The impressed-current cathodic protection rectifier and its electrical "
            "service equipment, which protect the steel Transmission Main No. 4, were "
            "fully submerged. Submergence of the rectifier and service panel constitutes "
            "physical damage and compromises the expected service life of the affected "
            "components."
        ),
        primary_cause="Flood", approx_cost=10_400, percent_complete=0.0,
        labor_type="C", prior_pa_grant="N", priority="Medium",
    )

    # -- Category G: parks and other facilities ---------------------------------
    g1 = site(
        category="G", name="Riverfront Park Trail and Restroom",
        address="500 Riverfront Drive",
        latitude=47.8455, longitude=-121.7767,
        damage_description=(
            "Floodwater covered approximately 3,400 linear feet of hard-surface trail, "
            "depositing silt to an average depth of 4 inches. The vault restroom was "
            "inundated and required pumping and disinfection before reopening."
        ),
        primary_cause="Flood", approx_cost=14_200, percent_complete=1.0,
        labor_type="FA/C", prior_pa_grant="N", priority="Low",
        ehp_flags={"floodplain": True},
    )
    g2 = site(
        category="G", name="Cascade Community Center — Refrigeration and Electrical",
        address="700 Park Street", zip_code="98288",
        latitude=47.8404, longitude=-121.7645,
        damage_description=(
            "The community center was closed and its building systems de-energized ahead "
            "of forecast inundation. On restoration of power the walk-in refrigeration "
            "system failed to restart; the compressor and controls were found "
            "unserviceable and require replacement. Domestic hot water, HVAC controls, "
            "and the access control system also required recommissioning."
        ),
        primary_cause="Flood", approx_cost=58_900, percent_complete=0.9,
        labor_type="C", prior_pa_grant="N", priority="Medium",
        structure_age_years=52,       # DEFECT: over the NHPA screening age
        # DEFECT: insurable building in an SFHA, flood-damaged, no flood coverage.
        # Triggers the Stafford Act Sec. 311 mandatory reduction.
        is_insurable_building=True,
        in_special_flood_hazard_area=True,
        sfha_designated_years=14,
        building_value=2_400_000,
        contents_value=310_000,
        flood_insurance_in_force=0.0,
    )

    s.sites = [a1, a2, a3, b1, b2, b3, b4, b5, c1, c2, d1, f1, f2, g1, g2]

    # -- Projects ---------------------------------------------------------------
    # Cat-A: all three debris sites grouped, which is what carries the $3,100 site.
    p_a = Project(
        title="Cat-A Debris Removal — Citywide (Work completed)",
        category="A", site_ids=[a1.id, a2.id, a3.id],
        scope_of_work=(
            "Collect and dispose of disaster-generated vegetative and construction "
            "debris from public rights-of-way and maintained shoulders citywide, "
            "including chipping on site where practicable and hauling the balance to "
            "the county transfer station."
        ),
        labor=[
            LaborLine(description="Street maintenance crew — debris collection",
                      employee_class=EmployeeClass.BUDGETED, employee_count=9,
                      straight_time_hours=168, overtime_hours=96,
                      straight_rate=41.20, overtime_rate=61.80, fringe_rate=0.34),
            LaborLine(description="Equipment operators — chipper and loader",
                      employee_class=EmployeeClass.BUDGETED, employee_count=4,
                      straight_time_hours=120, overtime_hours=44,
                      straight_rate=45.90, overtime_rate=68.85, fringe_rate=0.34),
        ],
        equipment=[
            EquipmentLine(description="Truck, Dump — 12 CY", fema_cost_code="8577",
                          hours=214, fema_rate=42.11, standby_hours=36),
            EquipmentLine(description="Chipper, Brush — 12 IN", fema_cost_code="8110",
                          hours=96, fema_rate=27.03),
            EquipmentLine(description="Loader, Wheeled — 2.5 CY", fema_cost_code="8360",
                          hours=88, fema_rate=61.55),
            EquipmentLine(description="Street Sweeper", fema_cost_code="8552",
                          hours=142, fema_rate=48.20),
        ],
        costs=[
            SimpleCostLine(cost_type=CostType.CONTRACT,
                           description="Debris hauling and transfer station disposal",
                           quantity=1, unit_cost=31_400, vendor="Regional Hauling LLC",
                           competed=True, sam_debarment_checked=True,
                           contract_date=date(2027, 1, 6)),
            SimpleCostLine(cost_type=CostType.MATERIALS,
                           description="Chipper blades, straps, fuel cans",
                           quantity=1, unit_cost=2_180, vendor="Valley Supply"),
        ],
    )

    # Cat-B: the levee flood fight. Seeded with the straight-time error, a bad
    # contract, and more donated value than the applicant share can absorb.
    p_b1 = Project(
        title="Cat-B Emergency Protective Measures — Levee District 3 Flood Fight",
        category="B", site_ids=[b1.id],
        scope_of_work=(
            "Construct temporary berm on the existing levee crest and place sandbags "
            "around wastewater treatment plant structures to prevent inundation of "
            "treatment works, then remove temporary materials after the river fell "
            "below flood stage."
        ),
        labor=[
            # DEFECT: straight time claimed for budgeted employees on Cat-B.
            LaborLine(description="Public works crew — berm construction",
                      employee_class=EmployeeClass.BUDGETED, employee_count=14,
                      straight_time_hours=240, overtime_hours=186,
                      straight_rate=43.75, overtime_rate=65.63, fringe_rate=0.34),
            LaborLine(description="Temporary flood-fight hires",
                      employee_class=EmployeeClass.TEMPORARY, employee_count=6,
                      straight_time_hours=180, overtime_hours=64,
                      straight_rate=28.00, overtime_rate=42.00, fringe_rate=0.18),
        ],
        equipment=[
            EquipmentLine(description="Excavator, Hydraulic — 1.5 CY", fema_cost_code="8256",
                          hours=142, fema_rate=94.44),
            EquipmentLine(description="Truck, Dump — 12 CY", fema_cost_code="8577",
                          hours=196, fema_rate=42.11, standby_hours=48),
            EquipmentLine(description="Pump, Trash — 6 IN", fema_cost_code="8471",
                          hours=310, fema_rate=18.66),
        ],
        costs=[
            # DEFECT: over the micro-purchase threshold, uncompeted, no SAM check.
            SimpleCostLine(cost_type=CostType.CONTRACT,
                           description="Emergency berm material placement",
                           quantity=1, unit_cost=290_000,
                           vendor="Northline Earthworks",
                           competed=False, sam_debarment_checked=False,
                           contract_date=date(2026, 12, 31)),
            SimpleCostLine(cost_type=CostType.MATERIALS,
                           description="Sandbags (11,000), poly sheeting, geotextile",
                           quantity=1, unit_cost=18_700, vendor="Valley Supply"),
            SimpleCostLine(cost_type=CostType.RENTAL,
                           description="Rented 8-inch bypass pumps (2 units, 9 days)",
                           quantity=18, unit_cost=410, vendor="Pacific Pump Rental"),
        ],
        donated=[
            # Fully creditable here, and worth walking through: the credit reduces
            # what the city writes a check for, not what FEMA obligates.
            DonatedResourceLine(resource_type="Labor",
                                description="Community volunteer sandbagging",
                                hours_or_quantity=1_850, valuation_rate=34.75,
                                donor="Cascade Valley CERT and community volunteers",
                                rate_basis="Bureau of Labor Statistics rate for "
                                           "equivalent construction labor, local area"),
            DonatedResourceLine(resource_type="Equipment",
                                description="Donated agricultural loader and operator",
                                hours_or_quantity=46, valuation_rate=61.55,
                                donor="Cascade Valley Grange",
                                rate_basis=""),   # DEFECT: no documented basis
        ],
    )

    p_b2 = Project(
        title="Cat-B Emergency Protective Measures — EOC and Departmental Response",
        category="B", site_ids=[b2.id, b3.id, b4.id, b5.id],
        scope_of_work=(
            "Activate and staff the Emergency Operations Center, operate standby "
            "generators at four wastewater lift stations, evacuate and relocate the "
            "municipal animal shelter, and relocate impounded vehicles out of the "
            "mapped flood zone."
        ),
        labor=[
            LaborLine(description="EOC staffing — all departments (overtime)",
                      employee_class=EmployeeClass.BUDGETED, employee_count=22,
                      straight_time_hours=0, overtime_hours=418,
                      straight_rate=46.10, overtime_rate=69.15, fringe_rate=0.34),
            LaborLine(description="Utilities crew — generator operations",
                      employee_class=EmployeeClass.BUDGETED, employee_count=3,
                      straight_time_hours=0, overtime_hours=58,
                      straight_rate=44.30, overtime_rate=66.45, fringe_rate=0.34),
        ],
        equipment=[
            EquipmentLine(description="Generator, 100 KW", fema_cost_code="8299",
                          hours=127, fema_rate=24.83),
            EquipmentLine(description="Automobile, Police", fema_cost_code="8073",
                          hours=96, fema_rate=19.14),
        ],
        costs=[
            SimpleCostLine(cost_type=CostType.CONTRACT,
                           description="Animal boarding at partner facility, 11 days",
                           quantity=1, unit_cost=8_400, vendor="Northwest Animal Care",
                           competed=True, sam_debarment_checked=True),
            SimpleCostLine(cost_type=CostType.MATERIALS,
                           description="Generator fuel, EOC consumables",
                           quantity=1, unit_cost=4_960, vendor="Various"),
            SimpleCostLine(cost_type=CostType.RENTAL,
                           description="Box truck rental for shelter relocation",
                           quantity=4, unit_cost=285, vendor="Cascade Truck Rental"),
        ],
    )

    # Cat-C: one project per facility. The bridge clears the large-project threshold.
    p_c1 = Project(
        title="Cat-C Roads and Bridges — Main Street and 3rd Avenue Signal",
        category="C", site_ids=[c1.id],
        scope_of_work=(
            "Replace the flood-damaged traffic signal controller cabinet and internal "
            "components, LED vehicle and pedestrian signal modules, conductor cable, "
            "pedestrian push buttons, and the northeast corner grounding circuit, and "
            "restore the intersection to pre-disaster function in conformance with "
            "current applicable codes and standards."
        ),
        costs=[
            SimpleCostLine(cost_type=CostType.CONTRACT,
                           description="Signal replacement — design and construction",
                           quantity=1, unit_cost=541_000,
                           vendor="[to be procured]",
                           competed=False, sam_debarment_checked=False),
            SimpleCostLine(cost_type=CostType.MATERIALS,
                           description="City-furnished controller and modules",
                           quantity=1, unit_cost=25_000, vendor="[to be procured]"),
        ],
    )

    p_c2 = Project(
        title="Cat-C Roads and Bridges — Mill Creek Bridge Scour Repair",
        category="C", site_ids=[c2.id],
        scope_of_work=(
            "Restore scoured streambed and embankment at the north and south abutments "
            "of Bridge No. CV-118, reconstruct the undermined north wingwall, and place "
            "scour countermeasures to restore the structure to its pre-disaster design, "
            "capacity, and function."
        ),
        costs=[
            SimpleCostLine(cost_type=CostType.CONTRACT,
                           description="Bridge scour repair — construction",
                           quantity=1, unit_cost=1_186_000,
                           vendor="[to be procured]",
                           competed=False, sam_debarment_checked=False),
            SimpleCostLine(cost_type=CostType.CONTRACT,
                           description="Design engineering and construction inspection",
                           quantity=1, unit_cost=54_000,
                           vendor="[to be procured]",
                           competed=False, sam_debarment_checked=False),
        ],
        codes_and_standards=[
            # Passes all five criteria: eligible upgrade cost.
            CodeStandard(
                citation="AASHTO LRFD Bridge Design Specifications, adopted 2019-01-01",
                description="Scour countermeasure design to current AASHTO standard",
                upgrade_cost=68_000,
                applies_to_repair_type=True,
                appropriate_to_predisaster_use=True,
                formally_adopted_before=True,
                applied_uniformly=True,
                actually_enforced=True,
            ),
            # DEFECT: adopted AFTER the declaration and never enforced. The upgrade
            # is the city's own expense, not a disaster cost.
            CodeStandard(
                citation="City Ordinance 2027-14, adopted 2027-05-02",
                description="Seismic retrofit of bridge substructure",
                upgrade_cost=240_000,
                applies_to_repair_type=True,
                appropriate_to_predisaster_use=True,
                formally_adopted_before=False,
                applied_uniformly=False,
                actually_enforced=False,
            ),
        ],
    )

    # Cat-D: the levee. Work is 25% complete with EHP unresolved.
    p_d = Project(
        title="Cat-D Water Control Facilities — Levee District 3 Scour Repair",
        category="D", site_ids=[d1.id],
        scope_of_work=(
            "Restore 13 scour locations along the Levee District 3 embankment to "
            "pre-disaster grade, section, and function, placing embankment material and "
            "riprap in accordance with the district's design section."
        ),
        costs=[
            # DEFECT: prohibited contract type.
            SimpleCostLine(cost_type=CostType.CONTRACT,
                           description="Levee scour repair — time and materials plus "
                                       "12 percent of incurred cost",
                           quantity=1, unit_cost=812_000,
                           vendor="Northline Earthworks",
                           competed=True, sam_debarment_checked=True,
                           cost_plus_percentage_of_cost=True,
                           contract_date=date(2027, 3, 2)),
            SimpleCostLine(cost_type=CostType.MATERIALS,
                           description="Riprap and embankment material",
                           quantity=1, unit_cost=33_000, vendor="Cascade Aggregates"),
        ],
    )

    p_f = Project(
        title="Cat-F Utilities — Transmission Main No. 4 Corridor",
        category="F", site_ids=[f1.id, f2.id],
        scope_of_work=(
            "Rehabilitate nine submerged air valve and blowoff vaults on Transmission "
            "Main No. 4, restore protective coating on exposed pipe, and replace the "
            "submerged impressed-current cathodic protection rectifier and electrical "
            "service equipment."
        ),
        costs=[
            SimpleCostLine(cost_type=CostType.CONTRACT,
                           description="Vault rehabilitation and coating repair",
                           quantity=1, unit_cost=63_500,
                           vendor="[to be procured]",
                           competed=False, sam_debarment_checked=False),
            SimpleCostLine(cost_type=CostType.CONTRACT,
                           description="Cathodic protection rectifier replacement",
                           quantity=1, unit_cost=10_400,
                           vendor="[to be procured]",
                           competed=False, sam_debarment_checked=False),
        ],
    )

    p_g = Project(
        title="Cat-G Parks and Other Facilities — Riverfront Park and Community Center",
        category="G", site_ids=[g1.id, g2.id],
        scope_of_work=(
            "Remove silt from hard-surface trail and restore the vault restroom at "
            "Riverfront Park; replace the unserviceable walk-in refrigeration compressor "
            "and controls and recommission building systems at the community center."
        ),
        labor=[
            LaborLine(description="Parks crew — trail silt removal and restroom service",
                      employee_class=EmployeeClass.BUDGETED, employee_count=5,
                      straight_time_hours=88, overtime_hours=12,
                      straight_rate=38.60, overtime_rate=57.90, fringe_rate=0.34),
        ],
        equipment=[
            EquipmentLine(description="Street Sweeper", fema_cost_code="8552",
                          hours=26, fema_rate=48.20),
            EquipmentLine(description="Loader, Skid-Steer", fema_cost_code="8371",
                          hours=34, fema_rate=29.87),
        ],
        costs=[
            SimpleCostLine(cost_type=CostType.CONTRACT,
                           description="Walk-in refrigeration replacement",
                           quantity=1, unit_cost=44_800, vendor="DK Mechanical",
                           competed=True, sam_debarment_checked=True,
                           contract_date=date(2027, 2, 24)),
            SimpleCostLine(cost_type=CostType.CONTRACT,
                           description="Septic pumping and restroom disinfection",
                           quantity=1, unit_cost=3_900, vendor="Valley Septic",
                           competed=True, sam_debarment_checked=True),
        ],
    )

    s.projects = [p_a, p_b1, p_b2, p_c1, p_c2, p_d, p_f, p_g]
    # DEFECT: no Cat-Z management cost project, and no Section 406 mitigation on
    # any of the four permanent work projects.
    return s


def main() -> None:
    s = build()
    save_scenario(s, OUT)

    from pa.costing import summarize_scenario
    from pa.scoring import score

    t = summarize_scenario(s)
    card = score(s)
    print(f"Wrote {OUT}")
    print(f"  {len(s.sites)} sites, {len(s.projects)} projects")
    print(f"  net eligible ${t.net_eligible:,.2f} | federal ${t.federal_share:,.2f} "
          f"| applicant ${t.applicant_out_of_pocket:,.2f}")
    print(f"  large {t.large_projects} / small {t.small_projects} / "
          f"below minimum {t.below_minimum}")
    print(f"  starting scorecard: {card.percent}% ({card.grade}) — "
          f"{len(card.review.errors)} errors, {len(card.review.warnings)} warnings")


if __name__ == "__main__":
    main()
