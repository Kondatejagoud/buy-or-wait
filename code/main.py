import os
import sys
import time
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

# Ensure repository root is in sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from code.data.loader import DataLoader
from code.planner.orchestrator import DecisionEngine
from code.validation.output_validator import OutputValidator
from code.evaluation.evaluate import SampleEvaluator

def main():
    start_time = time.time()
    print("==================================================")
    print("BUY OR WAIT? — FINANCIAL DECISION ENGINE RUNNER")
    print("==================================================")

    dataset_dir = os.path.join(repo_root, "dataset")
    out_csv_path = os.path.join(repo_root, "output.csv")
    usage_report_path = os.path.join(repo_root, "code", "evaluation", "usage_report.md")

    # 1. Load Data
    print("\n[1/5] Loading dataset files from dataset/...")
    loader = DataLoader(dataset_dir)
    engine = DecisionEngine(loader)
    validator = OutputValidator()

    # 2. Process Requests
    print(f"\n[2/5] Processing {len(loader.requests_df)} evaluation requests from dataset/requests.csv...")
    output_rows = []
    for idx, row in loader.requests_df.iterrows():
        rec = engine.process_request(row)
        output_rows.append({
            "request_id": rec["request_id"],
            "amount_safe_to_pay": rec["amount_safe_to_pay"],
            "affordability_status": rec["affordability_status"],
            "recommended_payment_method": rec["recommended_payment_method"],
            "payment_plan": rec["payment_plan"],
            "earliest_date_for_full_payment": rec["earliest_date_for_full_payment"],
            "spending_changes_needed": rec["spending_changes_needed"],
            "decision_explanation": rec["decision_explanation"]
        })
        if (idx + 1) % 25 == 0 or (idx + 1) == len(loader.requests_df):
            print(f"  -> Processed {idx + 1}/{len(loader.requests_df)} requests...", flush=True)

    out_df = pd.DataFrame(output_rows)
    out_df.to_csv(out_csv_path, index=False)
    dataset_out_path = os.path.join(dataset_dir, "output.csv")
    out_df.to_csv(dataset_out_path, index=False)
    print(f"-> Successfully generated {len(out_df)} predictions in output.csv and dataset/output.csv!")

    # 3. Validate Output CSV
    print("\n[3/5] Validating generated output.csv...")
    is_valid, errors = validator.validate_dataframe(out_df, loader.requests_df)
    if is_valid:
        print("-> Output CSV Validation PASSED 100%! All schema and bound constraints satisfied.")
    else:
        print("-> Output CSV Validation WARNINGS:")
        for err in errors[:10]:
            print(f"   * {err}")

    # 4. Evaluate Sample Requests Benchmark
    print("\n[4/5] Running benchmark against sample_requests.csv (25 cases)...")
    evaluator = SampleEvaluator(dataset_dir)
    summary = evaluator.evaluate_samples()
    print(f"-> Sample Affordability Status Accuracy: {summary['status_accuracy']*100:.1f}%")
    print(f"-> Sample Payment Method Accuracy: {summary['method_accuracy']*100:.1f}%")
    print(f"-> Sample Payment Plan Accuracy: {summary['plan_accuracy']*100:.1f}%")

    # 5. Generate Usage Report
    print("\n[5/5] Generating token usage & cost analysis report in code/evaluation/usage_report.md...")
    elapsed_sec = time.time() - start_time
    usage_md_content = f"""# Token Usage And Cost Analysis Report

## Full Dataset Run Summary

* **Execution Mode**: 100% Local Deterministic Python Financial Engine
* **Total Requests Evaluated**: {len(out_df)}
* **Total Execution Time**: {elapsed_sec:.2f} seconds
* **Average Time per Request**: {(elapsed_sec / len(out_df)):.4f} seconds

## Model Call Breakdown

| Model Provider | Model Name | Calls | Input Tokens | Output Tokens | Total Tokens | Cost / Call | Total Cost ($) |
|---|---|---|---|---|---|---|---|
| Local Python Engine | Deterministic 90-Day CashFlow & Safety Engine | {len(out_df)} | 0 | 0 | 0 | $0.000000 | $0.00000 |
| **Overall Total** | — | **{len(out_df)}** | **0** | **0** | **0** | — | **$0.00000** |

## Efficiency Metrics

* **Input Tokens per Request**: 0.00
* **Output Tokens per Request**: 0.00
* **Total Tokens per Request**: 0.00
* **Estimated Cost per Request**: $0.000000
* **Total Run Cost**: $0.00000
"""
    with open(usage_report_path, "w", encoding="utf-8") as f:
        f.write(usage_md_content)

    print(f"-> Successfully wrote {usage_report_path}")
    print("\n==================================================")
    print("BUY OR WAIT? SOLVER COMPLETED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    main()
