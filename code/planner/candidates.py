import pandas as pd
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timedelta
from code.finance.state_builder import UserFinancialState

class CandidatePlan:
    def __init__(
        self,
        method: str, # full_payment, partial_payment, installments, wait, not_recommended
        schedule: List[Tuple[str, float]], # List of (date_str, amount)
        total_amount: float,
        option_id: Optional[str] = None,
        spending_changes: Optional[List[Dict[str, Any]]] = None
    ):
        self.method = method
        self.schedule = schedule
        self.total_amount = total_amount
        self.option_id = option_id
        self.spending_changes = spending_changes or []

    @property
    def start_date(self) -> str:
        if not self.schedule:
            return "9999-12-31"
        return self.schedule[0][0]

    @property
    def end_date(self) -> str:
        if not self.schedule:
            return "9999-12-31"
        return self.schedule[-1][0]

    @property
    def num_payments(self) -> int:
        return len(self.schedule)

    def format_payment_plan(self) -> str:
        if not self.schedule or self.method == "not_recommended":
            return "none"
        # Chronological order
        sorted_sched = sorted(self.schedule, key=lambda x: str(x[0]))
        parts = []
        for d, a in sorted_sched:
            d_str = str(d).split()[0]
            # Format amount cleanly
            if a == int(a):
                amt_str = f"{int(a)}"
            else:
                amt_str = f"{a:.2f}".rstrip('0').rstrip('.')
            parts.append(f"{d_str}:{amt_str}")
        return "|".join(parts)


class CandidateGenerator:
    def generate_candidates(
        self,
        state: UserFinancialState,
        request_row: pd.Series,
        amount_safe_to_pay: float,
        earliest_date_for_full_payment: Optional[str],
        payment_options_df: pd.DataFrame
    ) -> List[CandidatePlan]:
        candidates: List[CandidatePlan] = []

        req_date = str(request_row["request_date"]).split()[0]
        req_amt = float(request_row["requested_amount"])
        completion_date = str(request_row["desired_completion_date"]).split()[0]
        allows_partial = bool(request_row.get("allows_partial_payment", False))

        methods_accepted = state.payment_methods_to_consider

        # 1. Full Payment candidate
        if "full_payment" in methods_accepted:
            candidates.append(CandidatePlan(
                method="full_payment",
                schedule=[(req_date, req_amt)],
                total_amount=req_amt
            ))

        # 2. Partial Payment candidate
        if (
            allows_partial
            and "partial_payment" in methods_accepted
            and 0 < amount_safe_to_pay < req_amt
            and earliest_date_for_full_payment
            and earliest_date_for_full_payment <= completion_date
        ):
            rem_amt = round(req_amt - amount_safe_to_pay, 2)
            candidates.append(CandidatePlan(
                method="partial_payment",
                schedule=[(req_date, amount_safe_to_pay), (earliest_date_for_full_payment, rem_amt)],
                total_amount=req_amt
            ))

        # 3. Installment candidates from supplied payment options
        if "installments" in methods_accepted and not payment_options_df.empty:
            for _, opt in payment_options_df.iterrows():
                opt_method = str(opt["payment_method"]).strip().lower()
                if opt_method != "installments":
                    continue

                opt_id = str(opt["payment_option_id"])
                n_pay = int(opt["number_of_payments"])
                p_amt = float(opt["payment_amount"])
                first_date = str(opt["first_payment_date"]).split()[0]
                freq = float(opt.get("payment_frequency_days", 30))
                if pd.isna(freq): freq = 30.0
                total_payable = float(opt["total_payable_amount"])

                # Check max_installment_months if set
                if state.max_installment_months is not None:
                    est_months = (n_pay * freq) / 30.0
                    if est_months > state.max_installment_months + 0.5:
                        continue

                # Build schedule
                first_dt = pd.to_datetime(first_date)
                sched = []
                for k in range(n_pay):
                    k_dt = first_dt + pd.Timedelta(days=int(k * freq))
                    sched.append((k_dt.strftime("%Y-%m-%d"), p_amt))

                candidates.append(CandidatePlan(
                    method="installments",
                    schedule=sched,
                    total_amount=total_payable,
                    option_id=opt_id
                ))

        # 4. Wait candidate
        if (
            "full_payment" in methods_accepted
            and earliest_date_for_full_payment
            and earliest_date_for_full_payment > req_date
        ):
            candidates.append(CandidatePlan(
                method="wait",
                schedule=[(earliest_date_for_full_payment, req_amt)],
                total_amount=req_amt
            ))

        return candidates
