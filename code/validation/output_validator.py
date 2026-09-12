import pandas as pd
from typing import List, Dict, Any, Tuple

class OutputValidator:
    REQUIRED_COLUMNS = [
        "request_id",
        "amount_safe_to_pay",
        "affordability_status",
        "recommended_payment_method",
        "payment_plan",
        "earliest_date_for_full_payment",
        "spending_changes_needed",
        "decision_explanation"
    ]

    ALLOWED_STATUSES = {
        "affordable_now",
        "affordable_with_plan",
        "affordable_later",
        "not_affordable"
    }

    ALLOWED_METHODS = {
        "full_payment",
        "partial_payment",
        "installments",
        "wait",
        "not_recommended"
    }

    def validate_dataframe(self, df: pd.DataFrame, requests_df: pd.DataFrame) -> Tuple[bool, List[str]]:
        errors = []

        # 1. Column check
        if list(df.columns) != self.REQUIRED_COLUMNS:
            errors.append(f"Column mismatch! Expected: {self.REQUIRED_COLUMNS}, Got: {list(df.columns)}")
            return False, errors

        # 2. Row count check
        if len(df) != len(requests_df):
            errors.append(f"Row count mismatch! Expected: {len(requests_df)}, Got: {len(df)}")

        req_map = {r["request_id"]: r for _, r in requests_df.iterrows()}

        for idx, row in df.iterrows():
            req_id = str(row["request_id"])
            if req_id not in req_map:
                errors.append(f"Row {idx}: unknown request_id '{req_id}'")
                continue

            req_row = req_map[req_id]
            req_amt = float(req_row["requested_amount"])

            # 3. amount_safe_to_pay bounds
            safe_amt = float(row["amount_safe_to_pay"])
            if not (0 <= safe_amt <= req_amt + 1e-5):
                errors.append(f"Row {idx} [{req_id}]: amount_safe_to_pay {safe_amt} out of bounds [0, {req_amt}]")

            # 4. Enums
            status = str(row["affordability_status"])
            if status not in self.ALLOWED_STATUSES:
                errors.append(f"Row {idx} [{req_id}]: invalid status '{status}'")

            method = str(row["recommended_payment_method"])
            if method not in self.ALLOWED_METHODS:
                errors.append(f"Row {idx} [{req_id}]: invalid method '{method}'")

            # 5. Date check for affordable_now
            earliest_date = str(row["earliest_date_for_full_payment"]) if pd.notna(row["earliest_date_for_full_payment"]) else ""
            req_date = str(req_row["request_date"]).split()[0]
            if status == "affordable_now" and earliest_date and earliest_date != req_date:
                errors.append(f"Row {idx} [{req_id}]: status is affordable_now but earliest_date '{earliest_date}' != request_date '{req_date}'")

            # 6. Payment plan validation
            plan = str(row["payment_plan"])
            if method == "not_recommended" and plan != "none":
                errors.append(f"Row {idx} [{req_id}]: method is not_recommended but plan is '{plan}' instead of 'none'")

        is_valid = len(errors) == 0
        return is_valid, errors
