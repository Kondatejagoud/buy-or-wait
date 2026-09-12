from typing import List, Optional
from code.planner.candidates import CandidatePlan

class PlanRanker:
    @staticmethod
    def rank_plans(
        safe_plans: List[CandidatePlan],
        desired_completion_date: str
    ) -> Optional[CandidatePlan]:
        if not safe_plans:
            return None

        comp_date = str(desired_completion_date).split()[0]

        def ranking_key(plan: CandidatePlan):
            # 1. Complete full request by desired_completion_date
            completes_by_deadline = 0 if (plan.end_date <= comp_date) else 1

            # 2. Require no spending changes (number of spending changes)
            num_spending_changes = len(plan.spending_changes)

            # 3. Minimize total amount paid
            total_cost = round(plan.total_amount, 2)

            # 4. Start payment earlier
            start_date_str = plan.start_date

            # 5. Use fewer payments
            n_payments = plan.num_payments

            # 6. Lowest payment_option_id as tie-breaker
            opt_id = plan.option_id if plan.option_id else "zzzzzz"

            return (
                completes_by_deadline,
                num_spending_changes,
                total_cost,
                start_date_str,
                n_payments,
                opt_id
            )

        sorted_plans = sorted(safe_plans, key=ranking_key)
        return sorted_plans[0]
