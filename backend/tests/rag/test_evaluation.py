"""Deterministic RAG evaluation harness (Phase 7 §16/§17).

A small, hand-authored synthetic enterprise knowledge set
(tests/fixtures/rag/) with a fixed set of questions with *known* answers,
each labeled with what it's testing:

    SUPPORTED         - the fact is genuinely in a specific document; the
                         system must retrieve it and answer from it.
    PARTIALLY_COVERED - the topic is covered but the exact detail asked
                         isn't; the system must not invent it.
    UNSUPPORTED       - nothing in the corpus is relevant; the system must
                         say so, not fabricate an answer.
    WRONG_DOCUMENT    - superficially plausible but the true source is a
                         *different* document than a naive keyword match
                         might suggest; wrong documents must be excluded.

This is a real, if modest, retrieval-quality evaluation - not a claim of
sophisticated RAG evaluation (no LLM-as-judge, no embedding-similarity
scoring of the answer text itself). For each SUPPORTED/WRONG_DOCUMENT case
it reports whether the expected source appears in top-K, its rank, and its
score - printed to stdout (run with `pytest -s` to see it) and asserted on,
so a regression in retrieval quality fails this test, not just prints a
warning. See backend/README.md's Phase 7 section for the documented
limitations of this methodology.
"""

from dataclasses import dataclass

from tests.conftest import FIXTURES_DIR

RAG_FIXTURES = FIXTURES_DIR / "rag"

_DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

_DOCS = [
    ("employee_handbook_policies.txt", "text/plain"),
    ("pricing_guide.md", "text/markdown"),
    ("regional_offices.docx", _DOCX_CONTENT_TYPE),
    ("data_retention_policy.pdf", "application/pdf"),
]


@dataclass
class EvalCase:
    category: str
    question: str
    expected_filename: str | None  # None for UNSUPPORTED
    expected_answer_fragment: str | None
    forbidden_fragment: str | None = None


EVAL_CASES = [
    EvalCase(
        "SUPPORTED",
        "How many vacation days do full-time employees get per year?",
        "employee_handbook_policies.txt",
        "20",
    ),
    EvalCase(
        "SUPPORTED",
        "How much does the Pro plan cost per month?",
        "pricing_guide.md",
        "49",
    ),
    EvalCase(
        "SUPPORTED",
        "Which city hosts the EMEA regional office?",
        "regional_offices.docx",
        "London",
    ),
    EvalCase(
        "SUPPORTED",
        "How long is customer data retained after account closure?",
        "data_retention_policy.pdf",
        "7 years",
    ),
    EvalCase(
        "WRONG_DOCUMENT",
        "Do Basic plan vacation days roll over to the next year?",
        # Deliberately shares vocabulary with both the pricing guide
        # ("Basic plan") and the vacation policy ("vacation days roll
        # over... next... year") - the true, only correct source for
        # anything about vacation rollover is the handbook; the pricing
        # guide never discusses rollover at all, so it must not outrank it.
        "employee_handbook_policies.txt",
        None,
        forbidden_fragment="pricing_guide.md",
    ),
    EvalCase(
        "PARTIALLY_COVERED",
        "What is the refund policy for the Pro plan?",
        "pricing_guide.md",
        None,
        forbidden_fragment="refund",
    ),
    EvalCase(
        "UNSUPPORTED",
        "What is the boiling point of tungsten in kelvin?",
        None,
        None,
    ),
]


def _upload_all_fixtures(client) -> None:
    for filename, content_type in _DOCS:
        path = RAG_FIXTURES / filename
        files = {"file": (filename, path.read_bytes(), content_type)}
        upload = client.post("/documents/upload", files=files)
        assert upload.status_code == 201, upload.text
        process = client.post(f"/documents/{upload.json()['id']}/process")
        assert process.status_code == 200 and process.json()["status"] == "ready", process.text


def test_rag_evaluation_suite(client, capsys):
    _upload_all_fixtures(client)

    report_lines = [
        f"{'category':<20}{'expected source':<32}{'in top-K':<10}{'rank':<6}{'score':<8}"
    ]
    failures = []

    for case in EVAL_CASES:
        response = client.post("/rag/query", json={"question": case.question})
        assert response.status_code == 200, response.text
        result = response.json()
        sources = result["sources"]

        if case.category == "UNSUPPORTED":
            in_top_k, rank, score = False, None, None
            report_lines.append(f"{case.category:<20}{'(none)':<32}{'n/a':<10}{'n/a':<6}{'n/a':<8}")
            if result["status"] != "insufficient_evidence" or sources:
                failures.append(
                    f"[{case.category}] expected insufficient_evidence: {case.question!r}"
                )
        else:
            match = next((s for s in sources if s["filename"] == case.expected_filename), None)
            in_top_k = match is not None
            rank = match["rank"] if match else None
            score = round(match["score"], 3) if match else None
            report_lines.append(
                f"{case.category:<20}{case.expected_filename:<32}{str(in_top_k):<10}"
                f"{str(rank):<6}{str(score):<8}"
            )
            if not in_top_k:
                failures.append(
                    f"[{case.category}] expected source {case.expected_filename!r} not in "
                    f"top-K for: {case.question!r}"
                )
            elif case.category == "WRONG_DOCUMENT" and rank != 1:
                failures.append(
                    f"[{case.category}] expected source did not rank first "
                    f"(rank={rank}) for: {case.question!r}"
                )

        if case.expected_answer_fragment and case.expected_answer_fragment not in result["answer"]:
            failures.append(
                f"[{case.category}] expected {case.expected_answer_fragment!r} in answer "
                f"for: {case.question!r}"
            )
        if case.forbidden_fragment and case.forbidden_fragment.lower() in result["answer"].lower():
            failures.append(
                f"[{case.category}] forbidden fragment {case.forbidden_fragment!r} found "
                f"in answer for: {case.question!r}"
            )

    with capsys.disabled():
        print("\n\n--- RAG retrieval-quality evaluation report ---")
        print("\n".join(report_lines))
        print(f"{len(EVAL_CASES) - len(failures)}/{len(EVAL_CASES)} cases passed.\n")

    assert not failures, "Evaluation failures:\n" + "\n".join(failures)
