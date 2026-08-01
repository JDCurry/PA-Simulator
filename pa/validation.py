"""Eligibility and compliance review.

FEMA tests four things independently, and a failure on any one of them kills the
project regardless of how strong the other three are:

    APPLICANT — is the entity eligible to receive PA at all?
    FACILITY  — was the damaged thing in use, in the declared area, and the
                applicant's legal responsibility at the time of the incident?
    WORK      — is the work required as a direct result of the declared incident,
                within the incident period, and not another agency's authority?
    COST      — is the cost documented if incurred, defensible if estimated,
                necessary, reasonable, and net of insurance?

Everything else in this module -- procurement, EHP, deadlines, documentation -- is
a way of failing the COST or WORK test after the fact, at closeout or on audit,
which is the expensive way to find out.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from .costing import summarize_project, summarize_scenario
from .models import CostType, EmployeeClass, Project, Scenario, Site
from .rules import CATEGORIES, RuleSet, WorkType

__all__ = ["Finding", "ReviewResult", "review"]


SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


@dataclass
class Finding:
    severity: str          # error | warning | info
    test: str              # Applicant | Facility | Work | Cost | Procurement | EHP | ...
    message: str
    citation: str = ""
    subject: str = ""      # project or site title
    remedy: str = ""

    @property
    def rank(self) -> int:
        return SEVERITY_ORDER.get(self.severity, 3)


@dataclass
class ReviewResult:
    findings: list[Finding] = field(default_factory=list)

    def add(self, *args, **kwargs) -> None:
        self.findings.append(Finding(*args, **kwargs))

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "warning"]

    @property
    def passed(self) -> bool:
        return not self.errors

    def sorted(self) -> list[Finding]:
        return sorted(self.findings, key=lambda f: (f.rank, f.test, f.subject))

    def by_test(self) -> dict[str, list[Finding]]:
        out: dict[str, list[Finding]] = {}
        for f in self.sorted():
            out.setdefault(f.test, []).append(f)
        return out


# -- APPLICANT -----------------------------------------------------------------


def check_applicant(scenario: Scenario, r: ReviewResult) -> None:
    a = scenario.applicant
    who = a.name or "Applicant"

    if not a.name:
        r.add("error", "Applicant", "No applicant name recorded.", subject=who,
              remedy="Set the applicant on the Scenario page.")
    if not a.fips:
        r.add("warning", "Applicant",
              "No applicant FIPS recorded. FEMA identifies applicants by FIPS, not "
              "by name — every submission and payment references it.",
              subject=who)

    for flag, label, why in (
        (a.has_pay_policy, "pay policy",
         "FEMA cannot formulate force account labor without the written pay policy "
         "that establishes straight-time and overtime rates and who is eligible for "
         "overtime."),
        (a.has_procurement_policy, "procurement policy",
         "Contract costs cannot be validated without the adopted procurement policy. "
         "Failure to follow proper procurement can jeopardize funding for the entire "
         "contract."),
        (a.has_insurance_policy, "insurance policy",
         "Insurance is the applicant's first means of funding; FEMA must see the "
         "policy to determine what proceeds reduce eligible cost."),
    ):
        if not flag:
            r.add("error", "Applicant", f"Missing {label}. {why}",
                  citation="PAPPG V5 p.78, 92, 220", subject=who,
                  remedy=f"Submit the {label} to the PDMG.")

    if not a.nfip_participating and any(
        p.category.upper() == "I" for p in scenario.projects
    ):
        r.add("error", "Applicant",
              "Communities suspended from or sanctioned under the National Flood "
              "Insurance Program are ineligible for Cat-I Building Code and "
              "Floodplain Management Enforcement funding.",
              citation="PAPPG V5 p.221", subject=who)

    # Private non-profits providing non-critical essential social services must
    # exhaust the SBA before PA will fund permanent work.
    if a.is_noncritical_pnp:
        has_permanent = any(
            (CATEGORIES.get(p.category.upper()) or None)
            and CATEGORIES[p.category.upper()].work_type is WorkType.PERMANENT
            for p in scenario.projects
        )
        if has_permanent and not a.sba_application_filed:
            r.add("error", "Applicant",
                  "This applicant is a private non-profit providing non-critical but "
                  "essential social services, and it has permanent work projects. It "
                  "must apply to the Small Business Administration FIRST. PA is "
                  "available only for what SBA declines to cover.",
                  citation="PAPPG V5 p.53", subject=who,
                  remedy="File the SBA disaster loan application and record the "
                         "outcome before pursuing permanent work under PA.")
        elif has_permanent and a.sba_application_filed and not a.sba_declined:
            r.add("warning", "Applicant",
                  "SBA application filed but no decline recorded. PA permanent work "
                  "funding for a non-critical PNP is limited to what SBA does not "
                  "cover, so the decline letter is what unlocks it.",
                  citation="PAPPG V5 p.53", subject=who)

    if a.section_428_debris_straight_time:
        r.add("info", "Cost",
              "Section 428 alternative procedures elected for debris removal. "
              "Straight-time force account labor is eligible for budgeted employees "
              "on eligible Cat-A work, an increased federal share applies on a sliding "
              "scale for accelerated completion, and recycling revenue may be retained.",
              citation="PAPPG V5 p.160, Appendix G", subject=who)
    elif any(p.category.upper() == "A" for p in scenario.projects):
        from .costing import summarize_all
        excluded = sum(
            cs.labor.straight_time_excluded
            for pid, cs in summarize_all(scenario).items()
            if (scenario.project_by_id(pid) or Project()).category.upper() == "A"
        )
        if excluded > 0:
            r.add("warning", "Cost",
                  f"${excluded:,.2f} of straight-time debris labor is being excluded "
                  "because the Section 428 alternative procedure for debris removal "
                  "was not elected. Electing it makes that labor eligible and can also "
                  "raise the federal share. The election is made per disaster and is "
                  "worth evaluating against actual force account hours.",
                  citation="PAPPG V5 p.160, Appendix G", subject=who,
                  remedy="Discuss the Section 428 debris election with the PDMG "
                         "before the window closes.")


# -- FACILITY and WORK ---------------------------------------------------------


def check_site(site: Site, scenario: Scenario, r: ReviewResult) -> None:
    subject = site.name or site.id
    d = scenario.disaster

    if not site.in_use_at_time_of_disaster:
        r.add("error", "Facility",
              "The facility was not in use at the time of the declared incident. "
              "An inactive or abandoned facility is not an eligible facility.",
              citation="PAPPG V5 p.61", subject=subject)
    if not site.applicant_legal_responsibility:
        r.add("error", "Facility",
              "The damaged infrastructure is not owned by, or the legal "
              "responsibility of, the applicant. Legal responsibility must have "
              "existed at the time of the incident — acquiring it afterward does not "
              "create eligibility.",
              citation="PAPPG V5 p.61", subject=subject)
    if not site.within_declared_area:
        r.add("error", "Facility",
              "The damage is outside the federally designated disaster area.",
              subject=subject)
    if not site.actively_used_and_maintained:
        r.add("warning", "Facility",
              "Facility is not actively used and maintained. Permanent work requires "
              "it; deferred maintenance damage is not disaster damage and FEMA will "
              "separate the two.",
              citation="PAPPG V5 p.167", subject=subject)
    if site.other_federal_agency_authority:
        r.add("error", "Work",
              "This work falls under the specific authority of another federal "
              "agency (for example FHWA Emergency Relief or NRCS EWP). PA is not "
              "available for work eligible under another federal program, and "
              "claiming it in both places is a duplication of benefits.",
              citation="PAPPG V5 p.62", subject=subject)

    if not site.damage_description or len(site.damage_description.strip()) < 40:
        r.add("warning", "Work",
              "The damage description is too thin to formulate a scope from. FEMA "
              "writes the Damage, Description and Dimensions from this text — state "
              "what was damaged, how the incident caused it, and quantify it.",
              subject=subject,
              remedy="Include component, quantity, dimension, and causal mechanism.")

    if not site.primary_cause:
        r.add("warning", "Work", "No primary cause of damage recorded.", subject=subject)
    elif d.incident_types and site.primary_cause not in d.incident_types:
        r.add("warning", "Work",
              f"Primary cause '{site.primary_cause}' is not among the declared "
              f"incident types ({', '.join(d.incident_types)}). Damage must be a "
              "direct result of the declared incident.",
              subject=subject)

    if site.work_start_date and d.incident_start and d.incident_end:
        if not d.within_incident_period(site.work_start_date):
            # Emergency work legitimately continues past the incident period; the
            # DAMAGE must fall inside it, not necessarily the repair.
            cat = CATEGORIES.get(site.category.upper())
            sev = "info" if cat and cat.work_type is WorkType.PERMANENT else "warning"
            r.add(sev, "Work",
                  f"Work began {site.work_start_date:%b %d, %Y}, outside the incident "
                  f"period ({d.incident_start:%b %d} – {d.incident_end:%b %d, %Y}). "
                  "That is normal for repairs, but the DAMAGE must have occurred "
                  "within the incident period and the record must show that.",
                  subject=subject)

    if site.latitude is not None and not (-90 <= site.latitude <= 90):
        r.add("warning", "Facility",
              f"Latitude {site.latitude} is out of range — likely a transcription "
              "error. Site coordinates drive EHP review and inspection scheduling.",
              subject=subject)
    if site.longitude is not None and site.longitude > 0 and (site.state or "").upper() == "WA":
        r.add("warning", "Facility",
              f"Longitude {site.longitude} is positive but the site is in Washington; "
              "west-hemisphere longitudes are negative. Check the sign.",
              subject=subject)

    # Section 311: the reduction applicants do not see coming.
    ins = scenario.rules.insurance
    if (site.is_insurable_building and site.in_special_flood_hazard_area
            and "flood" in (site.primary_cause or "").lower()):
        if site.sfha_designated_years < ins.sfha_designated_min_years:
            r.add("info", "Insurance",
                  f"Insurable building in an SFHA damaged by flood, but the SFHA has "
                  f"been identified for {site.sfha_designated_years:g} year(s), under "
                  f"the {ins.sfha_designated_min_years}-year threshold. The Section 311 "
                  "mandatory reduction does not apply. Verify the SFHA designation date.",
                  citation="44 CFR 206.252", subject=subject)
        elif site.flood_insurance_in_force <= 0:
            reduction = ins.section_311_reduction(
                site.building_value, site.contents_value, 0.0)
            if reduction > 0:
                r.add("error", "Insurance",
                      f"Section 311 mandatory reduction of ${reduction:,.2f}. This is "
                      "an insurable building in a Special Flood Hazard Area, damaged "
                      "by flood, with no flood insurance in force. FEMA must reduce "
                      "eligible cost by the maximum proceeds a standard NFIP policy "
                      "would have paid — whether or not a policy was ever purchased. "
                      "This is statutory and cannot be appealed away.",
                      citation="Stafford Act Sec. 311; 44 CFR 206.252", subject=subject,
                      remedy="Confirm the flood zone and the building and contents "
                             "values. Then obtain flood insurance before the next "
                             "event, because the reduction repeats every time.")
            else:
                r.add("warning", "Insurance",
                      "Insurable building in an SFHA damaged by flood with no flood "
                      "insurance, but no building or contents value is recorded, so "
                      "the Section 311 reduction cannot be sized. Enter the values — "
                      "FEMA will compute this reduction whether or not you do.",
                      citation="44 CFR 206.252", subject=subject)
        elif site.flood_insurance_in_force < ins.max_available_proceeds:
            gap = ins.section_311_reduction(
                site.building_value, site.contents_value, site.flood_insurance_in_force)
            if gap > 0:
                r.add("warning", "Insurance",
                      f"Underinsured for flood by ${gap:,.2f} against the maximum "
                      "standard NFIP proceeds. The Section 311 reduction applies to "
                      "the shortfall, not just to an outright absence of coverage.",
                      citation="44 CFR 206.252", subject=subject)

    if (site.is_insurable_building and site.in_special_flood_hazard_area
            and not site.obtain_and_maintain_acknowledged):
        r.add("warning", "Insurance",
              "Obtain-and-maintain has not been acknowledged. Accepting PA funding "
              "for this facility obligates the applicant to carry insurance for the "
              "peril that caused the damage, in at least the amount of the disaster "
              "damage, for the life of the facility. Letting it lapse makes the "
              "facility ineligible in the next disaster.",
              citation="PAPPG V5 p.220", subject=subject)

    if site.insured and site.total_insurance_offset <= 0:
        r.add("warning", "Cost",
              "Site is marked insured but no actual or anticipated proceeds are "
              "recorded. Both reduce eligible cost, and FEMA will deduct an "
              "anticipated amount whether or not the applicant has claimed it.",
              citation="PAPPG V5 p.220", subject=subject)
    if site.in_special_flood_hazard_area:
        r.add("info", "Insurance",
              "Site is in a Special Flood Hazard Area. Additional insurance "
              "requirements apply, and the applicant must obtain and maintain "
              "coverage for the peril that caused the damage, in at least the amount "
              "of the disaster damage, as a condition of funding.",
              citation="PAPPG V5 p.220", subject=subject)


# -- EHP -----------------------------------------------------------------------


def check_ehp(site: Site, scenario: Scenario, r: ReviewResult) -> None:
    subject = site.name or site.id
    ehp = scenario.rules.ehp
    triggered = [(k, desc) for k, desc in ehp.triggers if site.ehp_flags.get(k)]

    if (site.structure_age_years or 0) >= ehp.historic_structure_age_years:
        triggered.append((
            "historic_structure",
            f"Structure is {site.structure_age_years} years old (screening age "
            f"{ehp.historic_structure_age_years}) — NHPA Section 106 review",
        ))

    if triggered and site.ehp_consultation_complete:
        r.add("info", "EHP",
              f"{len(triggered)} environmental or historic trigger(s) identified and "
              "consultation recorded as complete"
              + (f": {site.ehp_resolution_note}" if site.ehp_resolution_note else ".")
              + " Keep the permits and agency correspondence in the project file — "
              "FEMA requires copies of all of them.",
              citation="PAPPG V5 p.69", subject=subject)
        return

    for _, desc in triggered:
        r.add("warning", "EHP", desc,
              citation="PAPPG V5 p.69, 182, 234", subject=subject,
              remedy="Raise with FEMA EHP before work proceeds. Obtaining permits is "
                     "the applicant's responsibility and they must be issued before "
                     "site activity begins.")

    if triggered and site.percent_complete > 0:
        r.add("error", "EHP",
              "Work has already started on a site with an unresolved EHP trigger. "
              "FEMA's environmental and historic consultation must be complete before "
              "work begins; starting early can render the entire project ineligible.",
              citation="PAPPG V5 p.69", subject=subject,
              remedy="Stop work and notify the PDMG. Document the sequence of events "
                     "and any emergency exigency that justified proceeding, then "
                     "record the consultation as complete once EHP signs off.")


# -- COST and PROCUREMENT ------------------------------------------------------


def check_project_costs(project: Project, scenario: Scenario, r: ReviewResult) -> None:
    subject = project.title or project.id
    rules = scenario.rules
    cat = CATEGORIES.get(project.category.upper())
    cs = summarize_project(project, scenario)

    if cat is None:
        r.add("error", "Work", f"Unknown work category '{project.category}'.",
              subject=subject)
        return

    if cs.labor.straight_time_excluded > 0:
        r.add("warning", "Cost",
              f"${cs.labor.straight_time_excluded:,.2f} of straight-time labor is "
              f"claimed on a Cat-{cat.code} project and is not eligible. "
              + cs.labor.exclusion_reason,
              citation=f"PAPPG V5 p.{cat.pappg_page}", subject=subject)

    if cs.equipment.standby_excluded > 0:
        r.add("warning", "Cost",
              f"${cs.equipment.standby_excluded:,.2f} of standby equipment time is "
              "recorded and excluded. Equipment must be in actual operation "
              "performing eligible work to be reimbursable.",
              citation="44 CFR 206.228", subject=subject)

    for note in cs.equipment.notes:
        r.add("info", "Cost", note, subject=subject)

    for c in project.costs:
        if c.cost_type is not CostType.CONTRACT:
            continue
        label = c.description or c.vendor or c.id
        method = rules.procurement_method(c.total)

        if c.cost_plus_percentage_of_cost:
            r.add("error", "Procurement",
                  f"Contract '{label}' is a cost-plus-percentage-of-cost contract. "
                  "These are explicitly prohibited for non-state entities by federal "
                  "procurement standards because they reward the contractor for "
                  "driving costs up. The associated costs are ineligible.",
                  citation="2 CFR 200.324(d)", subject=subject,
                  remedy="Have counsel and procurement staff re-read the contract; "
                         "CPPC provisions are often buried and hard to spot.")

        if not c.sam_debarment_checked:
            r.add("error", "Procurement",
                  f"Contract '{label}' has no documented SAM.gov debarment check. The "
                  "applicant must confirm the contractor is not debarred and place "
                  "the documentation in the project file.",
                  citation="2 CFR 200.214", subject=subject,
                  remedy="Run the vendor at sam.gov and file the screenshot or record.")

        if c.total >= rules.thresholds.micro_purchase and not c.competed:
            r.add("error", "Procurement",
                  f"Contract '{label}' at ${c.total:,.2f} exceeds the "
                  f"${rules.thresholds.micro_purchase:,.0f} micro-purchase threshold "
                  f"but is not documented as competed. Required method: {method}.",
                  citation="2 CFR 200.320", subject=subject)
        elif c.total >= rules.thresholds.micro_purchase:
            r.add("info", "Procurement",
                  f"Contract '{label}' at ${c.total:,.2f} — required method: {method}.",
                  subject=subject)

        if not c.prevailing_wage_paid:
            r.add("warning", "Procurement",
                  f"Contract '{label}' does not record payment of state prevailing "
                  "wages. Washington requires prevailing wage on public works "
                  "contracts. Note that Davis-Bacon does NOT apply to PA projects — "
                  "the state requirement is the operative one.",
                  subject=subject)

    for d in project.donated:
        if not d.rate_basis:
            r.add("warning", "Cost",
                  f"Donated resource '{d.description or d.id}' has no documented "
                  "valuation basis. Donated labor is valued at the rate for "
                  "equivalent work in the applicant's area, and the basis has to be "
                  "in the file.",
                  citation="PAPPG V5 p.105", subject=subject)

    if cs.donated_credit_unused > 0:
        r.add("info", "Cost",
              f"${cs.donated_credit_unused:,.2f} of donated resource value exceeds "
              "the applicant's non-federal share for this project and cannot be "
              "credited. Donated resources offset the applicant's share only — they "
              "never increase the federal contribution.",
              citation="PAPPG V5 p.105", subject=subject)

    if project.project_option in ("Improved", "Alternate") and not project.state_written_approval:
        r.add("error", "Cost",
              f"This is an {project.project_option} Project but there is no written "
              "approval from the state recipient on file. Written approval must be "
              "obtained BEFORE proceeding with the work, and requested in writing "
              "within 12 months of the Recovery Scoping Meeting.",
              citation="PAPPG V5 p.184-185", subject=subject)

    if project.mitigation and cat.code not in rules.mitigation.eligible_categories:
        r.add("warning", "Mitigation",
              f"Section 406 mitigation proposals are attached to a Cat-{cat.code} "
              "project, but 406 mitigation is available only on permanent work "
              f"(Cat-{'/'.join(rules.mitigation.eligible_categories)}). Consider the "
              "Section 404 Hazard Mitigation Grant Program instead — it is "
              "state-administered, statewide, and not tied to this declaration.",
              citation="PAPPG V5 p.178", subject=subject)

    # Codes and standards: the five-part test.
    from .costing import eligible_codes_and_standards
    _, excluded, cs_notes = eligible_codes_and_standards(project, rules)
    criteria = rules.codes_and_standards.criteria
    for standard in project.codes_and_standards:
        if standard.upgrade_cost <= 0:
            continue        # nothing claimed, nothing to test
        failing = standard.failing(criteria)
        label = standard.description or standard.citation or standard.id
        if failing:
            r.add("error", "Codes and Standards",
                  f"'{label}': ${standard.upgrade_cost:,.2f} of code-driven upgrade is "
                  f"not eligible. A code or standard must satisfy all five criteria; "
                  f"this one fails {len(failing)} — {'; '.join(failing)}.",
                  citation="PAPPG V5 p.168; 44 CFR 206.226(d)", subject=subject,
                  remedy="Either document the missing criteria, or fund the upgrade "
                         "outside the grant as an Improved Project.")

    if project.fixed_cost_offer_accepted:
        r.add("info", "Cost",
              f"Section 428 fixed-cost offer of ${project.fixed_cost_offer:,.2f} "
              "accepted. The award is capped at that figure regardless of actual "
              "cost — the applicant carries the overrun risk in exchange for scope "
              "flexibility and the ability to move funds across its alternative "
              "procedures projects.",
              citation="PAPPG V5 p.160, Appendix G", subject=subject)
    elif project.fixed_cost_offer > 0:
        r.add("warning", "Cost",
              f"A Section 428 fixed-cost offer of ${project.fixed_cost_offer:,.2f} is "
              "recorded but not marked accepted, so standard procedures apply and the "
              "offer has no effect on this project's funding.",
              subject=subject)

    if not project.scope_of_work.strip():
        r.add("warning", "Documentation",
              "No scope of work recorded. The SOW is what FEMA obligates against; "
              "work outside it is not reimbursable.",
              subject=subject)


# -- DEADLINES -----------------------------------------------------------------


def check_deadlines(scenario: Scenario, r: ReviewResult, today: date | None = None) -> None:
    d = scenario.disaster
    today = today or date.today()
    if not d.declaration_date:
        r.add("warning", "Deadlines",
              "No declaration date recorded — every work deadline is computed from it.")
        return

    # The RPA is the first deadline and the one that ends the process if missed.
    rpa_due = (d.designation_date or d.declaration_date) + timedelta(
        days=scenario.rules.deadlines.rpa_days_from_designation
    )
    if d.rpa_submitted_date:
        if d.rpa_submitted_date > rpa_due:
            r.add("error", "Deadlines",
                  f"Request for Public Assistance submitted {d.rpa_submitted_date:%b %d, %Y}, "
                  f"after the {rpa_due:%b %d, %Y} deadline "
                  f"({scenario.rules.deadlines.rpa_days_from_designation} days from "
                  "designation). A late RPA requires a documented justification and "
                  "may be denied outright.",
                  citation="44 CFR 206.202(c)")
        else:
            r.add("info", "Deadlines",
                  f"Request for Public Assistance submitted "
                  f"{d.rpa_submitted_date:%b %d, %Y}, within the deadline.")
    else:
        days = (rpa_due - today).days
        sev = "error" if days < 0 else ("warning" if days <= 10 else "info")
        r.add(sev, "Deadlines",
              f"No Request for Public Assistance recorded. The RPA is due "
              f"{rpa_due:%b %d, %Y}"
              + (f" — {abs(days)} days ago." if days < 0 else f", in {days} days.")
              + " Nothing downstream of it exists until it is filed and approved.",
              citation="44 CFR 206.202(c)",
              remedy="File the RPA in the FEMA Grants Portal.")

    resolved = scenario.rules.deadlines.resolve(
        d.declaration_date, d.rsm_date, d.designation_date)
    labels = {
        "rpa": "Request for Public Assistance",
        "impact_list": "Impact List submission",
        "emergency_work": "Emergency Work (Cat A–B) completion",
        "permanent_work": "Permanent Work (Cat C–G) completion",
        "code_enforcement": "Cat-I Building Code & Floodplain Management completion",
        "improved_alternate_request": "Improved / Alternate Project written request",
    }
    extendable = scenario.rules.deadlines.extendable

    for key, when in sorted(resolved.items(), key=lambda kv: kv[1]):
        if key == "rpa":
            continue        # reported above, with submission status
        days = (when - today).days
        label = labels.get(key, key)
        ext = (
            "Time extensions may be granted for extenuating circumstances, submitted "
            "through the recipient."
            if key in extendable
            else "NO time extensions are permitted for this deadline."
        )
        if days < 0:
            r.add("error", "Deadlines",
                  f"{label} deadline passed {abs(days)} days ago "
                  f"({when:%b %d, %Y}). {ext}",
                  citation="PAPPG V5 p.247")
        elif days <= 60:
            r.add("warning", "Deadlines",
                  f"{label} is due in {days} days ({when:%b %d, %Y}). {ext}",
                  citation="PAPPG V5 p.247")
        else:
            r.add("info", "Deadlines",
                  f"{label}: {when:%b %d, %Y} ({days} days out). {ext}")


# -- portfolio-level -----------------------------------------------------------


def check_portfolio(scenario: Scenario, r: ReviewResult) -> None:
    t = summarize_scenario(scenario)
    rules = scenario.rules

    if t.management_cost_claimed > t.management_cost_cap:
        r.add("error", "Cost",
              f"Cat-Z management costs of ${t.management_cost_claimed:,.2f} exceed the "
              f"{rules.management.applicant_cap_rate:.0%} cap of "
              f"${t.management_cost_cap:,.2f} on the applicant's total obligated "
              f"amount (${t.net_eligible:,.2f}). The excess is not reimbursable.",
              citation="PAPPG V5 p.74")
    elif t.management_cost_claimed == 0 and t.net_eligible > 0:
        r.add("info", "Cost",
              f"No Cat-Z management costs claimed. Up to "
              f"${t.management_cost_cap:,.2f} "
              f"({rules.management.applicant_cap_rate:.0%} of the total obligated "
              "amount) is available for the staff time spent gathering documentation, "
              "attending site visits, submitting for payment, and assembling "
              "closeout. Costs must be actual and auditable — track time and effort "
              "from the start of the grant, not at the end.",
              citation="PAPPG V5 p.74")

    if t.section_311_reduction > 0:
        pct = (
            f" — {t.section_311_reduction / t.gross_eligible:.1%} of gross eligible cost"
            if t.gross_eligible > 0 else ""
        )
        r.add("error", "Insurance",
              f"${t.section_311_reduction:,.2f} in Section 311 mandatory reductions "
              f"across the portfolio{pct}, removed before the cost share is even "
              "applied. This is the single largest avoidable loss in the PA program, "
              "and it recurs in every future flood until the coverage is in place.",
              citation="Stafford Act Sec. 311; 44 CFR 206.252")

    if t.donated_credit_unused > 0:
        r.add("info", "Cost",
              f"${t.donated_credit_unused:,.2f} of donated resource value exceeds the "
              "applicant share it can offset. For emergency work the credit is pooled "
              "across all Cat-A and Cat-B projects before the cap applies, so this is "
              "the true surplus, not a per-project artifact.",
              citation="PAPPG V5 p.105")

    r.add("info", "Cost",
          f"The state recipient has a separate management cost allowance of up to "
          f"${t.recipient_management_cost_cap:,.2f} "
          f"({scenario.rules.management.recipient_cap_rate:.0%} of the total obligated "
          f"amount), on top of the applicant's "
          f"{scenario.rules.management.applicant_cap_rate:.0%}. DRRA Sec. 1215 sets a "
          f"combined {scenario.rules.management.combined_cap_rate:.0%}. That is not "
          "the applicant's money, but it is what funds the state PA staff supporting "
          "this grant.",
          citation="DRRA Sec. 1215; PAPPG V5 p.74")

    r.add("info", "Documentation",
          f"Appeals: {scenario.rules.appeals.first_appeal_days} days from receipt of a "
          f"Determination Memo for a first appeal, and another "
          f"{scenario.rules.appeals.second_appeal_days} days from the first appeal "
          f"decision for a second. For disputes at or above "
          f"${t.arbitration_threshold:,.0f}, arbitration is available in lieu of a "
          "second appeal.",
          citation="PAPPG V5 p.42, 254; DRRA Sec. 1219")

    if t.single_audit_triggered:
        r.add("info", "Documentation",
              f"Federal share of ${t.federal_share:,.2f} meets or exceeds the "
              f"${rules.thresholds.single_audit:,.0f} Single Audit Act threshold for "
              "federal funds expended in a fiscal year. A single audit will be "
              "required.",
              citation="2 CFR 200 Subpart F")

    r.add("info", "Documentation",
          f"Retain all original documents and provide only copies to FEMA. Federal "
          f"retention is {rules.documentation.federal_retention_years} years from "
          f"RECIPIENT closeout — not applicant closeout — and Washington requires "
          f"{rules.documentation.state_retention_years} years.",
          citation="2 CFR 200.334")


# -- entry point ---------------------------------------------------------------


def review(scenario: Scenario, today: date | None = None) -> ReviewResult:
    r = ReviewResult()
    check_applicant(scenario, r)
    for site in scenario.sites:
        check_site(site, scenario, r)
        check_ehp(site, scenario, r)
    for project in scenario.projects:
        check_project_costs(project, scenario, r)
    check_deadlines(scenario, r, today=today)
    check_portfolio(scenario, r)
    return r
