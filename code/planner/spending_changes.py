import pandas as pd
from typing import Dict, Any, List, Optional, Tuple, Set
from code.finance.state_builder import UserFinancialState
from code.finance.cashflow import CashFlowSimulator

class SpendingChangesExplorer:
    def __init__(self, simulator: CashFlowSimulator):
        self.simulator = simulator

    def find_spending_changes_for_plan(
        self,
        state: UserFinancialState,
        request_date_str: str,
        payment_schedule: List[Tuple[str, float]]
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Explores valid spending changes (max 3) to make a payment_schedule safe if baseline simulation fails.
        Limits search space to top impact candidate actions for high performance.
        """
        base_res = self.simulator.simulate(state, request_date_str, payment_schedule, spending_changes=None)
        if base_res["is_safe"]:
            return []

        rec_expenses = state.recurring_streams.get("expenses", [])
        candidate_actions: List[Dict[str, Any]] = []

        for exp in rec_expenses:
            cat = exp["category"]
            ev_id = exp.get("latest_event_id")
            flex = exp.get("flexibility", "fixed")

            if cat in state.categories_to_protect:
                continue

            if flex == "fixed":
                continue

            # Can we stop this expense?
            if cat in state.categories_to_stop and flex in ["stoppable", "reducible_or_stoppable"]:
                candidate_actions.append({
                    "type": "stop",
                    "event_id": ev_id,
                    "category": cat,
                    "amount": 0.0,
                    "savings": exp["amount"],
                    "text": f"stop:{ev_id}"
                })

            # Can we reduce this expense?
            if cat in state.categories_to_reduce and flex in ["reducible", "reducible_or_stoppable"]:
                min_amt = exp.get("minimum_allowed_amount")
                if min_amt is not None and min_amt < exp["amount"]:
                    target_amt = float(min_amt)
                else:
                    target_amt = round(exp["amount"] * 0.5, 2)

                savings = exp["amount"] - target_amt
                if savings > 0:
                    candidate_actions.append({
                        "type": "reduce_to",
                        "event_id": ev_id,
                        "category": cat,
                        "amount": target_amt,
                        "savings": savings,
                        "text": f"reduce_to:{ev_id}:{target_amt:.2f}".rstrip('0').rstrip('.') if target_amt == int(target_amt) else f"reduce_to:{ev_id}:{target_amt}"
                    })

        if not candidate_actions:
            return None

        # Sort candidate actions by savings descending and cap at top 6
        candidate_actions.sort(key=lambda x: x["savings"], reverse=True)
        top_actions = candidate_actions[:6]

        # Test single actions
        for act in top_actions:
            res = self.simulator.simulate(state, request_date_str, payment_schedule, spending_changes=[act])
            if res["is_safe"]:
                return [act]

        # Test combinations of 2 actions
        for i in range(len(top_actions)):
            for j in range(i + 1, len(top_actions)):
                act1, act2 = top_actions[i], top_actions[j]
                if act1["event_id"] == act2["event_id"]:
                    continue
                res = self.simulator.simulate(state, request_date_str, payment_schedule, spending_changes=[act1, act2])
                if res["is_safe"]:
                    return [act1, act2]

        # Test combinations of 3 actions
        for i in range(len(top_actions)):
            for j in range(i + 1, len(top_actions)):
                for k in range(j + 1, len(top_actions)):
                    act1, act2, act3 = top_actions[i], top_actions[j], top_actions[k]
                    eids = {act1["event_id"], act2["event_id"], act3["event_id"]}
                    if len(eids) < 3:
                        continue
                    res = self.simulator.simulate(state, request_date_str, payment_schedule, spending_changes=[act1, act2, act3])
                    if res["is_safe"]:
                        return [act1, act2, act3]

        return None
