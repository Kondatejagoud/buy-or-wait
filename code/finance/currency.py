import pandas as pd
from typing import Dict, Tuple, List, Optional
from datetime import datetime

class CurrencyConverter:
    def __init__(self, rates_df: pd.DataFrame):
        self.rates_df = rates_df.copy()
        self.rates_df["rate_date"] = pd.to_datetime(self.rates_df["rate_date"])
        self._build_index()

    def _build_index(self):
        # Store rates as a map: date -> list of (from_curr, to_curr, rate)
        self.rates_by_date: Dict[pd.Timestamp, List[Tuple[str, str, float]]] = {}
        for _, row in self.rates_df.iterrows():
            d = row["rate_date"]
            if d not in self.rates_by_date:
                self.rates_by_date[d] = []
            self.rates_by_date[d].append((row["from_currency"], row["to_currency"], float(row["rate"])))

        self.sorted_dates = sorted(self.rates_by_date.keys())

    def get_rate(self, from_curr: str, to_curr: str, date_str: str) -> float:
        if from_curr == to_curr:
            return 1.0

        target_date = pd.to_datetime(date_str)
        # Find exact or most recent date <= target_date. If none <= target_date, pick earliest available.
        valid_dates = [d for d in self.sorted_dates if d <= target_date]
        if valid_dates:
            ref_date = max(valid_dates)
        else:
            ref_date = min(self.sorted_dates)

        # Build adjacency graph for ref_date
        edges: Dict[str, List[Tuple[str, float]]] = {}
        for fc, tc, r in self.rates_by_date[ref_date]:
            if fc not in edges:
                edges[fc] = []
            edges[fc].append((tc, r))

            if tc not in edges:
                edges[tc] = []
            if r > 0:
                edges[tc].append((fc, 1.0 / r))

        # BFS / shortest path to convert from_curr to to_curr
        visited = set()
        queue = [(from_curr, 1.0)]
        visited.add(from_curr)

        while queue:
            curr, mult = queue.pop(0)
            if curr == to_curr:
                return mult

            for nxt, r in edges.get(curr, []):
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append((nxt, mult * r))

        raise ValueError(f"No exchange rate path found from {from_curr} to {to_curr} on {date_str}")

    def convert(self, amount: float, from_curr: str, to_curr: str, date_str: str) -> float:
        if amount == 0 or from_curr == to_curr:
            return amount
        rate = self.get_rate(from_curr, to_curr, date_str)
        return amount * rate
