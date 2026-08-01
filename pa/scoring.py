"""Training-mode scoring.

The rubric grades the same things a FEMA Consolidated Resource Center reviewer and a
later auditor would grade, in roughly the order they cost the applicant money. It
works against any scenario -- there is no fixed answer key, because the engine
already knows the rules. A student's package is scored on whether it survives the
rules, not on whether it matches one instructor's solution.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .costing import summarize_all, summarize_project, summarize_scenario
from .export import documentation_checklist
from .formulation import classify, review_grouping
from .models import Project, Scenario
from .validation import ReviewResult, review


@dataclass
class Dimension:
    name: str
    weight: float
    score: float               # 0.0 - 1.0
    detail: str
    misses: list[str] = field(default_factory=list)

    @property
    def points(self) -> float:
        return round(self.score * self.weight, 1)


@dataclass
class Scorecard:
    dimensions: list[Dimension] = field(default_factory=list)
    review: ReviewResult | None = None
    #: False when there is no package to grade yet. Without this an empty scenario
    #: scores well, because every dimension with nothing to evaluate returns full
    #: credit -- zero contracts is a perfect procurement record.
    scorable: bool = True

    @property
    def total(self) -> float:
        return round(sum(d.points for d in self.dimensions), 1)

    @property
    def possible(self) -> float:
        return round(sum(d.weight for d in self.dimensions), 1)

    @property
    def percent(self) -> float:
        return round(100 * self.total / self.possible, 1) if self.possible else 0.0

    @property
    def grade(self) -> str:
        p = self.percent
        for cut, letter in ((93, "A"), (90, "A-"), (87, "B+"), (83, "B"), (80, "B-"),
                            (77, "C+"), (73, "C"), (70, "C-"), (60, "D")):
            if p >= cut:
                return letter
        return "F"


def _ratio(good: int, total: int) -> float:
    return 1.0 if total == 0 else round(good / total, 3)


def score(scenario: Scenario) -> Scorecard:
    r = review(scenario)
    if not scenario.projects:
        return Scorecard(review=r, scorable=False)

    card = Scorecard(review=r)
    by_test = r.by_test()

    def errors_in(*tests: str) -> list[str]:
        return [
            f"{f.subject + ': ' if f.subject else ''}{f.message}"
            for t in tests for f in by_test.get(t, []) if f.severity == "error"
        ]

    def warnings_in(*tests: str) -> list[str]:
        return [
            f"{f.subject + ': ' if f.subject else ''}{f.message}"
            for t in tests for f in by_test.get(t, []) if f.severity == "warning"
        ]

    # 1. Eligibility -- the four-part test. Any error here is fatal to a project,
    #    so it carries the most weight and is scored harshly.
    elig_errors = errors_in("Applicant", "Facility", "Work")
    elig_warn = warnings_in("Facility", "Work")
    n_checks = max(1, len(scenario.sites) * 4 + 4)
    elig_score = max(0.0, 1.0 - (len(elig_errors) * 0.25) - (len(elig_warn) * 0.05))
    card.dimensions.append(Dimension(
        "Eligibility — applicant, facility, work, cost", 25, round(elig_score, 3),
        f"{len(elig_errors)} disqualifying finding(s), {len(elig_warn)} caution(s) "
        f"across {len(scenario.sites)} site(s).",
        elig_errors + elig_warn,
    ))

    # 2. Project formulation -- grouping, thresholds, SPA routing.
    issues = review_grouping(scenario)
    form_errors = [i.message for i in issues if i.severity == "error"]
    form_warn = [i.message for i in issues if i.severity == "warning"]
    form_score = max(0.0, 1.0 - (len(form_errors) * 0.3) - (len(form_warn) * 0.1))
    sizes = [classify(p, scenario).size for p in scenario.projects]
    card.dimensions.append(Dimension(
        "Project formulation and thresholds", 18, round(form_score, 3),
        f"{len(scenario.projects)} project(s): "
        f"{sizes.count('Large')} large, {sizes.count('Small')} small, "
        f"{sizes.count('Below minimum')} below the minimum threshold.",
        form_errors + form_warn,
    ))

    # 3. Procurement.
    proc_errors = errors_in("Procurement")
    proc_warn = warnings_in("Procurement")
    contracts = sum(len(p.contracts()) for p in scenario.projects)
    proc_score = (
        1.0 if contracts == 0
        else max(0.0, 1.0 - (len(proc_errors) * 0.25) - (len(proc_warn) * 0.1))
    )
    card.dimensions.append(Dimension(
        "Procurement compliance", 15, round(proc_score, 3),
        f"{contracts} contract(s) reviewed; {len(proc_errors)} violation(s)."
        + ("" if contracts else " No contracts in this package."),
        proc_errors + proc_warn,
    ))

    # 4. Documentation completeness, measured against the per-category checklist.
    total_items = satisfied = 0
    doc_misses: list[str] = []
    for p in scenario.projects:
        for item, ok in documentation_checklist(p, scenario):
            total_items += 1
            if ok:
                satisfied += 1
            elif len(doc_misses) < 12:
                doc_misses.append(f"{p.title}: {item}")
    card.dimensions.append(Dimension(
        "Documentation and supporting records", 17, _ratio(satisfied, total_items),
        f"{satisfied} of {total_items} checklist items satisfied.",
        doc_misses,
    ))

    # 5. EHP and deadlines -- the two things that void otherwise-perfect packages.
    ehp_errors = errors_in("EHP", "Deadlines")
    ehp_warn = warnings_in("EHP", "Deadlines")
    ehp_score = max(0.0, 1.0 - (len(ehp_errors) * 0.4) - (len(ehp_warn) * 0.08))
    card.dimensions.append(Dimension(
        "EHP compliance and deadline management", 10, round(ehp_score, 3),
        f"{len(ehp_errors)} blocking issue(s), {len(ehp_warn)} pending review(s).",
        ehp_errors + ehp_warn,
    ))

    # 5b. Insurance and codes -- the reductions applied before the cost share, and
    #     the ones applicants most often fail to anticipate.
    ins_errors = errors_in("Insurance", "Codes and Standards")
    ins_warn = warnings_in("Insurance", "Codes and Standards")
    ins_score = max(0.0, 1.0 - (len(ins_errors) * 0.35) - (len(ins_warn) * 0.1))
    detail = f"{len(ins_errors)} blocking, {len(ins_warn)} caution."
    totals_preview = summarize_scenario(scenario)
    if totals_preview.section_311_reduction > 0:
        detail += (
            f" ${totals_preview.section_311_reduction:,.2f} lost to the Section 311 "
            "mandatory reduction."
        )
    card.dimensions.append(Dimension(
        "Insurance exposure and codes and standards", 10, round(ins_score, 3),
        detail, ins_errors + ins_warn,
    ))

    # 6. Did the applicant leave money on the table? Cat-Z, 406 mitigation, and the
    #    Section 428 debris election are the most commonly under-claimed sources.
    t = summarize_scenario(scenario)
    left: list[str] = []
    recovery = 1.0
    if t.management_cost_claimed == 0 and t.management_cost_cap > 0:
        left.append(
            f"No Cat-Z management costs claimed; up to ${t.management_cost_cap:,.2f} "
            "was available for grant administration time."
        )
        recovery -= 0.4

    debris_st_excluded = sum(
        cs.labor.straight_time_excluded
        for pid, cs in summarize_all(scenario).items()
        if (scenario.project_by_id(pid) or Project()).category.upper() == "A"
    )
    if debris_st_excluded > 0 and not scenario.applicant.section_428_debris_straight_time:
        left.append(
            f"${debris_st_excluded:,.2f} of straight-time debris labor is excluded "
            "because the Section 428 debris election was not made. Electing it also "
            "opens an increased federal cost share for accelerated completion."
        )
        recovery -= 0.4
    perm = [p for p in scenario.projects
            if p.category.upper() in scenario.rules.mitigation.eligible_categories]
    if perm and not any(p.mitigation for p in perm):
        left.append(
            f"{len(perm)} permanent work project(s) carry no Section 406 mitigation "
            "proposal. Mitigation up to 15% of project cost is approvable without "
            "further justification and protects the facility against the next event."
        )
        recovery -= 0.3
    donated_lost = sum(
        summarize_project(p, scenario).donated_credit_unused for p in scenario.projects
    )
    if donated_lost > 0:
        left.append(
            f"${donated_lost:,.2f} in donated resource value exceeds the applicant "
            "share on its project and is stranded. Donated resources credit against "
            "the non-federal share only — spreading them across projects captures more."
        )
        recovery -= 0.2
    card.dimensions.append(Dimension(
        "Maximizing eligible recovery", 5, max(0.0, round(recovery, 3)),
        "Funding available but not claimed." if left else
        "Management costs and mitigation opportunities addressed.",
        left,
    ))

    return card


#: Prompts an instructor can drop into an assignment. Each maps to something the
#: engine can check, so a student can self-assess before submitting.
REFLECTION_PROMPTS = [
    "Your Cat-B emergency protective measures project claims straight-time labor for "
    "budgeted employees. How much of it is eligible, and what would have to be true "
    "for that answer to change?",
    "One of your projects lands at $1.05M and another at $1.15M. Describe every way "
    "the administration of those two projects differs from here to closeout.",
    "You grouped four debris sites into one project totaling $3,900. What happens, and "
    "what are your options?",
    "A contractor quoted $290,000 for dike repair. What procurement method is required, "
    "and what has to be in the file before the invoice can be paid?",
    "Your city received $60,000 in flood insurance proceeds on a facility with $200,000 "
    "in eligible damage. Walk the federal share through to the applicant's out-of-pocket.",
    "Volunteers contributed 400 hours of sandbagging. Explain precisely what that is "
    "worth to the applicant, and why it is not simply added to the project cost.",
    "Work started on a streambank repair before EHP consultation was complete. What is "
    "the exposure, and what is the first thing you do?",
    "Estimate the Cat-Z management cost cap for your portfolio, and list the specific "
    "staff activities you would have tracked from day one to claim it.",
]
