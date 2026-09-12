import pandas as pd
from typing import Dict, Any, List, Optional

class ExplanationGenerator:
    """
    Generates grounded decision explanations from deterministic financial decision facts.
    """
    @staticmethod
    def format_currency_amount(amount: float, currency: str) -> str:
        symbol_map = {"INR": "INR", "ZAR": "ZAR", "IDR": "IDR", "USD": "USD", "EUR": "EUR"}
        curr_str = symbol_map.get(currency, currency)

        if amount == int(amount):
            amt_str = f"{int(amount):,}"
        else:
            amt_str = f"{amount:,.2f}".rstrip('0').rstrip('.')

        return f"{curr_str} {amt_str}"

    @staticmethod
    def format_date_friendly(date_str: str) -> str:
        try:
            dt = pd.to_datetime(date_str)
            return dt.strftime("%d %B %Y").lstrip("0")
        except Exception:
            return date_str

    def generate_explanation(
        self,
        recommendation: Dict[str, Any]
    ) -> str:
        method = recommendation["recommended_payment_method"]
        status = recommendation["affordability_status"]
        currency = recommendation["currency"]
        req_amt = recommendation["requested_amount"]
        safe_amt = recommendation["amount_safe_to_pay"]
        min_keep = recommendation["minimum_balance_to_keep"]
        plan_str = recommendation["payment_plan"]
        earliest_date = recommendation.get("earliest_date_for_full_payment")
        spending_changes = recommendation.get("spending_changes_needed", "none")
        deadline = recommendation.get("desired_completion_date", "")

        curr_req = self.format_currency_amount(req_amt, currency)
        curr_safe = self.format_currency_amount(safe_amt, currency)
        curr_min = self.format_currency_amount(min_keep, currency)

        if method == "full_payment":
            if spending_changes != "none":
                return f"Make the required spending adjustments, then pay {curr_req} today. This keeps the projected balance above the required minimum."
            else:
                return f"Pay {curr_req} today. This leaves at least {curr_min} available."

        elif method == "partial_payment":
            # Extract two payment amounts and date from plan_str
            parts = plan_str.split("|")
            p1_amt = self.format_currency_amount(safe_amt, currency)
            p2_date_str = parts[1].split(":")[0] if len(parts) > 1 else earliest_date
            p2_amt_val = req_amt - safe_amt
            p2_amt = self.format_currency_amount(p2_amt_val, currency)
            friendly_date = self.format_date_friendly(p2_date_str)
            return f"Pay {p1_amt} today and the remaining {p2_amt} on {friendly_date}. This completes the full request and keeps the {curr_min} minimum protected."

        elif method == "installments":
            parts = plan_str.split("|")
            num_inst = len(parts)
            first_date_str = parts[0].split(":")[0]
            inst_amt_val = float(parts[0].split(":")[1])
            inst_amt = self.format_currency_amount(inst_amt_val, currency)
            friendly_date = self.format_date_friendly(first_date_str)
            return f"Use {num_inst} installments of {inst_amt}, starting {friendly_date}. This leaves at least {curr_min} available."

        elif method == "wait":
            if earliest_date:
                friendly_date = self.format_date_friendly(earliest_date)
                return f"Pay {curr_req} in full on {friendly_date}. Paying earlier would take the balance below the {curr_min} minimum."
            else:
                return f"Wait until the full amount becomes safe. Paying today would reduce the balance below the {curr_min} minimum."

        else: # not_recommended
            if deadline:
                friendly_deadline = self.format_date_friendly(deadline)
                return f"Do not make this payment by {friendly_deadline}. None of the available options keeps the {curr_min} minimum protected."
            else:
                return f"Do not proceed with this request today. Paying the requested amount would reduce the balance below the {curr_min} minimum."
