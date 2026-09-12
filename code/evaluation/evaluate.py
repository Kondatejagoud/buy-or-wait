import os
import sys
import pandas as pd
from typing import Dict, Any, List

# Ensure repo root is in sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from code.data.loader import DataLoader
from code.planner.orchestrator import DecisionEngine
from code.validation.output_validator import OutputValidator

class SampleEvaluator:
    def __init__(self, dataset_dir: str = "dataset"):
        self.loader = DataLoader(dataset_dir)
        self.engine = DecisionEngine(self.loader)
        self.validator = OutputValidator()

    def evaluate_samples(self) -> Dict[str, Any]:
        samples_df = pd.read_csv(os.path.join(repo_root, "dataset", "sample_requests.csv"))
        results = []

        status_matches = 0
        method_matches = 0
        plan_matches = 0
        safe_amt_matches = 0
        earliest_date_matches = 0
        spending_changes_matches = 0

        for idx, row in samples_df.iterrows():
            req_id = row["request_id"]
            pred = self.engine.process_request(row)

            gt_status = str(row["affordability_status"])
            gt_method = str(row["recommended_payment_method"])
            gt_plan = str(row["payment_plan"])
            gt_safe_amt = float(row["amount_safe_to_pay"])
            gt_earliest = str(row["earliest_date_for_full_payment"]) if pd.notna(row["earliest_date_for_full_payment"]) else ""
            gt_changes = str(row["spending_changes_needed"])

            pred_status = pred["affordability_status"]
            pred_method = pred["recommended_payment_method"]
            pred_plan = pred["payment_plan"]
            pred_safe_amt = float(pred["amount_safe_to_pay"])
            pred_earliest = str(pred["earliest_date_for_full_payment"])
            pred_changes = str(pred["spending_changes_needed"])

            m_status = (pred_status == gt_status)
            m_method = (pred_method == gt_method)
            m_plan = (pred_plan == gt_plan)
            m_safe_amt = (abs(pred_safe_amt - gt_safe_amt) < 1.0) # Within $1 / rounding
            m_earliest = (pred_earliest == gt_earliest)
            m_changes = (pred_changes == gt_changes)

            if m_status: status_matches += 1
            if m_method: method_matches += 1
            if m_plan: plan_matches += 1
            if m_safe_amt: safe_amt_matches += 1
            if m_earliest: earliest_date_matches += 1
            if m_changes: spending_changes_matches += 1

            results.append({
                "request_id": req_id,
                "status_match": m_status,
                "method_match": m_method,
                "plan_match": m_plan,
                "safe_amt_match": m_safe_amt,
                "gt_status": gt_status, "pred_status": pred_status,
                "gt_method": gt_method, "pred_method": pred_method,
                "gt_plan": gt_plan, "pred_plan": pred_plan,
                "gt_safe_amt": gt_safe_amt, "pred_safe_amt": pred_safe_amt
            })

        total = len(samples_df)
        summary = {
            "total_samples": total,
            "status_accuracy": status_matches / total,
            "method_accuracy": method_matches / total,
            "plan_accuracy": plan_matches / total,
            "safe_amt_accuracy": safe_amt_matches / total,
            "earliest_date_accuracy": earliest_date_matches / total,
            "spending_changes_accuracy": spending_changes_matches / total,
            "results": results
        }
        return summary

if __name__ == "__main__":
    evaluator = SampleEvaluator()
    summary = evaluator.evaluate_samples()
    print("=== SAMPLE EVALUATION SUMMARY ===")
    print(f"Total Samples: {summary['total_samples']}")
    print(f"Affordability Status Accuracy: {summary['status_accuracy']*100:.1f}% ({int(summary['status_accuracy']*summary['total_samples'])}/{summary['total_samples']})")
    print(f"Payment Method Accuracy: {summary['method_accuracy']*100:.1f}% ({int(summary['method_accuracy']*summary['total_samples'])}/{summary['total_samples']})")
    print(f"Payment Plan Accuracy: {summary['plan_accuracy']*100:.1f}% ({int(summary['plan_accuracy']*summary['total_samples'])}/{summary['total_samples']})")
    print(f"Safe Amount Accuracy: {summary['safe_amt_accuracy']*100:.1f}% ({int(summary['safe_amt_accuracy']*summary['total_samples'])}/{summary['total_samples']})")
    print(f"Earliest Date Accuracy: {summary['earliest_date_accuracy']*100:.1f}% ({int(summary['earliest_date_accuracy']*summary['total_samples'])}/{summary['total_samples']})")
    print(f"Spending Changes Accuracy: {summary['spending_changes_accuracy']*100:.1f}% ({int(summary['spending_changes_accuracy']*summary['total_samples'])}/{summary['total_samples']})")
