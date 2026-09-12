import pandas as pd
from typing import Dict, Any, List, Set, Optional

class UserFinancialState:
    def __init__(
        self,
        user_id: str,
        home_currency: str,
        current_available_balance: float,
        minimum_balance_to_keep: float,
        categories_to_protect: Set[str],
        categories_to_reduce: Set[str],
        categories_to_stop: Set[str],
        payment_methods_to_consider: Set[str],
        max_installment_months: Optional[float],
        resolved_events: List[Dict[str, Any]],
        recurring_streams: Dict[str, Any]
    ):
        self.user_id = user_id
        self.home_currency = home_currency
        self.current_available_balance = current_available_balance
        self.minimum_balance_to_keep = minimum_balance_to_keep
        self.categories_to_protect = categories_to_protect
        self.categories_to_reduce = categories_to_reduce
        self.categories_to_stop = categories_to_stop
        self.payment_methods_to_consider = payment_methods_to_consider
        self.max_installment_months = max_installment_months
        self.resolved_events = resolved_events
        self.recurring_streams = recurring_streams


class StateBuilder:
    @staticmethod
    def _parse_pipe_list(val: Any) -> Set[str]:
        if pd.isna(val) or not val or str(val).strip().lower() in ["nan", "none"]:
            return set()
        return {item.strip().lower() for item in str(val).split("|") if item.strip()}

    def build_state(
        self,
        profile: Dict[str, Any],
        resolved_events: List[Dict[str, Any]],
        recurring_streams: Dict[str, Any]
    ) -> UserFinancialState:
        user_id = str(profile.get("user_id", ""))
        home_currency = str(profile.get("home_currency", "USD"))
        curr_bal = float(profile.get("current_available_balance", 0.0))
        min_bal = float(profile.get("minimum_balance_to_keep", 0.0))

        protect = self._parse_pipe_list(profile.get("expense_categories_to_protect"))
        reduce_cats = self._parse_pipe_list(profile.get("expense_categories_user_is_willing_to_reduce"))
        stop_cats = self._parse_pipe_list(profile.get("expense_categories_user_is_willing_to_stop"))
        methods = self._parse_pipe_list(profile.get("payment_methods_user_will_consider"))

        max_inst = profile.get("max_installment_months")
        if pd.notna(max_inst) and str(max_inst).strip().lower() != "nan":
            max_inst_months = float(max_inst)
        else:
            max_inst_months = None

        return UserFinancialState(
            user_id=user_id,
            home_currency=home_currency,
            current_available_balance=curr_bal,
            minimum_balance_to_keep=min_bal,
            categories_to_protect=protect,
            categories_to_reduce=reduce_cats,
            categories_to_stop=stop_cats,
            payment_methods_to_consider=methods,
            max_installment_months=max_inst_months,
            resolved_events=resolved_events,
            recurring_streams=recurring_streams
        )
