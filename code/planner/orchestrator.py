import pandas as pd
from typing import Dict, Any, List, Optional
from code.data.loader import DataLoader
from code.finance.currency import CurrencyConverter
from code.evidence.image_parser import ImageParser
from code.evidence.event_resolver import EventResolver
from code.finance.recurrence import RecurrenceEngine
from code.finance.state_builder import StateBuilder
from code.finance.cashflow import CashFlowSimulator
from code.finance.safety import SafetyCalculator
from code.planner.spending_changes import SpendingChangesExplorer
from code.planner.candidates import CandidateGenerator, CandidatePlan
from code.planner.ranking import PlanRanker
from code.ai.explanation import ExplanationGenerator

class DecisionEngine:
    def __init__(self, data_loader: DataLoader):
        self.loader = data_loader
        self.fx = CurrencyConverter(self.loader.rates_df)
        self.img_parser = ImageParser()
        self.resolver = EventResolver(self.fx, self.img_parser)
        self.recurrence_engine = RecurrenceEngine()
        self.state_builder = StateBuilder()
        self.simulator = CashFlowSimulator(horizon_days=90)
        self.safety_calc = SafetyCalculator(self.simulator)
        self.spending_explorer = SpendingChangesExplorer(self.simulator)
        self.candidate_gen = CandidateGenerator()
        self.ranker = PlanRanker()
        self.explainer = ExplanationGenerator()

    def process_request(self, request_row: pd.Series) -> Dict[str, Any]:
        req_id = str(request_row["request_id"])
        user_id = str(request_row["user_id"])
        req_date = str(request_row["request_date"]).split()[0]
        req_amt = float(request_row["requested_amount"])
        desired_deadline = str(request_row["desired_completion_date"]).split()[0]
        allows_partial = bool(request_row.get("allows_partial_payment", False))

        # 1. Retrieve user data
        profile = self.loader.get_user_profile(user_id)
        raw_events = self.loader.get_user_events(user_id)
        payment_opts = self.loader.get_request_payment_options(req_id)
        user_msgs = self.loader.get_user_messages(user_id)

        home_curr = profile.get("home_currency", "USD")

        # 2. Resolve events
        resolved_events = self.resolver.resolve_user_events(
            user_id,
            home_curr,
            raw_events,
            self.loader.images_by_event,
            user_msgs
        )

        # 3. Detect recurrence
        recurring_streams = self.recurrence_engine.detect_recurring_patterns(resolved_events, req_date, user_msgs)

        # 4. Build user state
        state = self.state_builder.build_state(profile, resolved_events, recurring_streams)

        # 5. Compute amount_safe_to_pay (before spending changes)
        safe_amt = self.safety_calc.compute_amount_safe_to_pay(state, req_date, req_amt)

        # 6. Compute earliest_date_for_full_payment (before spending changes)
        earliest_full_date = self.safety_calc.compute_earliest_date_for_full_payment(state, req_date, req_amt)
        earliest_full_date_str = earliest_full_date if earliest_full_date else ""

        # 7. Generate candidate plans
        candidates = self.candidate_gen.generate_candidates(
            state,
            request_row,
            safe_amt,
            earliest_full_date,
            payment_opts
        )

        # 8. Evaluate candidates & spending changes
        safe_candidates: List[CandidatePlan] = []
        for cand in candidates:
            cand_max_date = max(desired_deadline, cand.end_date) if cand.end_date != "9999-12-31" else desired_deadline
            res_base = self.simulator.simulate(state, req_date, cand.schedule, spending_changes=None, max_eval_date=cand_max_date)
            if res_base["is_safe"]:
                cand.spending_changes = []
                safe_candidates.append(cand)
            else:
                sp_changes = self.spending_explorer.find_spending_changes_for_plan(state, req_date, cand.schedule)
                if sp_changes is not None:
                    # Re-verify safety with spending changes
                    res_sp = self.simulator.simulate(state, req_date, cand.schedule, spending_changes=sp_changes, max_eval_date=cand_max_date)
                    if res_sp["is_safe"]:
                        cand.spending_changes = sp_changes
                        safe_candidates.append(cand)

        # 9. Rank safe plans
        best_plan = self.ranker.rank_plans(safe_candidates, desired_deadline)

        # 10. Construct final recommendation metrics
        if best_plan is not None:
            rec_method = best_plan.method
            plan_str = best_plan.format_payment_plan()
            sp_change_texts = [sc["text"] for sc in best_plan.spending_changes]
            sp_changes_str = "|".join(sp_change_texts) if sp_change_texts else "none"

            if rec_method == "full_payment" and best_plan.start_date == req_date and len(best_plan.spending_changes) == 0:
                aff_status = "affordable_now"
                final_earliest_date = req_date
            elif rec_method == "wait" and len(best_plan.spending_changes) == 0:
                aff_status = "affordable_later"
                final_earliest_date = earliest_full_date_str
            else:
                aff_status = "affordable_with_plan"
                final_earliest_date = earliest_full_date_str
        else:
            rec_method = "not_recommended"
            aff_status = "not_affordable"
            plan_str = "none"
            sp_changes_str = "none"
            final_earliest_date = ""


        rec_dict = {
            "request_id": req_id,
            "amount_safe_to_pay": safe_amt,
            "affordability_status": aff_status,
            "recommended_payment_method": rec_method,
            "payment_plan": plan_str,
            "earliest_date_for_full_payment": final_earliest_date,
            "spending_changes_needed": sp_changes_str,
            "currency": home_curr,
            "requested_amount": req_amt,
            "minimum_balance_to_keep": state.minimum_balance_to_keep,
            "desired_completion_date": desired_deadline
        }

        # 11. Generate explanation
        explanation = self.explainer.generate_explanation(rec_dict)
        rec_dict["decision_explanation"] = explanation

        return rec_dict
