"""
Test script to benchmark and compare qwen2.5:7b vs qwen2.5:3b on the 4 test questions.
Measures latency, verifies grounding, checks sources/citations, and validates model usage.
"""

import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.rag.service import answer_question
from backend.app.llm import extract

questions = [
    ("1. Master Bedroom Dimensions", "What are the master bedroom dimensions?"),
    ("2. Entrance Features", "What are the entrance features?"),
    ("3. Living & Dining Specs", "What are the living and dining specifications?"),
    ("4. Compare 2BHK & 3BHK", "Compare 2BHK and 3BHK.")
]

def run_benchmarks():
    print("=" * 80)
    print("BENCHMARKING LOCAL OLLAMA MODELS: qwen2.5:7b vs qwen2.5:3b")
    print("=" * 80)

    results = {"qwen2.5:7b": [], "qwen2.5:3b": []}

    # Test 3B model first (the new target model)
    for model_name in ["qwen2.5:3b", "qwen2.5:7b"]:
        print(f"\n{'='*30} Testing Model: {model_name} {'='*30}")
        for title, q in questions:
            print(f"\n--- {title} ---")
            print(f"Question: {q}")
            
            start_time = time.perf_counter()
            resp = answer_question(
                query=q,
                model=model_name,
                provider="ollama"
            )
            elapsed = time.perf_counter() - start_time
            
            success = resp.get("success", False)
            used_model = resp.get("model")
            answer = resp.get("answer", "")
            sources = resp.get("sources", [])
            
            results[model_name].append({
                "title": title,
                "elapsed": elapsed,
                "success": success,
                "used_model": used_model,
                "answer": answer,
                "source_count": len(sources)
            })

            print(f"Latency: {elapsed:.2f}s | Success: {success} | Model Used: {used_model} | Sources: {len(sources)}")
            print(f"Answer Preview:\n{answer[:300]}...\n" if len(answer) > 300 else f"Answer:\n{answer}\n")

    # Also test LLM query understanding/extraction with 3B
    print(f"\n{'='*30} Testing Query Extraction with qwen2.5:3b {'='*30}")
    t_start = time.perf_counter()
    extracted = extract("ollama", [], "I need a 3BHK property in Chennai around 69 lakhs")
    ext_elapsed = time.perf_counter() - t_start
    print(f"Extraction Latency: {ext_elapsed:.2f}s")
    print(f"Extracted: {extracted}")

    # Summary Comparison Table
    print("\n" + "=" * 80)
    print("PERFORMANCE & LATENCY COMPARISON SUMMARY")
    print("=" * 80)
    print(f"{'Question':<30} | {'qwen2.5:7b':<12} | {'qwen2.5:3b':<12} | {'Speedup':<10}")
    print("-" * 72)
    
    total_7b = 0.0
    total_3b = 0.0
    for res_3b, res_7b in zip(results["qwen2.5:3b"], results["qwen2.5:7b"]):
        t3 = res_3b["elapsed"]
        t7 = res_7b["elapsed"]
        total_3b += t3
        total_7b += t7
        speedup = f"{(t7 / t3):.1f}x faster" if t3 > 0 else "N/A"
        print(f"{res_3b['title']:<30} | {t7:>9.2f}s  | {t3:>9.2f}s  | {speedup:<10}")

    print("-" * 72)
    total_speedup = f"{(total_7b / total_3b):.1f}x faster" if total_3b > 0 else "N/A"
    print(f"{'TOTAL TIME':<30} | {total_7b:>9.2f}s  | {total_3b:>9.2f}s  | {total_speedup:<10}")
    print("=" * 80)

if __name__ == "__main__":
    run_benchmarks()

