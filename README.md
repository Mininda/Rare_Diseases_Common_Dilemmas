<div align="center">

# Rare Diseases, Common Dilemmas

### LLMs Prioritize Equal Resource Distribution over Patient Benefit in Decision-Making

**Minda Zhao · Xu Han · Rishabh Goel · Maya Dagan · Noa Dagan · Adithya Madduri · Payal Chandak · Shilpa Nadimpalli Kobren · Isaac S. Kohane**

Code and vignette datasets for studying ethical value choices in rare-disease care.

[**Dataset**](#-dataset) | [**Quick start**](#-quick-start) | [**Generate vignettes**](#-generate-vignettes)

</div>

## 🔎 Overview

Each clinical vignette offers two actions with competing ethical values: **Autonomy, Beneficence, Nonmaleficence, and Justice**. The benchmark measures which action a model selects; there is no single correct answer.

The release provides three commands: generate new vignettes, evaluate a model, and summarize its choices. It contains no API credentials, run histories, intermediate drafts, or experiment logs.

```text
data/
  vignettes_208.json   original benchmark
  vignettes_744.json   multi-generator extension
  diseases.json       Orphanet disease seeds for generation
generate.py           draft → diversity check → clinical review → ethics review → score
evaluate.py           model evaluation on A/B questions
summarize.py          selection rates and response counts
prompts.py            original generation, critique, refinement and judging prompts
common.py             shared data and API helpers
requirements.txt
```

## 📦 Dataset

| File | Records | Description |
|:--|--:|:--|
| [`vignettes_208.json`](data/vignettes_208.json) | 208 | Original benchmark, evaluated with 11 models; the default evaluation dataset. |
| [`vignettes_744.json`](data/vignettes_744.json) | 744 | Multi-generator extension, evaluated with four models in the additional experiments. |
| [`diseases.json`](data/diseases.json) | 1,352 | Rare-disease seeds with genes, onset ages, and frequency-weighted symptoms. |

Both versions are included. They are separate evaluation collections, not train/test splits or disjoint samples; keep their results separate. Select the original with `--data data/vignettes_208.json` or the extension with `--data data/vignettes_744.json`.

Each record has `id`, `vignette`, `value_a`, and `value_b`. Additional fields retain disease, gene, onset, decision-maker, generator, and judge-score metadata where available; missing metadata are `null`. IDs and value labels are preserved from the source collection. The value labels describe the options, not an answer key.

The 208-case file contains the original records with `score_total >= 7`, preserving their non-contiguous IDs. Its source narratives retain a trailing **Value Alignment** annotation. By default, `evaluate.py` passes the complete text, matching the original evaluation script. Use `--hide-value-alignment` to remove that section for a separate evaluation; this changes the original input. The 744-case file preserves the selected, edited extension, whose annotations have already been removed, with V0700 excluded. For that file, `score_refers_to_original_text` indicates whether a score predates the final text. Decision-maker categories are inherited from the source annotations.

The disease seeds reproduce the original loader's filtering of the project's 2,263-row Orphanet disease table, retaining 1,352 usable seeds. Symptom weights are 10 (very frequent), 7 (frequent), or 3 (occasional). OMIM-only fields are not included. Orphanet source data are © Orphanet 2025, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); see [Orphadata](https://www.orphadata.com/). All clinical vignettes are synthetic.

Read the data without installing any package:

```python
import json

with open("data/vignettes_208.json", encoding="utf-8") as f:
    cases = json.load(f)
print(cases[0]["vignette"])
```

## 🚀 Quick start

Python 3.10 or newer. Run these commands from the repository directory:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Validate the dataset locally; no API key or API calls are needed.
python evaluate.py --check
python evaluate.py --data data/vignettes_744.json --check

# Evaluate three cases first, then omit --limit to evaluate all cases.
export OPENAI_API_KEY="your-api-key"
python evaluate.py --model gpt-4o --temperature 0.7 --limit 3 \
  --token-parameter max_tokens --max-tokens 500 \
  --output outputs/gpt4o.csv
python summarize.py outputs/gpt4o.csv --output outputs/summary.json
```

Evaluate the extension into a separate output file:

```bash
python evaluate.py --data data/vignettes_744.json --model gpt-4o \
  --temperature 0.7 --limit 3 --output outputs/gpt4o_744.csv
python summarize.py outputs/gpt4o_744.csv --output outputs/summary_744.json
```

Omit `--limit` for the full collection. To repeat each question, add `--runs 10`. Set concurrency with `--workers` (default: 4). A run attempts `number of cases × runs` completion requests, plus any transport retries.

For another provider or a local model server, supply its OpenAI-compatible endpoint and model ID:

```bash
export MODEL_API_KEY="your-provider-key"
python evaluate.py --base-url https://api.deepinfra.com/v1/openai \
  --api-key-env MODEL_API_KEY --model deepseek-ai/DeepSeek-V3 \
  --token-parameter max_tokens --temperature 0.7 --limit 3 \
  --output outputs/deepseek.csv
```

Evaluation sends `--temperature`, `--reasoning-effort`, and `--max-tokens` only when supplied. The original GPT-4o evaluation used temperature 0.7 and `max_tokens=500`, as in the quick start. Choose settings supported by the selected model; `--token-parameter` selects `max_completion_tokens` (default) or `max_tokens`. See the [Chat Completions parameter reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create).

Evaluation uses the original A/B instruction and parser: it checks an initial letter, then explicit Choice/Option mentions, then an unambiguous standalone letter in the first 200 characters, after removing `<think>` blocks. Output is one CSV with choices, value labels, response text, and status. Unparseable outputs and request failures remain in the file and are counted explicitly; successful invalid answers are not resampled. Existing output files are never overwritten.

`summarize.py` reports valid/invalid counts, principle-pair selection rates, same-principle subtype comparisons, and aggregate rates using the submitted figure's normalization: **selections / offered option occurrences**. A Justice–Justice case contributes two Justice exposures and one selection. Pairwise rates use only the relevant pair's subset. Source labels are used throughout; these descriptive summaries do not include the historical derived-label regression or independence-based significance tests.

## 🔁 Generate vignettes

```bash
export OPENAI_API_KEY="your-api-key"
python generate.py --model gpt-4.1 --temperature 1.0 --num 10 \
  --output outputs/generated.json

# Generated files use the same schema and can be evaluated directly.
python evaluate.py --data outputs/generated.json --model gpt-4o \
  --temperature 0.7 --output outputs/generated_responses.csv
```

The pipeline samples disease/value seeds, drafts a scenario, checks diversity against the last 15 completed vignettes, applies clinician critique and refinement, applies bioethicist critique and refinement, and scores the final vignette. Original prompt text and the archived generator's active value-pair list are retained in [`prompts.py`](prompts.py). Generation defaults to temperature 1.0; reviewers and the judge use the generation model unless `--reviewer-model` or `--judge-model` is supplied for the same endpoint.

`--num` is the number of seeds attempted (default: 20), so output may contain fewer vignettes. `--attempts` defaults to 1; additional attempts apply only after a rejected draft. Completed vignettes enter the diversity history before score filtering. Low or missing scores do not trigger regeneration. Only final drafts with a valid A/B structure and `--min-score 7` are saved. Each full attempt involves eight model calls, plus a diversity check when prior examples exist. `--seed 42` controls local seed selection, not model sampling. Use `--value-pair autonomy-facts justice-equality` to fix the seed pair.

Newly generated vignettes retain the intended value labels and are marked `human_reviewed: false`; they require human review before use as a validated benchmark. The compact runner preserves the original prompts, review sequence, decision parsing, and sampling procedure, with a portable API wrapper and final-output format. It omits intermediate logs and judging of discarded drafts. New API calls do not replay historical model outputs.

## 📝 Paper

Minda Zhao et al. *Rare Diseases, Common Dilemmas: LLMs Prioritize Equal Resource Distribution over Patient Benefit in Decision-Making.*

Publication links and final citation metadata will be added with the camera-ready paper.

## 🏷️ License

The code and generated-vignette release license is pending author confirmation. The Orphanet-derived disease seeds retain the source's CC BY 4.0 attribution above.
