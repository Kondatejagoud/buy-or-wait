import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

class RecurrenceEngine:
    def __init__(self):
        pass

    def detect_recurring_patterns(
        self,
        resolved_events: List[Dict[str, Any]],
        request_date_str: str,
        user_messages_df: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        Analyzes resolved events for a user and detects recurring income and recurring expenses.
        Extracts frequency (monthly, weekly, biweekly), typical amount, day_of_month, and last_event_date.
        Excludes terminal payrolls, ended contracts, and unconfirmed variable income.
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

        # Check messages for job loss / contract ended / payout unconfirmed notes
        msg_texts = []
        if user_messages_df is not None and not user_messages_df.empty:
            for _, m in user_messages_df.iterrows():
                msg_texts.append(str(m.get("message_text", "")).lower())
        all_msg_text = " ".join(msg_texts)

        recurring_income: List[Dict[str, Any]] = []
        recurring_expenses: List[Dict[str, Any]] = []

        for cat, ev_list in events_by_cat.items():
            if not ev_list:
                continue

            sorted_evs = sorted(ev_list, key=lambda x: pd.to_datetime(x["event_date"]))
            latest_ev = sorted_evs[-1]

            # Convert amounts, excluding one-time/arrears/adjustment descriptions for recurring stream baseline
            one_time_kws = ["outstanding", "arrears", "one-time", "one-off", "adjustment", "bonus", "penalty", "refund"]
            regular_evs = [e for e in sorted_evs if not any(kw in str(e.get("description", "")).lower() for kw in one_time_kws)]
            
            if regular_evs:
                reg_amounts = [e["amount"] for e in regular_evs if e["amount"] > 0]
                typical_amt = reg_amounts[-1] if reg_amounts else sorted_evs[-1]["amount"]
                avg_amt = sum(reg_amounts) / len(reg_amounts) if reg_amounts else sorted_evs[-1]["amount"]
            else:
                reg_amounts = [e["amount"] for e in sorted_evs if e["amount"] > 0]
                typical_amt = sorted_evs[-1]["amount"]
                avg_amt = sum(reg_amounts) / len(reg_amounts) if reg_amounts else 0.0

            if typical_amt <= 0:
                continue

            dates = [pd.to_datetime(e["event_date"]) for e in sorted_evs]
            last_date_str = sorted_evs[-1]["event_date"]

            direction = latest_ev["direction"]
            ev_type = latest_ev["event_type"]
            is_income_cat = (direction == "credit" or ev_type == "income" or cat == "salary")

            if is_income_cat:
                # 1. Require historical evidence (at least 2 events) OR explicit future scheduled credit
                has_scheduled_future = any(e["status"] == "scheduled" and e["event_date"] >= request_date_str for e in sorted_evs)
                if len(dates) < 2 and not has_scheduled_future:
                    continue

                # 2. Check for terminal employer payroll or contract ended keywords
                descriptions = " ".join([str(e.get("description", "")).lower() for e in sorted_evs])
                terminal_keywords = [
                    "final employer payroll", "final payroll", "last salary", "contract ended",
                    "contract has ended", "employment ended", "terminated", "berakhir",
                    "dikeluarkan dari perkiraan", "no off-season income", "not withdrawable"
                ]
                if any(kw in descriptions for kw in terminal_keywords) or any(kw in all_msg_text for kw in terminal_keywords):
                    # Check if there is an explicit future scheduled payment overriding this
                    if not has_scheduled_future:
                        continue

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

            pattern = {
                "category": cat,
                "amount": typical_amt,
                "avg_amount": avg_amt,
                "frequency": freq,
                "day_of_month": common_day,
                "last_event_date": last_date_str,
                "flexibility": latest_ev["flexibility"],
                "minimum_allowed_amount": latest_ev["minimum_allowed_amount"],
                "latest_event_id": latest_ev["event_id"],
                "all_event_ids": [e["event_id"] for e in sorted_evs]
            }

            if is_income_cat:
                recurring_income.append(pattern)
            elif (direction == "debit" or ev_type in ["expense", "subscription", "debt_payment"]) and len(dates) >= 2:
                recurring_expenses.append(pattern)

        return {
            "income": recurring_income,
            "expenses": recurring_expenses
        }

