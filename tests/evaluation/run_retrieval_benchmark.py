# Import JSON to read benchmark cases and save results.
import json

# Import time to measure retrieval latency.
import time

# Import Path to locate files independently of the working directory.
from pathlib import Path

# Import NEXORA's existing hybrid retrieval function.
from rag.retrieval.hybrid_search import hybrid_search

# Identify the directory containing this evaluation script.
directory = Path(__file__).resolve().parent

# Load the benchmark questions and expected evidence.
cases = json.loads((directory / "retrieval_cases.json").read_text())

# Create a container for individual evaluation results.
results = []

# Evaluate each question using the existing retrieval implementation.
for case in cases:
    # Record the time immediately before retrieval.
    started = time.perf_counter()

    # Retrieve five passages from the multimodal Azure Search index.
    passages = hybrid_search(case["question"], top_k=5, multimodal=True)

    # Calculate elapsed retrieval time in seconds.
    latency = time.perf_counter() - started

    # Define page-level relevance using document ID and expected page.
    def page_relevant(passage):
        return (
            passage["document_id"] == case["expected_document_id"]
            and passage["page_number"] in case["expected_pages"]
        )

    # Define exact-chunk relevance using the benchmark's chunk IDs.
    def chunk_relevant(passage):
        return passage["chunk_id"] in case["expected_chunk_ids"]

    # Find the rank of the first page-level relevant result.
    relevant_ranks = [
        rank
        for rank, passage in enumerate(passages, start=1)
        if page_relevant(passage)
    ]

    # Calculate reciprocal rank, or zero if no relevant result was found.
    reciprocal_rank = 1 / relevant_ranks[0] if relevant_ranks else 0.0

    # Store the complete evaluation result.
    result = {
        "id": case["id"],
        "page_hit_at_5": bool(relevant_ranks),
        "exact_chunk_hit_at_5": (
            any(chunk_relevant(passage) for passage in passages)
            if case["expected_chunk_ids"]
            else None
        ),
        "reciprocal_rank": reciprocal_rank,
        "latency_seconds": round(latency, 3),
        "retrieved": [
            {
                "rank": rank,
                "chunk_id": passage["chunk_id"],
                "page_number": passage["page_number"],
                "score": passage["score"],
            }
            for rank, passage in enumerate(passages, start=1)
        ],
    }

    # Add this case to the evaluation results.
    results.append(result)

    # Print the result immediately so progress is visible.
    print(
        f"{case['id']}: "
        f"page_hit={result['page_hit_at_5']} "
        f"chunk_hit={result['exact_chunk_hit_at_5']} "
        f"MRR={result['reciprocal_rank']:.3f} "
        f"latency={result['latency_seconds']:.2f}s",
        flush=True,
    )

# Calculate aggregate page-level Hit@5.
page_hit_rate = sum(r["page_hit_at_5"] for r in results) / len(results)

# Include only cases with known exact chunk labels.
labeled = [r for r in results if r["exact_chunk_hit_at_5"] is not None]

# Calculate aggregate exact-chunk Hit@5.
chunk_hit_rate = (
    sum(r["exact_chunk_hit_at_5"] for r in labeled) / len(labeled)
    if labeled else None
)

# Calculate mean reciprocal rank across all benchmark cases.
mean_reciprocal_rank = sum(r["reciprocal_rank"] for r in results) / len(results)

# Create the final benchmark report.
report = {
    "configuration": {"top_k": 5, "multimodal": True, "retrieval": "hybrid"},
    "metrics": {
        "page_hit_at_5": page_hit_rate,
        "exact_chunk_hit_at_5": chunk_hit_rate,
        "mrr_at_5": mean_reciprocal_rank,
        "average_latency_seconds": sum(r["latency_seconds"] for r in results) / len(results),
    },
    "cases": results,
}

# Save the baseline results alongside the evaluation script.
output = directory / "baseline_results.json"
output.write_text(json.dumps(report, indent=2))

# Display the aggregate benchmark metrics.
print("\nBASELINE RESULTS")
print(json.dumps(report["metrics"], indent=2))
print(f"\nSaved: {output}")
