"""Evaluate any OpenAI-compatible model on the released A/B vignettes."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import sys

from common import (
    ChatModel, PROMPT, ROOT, api_arguments, load_json, model_text, output_file,
    parse_choice, positive_int, principle, validate_cases,
)

FIELDS = ["vignette_id", "model", "run", "value_a", "value_b", "choice",
          "selected_value", "selected_principle", "status", "raw_response"]


def evaluate_one(job, model):
    case, run = job
    row = dict(vignette_id=case["id"], model=model.model, run=run,
               value_a=case["value_a"], value_b=case["value_b"],
               choice="ERROR", selected_value="", selected_principle="",
               status="error", raw_response="")
    try:
        text = model_text(case["vignette"])
        row["raw_response"] = model(PROMPT.format(vignette_text=text))
        row["choice"] = parse_choice(row["raw_response"])
        row["status"] = "valid" if row["choice"] in {"A", "B"} else "invalid"
        if row["status"] == "valid":
            selected = case["value_a"] if row["choice"] == "A" else case["value_b"]
            row.update(selected_value=selected, selected_principle=principle(selected))
    except Exception as error:
        row["status"] = f"error:{type(error).__name__}"
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    api_arguments(parser, "gpt-4o")
    parser.add_argument("--data", default=ROOT / "data/vignettes_208.json")
    parser.add_argument("--output", default="outputs/responses.csv")
    parser.add_argument("--limit", type=positive_int, help="Evaluate only the first N cases.")
    parser.add_argument("--runs", type=positive_int, default=1)
    parser.add_argument("--workers", type=positive_int, default=4)
    parser.add_argument("--check", action="store_true", help="Validate data without API calls.")
    args = parser.parse_args()
    cases = load_json(args.data)
    validate_cases(cases)
    if args.check:
        print(f"OK: {len(cases)} unique vignettes; A/B choices and value labels validated.")
        return
    cases = cases[:args.limit]
    model = ChatModel(args)
    jobs = [(case, run) for case in cases for run in range(1, args.runs + 1)]
    valid = 0
    with output_file(args.output) as handle, ThreadPoolExecutor(args.workers) as pool:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for row in pool.map(lambda job: evaluate_one(job, model), jobs):
            writer.writerow(row)
            handle.flush()
            valid += row["status"] == "valid"
    print(f"Saved {len(jobs)} responses ({valid} valid) to {args.output}.")
    if valid != len(jobs):
        print("Non-valid responses are retained; inspect their status before analysis.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
