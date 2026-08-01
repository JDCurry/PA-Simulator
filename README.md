# Public Assistance Workbench

A FEMA Public Assistance reimbursement workbench and training simulator.

An applicant works a disaster the way it actually runs: impact list in, projects
formulated, costs built up against the FEMA equipment rate schedule, compliance
tested, package exported. The same engine grades a student's package, so the tool is
usable both as a jurisdiction's working file and as a classroom exercise.

Built against **PAPPG V5 Amended (January 2025)** and **FEMA Policy FP-104-23-001**
(Public Assistance Simplified Procedures, January 2023).

> Not affiliated with FEMA. A planning and training aid. Verify every figure against
> the current PAPPG and your own award before relying on it.

---

## What it does

| | |
|---|---|
| **Impact List** | Enter or import the damage inventory. Reads the standard FEMA damage inventory workbook your state recipient distributes. |
| **Formulation** | Group sites into projects following FEMA's conventions, and see immediately what the grouping decides. |
| **Cost Buildup** | Force account labor and equipment, contracts, materials, rentals, donated resources, Section 406 mitigation, codes and standards, and Section 428 alternative procedures. 465 rates from the 2025 FEMA Schedule of Equipment Rates are searchable inline. |
| **Compliance** | The four-part eligibility test, plus procurement, EHP, insurance and the Section 311 reduction, codes and standards, deadlines, and documentation — each finding cited to the PAPPG, the Stafford Act, or 2 CFR 200. |
| **Package** | DDD narratives, cost summaries, per-category documentation checklists, and exports. |
| **Training** | A scorecard across seven weighted dimensions, the six-phase PA process, a category and reductions reference, a glossary, and reflection prompts. |
| **Manual** | The full user manual, rendered in the app so anyone with just the URL has it. |

## The rules it actually implements

Not a form-filler. The engine encodes the rules that decide the money:

- **Labor eligibility by category.** *All* Emergency Work — Cat-A debris and Cat-B
  protective measures — reimburses budgeted employees for **overtime only**. Permanent
  work reimburses straight time as well; temporary and emergency hires are fully
  eligible everywhere. This asymmetry is the most common source of de-obligation on
  emergency work.
- **Section 311 / NFIP mandatory reduction.** An insurable building in a Special Flood
  Hazard Area, damaged by flood, with no flood coverage, has eligible cost reduced by
  the maximum proceeds a standard NFIP policy would have paid — $500,000 building plus
  $500,000 contents. **Sized on policy limits, not on damage**, so it routinely exceeds
  the entire project. Statutory; not appealable.
- **Section 428 Alternative Procedures.** For debris: the election makes straight-time
  force account labor eligible, pays an increased federal share on a sliding scale
  (85% within 30 days of the incident period ending, 80% within 90, 75% within 180),
  and lets the applicant retain recycling revenue. For permanent work: a fixed-cost
  offer that caps the award in exchange for scope flexibility.
- **Project thresholds.** Below $4,100 there is no project. Above $1,093,800 a project
  is paid on actual cost with 10% retainage, progressive draws, a final inspection,
  and a SOD-FIR at closeout — and Simplified Procedures stop applying.
- **Order of operations on cost.** Gross eligible → add approved 406 mitigation →
  subtract insurance proceeds, actual *and* anticipated → subtract the Section 311
  reduction → apply any Section 428 fixed-cost cap → split at the applicable federal
  share → credit donated resources against the applicant's share only.
- **Donated resources.** Emergency work pools the credit across *all* Cat-A and Cat-B
  projects before capping; permanent work caps per project. Capping emergency work per
  project strands value the applicant is entitled to.
- **Section 406 mitigation.** Permanent work only. Up to 15% of eligible repair is
  approvable outright; PAPPG-listed measures up to 100%; anything above needs a
  favorable BCA.
- **Codes and standards.** The five-part test. An upgrade driven by a code is eligible
  only if the code applies to the repair type, suits the pre-disaster use, was formally
  adopted before the declaration, applies uniformly, and was actually enforced.
- **Management costs.** DRRA §1215 sets a combined 12% — 7% recipient, 5%
  subrecipient. The applicant's 5% is computed against its *total obligated amount*,
  which is only knowable after every other project is rolled up.
- **Deadlines from the RPA forward.** The Request for Public Assistance is due 30 days
  from designation and is the deadline that ends the process if missed.
- **Appeals and arbitration.** 60 days for a first appeal, 60 more for a second, and
  DRRA §1219 arbitration in lieu of a second appeal above $500,000 ($100,000 for small
  impoverished communities).
- **Procurement.** Micro-purchase and simplified acquisition thresholds, SAM.gov
  debarment checks, and cost-plus-percentage-of-cost contracts, which are prohibited
  outright for non-state entities.
- **Equipment.** FEMA schedule rate or the applicant's adopted rate, whichever is
  lower. Standby time excluded. Operator labor billed separately. The
  equipment-versus-supply test that governs disposition at closeout.
- **Deadlines** computed from designation, declaration, and the RSM, flagging that
  Cat-I's 180-day deadline is the one FEMA will not extend.
- **PNP rules**, including the requirement that a non-critical private non-profit
  exhaust the SBA before PA will fund permanent work.

## Disaster-agnostic by construction

Everything that changes between disasters lives in `pa/rules.py` as data, not as
branches through the costing code. A new disaster is a new `RuleSet`:

```python
from pa.rules import RuleSet
from dataclasses import replace

# A declaration at 90/10 with the following year's indexed threshold.
rules = replace(
    RuleSet().with_cost_share(0.90),
    thresholds=replace(RuleSet().thresholds, large_project_threshold=1_120_000),
)
```

Scenarios are plain JSON and carry their own ruleset, so a file written for one
declaration never silently inherits another's thresholds.


## Scenarios

**The app opens empty.** A jurisdiction starts from its own impact list, not from
someone else's disaster. The sidebar offers four actions: save the working file to
JSON, open a saved one, load the bundled training scenario, or clear and start over.
Nothing is stored on the server.

One scenario ships with the repository:

- `training_cascade_valley.json` — a fictional mid-size Washington city on a winter
  storm and flood declaration. 15 sites, 8 projects, ~$4.5M net eligible. Seeded with
  defects on purpose, each mapping to a rule the engine checks. It opens at **33.3%,
  grade F, 20 blocking findings** — working it clean is the exercise. Two decisions
  alone (electing Section 428 for debris, and carrying the flood insurance that
  triggers the Section 311 reduction) move it to 46.7% and add $191,000 of eligible
  cost. Worked all the way clean it reaches **98.2%, grade A**, with eligible cost up
  $773,000 and the federal share up $606,000 — the step-by-step path is in the
  [user manual](docs/USER_MANUAL.md#guided-walkthrough-f-to-a).

Files named `*.local.json` are gitignored. That suffix is the convention for a real
jurisdiction's impact list: it stays on the machine that built it, and a test asserts
that nothing but the fictional scenario is ever committed.

### Importing a real damage inventory

Upload the workbook on the Impact List page. The importer reads the standard FEMA
template, merges multiple files, de-duplicates on category and site name, and
corrects western-hemisphere longitudes keyed without their sign.

**On personal information:** the `Scenario` model has no field for a person's name,
phone number, or email address. The importer reads the workbook's header block to
pick up the applicant name, FIPS, and disaster number, and discards the rest. What is
kept is the applicant's *role*, not the individual.

## Layout

```
pa/                 the engine — no Streamlit dependency, drivable from a script
  rules.py          versioned, declarative policy configuration
  models.py         Scenario / Site / Project / cost lines
  costing.py        labor, equipment, mitigation, insurance, cost share
  formulation.py    grouping conventions and small-vs-large classification
  validation.py     the four-part test, procurement, EHP, deadlines
  equipment.py      FEMA Schedule of Equipment Rates
  importers.py      FEMA damage inventory workbook reader
  export.py         DDD, cost summaries, checklists, reimbursement request
  scoring.py        training-mode rubric
  scenario.py       JSON serialization
ui/                 Streamlit pages
data/
  equipment_rates_2025.csv    465 rates, extracted from the FEMA schedule
  scenarios/                  bundled scenarios; *.local.json is gitignored
tools/              scenario builders
tests/              83 tests pinning the rules
```

The engine has no UI dependency. To drive it from a notebook or a script:

```python
from pa import load_scenario, summarize_scenario, review, score

s = load_scenario("data/scenarios/training_cascade_valley.json")
totals = summarize_scenario(s)
print(f"Federal share: ${totals.federal_share:,.2f}")

for f in review(s).errors:
    print(f"[{f.test}] {f.subject}: {f.message}")

print(score(s).percent)
```

## Caveats

- Thresholds are indexed annually. The bundled defaults are the figures in force for
  a 2026 declaration; check yours.
- The engine models the rules, not the judgement. Grouping decisions, damage
  causation, and reasonableness of cost are made with your PDMG, not by software.
- Section 404 HMGP is deliberately out of scope. It is state-administered, statewide,
  and not tied to a specific declaration.
- The Section 428 debris sliding scale is modeled at the project level from a single
  completion date. FEMA applies it to costs *incurred* inside each window, so debris
  spanning windows is normally formulated as separate projects per window.
- NFIP limits are the non-residential figures. Residential limits are lower and are
  not modeled, because public facilities are non-residential.
- Scenarios live in the browser session only. Save the working file before closing
  the tab.
