import pandas as pd
from typing import Dict, Any, List, Tuple, Optional, Set
from datetime import datetime, timedelta
from code.finance.state_builder import UserFinancialState

class CashFlowSimulator:
    def __init__(self, horizon_days: int = 90):
        self.horizon_days = horizon_days

    def simulate(
        self,
        state: UserFinancialState,
        request_date_str: str,
        payment_schedule: List[Tuple[str, float]],
        spending_changes: Optional[List[Dict[str, Any]]] = None,
        max_eval_date: Optional[str] = None
    ) -> Dict[str, Any]:
        req_dt = pd.to_datetime(request_date_str)
        curr_bal = state.current_available_balance
        min_keep = state.minimum_balance_to_keep

        if max_eval_date:
            max_eval_dt = pd.to_datetime(str(max_eval_date).split()[0])
            eval_days = max(1, min(self.horizon_days, (max_eval_dt - req_dt).days + 1))
        else:
            eval_days = self.horizon_days

        stopped_events: Set[str] = set()
        stopped_categories: Set[str] = set()
        reduced_events: Dict[str, float] = {}
        reduced_categories: Dict[str, float] = {}

        if spending_changes:
            for sc in spending_changes:
                action_type = sc.get("type")
                ev_id = sc.get("event_id")
                cat = sc.get("category")
                amt = sc.get("amount", 0.0)

                if action_type == "stop":
                    if ev_id: stopped_events.add(ev_id)
                    if cat: stopped_categories.add(cat)
                elif action_type == "reduce_to":
                    if ev_id: reduced_events[ev_id] = amt
                    if cat: reduced_categories[cat] = amt

        plan_payments_by_date: Dict[str, float] = {}
        for pdate, pamt in payment_schedule:
            pdate_str = str(pdate).split()[0]
            plan_payments_by_date[pdate_str] = plan_payments_by_date.get(pdate_str, 0.0) + pamt

        # Pre-group resolved events by date
        events_by_date: Dict[str, List[Dict[str, Any]]] = {}
        pending_debits_before_req: List[Dict[str, Any]] = []

        for ev in state.resolved_events:
            status = ev["status"]
            if status in ["cancelled", "failed", "unrealized"]:
                continue
            sdate = str(ev.get("settlement_date", ev.get("event_date", ""))).split()[0]
            if sdate:
                if sdate < request_date_str:
                    if status == "pending" and ev["direction"] == "debit":
                        pending_debits_before_req.append(ev)
                else:
                    if sdate not in events_by_date:
                        events_by_date[sdate] = []
                    events_by_date[sdate].append(ev)

        # Include un-settled pending debits before request_date on request_date_str
        if pending_debits_before_req:
            if request_date_str not in events_by_date:
                events_by_date[request_date_str] = []
            events_by_date[request_date_str].extend(pending_debits_before_req)

        # Pre-compute recurring stream dates for the horizon
        rec_income = state.recurring_streams.get("income", [])
        rec_expenses = state.recurring_streams.get("expenses", [])

        projected_recurring_by_date: Dict[str, List[Dict[str, Any]]] = {}

        for inc in rec_income:
            freq = inc["frequency"]
            last_dt = pd.to_datetime(inc["last_event_date"])
            for i in range(0, eval_days):
                day_dt = req_dt + pd.Timedelta(days=i)
                day_str = day_dt.strftime("%Y-%m-%d")
                is_due = False
                if freq == "monthly" and day_dt.day == inc["day_of_month"]:
                    is_due = True
                elif freq == "weekly" and (day_dt - last_dt).days >= 0 and (day_dt - last_dt).days % 7 == 0:
                    is_due = True
                elif freq == "biweekly" and (day_dt - last_dt).days >= 0 and (day_dt - last_dt).days % 14 == 0:
                    is_due = True

                if is_due:
                    if day_str not in projected_recurring_by_date:
                        projected_recurring_by_date[day_str] = []
                    projected_recurring_by_date[day_str].append({
                        "type": "income",
                        "category": inc["category"],
                        "amount": inc["amount"],
                        "event_id": inc.get("latest_event_id")
                    })

        for exp in rec_expenses:
            freq = exp["frequency"]
            last_dt = pd.to_datetime(exp["last_event_date"])
            for i in range(0, eval_days):
                day_dt = req_dt + pd.Timedelta(days=i)
                day_str = day_dt.strftime("%Y-%m-%d")
                is_due = False
                if freq == "monthly" and day_dt.day == exp["day_of_month"]:
                    is_due = True
                elif freq == "weekly" and (day_dt - last_dt).days >= 0 and (day_dt - last_dt).days % 7 == 0:
                    is_due = True
                elif freq == "biweekly" and (day_dt - last_dt).days >= 0 and (day_dt - last_dt).days % 14 == 0:
                    is_due = True

                if is_due:
                    if day_str not in projected_recurring_by_date:
                        projected_recurring_by_date[day_str] = []
                    projected_recurring_by_date[day_str].append({
                        "type": "expense",
                        "category": exp["category"],
                        "amount": exp["amount"],
                        "event_id": exp.get("latest_event_id")
                    })

        daily_balances: Dict[str, float] = {}
        running_bal = curr_bal
        min_bal = curr_bal
        min_bal_date = request_date_str
        is_safe = True

        for i in range(eval_days):

            day_dt = req_dt + pd.Timedelta(days=i)
            day_str = day_dt.strftime("%Y-%m-%d")

            inflow = 0.0
            outflow = 0.0

            # 1. Explicit events on day_str
            explicit_cats_on_day: Set[str] = set()
            if day_str in events_by_date:
                for ev in events_by_date[day_str]:
                    direction = ev["direction"]
                    status = ev["status"]
                    amt = ev["amount"]
                    ev_id = ev["event_id"]
                    cat = ev["category"]
                    sdate = str(ev.get("settlement_date", ev.get("event_date", ""))).split()[0]

                    if sdate < request_date_str:
                        continue

                    explicit_cats_on_day.add(cat)

                    if direction == "debit":
                        if status in ["pending", "scheduled", "settled"]:
                            if ev_id in stopped_events or cat in stopped_categories:
                                pass
                            elif ev_id in reduced_events:
                                outflow += reduced_events[ev_id]
                            elif cat in reduced_categories:
                                outflow += reduced_categories[cat]
                            else:
                                outflow += amt

                    elif direction == "credit":
                        if status == "pending":
                            pass # Reserve pending credits -> MUST NOT COUNT!
                        elif status in ["scheduled", "settled"]:
                            inflow += amt

            # 2. Projected recurring streams on day_str
            if day_str in projected_recurring_by_date:
                for item in projected_recurring_by_date[day_str]:
                    cat = item["category"]
                    ev_id = item["event_id"]
                    amt = item["amount"]
                    stype = item["type"]

                    if cat in explicit_cats_on_day:
                        continue

                    if stype == "income":
                        inflow += amt
                    elif stype == "expense":
                        if ev_id in stopped_events or cat in stopped_categories:
                            pass
                        elif ev_id in reduced_events:
                            outflow += reduced_events[ev_id]
                        elif cat in reduced_categories:
                            outflow += reduced_categories[cat]
                        else:
                            outflow += amt

            # 3. Candidate plan payment on day_str
            if day_str in plan_payments_by_date:
                outflow += plan_payments_by_date[day_str]

            running_bal += (inflow - outflow)
            daily_balances[day_str] = running_bal

            if running_bal < min_bal:
                min_bal = running_bal
                min_bal_date = day_str

            if running_bal < min_keep - 1e-4:
                is_safe = False

        return {
            "daily_balances": daily_balances,
            "min_balance": min_bal,
            "min_balance_date": min_bal_date,
            "is_safe": is_safe,
            "min_keep": min_keep
        }
