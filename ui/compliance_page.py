"""Compliance review: the four-part eligibility test and everything that voids a
project after the fact."""

from __future__ import annotations

import streamlit as st

from pa.validation import review
from .common import finding_block, get_scenario, purpose

_TEST_BLURB = {
    "Applicant": "Is the entity eligible to receive Public Assistance at all, and has "
                 "it given FEMA the policies needed to formulate costs?",
    "Facility": "Was the damaged thing in use, inside the declared area, and the "
                "applicant's legal responsibility at the time of the incident?",
    "Work": "Is the work required as a direct result of the declared incident, within "
            "the incident period, and not another federal agency's authority?",
    "Cost": "Is the cost documented if incurred, defensible if estimated, necessary, "
            "reasonable, and net of insurance?",
    "Procurement": "Federal procurement standards. This is where eligible work most "
                   "often gets de-obligated on audit.",
    "EHP": "Environmental and historic preservation. Consultation must finish before "
           "work starts.",
    "Insurance": "Insurance is the applicant's first means of funding, and "
                 "obtain-and-maintain requirements follow the award.",
    "Deadlines": "Regulatory deadlines running from the declaration and the RSM.",
    "Documentation": "Record retention and audit exposure.",
    "Mitigation": "Section 406 hazard mitigation eligibility.",
}


def render() -> None:
    s = get_scenario()
    st.title("Compliance Review")
    purpose("Compliance")
    st.write(
        "FEMA tests applicant, facility, work, and cost independently. A failure on "
        "any one of them ends the project regardless of how strong the other three "
        "are. Everything below the fold is a way of failing one of those four later, "
        "at closeout or on audit, which is the expensive way to find out."
    )

    result = review(s)
    errors, warnings = result.errors, result.warnings
    infos = [f for f in result.findings if f.severity == "info"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Blocking", len(errors))
    c2.metric("Caution", len(warnings))
    c3.metric("For awareness", len(infos))
    c4.metric("Status", "Clear" if result.passed else "Not submittable")

    if result.passed:
        st.success(
            "No blocking findings. Work the cautions before submission — they are "
            "what a Consolidated Resource Center reviewer will send back."
        )
    else:
        st.error(
            f"{len(errors)} blocking finding(s). Each one either makes a project "
            "ineligible or makes specific costs unallowable."
        )

    by_test = result.by_test()
    severity = st.radio(
        "Show", ["Blocking only", "Blocking and caution", "Everything"],
        index=1, horizontal=True,
    )
    keep = {
        "Blocking only": {"error"},
        "Blocking and caution": {"error", "warning"},
        "Everything": {"error", "warning", "info"},
    }[severity]

    order = ["Applicant", "Facility", "Work", "Cost", "Procurement",
             "EHP", "Insurance", "Mitigation", "Deadlines", "Documentation"]
    ordered = [t for t in order if t in by_test] + [
        t for t in by_test if t not in order]

    shown = False
    for test in ordered:
        findings = [f for f in by_test[test] if f.severity in keep]
        if not findings:
            continue
        shown = True
        counts = ", ".join(
            f"{sum(1 for f in findings if f.severity == sev)} {label.lower()}"
            for sev, label in (("error", "blocking"), ("warning", "caution"),
                               ("info", "note"))
            if any(f.severity == sev for f in findings)
        )
        with st.expander(f"**{test}** — {counts}", expanded=(test in ("Applicant", "Facility", "Work"))):
            if test in _TEST_BLURB:
                st.caption(_TEST_BLURB[test])
            finding_block(findings)

    if not shown:
        st.info("Nothing at this severity.")
