# Buy or Wait? — AI Financial Decision Engine

An AI-assisted financial decision agent that evaluates a user's purchase or payment request against their complete financial position and produces a personalized, deterministically verified payment recommendation.

---

## Problem Overview

For every financial request, the system must evaluate whether the user can afford the expense and output a structured decision containing:

* **Amount Safe to Pay**: The maximum amount safe to pay today before optional spending changes.
* **Affordability Status**: `affordable_now`, `affordable_with_plan`, `affordable_later`, or `not_affordable`.
* **Recommended Payment Method**: `full_payment`, `partial_payment`, `installments`, `wait`, or `not_recommended`.
* **Payment Plan**: Chronological `<YYYY-MM-DD>:<amount>` entries joined by `|`, or `none`.
* **Earliest Date for Full Payment**: First conservative projected date for one safe full payment.
* **Spending Changes Needed**: Permitted `stop:<event_id>` or `reduce_to:<event_id>:<amount>` actions, or `none`.
* **Decision Explanation**: Grounded, concise explanation of the recommendation.

---

## Pipeline Architecture

```text
       Raw Dataset Files (dataset/)
                   │
                   ▼
             DataLoader
                   │
                   ▼
       Event & Evidence Resolver (Dated FX + Multimodal VLM Parser)
                   │
                   ▼
             Recurrence Engine (Pattern & Stream Detection)
                   │
                   ▼
        User Financial State Construction
                   │
                   ▼
      90-Day Cash-Flow Safety Simulator (Minimum Balance Bounding)
                   │
                   ▼
        Candidate Payment Plan Explorer
                   │
                   ▼
        Plan Ranker & Decision Engine
                   │
                   ▼
              output.csv
```

---

## Data Sources

The decision engine reconciles financial context from eight structured data sources in `dataset/`:

* `requests.csv`: Evaluation purchase requests requiring predictions.
* `financial_profiles.csv`: Available starting balance, minimum balance to keep, categories to protect/reduce/stop, and payment preferences.
* `financial_events.csv`: Historical, pending, scheduled, and settled cashflow transactions.
* `exchange_rates.csv`: Fixed, dated exchange rates for multi-currency conversion.
* `request_payment_options.csv`: Provider-offered installment and payment schedules.
* `messages.csv`: Contextual user and bank communications (cancellations, settlements, employer payroll updates).
* `images.csv`: Metadata mapping event IDs to receipt, bill, or statement image files.
* `media/images/`: Image files processed by the evidence parser for extracting missing amounts or dates.

---

## Safety Model & Constraints

The system evaluates `amount_safe_to_pay` against a strict **90-day cash-flow safety model**. A candidate payment amount or schedule is considered safe if and only if the user's projected daily balance **never falls below `minimum_balance_to_keep`** throughout the entire 90-day forecast horizon.

---

## Engine Architecture & AI Usage

* **Deterministic Core Engine**: All cashflow simulations, recurring stream projections, headroom calculations, candidate plan ranking, and safety bounds are computed locally by deterministic algorithms in Python to ensure 100% reproducibility and fast, offline execution.
* **Evidence Parser**: Structured evidence parsing extracts missing transaction amounts and settlement statuses from dataset evidence files without requiring external third-party AI API keys or network requests.
* **API Cost & Token Usage**: 0 API calls, 0 tokens consumed, $0.00 execution cost.

---

## Recurrence & Pattern Handling

The engine detects recurring income and expense streams using historical frequency analysis and pattern clustering:

* **Frequency Classification**: Historical intervals are analyzed to classify streams into `weekly`, `biweekly`, or `monthly` patterns.
* **Amount Projection**: For contractual/fixed categories (rent, insurance, debt payments, subscriptions), stream amounts maintain contractual values. For variable/discretionary categories (`groceries`, `dining`, `transport`, `shopping`, `entertainment`), future stream amounts are projected using historical averages derived from prior observed occurrences.
* **Interval Handling**: Non-standard recurrence intervals (e.g. 10-day recurring streams) are preserved cleanly to prevent misclassification.
* **Data-Driven Execution**: The recurrence detection pipeline is 100% data-driven and contains zero user-specific or request-specific hardcoded values.

---

## Output Schema Format

The submission produces `output.csv` with exactly 250 prediction rows and 8 required columns:

| Column | Description | Format / Allowed Values |
|---|---|---|
| `request_id` | Unique request identifier | Text |
| `amount_safe_to_pay` | Safe amount on `request_date` | Float (`0 <= amount <= requested_amount`) |
| `affordability_status` | Affordability decision | `affordable_now` \| `affordable_with_plan` \| `affordable_later` \| `not_affordable` |
| `recommended_payment_method` | Payment recommendation | `full_payment` \| `partial_payment` \| `installments` \| `wait` \| `not_recommended` |
| `payment_plan` | Payment schedule | `YYYY-MM-DD:amount|...` or `none` |
| `earliest_date_for_full_payment` | Earliest safe full payment date | `YYYY-MM-DD` or empty |
| `spending_changes_needed` | Flexible spending adjustments | `stop:<event_id>` \| `reduce_to:<event_id>:<amt>` or `none` |
| `decision_explanation` | Concise decision rationale | Grounded text summary |

---

## Setup & Running the Solution

### Requirements
* Python 3.8+
* Dependencies listed in `requirements.txt`:
  ```bash
  pip install -r requirements.txt
  ```

### Running the Solver
To run the solver over `dataset/requests.csv` and generate `output.csv`, execute either command from the root directory:

```bash
python run.py
```
or
```bash
python code/main.py
```

### Running Benchmark Evaluation
To run the benchmark evaluation against `dataset/sample_requests.csv`:

```bash
python code/evaluation/evaluate.py
```

---

## Final Verified Benchmark Results

Evaluation against `dataset/sample_requests.csv` (25 sample cases):

| Evaluation Metric | Verified Accuracy | Match Count |
|---|:---:|:---:|
| **Affordability Status Accuracy** | **80.0%** | 20 / 25 |
| **Recommended Payment Method Accuracy** | **88.0%** | 22 / 25 |
| **Payment Plan Accuracy** | **76.0%** | 19 / 25 |
| **Earliest Date for Full Payment Accuracy** | **72.0%** | 18 / 25 |
| **Spending Changes Needed Accuracy** | **88.0%** | 22 / 25 |
| **Safe Amount Accuracy** | **16.0%** | 4 / 25 |

---

## Known Limitations

* **Safe Amount Sensitivity**: Exact penny accuracy for `amount_safe_to_pay` is lower (16.0%) than decision-level metrics (80–88%). Safe amount calculations are highly sensitive to subtle variance in historical variable-amount recurring expenses.
* **Recurrence Interval Edge Cases**: Recurring expense estimation involves edge cases around variable amounts and non-standard recurrence intervals. For instance, streams with 10-day intervals require careful frequency handling to avoid falling back into standard monthly defaults.
* **Pre-Income Window Boundary**: The boundary treatment for an income event landing exactly on a forecast boundary is an interpretive modeling decision. Our implementation treats the next confirmed income date as an exclusive upper boundary for pre-income debit aggregation (`request_date <= event_date < next_income_date`).
* **Authoritative 90-Day Horizon**: The 90-day cashflow safety simulation remains authoritative for safety verification, ensuring minimum balance constraints are never breached across the entire forecast window.
