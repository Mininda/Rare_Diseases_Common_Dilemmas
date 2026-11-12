"""Summarize valid A/B choices; report denominators and invalid-response counts."""

import argparse
from collections import Counter, defaultdict
import csv
import json

from common import output_file, principle


def summarize(rows):
    coverage = defaultdict(Counter)
    pairs = defaultdict(Counter)
    subtypes = defaultdict(Counter)
    values = defaultdict(Counter)
    seen = set()
    for row in rows:
        model = row["model"]
        key = (model, row["vignette_id"], row["run"])
        if key in seen:
            raise ValueError(f"Duplicate model/vignette/run: {key}")
        seen.add(key)
        coverage[model]["total"] += 1
        if row["status"] != "valid":
            coverage[model]["non_valid"] += 1
            continue
        if row["choice"] not in {"A", "B"}:
            raise ValueError("A valid response must select A or B.")
        coverage[model]["valid"] += 1
        a, b = row["value_a"], row["value_b"]
        selected = a if row["choice"] == "A" else b
        pa, pb, chosen = principle(a), principle(b), principle(selected)
        for value in (pa, pb):
            values[model, value]["option_exposures"] += 1
        values[model, chosen]["selected"] += 1
        if pa == pb:
            coverage[model]["same_principle"] += 1
            left, right = sorted((a, b))
            subtypes[model, left, right]["n"] += 1
            subtypes[model, left, right]["left_selected"] += selected == left
        else:
            left, right = sorted((pa, pb))
            pairs[model, left, right]["n"] += 1
            pairs[model, left, right]["left_selected"] += chosen == left
    return {
        "definition": "Valid responses only. Aggregate rate = selections / offered option occurrences; pairwise rates condition on the pair.",
        "coverage": {m: {k: c[k] for k in ("total", "valid", "non_valid", "same_principle")}
                     for m, c in sorted(coverage.items())},
        "by_value": [dict(model=m, value=v, selected=c["selected"],
                          option_exposures=c["option_exposures"],
                          rate=c["selected"] / c["option_exposures"])
                     for (m, v), c in sorted(values.items())],
        "by_pair": [dict(model=m, value_left=a, value_right=b, **c,
                         left_rate=c["left_selected"] / c["n"])
                    for (m, a, b), c in sorted(pairs.items())],
        "by_subtype_pair": [dict(model=m, value_left=a, value_right=b, **c,
                                 left_rate=c["left_selected"] / c["n"])
                            for (m, a, b), c in sorted(subtypes.items())],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("responses", nargs="+", help="One or more evaluation CSVs for the same dataset.")
    parser.add_argument("--output", help="Optional JSON file; otherwise print the summary.")
    args = parser.parse_args()
    rows = []
    for path in args.responses:
        with open(path, encoding="utf-8", newline="") as handle:
            rows.extend(csv.DictReader(handle))
    if not rows:
        parser.error("No response rows were found.")
    result = summarize(rows)
    if args.output:
        with output_file(args.output) as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        print(f"Saved summary to {args.output}.")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
