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
        Uses the pre-income minimum balance horizon for exact precision.
        """
        if requested_amount <= 0:
            return 0.0

        req_dt = pd.to_datetime(request_date_str)
        res_base = self.simulator.simulate(state, request_date_str, [], spending_changes=None)
        daily_balances = res_base["daily_balances"]
        min_keep = res_base["min_keep"]

        # Determine next income / salary date
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
                next_sal_date = (req_dt + pd.Timedelta(days=30)).strftime("%Y-%m-%d")

        pre_sal_bals = [bal for d_str, bal in daily_balances.items() if d_str < next_sal_date]
        if not pre_sal_bals:
            min_pre_sal = res_base["min_balance"]
        else:
            min_pre_sal = min(pre_sal_bals)

        max_safe = min_pre_sal - min_keep
        safe_amt = max(0.0, min(requested_amount, max_safe))
        return float(int(safe_amt * 100.0) / 100.0)

    def compute_earliest_date_for_full_payment(
        self,
        state: UserFinancialState,
        request_date_str: str,
        requested_amount: float,
        horizon_days: int = 90
    ) -> Optional[str]:
        """
        Finds the earliest date (from request_date_str to request_date_str + horizon_days)
        on which full payment of requested_amount is safe as a single payment (before optional spending changes).
        """
        req_dt = pd.to_datetime(request_date_str)
        res_base = self.simulator.simulate(state, request_date_str, [], spending_changes=None)
        daily_balances = res_base["daily_balances"]
        min_keep = res_base["min_keep"]

        day_strs = [(req_dt + pd.Timedelta(days=i)).strftime("%Y-%m-%d") for i in range(horizon_days)]

        suffix_mins = [0.0] * horizon_days
        curr_min = float("inf")
        for i in range(horizon_days - 1, -1, -1):
            d_str = day_strs[i]
            bal = daily_balances.get(d_str, 0.0)
            if bal < curr_min:
                curr_min = bal
            suffix_mins[i] = curr_min

        for i in range(horizon_days):
            if suffix_mins[i] - requested_amount >= min_keep - 1e-4:
                return day_strs[i]

        return None
