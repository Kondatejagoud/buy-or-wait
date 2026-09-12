import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

class RecurrenceEngine:
    def __init__(self):
        pass

    def detect_recurring_patterns(
        self,
        resolved_events: List[Dict[str, Any]],
        request_date_str: str
    ) -> Dict[str, Any]:
        """
        Analyzes resolved events for a user and detects recurring income and recurring expenses.
        Extracts frequency (monthly, weekly, biweekly), typical amount, day_of_month, and last_event_date.
        """
        events_by_cat: Dict[str, List[Dict[str, Any]]] = {}
        for ev in resolved_events:
            status = ev["status"]
            if status in ["cancelled", "failed", "unrealized"]:
                continue
            cat = ev["category"]
            if cat not in events_by_cat:
                events_by_cat[cat] = []
            events_by_cat[cat].append(ev)

        recurring_income: List[Dict[str, Any]] = []
        recurring_expenses: List[Dict[str, Any]] = []

        for cat, ev_list in events_by_cat.items():
            if not ev_list:
                continue

            sorted_evs = sorted(ev_list, key=lambda x: pd.to_datetime(x["event_date"]))
            latest_ev = sorted_evs[-1]

            # Convert amounts
            amounts = [e["amount"] for e in sorted_evs if e["amount"] > 0]
            if not amounts:
                continue
            avg_amt = sum(amounts) / len(amounts)
            latest_amt = latest_ev["amount"] if latest_ev["amount"] > 0 else avg_amt

            dates = [pd.to_datetime(e["event_date"]) for e in sorted_evs]
            last_date_str = sorted_evs[-1]["event_date"]

            if len(dates) >= 2:
                diffs = [(dates[i] - dates[i-1]).days for i in range(1, len(dates))]
                avg_diff = sum(diffs) / len(diffs)
            else:
                avg_diff = 30

            if 5 <= avg_diff <= 9:
                freq = "weekly"
            elif 12 <= avg_diff <= 16:
                freq = "biweekly"
            else:
                freq = "monthly"

            days_of_month = [d.day for d in dates]
            common_day = max(set(days_of_month), key=days_of_month.count)

            direction = latest_ev["direction"]
            ev_type = latest_ev["event_type"]

            pattern = {
                "category": cat,
                "amount": latest_amt,
                "avg_amount": avg_amt,
                "frequency": freq,
                "day_of_month": common_day,
                "last_event_date": last_date_str,
                "flexibility": latest_ev["flexibility"],
                "minimum_allowed_amount": latest_ev["minimum_allowed_amount"],
                "latest_event_id": latest_ev["event_id"],
                "all_event_ids": [e["event_id"] for e in sorted_evs]
            }

            if direction == "credit" or ev_type == "income" or cat == "salary":
                recurring_income.append(pattern)
            elif direction == "debit" or ev_type in ["expense", "subscription", "debt_payment"]:
                recurring_expenses.append(pattern)

        return {
            "income": recurring_income,
            "expenses": recurring_expenses
        }
