"""Run NEXORA groundedness evaluations in Microsoft Foundry."""

import argparse
import json
import os
import time
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential


DEFAULT_ENDPOINT = (
    "https://enterprise-copilot-dev-resource.services.ai.azure.com"
    "/api/projects/enterprise-copilot-dev"
)

DEFAULT_MODEL = "gpt-5.4-mini"

TEST_CASES = [
    {
        "question": "What was Electronics revenue growth?",
        "context": "Electronics revenue increased by 30%.",
        "response": "Electronics revenue increased by 30%.",
        "expected": "PASS",
    },
    {
        "question": "What was Electronics revenue growth?",
        "context": "Electronics revenue increased by 30%.",
        "response": "Electronics revenue increased by 80%.",
        "expected": "FAIL",
    },
]


def create_client():
    """Authenticate using the existing Azure identity."""
    project = AIProjectClient(
        endpoint=os.getenv("AZURE_AI_PROJECT_ENDPOINT", DEFAULT_ENDPOINT),
        credential=DefaultAzureCredential(),
    )
    return project.get_openai_client()


def run_evaluation(client, cases, model, timeout):
    """Create an evaluation, execute it, and wait for completion."""
    evaluation = client.evals.create(
        name="nexora-groundedness-regression",
        data_source_config={
            "type": "custom",
            "item_schema": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "context": {"type": "string"},
                    "response": {"type": "string"},
                    "expected": {"type": "string"},
                },
                "required": [
                    "question", "context", "response", "expected"
                ],
            },
            "include_sample_schema": True,
        },
        testing_criteria=[
            {
                "type": "label_model",
                "name": "groundedness",
                "model": model,
                "input": [
                    {
                        "role": "developer",
                        "content": (
                            "Evaluate whether every factual claim in the "
                            "response is supported by the context. "
                            "Return PASS only when all factual claims "
                            "are supported. Otherwise return FAIL."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            "Question: {{item.question}}\n"
                            "Context: {{item.context}}\n"
                            "Response: {{item.response}}"
                        ),
                    },
                ],
                "labels": ["PASS", "FAIL"],
                "passing_labels": ["PASS"],
            }
        ],
    )

    run = client.evals.runs.create(
        eval_id=evaluation.id,
        name="nexora-groundedness-regression-run",
        data_source={
            "type": "jsonl",
            "source": {
                "type": "file_content",
                "content": [
                    {
                        "item": {
                            key: value
                            for key, value in case.items()
                        }
                    }
                    for case in cases
                ],
            },
        },
    )

    deadline = time.monotonic() + timeout

    while run.status not in ("completed", "failed", "canceled"):
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"Foundry run {run.id} exceeded {timeout} seconds."
            )

        time.sleep(5)

        run = client.evals.runs.retrieve(
            eval_id=evaluation.id,
            run_id=run.id,
        )

        print(f"Foundry run status: {run.status}", flush=True)

    return evaluation, run



def verify_predictions(client, evaluation_id, run_id, cases):
    """Verify each evaluator prediction against its expected label."""
    items = list(
        client.evals.runs.output_items.list(
            eval_id=evaluation_id,
            run_id=run_id,
            limit=100,
        )
    )

    if len(items) != len(cases):
        raise AssertionError(
            f"Expected {len(cases)} results, received {len(items)}."
        )

    predictions = []
    seen_ids = set()

    for item in items:
        index = item.datasource_item_id

        if not isinstance(index, int) or index < 0 or index >= len(cases):
            raise AssertionError(f"Unexpected datasource item ID: {index}")

        if index in seen_ids:
            raise AssertionError(f"Duplicate datasource item ID: {index}")

        seen_ids.add(index)

        if item.status != "completed" or len(item.results) != 1:
            raise AssertionError(f"Incomplete evaluation for case {index}")

        result = item.results[0]

        if result.status != "completed" or result.passed is None:
            raise AssertionError(f"Invalid evaluator result for case {index}")

        predicted = "PASS" if result.passed else "FAIL"
        expected = cases[index]["expected"]

        predictions.append({
            "case_index": index,
            "expected": expected,
            "predicted": predicted,
            "correct": predicted == expected,
        })

    predictions.sort(key=lambda entry: entry["case_index"])

    if not all(entry["correct"] for entry in predictions):
        raise AssertionError(f"Incorrect predictions: {predictions}")

    return predictions


def main():
    """Execute the evaluation and save its results."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    client = create_client()

    evaluation, run = run_evaluation(
        client=client,
        cases=TEST_CASES,
        model=args.model,
        timeout=args.timeout,
    )

    if run.status != "completed":
        raise RuntimeError(f"Foundry evaluation ended with {run.status}")

    predictions = verify_predictions(
        client, evaluation.id, run.id, TEST_CASES
    )

    output = {
        "predictions": predictions,
        "evaluation_id": evaluation.id,
        "run_id": run.id,
        "status": run.status,
        "model": args.model,
        "cases": TEST_CASES,
        "result_counts": (
            run.result_counts.model_dump(mode="json")
            if run.result_counts else None
        ),
        "criteria_results": [
            result.model_dump(mode="json")
            for result in (run.per_testing_criteria_results or [])
        ],
        "report_url": run.report_url,
        "error": (
            run.error.model_dump(mode="json")
            if run.error else None
        ),
    }

    output_dir = Path("data/evaluation_results")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "foundry_groundedness_latest.json"
    output_path.write_text(
        json.dumps(output, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(output, indent=2))
    print(f"\nResults saved to: {output_path}")

    if run.status != "completed":
        raise SystemExit(1)

    if not run.result_counts or run.result_counts.errored:
        raise SystemExit("Evaluation encountered errors.")


if __name__ == "__main__":
    main()
