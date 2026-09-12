import pandas as pd
from typing import Dict, Any, Optional
from code.finance.state_builder import UserFinancialState
from code.finance.cashflow import CashFlowSimulator

class SafetyCalculator:
    def __init__(self, simulator: CashFlowSimulator):
        self.simulator = simulator

    def compute_amount_safe_to_pay(
        self,
        state: UserFinancialState,
        request_date_str: str,
        requested_amount: float
    ) -> float:
        """
        Calculates the maximum amount safe to pay on request_date before optional spending changes.
        Uses exact pre-payday cash headroom as an UPPER BOUND for the 90-day simulation binary search.
        """
        if requested_amount <= 0:
            return 0.0

        req_dt = pd.to_datetime(request_date_str)

        # 1. Determine next confirmed salary / income date
        sal_events = [e for e in state.resolved_events if e["category"] == "salary" and e["status"] in ["scheduled", "settled"] and e["event_date"] > request_date_str]
        if sal_events:
            next_sal_date = min(e["event_date"] for e in sal_events)
        else:
            inc_streams = state.recurring_streams.get("income", [])
            if inc_streams:
                inc_day = inc_streams[0]["day_of_month"]
                if inc_day > req_dt.day:
                    next_sal_dt = pd.Timestamp(year=req_dt.year, month=req_dt.month, day=inc_day)
                else:
                    next_m = req_dt.month % 12 + 1
                    next_y = req_dt.year + (1 if req_dt.month == 12 else 0)
                    next_sal_dt = pd.Timestamp(year=next_y, month=next_m, day=min(inc_day, 28))
                next_sal_date = next_sal_dt.strftime("%Y-%m-%d")
            else:
                next_sal_date = (req_dt + pd.Timedelta(days=90)).strftime("%Y-%m-%d")

        # 2. Calculate pre-payday required expenses
        pre_payday_expenses = 0.0
        explicit_cats_pre = set()
        for ev in state.resolved_events:
            if ev["status"] in ["cancelled", "failed", "unrealized"]:
                continue
            if ev["direction"] == "debit":
                edate = str(ev.get("settlement_date", ev.get("event_date", ""))).split()[0]
                if request_date_str <= edate < next_sal_date or (ev["status"] == "pending" and edate <= next_sal_date):
                    pre_payday_expenses += ev["amount"]
                    explicit_cats_pre.add(ev["category"])

        days_to_sal = (pd.to_datetime(next_sal_date) - req_dt).days
        for i in range(0, max(1, days_to_sal)):
            day_dt = req_dt + pd.Timedelta(days=i)
            for exp in state.recurring_streams.get("expenses", []):
                cat = exp["category"]
                freq = exp["frequency"]
                dom = exp["day_of_month"]
                amt = exp["amount"]
                is_due = False
                if freq == "monthly" and day_dt.day == dom:
                    is_due = True
                elif freq == "weekly" and (day_dt - pd.to_datetime(exp["last_event_date"])).days >= 0 and (day_dt - pd.to_datetime(exp["last_event_date"])).days % 7 == 0:
                    is_due = True
                elif freq == "biweekly" and (day_dt - pd.to_datetime(exp["last_event_date"])).days >= 0 and (day_dt - pd.to_datetime(exp["last_event_date"])).days % 14 == 0:
                    is_due = True

                if is_due and cat not in explicit_cats_pre:
                    pre_payday_expenses += amt

        # 3. Headroom upper bound
        headroom = max(0.0, state.current_available_balance - state.minimum_balance_to_keep - pre_payday_expenses)
        upper_bound = min(requested_amount, headroom)

        # 4. Check if upper_bound passes 90-day simulation
        res_ub = self.simulator.simulate(
            state, request_date_str, [(request_date_str, upper_bound)], spending_changes=None
        )
        if res_ub["is_safe"]:
            return float(int(round(upper_bound, 4) * 100.0) / 100.0)

        # 5. Deterministic binary search within [0, upper_bound] validated by 90-day simulator
        low = 0.0
        high = upper_bound
        best_safe = 0.0

        for _ in range(25):
            mid = (low + high) / 2.0
            res = self.simulator.simulate(
                state, request_date_str, [(request_date_str, mid)], spending_changes=None
            )
            if res["is_safe"]:
                best_safe = mid
                low = mid
            else:
                high = mid

        safe_amt = float(int(round(best_safe, 4) * 100.0) / 100.0)
        return max(0.0, min(requested_amount, safe_amt))

    def compute_earliest_date_for_full_payment(
        self,
        state: UserFinancialState,
        request_date_str: str,
        requested_amount: float,
        horizon_days: int = 90
    ) -> Optional[str]:
        """
        Finds the earliest date (from request_date_str to request_date_str + horizon_days)
        on which a single full payment of requested_amount is safe (before optional spending changes).
        Tests each candidate date using the authoritative financial simulator.
        """
        req_dt = pd.to_datetime(request_date_str)
        for i in range(horizon_days):
            cand_date = (req_dt + pd.Timedelta(days=i)).strftime("%Y-%m-%d")
            res = self.simulator.simulate(
                state,
                request_date_str,
                [(cand_date, requested_amount)],
                spending_changes=None
            )
            if res["is_safe"]:
                return cand_date

        return None


