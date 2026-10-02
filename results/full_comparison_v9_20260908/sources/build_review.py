"""Persist explicit manual adjudications against immutable trial identities."""
import datetime
import hashlib
import json
from pathlib import Path
import re

OUT = Path(__file__).resolve().parent
RUN = OUT.parent


def load(p):
    return json.loads(p.read_text(encoding="utf-8"))


if __name__ == "__main__":
    rubric = RUN / "accuracy_protocol.json"
    decisions = load(OUT / "adjudications.json")
    refs = load(OUT / "reference_facts.json")["facts"]
    protocol = load(RUN / "protocol.json")
    rows = [json.loads(x) for x in (RUN / "runs.jsonl").read_text(encoding="utf-8").splitlines()]
    by = {(r["id"], r["condition"]): r for r in rows}
    cases = []
    for question in protocol["cases"]:
        i = question["id"]
        if i not in decisions["cases"]:
            continue
        c = {"id": i, "functional_group": question["endpoint"], "question": question["question"],
             "reference": refs[i]["reference"], "checks": question["checks"]}
        for p, decision in zip(decisions["order"], decisions["cases"][i], strict=True):
            assert (i, p) in by
            label, reason, *optional = decision
            extras = optional[0] if optional else []
            c[p] = {
                "label": label, "reason": reason,
                "sources": list(dict.fromkeys(refs[i]["sources"] + extras)),
                "technical_failure": not by[i,p]["completed"],
                "delivery_defects": optional[1] if len(optional) > 1 else [],
                "ancillary_errors": optional[2] if len(optional) > 2 else [],
                "answer_sha256": hashlib.sha256(by[i,p].get("answer", "").encode()).hexdigest(),
                "review_type": "explicit manual non-blinded AI classification; no judge-model call",
            }
            assert all((OUT / f"{s}.json").exists() for s in c[p]["sources"])
        cases.append(c)
    final = len(cases) == 30 and len(rows) == 90 and bool(load(RUN / "manifest.json").get("finished_at"))
    result = {"version": "v9", "finalized": final, "classified_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "accuracy_protocol_sha256": hashlib.sha256(rubric.read_bytes()).hexdigest(), "cases": cases,
              "criteria_changed_after_freeze": False, "all_trials_reviewed": final}
    (RUN / "accuracy_review.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(f"{len(cases)*3}/90 explicit classifications persisted; finalized={final}")
