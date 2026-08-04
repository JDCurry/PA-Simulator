"""Where am I, and what should I do next?

The rest of this package is organized around FEMA's data model -- scenarios, sites,
projects, cost lines. That is the right shape for the rules, and the wrong shape for
somebody who has never done this. A newcomer opening the app needs two things the
data model cannot give them: a sense of sequence, and a single concrete instruction.

This module supplies both. It reads the scenario and answers:

    progress()      -- the six working steps, each marked done / current / blocked
    next_action()   -- the ONE thing most worth doing right now, in plain language,
                       naming the page and the control to use
    is_untouched()  -- whether the user has actually started, so an empty form is not
                       reported as four blocking failures

Nothing here changes any calculation. It is a reading of state, kept separate so the
rules engine stays free of interface concerns.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .costing import summarize_all, summarize_scenario
from .models import CostType, Scenario
from .rules import CATEGORIES
from .validation import Finding, review

#: Which page a finding is fixed on. Findings know the rule they enforce; they do
#: not know the interface, so the mapping lives here.
FINDING_PAGE: dict[str, tuple[str, str]] = {
    "Applicant": ("Scenario", "Scenario, Applicant tab"),
    "Deadlines": ("Scenario", "Scenario, Disaster declaration tab"),
    "Facility": ("Impact List", "Impact List, Site detail tab"),
    "Work": ("Impact List", "Impact List, Site detail tab"),
    "EHP": ("Impact List", "Impact List, Site detail tab"),
    "Insurance": ("Impact List", "Impact List, Site detail tab"),
    "Cost": ("Cost Buildup", "Cost Buildup"),
    "Procurement": ("Cost Buildup", "Cost Buildup, Contracts and materials tab"),
    "Codes and Standards": ("Cost Buildup", "Cost Buildup, Codes and standards tab"),
    "Mitigation": ("Cost Buildup", "Cost Buildup, 406 Mitigation tab"),
    "Documentation": ("Package", "Package, Project detail tab"),
}


@dataclass
class Step:
    number: int
    title: str          # what the user is doing, in their words
    page: str           # the page it happens on
    fema_term: str      # what FEMA calls it, kept visible because it is the content
    purpose: str        # one plain sentence
    status: str         # "done" | "current" | "todo"
    detail: str = ""    # progress within the step

    @property
    def label(self) -> str:
        return f"{self.number} · {self.title}"


@dataclass
class NextAction:
    headline: str       # the instruction
    why: str            # why it matters, one sentence
    page: str           # page to navigate to
    where: str          # the control, spelled out
    severity: str = "info"   # "blocking" | "opportunity" | "info"


@dataclass
class Progress:
    steps: list[Step] = field(default_factory=list)
    completed: int = 0

    @property
    def total(self) -> int:
        return len(self.steps)

    @property
    def current(self) -> Step | None:
        return next((s for s in self.steps if s.status == "current"), None)

    @property
    def fraction(self) -> float:
        return self.completed / self.total if self.total else 0.0


def is_untouched(scenario: Scenario) -> bool:
    """True before the user has entered anything.

    An empty form is not a failing package. Reporting it as one teaches people to
    ignore the finding count, which is the one number they most need to trust.
    """
    return (
        not scenario.applicant.name.strip()
        and not scenario.sites
        and not scenario.projects
    )


def progress(scenario: Scenario) -> Progress:
    """The six working steps, with the first incomplete one marked current."""
    a, d = scenario.applicant, scenario.disaster
    sites, projects = scenario.sites, scenario.projects

    setup_done = bool(a.name.strip() and d.declaration_date)
    setup_detail = []
    if not a.name.strip():
        setup_detail.append("applicant name")
    if not d.declaration_date:
        setup_detail.append("declaration date")

    unassigned = scenario.unassigned_sites() if projects else sites
    grouped_done = bool(projects) and not unassigned

    def has_cost(p) -> bool:
        return bool(p.labor or p.equipment or p.costs or p.donated)

    priced = [p for p in projects if has_cost(p)]
    priced_done = bool(projects) and len(priced) == len(projects)

    result = review(scenario) if not is_untouched(scenario) else None
    blocking = len(result.errors) if result else 0
    clean_done = bool(projects) and blocking == 0

    from .export import documentation_checklist
    doc_total = doc_ok = 0
    for p in projects:
        for _, ok in documentation_checklist(p, scenario):
            doc_total += 1
            doc_ok += 1 if ok else 0
    package_done = bool(projects) and doc_total > 0 and doc_ok == doc_total

    specs = [
        (1, "Set up the disaster", "Scenario", "Scenario",
         "Tell the tool who you are and which declaration you are working under. "
         "Every deadline and dollar threshold comes from this.",
         setup_done,
         "Still needed: " + ", ".join(setup_detail) if setup_detail else "Ready."),
        (2, "List the damage", "Impact List", "Impact List / damage inventory",
         "Record every damaged site: what broke, where, and roughly what it costs.",
         bool(sites),
         f"{len(sites)} site(s) recorded." if sites else "No sites yet."),
        (3, "Group sites into projects", "Formulation", "Project formulation",
         "Combine sites into the units FEMA actually funds. Grouping decides whether "
         "costs clear the minimum and whether a project counts as large.",
         grouped_done,
         f"{len(projects)} project(s), {len(unassigned)} site(s) unassigned."
         if projects else "No projects yet."),
        (4, "Price the work", "Cost Buildup", "Cost buildup",
         "Enter labor, equipment, contracts, and materials. The tool applies the "
         "eligibility rules as you go.",
         priced_done,
         f"{len(priced)} of {len(projects)} project(s) have costs."
         if projects else "Group projects first."),
        (5, "Fix what FEMA would reject", "Compliance", "Compliance review",
         "Work the blocking findings until none are left. Each one would cost you "
         "money at obligation or on audit.",
         clean_done,
         f"{blocking} blocking finding(s) left." if projects
         else "Nothing to review yet."),
        (6, "Assemble the package", "Package", "Project application and closeout",
         "Confirm the supporting records exist, then export what you would submit.",
         package_done,
         f"{doc_ok} of {doc_total} documentation items confirmed."
         if doc_total else "Build projects first."),
    ]

    steps: list[Step] = []
    current_assigned = False
    for num, title, page, term, purpose, done, detail in specs:
        if done:
            status = "done"
        elif not current_assigned:
            status = "current"
            current_assigned = True
        else:
            status = "todo"
        steps.append(Step(num, title, page, term, purpose, status, detail))

    return Progress(steps=steps, completed=sum(1 for s in steps if s.status == "done"))


def _finding_action(f: Finding) -> NextAction:
    page, where = FINDING_PAGE.get(f.test, ("Compliance", "Compliance"))
    subject = f" ({f.subject})" if f.subject else ""
    return NextAction(
        headline=f"Fix a blocking {f.test.lower()} problem{subject}",
        why=f.remedy or f.message,
        page=page,
        where=where,
        severity="blocking",
    )


def next_action(scenario: Scenario) -> NextAction:
    """The single most valuable thing to do right now.

    Ordered by what actually costs the applicant: get the package to exist, then
    clear what would be rejected, then claim what is being left unclaimed.
    """
    if is_untouched(scenario):
        return NextAction(
            headline="Load the training scenario, or start your own disaster",
            why="Nothing is loaded yet. The training scenario is a worked example with "
                "deliberate errors in it, which is the fastest way to see how the "
                "program behaves.",
            page="Start",
            where="Start page, or the sidebar",
            severity="info",
        )

    prog = progress(scenario)
    step = prog.current

    # Steps 1 through 4: the package does not exist yet. Say so plainly.
    if step and step.number <= 4:
        return NextAction(
            headline=step.title,
            why=f"{step.purpose} {step.detail}".strip(),
            page=step.page,
            where=step.page,
            severity="info",
        )

    # Step 5: work the blocking findings, worst first.
    result = review(scenario)
    if result.errors:
        priority = ["Applicant", "Facility", "Work", "Procurement", "Insurance",
                    "Codes and Standards", "EHP", "Cost", "Deadlines"]
        ordered = sorted(
            result.errors,
            key=lambda f: priority.index(f.test) if f.test in priority else 99,
        )
        action = _finding_action(ordered[0])
        remaining = len(result.errors)
        if remaining > 1:
            action.why += f" ({remaining} blocking findings in total.)"
        return action

    # Nothing blocking. Point at money being left on the table.
    totals = summarize_scenario(scenario)
    if totals.management_cost_claimed == 0 and totals.management_cost_cap > 0:
        return NextAction(
            headline="Claim your Cat-Z management costs",
            why=f"Up to ${totals.management_cost_cap:,.2f} is available for the staff "
                "time spent administering this grant, and none is claimed. Applicants "
                "routinely forfeit it because nobody tracked the hours.",
            page="Formulation",
            where="Formulation, then add a Cat-Z project",
            severity="opportunity",
        )

    permanent = [
        p for p in scenario.projects
        if p.category.upper() in scenario.rules.mitigation.eligible_categories
    ]
    if permanent and not any(p.mitigation for p in permanent):
        return NextAction(
            headline="Add Section 406 mitigation to your permanent work",
            why=f"{len(permanent)} permanent work project(s) carry no mitigation. Up "
                "to 15 percent of the repair cost is approvable without further "
                "justification, and it protects the facility against the next event.",
            page="Cost Buildup",
            where="Cost Buildup, 406 Mitigation tab",
            severity="opportunity",
        )

    debris_excluded = sum(
        cs.labor.straight_time_excluded
        for pid, cs in summarize_all(scenario).items()
        if (scenario.project_by_id(pid) and
            scenario.project_by_id(pid).category.upper() == "A")
    )
    if debris_excluded > 0 and not scenario.applicant.section_428_debris_straight_time:
        return NextAction(
            headline="Consider electing Section 428 for debris",
            why=f"${debris_excluded:,.2f} of straight-time debris labor is being "
                "excluded. The election makes it eligible and can raise the federal "
                "share for fast completion.",
            page="Scenario",
            where="Scenario, Applicant tab",
            severity="opportunity",
        )

    if not prog.current:
        return NextAction(
            headline="Export your package",
            why="Every step is complete and nothing is blocking. Download the package "
                "and save your working file.",
            page="Package",
            where="Package, Export tab",
            severity="info",
        )

    return NextAction(
        headline=prog.current.title,
        why=f"{prog.current.purpose} {prog.current.detail}".strip(),
        page=prog.current.page,
        where=prog.current.page,
        severity="info",
    )


#: Plain-English purpose line for each page, shown at the top before the expert
#: framing. Someone who has never done this needs to know what a page is FOR before
#: they can care about how it works.
PAGE_PURPOSE: dict[str, str] = {
    "Start": "Where to begin, and what to do next.",
    "Scenario": "Who you are and which disaster you are claiming under. "
                "Everything else is calculated from this.",
    "Impact List": "Every damaged site, in one list. This is what FEMA calls your "
                   "damage inventory, and it is due 60 days after your scoping meeting.",
    "Formulation": "Combine sites into projects. A project is the unit FEMA funds, "
                   "and how you group them changes how much you get and how it is paid.",
    "Cost Buildup": "Price each project. Labor, equipment, contracts, materials — "
                    "with the eligibility rules applied as you type.",
    "Compliance": "Your package reviewed the way FEMA would review it, with a "
                  "citation for every problem found.",
    "Package": "What you would actually submit, plus the records you need on file.",
    "Training": "How you are doing, how the program works, and a suggested assignment.",
    "Manual": "The full user manual.",
}
