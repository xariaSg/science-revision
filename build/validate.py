"""Mechanical rubric checks (plan section 1e, CLAUDE.md section 3.4).

These catch the rubric bugs that are checkable without judgement. They do not tell
you a rubric is *right* -- only that it is not obviously wrong. Human review is
still the gate.

The facet rule is the interesting one. A 2-3 mark question is meant to award marks
for addressing different facets: identify the change, cite the evidence, state the
consequence. Two `result` keypoints on a 2-mark question usually means one point was
split in half rather than two genuine points found, so it is flagged.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RUBRIC_DIR = REPO / "rubrics"

FACETS = {"variable", "action", "result"}


def check_rubric(rubric: dict) -> list[str]:
    label = f"{rubric['question_id']}({rubric['part'] or '-'})"
    problems: list[str] = []
    chains = rubric.get("chains") or []

    # Some questions are answered by drawing on the paper — 2025 Q35 says "use a
    # pencil to complete the circuit". They cannot be spoken, cannot be graded from
    # a transcript, and must not sit in the queue looking like missing work.
    if rubric.get("response_mode") == "drawn":
        if chains:
            problems.append(f"{label}: marked response_mode=drawn but has chains")
        return problems

    if not chains:
        return [f"{label}: no chains authored"]

    marks = rubric.get("marks")
    if marks is None:
        problems.append(f"{label}: no mark allocation")

    keypoints = [kp for chain in chains for kp in chain.get("keypoints", [])]
    if not keypoints:
        problems.append(f"{label}: chains present but no keypoints")
        return problems

    # How marks map onto the rubric differs by question shape, so it is recorded
    # rather than inferred:
    #   per_keypoint — each link is a mark. "State two functions of roots" [2] is
    #                  two independent points; a 3-mark explanation is three links.
    #   per_chain    — each completed route is a mark. 2024 Q32(c) [2] reaches the
    #                  same conclusion through food and through dissolved oxygen,
    #                  and each route earns one mark however many links it has.
    mark_model = rubric.get("mark_model", "per_keypoint")
    required = rubric.get("chains_required") or 1
    if mark_model not in {"per_keypoint", "per_chain"}:
        problems.append(f"{label}: unknown mark_model {mark_model!r}")
    elif marks is not None:
        if mark_model == "per_keypoint":
            if len(keypoints) != marks:
                problems.append(
                    f"{label}: {len(keypoints)} keypoints for {marks} marks "
                    f"(mark_model=per_keypoint)")
        else:
            if len(chains) != marks:
                problems.append(
                    f"{label}: {len(chains)} chains for {marks} marks "
                    f"(mark_model=per_chain)")
            if required != len(chains):
                problems.append(
                    f"{label}: chains_required={required} but {len(chains)} chains "
                    f"are defined; per_chain marking needs every route")

    for keypoint in keypoints:
        facet = keypoint.get("facet")
        if facet not in FACETS:
            problems.append(f"{label}: keypoint {keypoint.get('kp_id')} has facet "
                            f"{facet!r}, expected one of {sorted(FACETS)}")
        if not keypoint.get("statement", "").strip():
            problems.append(f"{label}: keypoint {keypoint.get('kp_id')} has no statement")

    # Two `result` keypoints on a 2-mark question usually means one point was split
    # in half rather than two genuine points found. Only meaningful when each
    # keypoint is a mark: a per_chain rubric's links are diagnostic, not marks.
    if marks and marks > 1 and mark_model == "per_keypoint":
        for chain in chains:
            facets = {kp.get("facet") for kp in chain.get("keypoints", [])}
            if len(chain.get("keypoints", [])) > 1 and len(facets) == 1:
                problems.append(
                    f"{label}: chain '{chain.get('chain_id')}' awards {marks} marks "
                    f"all on facet {facets.pop()!r} — likely one point split in two")

    for chain in chains:
        positions = [kp.get("position") for kp in chain.get("keypoints", [])]
        if positions != sorted(positions) or len(set(positions)) != len(positions):
            problems.append(f"{label}: chain '{chain.get('chain_id')}' positions "
                            f"{positions} are not a clean ordering")

    # The contextual gate needs something specific to test an answer against. Some
    # questions have no scenario at all -- "state two functions of roots" asks for
    # general knowledge, and there is nothing to anchor to. Those declare
    # context_gate "general" and are exempt; everything else must name its entities,
    # or a memorised recital would pass the gate.
    gate = rubric.get("context_gate", "anchored")
    if gate not in {"anchored", "general"}:
        problems.append(f"{label}: unknown context_gate {gate!r}")
    if gate == "anchored" and not rubric.get("scenario_anchors") and (marks or 0) > 1:
        problems.append(f"{label}: no scenario anchors — the contextual gate needs at "
                        f"least one specific entity from the question")

    # An `accepts` entry that merely restates the statement adds nothing and hides
    # how much genuine paraphrase the rubric tolerates.
    for keypoint in keypoints:
        statement = keypoint.get("statement", "").strip().lower()
        for alt in keypoint.get("accepts", []):
            if alt.strip().lower() == statement:
                problems.append(f"{label}: keypoint {keypoint.get('kp_id')} lists an "
                                f"`accepts` identical to its statement")

    ids = [kp.get("kp_id") for kp in keypoints]
    if len(set(ids)) != len(ids):
        problems.append(f"{label}: duplicate keypoint ids {ids}")

    return problems


def validate_file(path: Path) -> tuple[int, int, list[str]]:
    data = json.loads(path.read_text())
    problems: list[str] = []
    authored = 0
    for rubric in data["rubrics"]:
        if rubric.get("chains"):
            authored += 1
        problems.extend(check_rubric(rubric))
    return len(data["rubrics"]), authored, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rubrics", type=Path, default=RUBRIC_DIR)
    parser.add_argument("--quiet-unauthored", action="store_true",
                        help="do not report rubrics that have no chains yet")
    args = parser.parse_args(argv)

    files = sorted(args.rubrics.glob("*.json"))
    if not files:
        print(f"no rubric files in {args.rubrics}; run rubric.py first", file=sys.stderr)
        return 1

    exit_code = 0
    for path in files:
        total, authored, problems = validate_file(path)
        if args.quiet_unauthored:
            problems = [p for p in problems if not p.endswith("no chains authored")]
        print(f"{path.stem}: {total} rubrics, {authored} authored, "
              f"{len(problems)} problem(s)")
        for problem in problems:
            print(f"    {problem}")
        if problems:
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
