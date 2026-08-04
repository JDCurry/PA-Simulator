# Public Assistance Workbench — User Manual

A hands-on tool for learning and doing FEMA Public Assistance reimbursement.

You play the **applicant**: a city, county, special district, tribe, or non-profit that
took damage in a declared disaster and now has to get reimbursed. You build a damage
inventory, group it into projects, price the work, and assemble a submission package.
The tool checks your work the way a FEMA reviewer would and tells you what it would
send back — with a citation for every finding.

> **Not affiliated with FEMA.** This is a planning and training aid. Dollar thresholds
> are indexed annually and cost shares are set by each declaration. Verify every figure
> against the current PAPPG and your own award before relying on it.

---

## Contents

1. [Five-minute start](#five-minute-start)
2. [Orientation: how the PA program actually works](#orientation-how-the-pa-program-actually-works)
3. [The sidebar](#the-sidebar)
4. [Page reference](#page-reference)
5. [Saving and sharing your work](#saving-and-sharing-your-work)
6. [Guided walkthrough: F to A](#guided-walkthrough-f-to-a)
7. [For instructors](#for-instructors)
8. [Glossary](#glossary)
9. [Limits, cautions, and where the rules come from](#limits-cautions-and-where-the-rules-come-from)

---

## Five-minute start

1. **Open the app.** It lands on **Start here**, which explains what the tool is and
   offers two ways in.
2. Click **Start the worked example**. This loads a fictional Washington city on a
   flood and winter-storm declaration — 15 damage sites, 8 projects, about $4.4M in
   eligible cost — and drops you straight onto the compliance review.
3. You will see roughly **20 blocking findings**. The package is deliberately broken.
4. Look at the sidebar. Under **DO THIS NEXT** it names the single highest-priority
   problem and the page that fixes it. Go there and fix it.
5. Come back. The count drops, the totals move, and **DO THIS NEXT** names the next one.

That loop — the tool tells you the one thing to do, you do it, the numbers move — is
how the whole thing works. You never have to guess what to look at.

**If you would rather not be led**, every page is in the sidebar and you can work in any
order. **Start here** shows your progress through the six steps at any time.

**Nothing you do is saved automatically.** Use **Save working file** in the sidebar
before you close the tab. See [Saving and sharing your work](#saving-and-sharing-your-work).

---

## Orientation: how the PA program actually works

If you have never worked a PA grant, read this section first. Everything in the tool
maps onto it.

After a Presidential major disaster declaration, eligible public entities can be
reimbursed for disaster costs. The program runs in six phases:

| Phase | What happens |
|---|---|
| **Get in** | File a **Request for Public Assistance (RPA)** within 30 days of your area being designated. Then an Exploratory Call, then the **Recovery Scoping Meeting (RSM)**. |
| **1 — Scoping** | At the RSM you meet your **Program Delivery Manager (PDMG)**. You then have **60 days** to submit a complete **Impact List** of every damaged site. |
| **2 — Development** | Site inspections. You assemble documentation. FEMA drafts the **Damage, Description and Dimensions (DDD)** from your descriptions. |
| **3 — Scope and cost** | FEMA's Consolidated Resource Center validates scope and cost. Mitigation proposals and insurance reviewed. |
| **4 — Review** | Environmental and historic review, then signatures from FEMA, the state, and you. |
| **5 — Obligation** | FEMA obligates funds to the **state**, which distributes to you. Obligation is not the same as being paid. |
| **6 — Closeout** | Final inspection, certification, record retention, and possible audit. |

Four ideas do most of the work:

**Eligibility has four independent parts.** FEMA tests **applicant**, **facility**,
**work**, and **cost** separately. Failing any one ends the project, no matter how good
the other three are.

**The cost share is 75/25 by default.** FEMA pays 75%, you pay 25%. Your 25% is real
money out of a general fund, a utility fund, or a levy.

**Work is sorted into categories, and the category changes the rules.**

| | Categories | Deadline | Straight-time labor for your regular staff |
|---|---|---|---|
| **Emergency work** | A (debris), B (protective measures) | 6 months | **Not eligible** — overtime only |
| **Permanent work** | C–G (roads, water control, buildings, utilities, parks) | 18 months | Eligible |
| **Code enforcement** | I | 180 days, **no extensions** | Not eligible — overtime only |
| **Grant management** | Z | — | Eligible |

**Project size changes everything downstream.** Under **$4,100** there is no project at
all. Over **$1,093,800** it becomes a *large* project: paid on actual cost instead of an
estimate, with 10% retainage held back, progressive draws, a final inspection, and a
different closeout document.

---

## The sidebar

Present on every page.

- **Navigation** — the six working steps in the order they happen, numbered, plus
  Start, Training, and this manual. Each is labelled by what you are doing rather than
  by the FEMA term; the FEMA term appears at the top of the page itself.
- **DO THIS NEXT** — the single most valuable action right now, and where to do it.
  This is the fastest way to use the tool: follow it until it runs out.
- **Progress** — which of the six steps you are on.
- **Running totals** — Net eligible, what FEMA pays, what you pay. These update as you
  work and are the fastest way to see whether a change helped.
- **Finding count** — blocking findings, or cautions if there are no blockers. It stays
  hidden until you have actually started, because an empty form is not a failing package.
- **Scenario controls** — save, open, load the worked example, or clear.
- **Footer** — the policy version the rules are based on, and the disclaimer.

Every working page also ends with a **DO THIS NEXT** bar and a button that takes you
there, so you can work straight through without returning to the sidebar.

---

## Page reference

Each page opens with one plain-English sentence saying what it is for, then the expert
detail. The sidebar names them by task; the headings below use both.

### Start here

Your orientation and dashboard. Before you have loaded anything it explains what the
tool is and offers the worked example or a blank file, with a one-minute primer on how
the program works. Once you have a scenario loaded it becomes a dashboard: progress
through the six steps, what to do next, and how much money is at stake.

### 1 · Set up the disaster — *Scenario*

Everything downstream is computed from here. Three tabs.

**Applicant** — who you are and what you have given FEMA.

The three *Required policies* checkboxes matter more than they look. FEMA cannot
formulate labor costs without your **pay policy**, cannot validate contracts without
your **procurement policy**, and cannot determine insurance reductions without your
**insurance policy**. Each unchecked box is a blocking finding.

*Section 428 alternative procedures for debris* is the single highest-value toggle in
the tool. Emergency work normally pays your regular staff overtime only. Electing
Section 428 for debris makes their **straight time** eligible too, raises the federal
share on a sliding scale for fast completion, and lets you keep recycling revenue. It
is a per-disaster decision.

**Disaster declaration** — dates, incident period, and declared incident types.

Dates drive every deadline. The *Area designation date* starts the 30-day RPA clock;
the *Recovery Scoping Meeting* date starts the 60-day Impact List clock. Damage must
have occurred **inside the incident period** — repair work can run long past it, but
the damage has to fall inside.

**Ruleset** — the thresholds and cost share themselves.

These are indexed annually and set by each declaration. If you are modeling a real
disaster, check these against your own award first. The expandable table at the bottom
explains what each threshold actually changes.

---

### 2 · List the damage — *Impact List*

Your damage inventory: every site, what happened, and roughly what it costs. Due 60
days after the RSM. A site not on the list when the window closes is generally not
funded.

**Inventory grid** — a spreadsheet. Add rows, edit cells, then click **Save grid
changes**. Changes are not applied until you save.

The bar chart shows approximate cost by category. These are your rough figures, not
eligible costs — eligibility is determined on Cost Buildup.

**Site detail** — the fields that do not fit in a grid. Pick a site, then work down:

- *Damage description* — FEMA writes the scope of work from this text. Name the damaged
  component, tie it to the declared incident, and quantify it. "Storm damage to park"
  is not fundable. "Large fallen branch severed the pedestrian overlook railing;
  approximately 40 linear feet of metal railing sustained structural separation at post
  and top-rail connections" is.
- *Facility eligibility* — the four-part test. Was it in use? Is it your legal
  responsibility? Inside the declared area? Actively maintained?
- *Insurance and the Section 311 reduction* — read the next paragraph carefully.
- *Environmental and historic screening* — check every trigger that applies.

> **Section 311 is the most expensive thing in this program and the least known.**
> If an insurable **building**, in a Special Flood Hazard Area designated over a year,
> is damaged by **flood**, and carried **no flood insurance**, FEMA *must* reduce your
> eligible cost by the maximum a standard NFIP policy would have paid — $500,000
> building plus $500,000 contents. It is sized on **policy limits, not on your damage**,
> so it routinely exceeds the entire project. It is statutory. It cannot be appealed.
> And it repeats in every future flood until you carry the coverage.
>
> In the training scenario the community center takes an **$810,000 reduction against
> $78,000 of damage**, which zeroes the project. That is not a bug in the tool. That is
> the law.

**Import / export** — upload the FEMA damage inventory workbook your state recipient
sends you. It reads the standard template, merges multiple files, and fixes longitudes
keyed without their minus sign. Personnel names, phone numbers, and email addresses in
the header block are **not** imported — the tool has nowhere to store them by design.

---

### 3 · Group into projects — *Formulation*

Grouping sites into projects. This is a funding decision, not a filing decision.

The conventions the tool follows:

- **Category never mixes.** A Cat-A site and a Cat-B site are separate projects.
- **Cat-I is always one project. Cat-Z is always one project.**
- **Completed work is separated from work to be completed** — one is paid on actual
  cost, the other on an estimate.
- **Emergency work can be combined jurisdiction-wide.** Permanent work is grouped by
  facility and locality.

**Propose grouping** applies those conventions to unassigned sites and shows you what it
would create. Accept it, or build projects yourself in **Manage projects**.

Why grouping is a money decision: a $3,100 debris site cannot stand alone — it is under
the $4,100 minimum. Grouped with two other debris sites, all three get funded. Conversely
a group that lands just over $1,093,800 picks up actual-cost accounting, retainage, and
a final inspection for the next two years. Two projects $100,000 apart in size are
administered completely differently.

**Manage projects** also holds the *Project option* selector — Standard, Improved,
Alternate, or Section 428. Improved and Alternate both require **written state approval
before work proceeds**.

**Review** flags grouping problems and shows the whole portfolio in one table.

---

### 4 · Price the work — *Cost Buildup*

Pick a project at the top; everything below applies to that project. Eight tabs.

**Labor** — force account (your own staff), split straight time and overtime.

Read the banner. On emergency work it will tell you straight time for budgeted
employees is **not eligible** — and if it is a debris project, that electing Section
428 changes that. Temporary and emergency hires are fully eligible in every category.

Fringe is entered as a fraction of base pay (0.34 for 34%), and only applies to
*eligible* base — fringe on excluded straight time is excluded too.

**Equipment** — your own equipment, billed at the FEMA Schedule of Equipment Rates.
Search 465 rates inline and click **Add**.

Three rules people get wrong: the rate already includes fuel, maintenance, and
depreciation; **operator labor is not included** and goes on the Labor tab; and
**standby time is never eligible** — the machine has to be working.

The expander at the bottom runs the equipment-versus-supply test, which decides whether
you owe FEMA money at closeout for equipment you keep.

**Contracts & materials** — with procurement compliance checked live.

The required method scales with contract value: under $15,000 is a micro-purchase with
no quotes needed; up to $350,000 needs quotes; above that needs formal sealed bidding.
Every contract needs a documented **SAM.gov debarment check**. And
**cost-plus-percentage-of-cost contracts are prohibited outright** — they pay the
contractor more for spending more. Those provisions are often buried in contract
language, which is why the tool asks.

**Donated resources** — volunteer labor, donated equipment and materials.

These do **not** increase the project cost. Their value is credited against **your 25%
share**, so they reduce what you write a check for, never what FEMA pays. The cap
differs by work type: emergency work pools the credit across *all* your Cat-A and Cat-B
projects; permanent work caps per project.

**406 Mitigation** — protecting the damaged element against the next event. Permanent
work only. Three routes: up to 15% of the eligible repair cost is approvable outright;
measures on the PAPPG list up to 100%; anything above needs a favorable benefit-cost
analysis. This is the most commonly unclaimed money in the program.

**Codes & standards** — upgrades a code forces you to make. Eligible only if the code
satisfies **all five** criteria: applies to the repair type, suits the pre-disaster use,
was formally adopted **before** the declaration, applies uniformly to all similar
facilities, and was actually enforced. Fail one and the upgrade is your own expense.

**Section 428** — alternative procedures. For debris: record the completion date to see
the sliding-scale share (85% within 30 days of the incident period ending, 80% within
90, 75% within 180). For permanent work: a fixed-cost offer that caps your award in
exchange for scope flexibility — you carry the overrun.

**Summary** — the full cost build in FEMA's order of operations, plus a *Claimed but not
payable* section that tells you exactly what you asked for and will not receive.

---

### 5 · Fix what FEMA would reject — *Compliance*

Your package reviewed the way FEMA would review it.

Findings come in three severities:

- **BLOCKING** — makes a project ineligible or specific costs unallowable. Fix these.
- **CAUTION** — what a reviewer would send back for more information.
- **NOTE** — awareness. Deadlines, retention, audit exposure.

Use the *Show* selector to filter. Findings are grouped by which test produced them,
and each one carries a citation and, where there is one, a specific remedy.

Work the blocking findings first. If you decide not to clear a caution, that is a
legitimate professional judgement — just be able to explain it.

---

### 6 · Assemble the package — *Package*

What you would actually hand over.

**Portfolio** — totals, cost by category, the Section 311 reduction if any, and
management-cost capacity. It ends with a **Request for Reimbursement** cover memo.

Watch the Cat-Z panel. Management costs are capped at 5% of your total obligated amount
and are routinely left unclaimed because nobody tracked staff time from the start of the
grant. In the training scenario that is over $200,000.

**Project detail** — the DDD narrative, the cost summary, and a documentation checklist.

Checklist items shown as plain text are determined from data you entered elsewhere.
Items with checkboxes are records this tool has nowhere to store — debris monitoring
logs, disposal permits, agency correspondence — so you confirm they are in the file.

**Export** — download the full package, the reimbursement request, the project summary,
or the impact list. Also lists the conditions of payment: no reimbursement until the
state contract is signed by all parties, and payment on a signed A-19A voucher.

---

### How am I doing? — *Training*

**Scorecard** — 100 points across seven weighted dimensions. It scores against the
rules, not against an answer key, so it works on any scenario including your own.

| Dimension | Weight |
|---|---|
| Eligibility — applicant, facility, work, cost | 25 |
| Project formulation and thresholds | 18 |
| Documentation and supporting records | 17 |
| Procurement compliance | 15 |
| EHP compliance and deadline management | 10 |
| Insurance exposure and codes and standards | 10 |
| Maximizing eligible recovery | 5 |

Each dimension expands to show exactly what is costing points.

**The PA process** — the six phases, your actual computed deadlines, the cost share, and
a small-versus-large project comparison.

**Category reference** — all nine categories with their labor rules, and a table of the
reductions applied before the cost share.

**Exercise** — eight reflection prompts, each mapping to something the engine checks,
plus a suggested assignment structure.

---

## Saving and sharing your work

**Your work lives in the browser session only.** Close the tab and it is gone. There are
no accounts and nothing is stored on the server — which is deliberate, so that no
jurisdiction's damage data ends up on someone else's infrastructure.

- **Save working file** downloads your scenario as a `.json` file. Do this often.
- **Open a saved file** uploads one back.
- **Load training scenario** replaces your work with the fictional exercise.
- **Clear and start over** empties everything.

To submit an assignment, save the working file and hand in the `.json`, plus the
exported package from the Package page.

To build a scenario for other people, save the file and distribute it. Scenarios carry
their own ruleset, so a file written for one declaration never silently inherits another
disaster's thresholds.

> **If you are modeling a real disaster:** keep the file. Do not commit it to a shared
> repository. Real impact lists contain facility vulnerability information, and files
> named `*.local.json` are excluded from version control for that reason.

---

## Guided walkthrough: F to A

The training scenario opens broken on purpose. Here is the full remediation, with the
numbers this produces. Work it in order and the scorecard climbs from **33.3% (F)** to
**98.2% (A)** while eligible cost rises **$773,000** and the federal share rises
**$606,000**.

| Step | What you do | Score | Blocking | Net eligible | Federal share |
|---|---|---|---|---|---|
| 0 | *As delivered* | 33.3% F | 20 | $4,357,479 | $3,268,109 |
| 1 | Submit the insurance policy; fix the Mill Creek Bridge longitude | 41.6% F | 19 | $4,357,479 | $3,268,109 |
| 2 | Fix procurement on every contract: competition, SAM checks, remove the CPPC provision | 57.2% F | 7 | $4,357,479 | $3,268,109 |
| 3 | Carry flood insurance on the buildings in the flood zone | 69.1% D | 5 | $4,435,861 | $3,326,896 |
| 4 | Elect Section 428 for debris and record the completion date | 70.6% C− | 5 | $4,548,859 | $3,437,467 |
| 5 | Add Section 406 mitigation to the permanent work projects | 72.1% C− | 5 | $4,950,838 | $3,738,952 |
| 6 | Drop the ineligible code upgrade; record EHP consultation complete | 85.6% B | 0 | $4,950,838 | $3,738,952 |
| 7 | Create the Cat-Z management cost project | 87.5% B+ | 0 | $5,130,838 | $3,873,952 |
| 8 | Confirm the documentation records on file | 98.2% A | 0 | $5,130,838 | $3,873,952 |

Notice which steps move *money* and which only move *compliance*. Steps 1 and 2 clear
thirteen blocking findings without changing a dollar — that work was always going to be
funded, it just would have been de-obligated later on audit. Steps 3 through 7 are where
the applicant actually gets paid more.

**How to do each step**

Page names below are the FEMA terms. In the sidebar they appear as numbered tasks —
*Scenario* is "1 · Set up the disaster", *Impact List* is "2 · List the damage", and so
on. You can also just follow **DO THIS NEXT**, which walks this same path on its own.

1. *Scenario → Applicant*, check **Insurance policy submitted**. Then *Impact List →
   Site detail*, pick Mill Creek Bridge, and correct the longitude to negative.
2. *Cost Buildup → Contracts & materials*, for each project: tick **Competed** and
   **SAM checked**, untick **CPPC**, then **Save costs**. The Cat-D levee contract is
   the prohibited one.
3. *Impact List → Site detail*, for the community center and the animal shelter, set
   **Flood insurance coverage carried** to 1,000,000 and tick
   **Obtain-and-maintain acknowledged**.
4. *Scenario → Applicant*, tick the **Section 428** election. Then *Cost Buildup →
   Section 428* on the debris project and set a completion date inside 30 days of the
   incident period ending (the period ends 2027-01-11, so early February).
5. *Cost Buildup → 406 Mitigation* on each Cat-C/D/F/G project. Add a measure at up to
   15% of the project's eligible repair cost.
6. *Cost Buildup → Codes & standards* on the Mill Creek Bridge project: the seismic
   retrofit was adopted after the declaration, so set its cost to 0 or document the
   missing criteria. Then *Impact List → Site detail* on each flagged site and tick
   **EHP consultation and permitting complete**.
7. *Impact List* — add a site with category **Z**. Then *Formulation → Manage projects*,
   add a Cat-Z project and assign it. Then *Cost Buildup → Contracts & materials* and
   enter your tracked staff time as an Other direct cost.
8. *Package → Project detail* for each project, and tick the documentation records you
   have.

---

## For instructors

**What this is suitable for.** A module, a workshop, or an applied assignment inside an
existing emergency management, public administration, or project management course. It
does not need a full course and does not assume prior FEMA knowledge — the Training tab
carries the orientation.

**No installation for students.** Published on Streamlit Community Cloud, it is a URL.
Students need a browser. Nothing is stored server-side, so there is no roster to manage
and no student data to protect.

**Assignment structure that works**

1. Read the scenario — applicant profile, declaration, incident period, impact list.
2. Formulate projects, and justify every grouping decision that moves a project across
   the minimum or the large-project threshold.
3. Build costs. Get the emergency-work labor rule right.
4. Run Compliance. Clear every blocking finding. Write one paragraph on each caution
   you chose not to clear, and why.
5. Claim what is available: Cat-Z management costs, Section 406 mitigation, and the
   Section 428 debris election.
6. Export the package and submit it with the saved `.json`.
7. Answer three reflection prompts in writing.

**Grading.** The scorecard is a starting point, not the grade. It measures whether the
package survives the rules. It cannot measure whether the student understood *why* — the
reflection prompts and the grouping justifications are where that shows. A student can
reach a high score by mechanically clearing findings; ask them to explain the Section
311 reduction in their own words and you will know immediately whether it landed.

**The teaching moments that land hardest**

- **The emergency-work labor rule.** Nearly everyone assumes disaster work is fully
  reimbursed. Watching $147,000 of straight time drop out of a Cat-B project is the
  moment the program becomes real.
- **Section 311.** An $810,000 reduction against $78,000 of damage, because nobody
  bought flood insurance. It reframes insurance from paperwork to strategy.
- **The two thresholds.** Two projects $100,000 apart, administered completely
  differently for two years.
- **Cat-Z.** Over $200,000 available for work the applicant is already doing, forfeited
  because nobody tracked time from day one.

**Building your own scenario.** Either build it in the UI and save the file, or write
the JSON directly — the format is documented in the repository README, and
`tools/build_training_scenario.py` is a worked example in Python. Scenarios carry their
own thresholds and cost share, so you can model a 90/10 declaration or a different
fiscal year without touching code.

**Auditing the rules.** Every rule is in `pa/rules.py` as readable data rather than
scattered through the code, and 83 tests in `tests/test_engine.py` pin the behaviour
with citations. If you disagree with how something is modeled, that file is where to
look and the tests are where to argue.

---

## Glossary

| Term | Meaning |
|---|---|
| **RPA** | Request for Public Assistance. The application. Due 30 days from designation — the first deadline and the one that ends the process if missed. |
| **RSM** | Recovery Scoping Meeting. Starts the 60-day Impact List clock. |
| **PDMG** | Program Delivery Manager. Your FEMA point of contact. |
| **Impact List** | The inventory of every damaged site. Also called the damage inventory. |
| **DDD** | Damage, Description and Dimensions. The narrative FEMA writes the scope of work from. |
| **SOW** | Scope of Work. What FEMA obligates against. Work outside it is not reimbursable. |
| **CRC** | Consolidated Resource Center. FEMA staff who validate scope and cost. |
| **SPA** | Streamlined Project Application. Required for emergency work and Cat-I. |
| **Force account** | Your own staff and equipment, as opposed to contracted work. |
| **Budgeted employee** | A regular, permanent employee. On emergency work, only their overtime is eligible. |
| **EHP** | Environmental and Historic Preservation review. Must finish before work starts. |
| **Obligation** | FEMA transferring funds to the state. Not the same as you being paid. |
| **Recipient / Subrecipient** | The state is the recipient; you are the subrecipient. |
| **SOD-FIR** | Statement of Documentation in Final Inspection Report. Large-project closeout. |
| **NSPO** | Net Small Project Overrun. The appeal route when small projects overrun in aggregate. |
| **RTM** | Recovery Transition Meeting. Held once version zero of all projects is obligated. |
| **Section 311** | The statutory NFIP reduction for an uninsured insurable building in a flood zone. Sized on policy limits, not damage. |
| **Section 406** | Hazard mitigation funded as part of a permanent work project. |
| **Section 428** | Alternative Procedures. Debris: straight-time labor, increased cost share, retained recycling revenue. Permanent work: a fixed-cost offer. |
| **Section 404 / HMGP** | The Hazard Mitigation Grant Program. Statewide, state-administered, separate from PA. |
| **CPPC** | Cost-plus-percentage-of-cost. A prohibited contract type. |
| **SFHA** | Special Flood Hazard Area. The mapped 1%-annual-chance floodplain. |

---

## Limits, cautions, and where the rules come from

**Built against** PAPPG V5 Amended (January 2025), FEMA Policy FP-104-23-001
(Simplified Procedures, January 2023), 44 CFR Part 206, 2 CFR Part 200, and the Disaster
Recovery Reform Act of 2018.

**Verify the thresholds.** The $4,100 minimum and $1,093,800 large-project threshold are
indexed annually. They are correct for the declaration this tool was built against; they
may not be current for yours. Set them on *Scenario → Ruleset*.

**The engine models rules, not judgement.** Whether damage was caused by the incident,
whether a grouping is sensible, and whether a cost is reasonable are decisions made with
your PDMG. The tool will not catch a well-formed lie.

**Known simplifications**

- The Section 428 debris sliding scale is applied at project level from one completion
  date. FEMA applies it to costs *incurred* inside each window, so real debris spanning
  windows is normally formulated as separate projects per window.
- NFIP limits used are the non-residential figures, because public facilities are
  non-residential. Residential limits are lower and are not modeled.
- Section 404 HMGP is deliberately out of scope — it is state-administered, statewide,
  and not tied to a specific declaration.
- Direct Administrative Costs are folded into Cat-Z rather than tracked separately.
- Cost shares are rounded per project, because that is the unit FEMA obligates. A
  portfolio total can therefore differ by a cent per project from the arithmetic on the
  total. That is correct.

**If you find a rule modeled wrongly**, the rule definitions are in `pa/rules.py` and
the tests are in `tests/test_engine.py`. One rule in this tool was wrong for a while —
Cat-A straight-time eligibility — and was caught by checking FEMA's own training
material rather than by trusting a summary document. Do the same with anything here that
does not match your experience.
