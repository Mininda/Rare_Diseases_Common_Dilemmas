"""Generate rare-disease vignettes using the original prompts and review stages."""

import argparse
import json
import random

from common import ChatModel, ROOT, api_arguments, load_json, output_file, positive_int, validate_cases
import prompts as p

BINARY_RULE = (
    "Binary clinical decision for a single patient, choosing between two different "
    "management options (Option A vs Option B). "
    "Do not use scenarios where there is patient A vs patient B."
)


def parse_json(text):
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def history_block(history):
    if not history:
        return "No prior drafts or critiques are provided."
    lines = ["Previous drafts and critiques (for context only, do NOT copy verbatim):"]
    for index, (draft, critique) in enumerate(history, 1):
        lines += [f"\n--- Iteration {index} ---", "Draft vignette:", draft, "Critique:", critique]
    return "\n".join(lines)


def generate_one(seed, model, completed, reviewer_model, judge_model):
    system = p.INITIAL_SYSTEM_PROMPT.format(values_block=p.WITHIN_VALUES_BLOCK)
    fields = {**seed, "binary_decision_rule": BINARY_RULE}
    draft = model(p.INITIAL_PROMPT.format(**fields), system)
    if not draft.strip():
        return None
    if completed:
        examples = "\n".join(line for i, v in enumerate(completed[-15:], 1)
                             for line in (f"--- Example {i} ---", v, ""))
        decision = parse_json(model(p.DIVERSITY_PROMPT_TEMPLATE.format(
            **fields, previous_block=examples, vignette_text=draft
        ), p.DIVERSITY_SYSTEM_PROMPT, reviewer_model)).get("decision")
        if decision == "start_over":
            return None
    history = []
    stages = [
        (p.SYSTEM_PROMPT_CLINICIAN, p.CLINICIAN_CRITIQUE_PROMPT, p.CLINICIAN_DECISION_PROMPT_EARLY),
        (p.SYSTEM_PROMPT_BIOETHICIST.format(values_specialty_line=p.WITHIN_VALUES_SPECIALTY_LINE),
         p.BIOETHICIST_CRITIQUE_PROMPT, p.BIOETHICIST_DECISION_PROMPT_EARLY),
    ]
    for reviewer_system, critique_template, decision_template in stages:
        context = {**fields, "vignette_text": draft, "history_block": history_block(history)}
        critique = model(critique_template.format(**context), reviewer_system, reviewer_model)
        context["critique_text"] = critique
        decision = parse_json(model(decision_template.format(**context), reviewer_system,
                                    reviewer_model)).get("decision")
        if decision not in {"refine", "finish"}:
            return None
        refined = model(p.REFINE_PROMPT.format(**context), system)
        history.append((draft, critique))
        draft = refined
    scores = parse_json(model(p.JUDGE_PROMPT_TEMPLATE.format(vignette_text=draft),
                              p.SYSTEM_PROMPT_JUDGE, judge_model)).get("scores", {})
    return draft, scores if isinstance(scores, dict) else {}


def sample_seed(diseases, pairs, rng):
    value_a, value_b = rng.sample(pairs, 1)[0]
    disease = rng.sample(diseases, 1)[0]
    symptoms = disease["symptoms"]
    return {
        "disease_name": disease["disease"],
        "gene_name": rng.sample(disease["genes"], 1)[0] if disease["genes"] else "N/A",
        "age_of_onset": rng.sample(disease["onset_ages"], 1)[0] if disease["onset_ages"] else "N/A",
        "symptoms_list": ", ".join(rng.choices([s["name"] for s in symptoms],
            weights=[s["weight"] for s in symptoms], k=min(30, len(symptoms)))),
        "value_1": value_a, "value_2": value_b,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    api_arguments(parser, "gpt-4.1")
    parser.set_defaults(temperature=1.0)
    parser.add_argument("--data", default=ROOT / "data/diseases.json", help="Disease seeds JSON.")
    parser.add_argument("--num", type=positive_int, default=20, help="Number of disease/value seeds to try.")
    parser.add_argument("--seed", type=int, default=42, help="Local seed selection; does not seed the API.")
    parser.add_argument("--attempts", type=positive_int, default=1, help="Draft attempts per seed after reviewer rejection.")
    parser.add_argument("--min-score", type=int, choices=range(1, 11), default=7)
    parser.add_argument("--value-pair", nargs=2, metavar=("VALUE_A", "VALUE_B"))
    parser.add_argument("--reviewer-model", help="Same endpoint as --model; defaults to --model.")
    parser.add_argument("--judge-model", help="Same endpoint as --model; defaults to --model.")
    parser.add_argument("--output", default="outputs/generated.json")
    args = parser.parse_args()
    diseases = load_json(args.data)
    if not diseases or any(not d.get("symptoms") for d in diseases):
        parser.error("Disease seeds must be nonempty and each contain symptoms.")
    pairs = [tuple(args.value_pair)] if args.value_pair else p.VALUE_PAIRS
    if args.value_pair and tuple(args.value_pair) not in p.VALUE_PAIRS:
        parser.error("Use a value pair from VALUE_PAIRS in prompts.py.")
    model = ChatModel(args)
    rng, completed, records = random.Random(args.seed), [], []
    with output_file(args.output) as handle:
        try:
            for index in range(1, args.num + 1):
                seed = sample_seed(diseases, pairs, rng)
                for _ in range(args.attempts):
                    result = generate_one(seed, model, completed, args.reviewer_model, args.judge_model)
                    if result is None:
                        continue
                    draft, scores = result
                    completed.append(draft)
                    total = scores.get("Total Score")
                    if type(total) not in (int, float) or not total >= args.min_score:
                        break
                    record = dict(
                        id=f"generated-{index:04d}", disease=seed["disease_name"],
                        gene=seed["gene_name"], age_of_onset=seed["age_of_onset"],
                        symptoms=seed["symptoms_list"], value_a=seed["value_1"],
                        value_b=seed["value_2"], vignette=draft, generator=args.model,
                        reviewer=args.reviewer_model or args.model,
                        judge=args.judge_model or args.model, scores=scores,
                        human_reviewed=False,
                    )
                    try:
                        validate_cases([record])
                    except ValueError:
                        break
                    records.append(record)
                    break
        finally:
            json.dump(records, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    print(f"Saved {len(records)}/{args.num} accepted drafts to {args.output}; human review is still required.")


if __name__ == "__main__":
    main()
