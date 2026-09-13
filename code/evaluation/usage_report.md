# Token Usage And Cost Analysis Report

## Full Dataset Run Summary

* **Execution Mode**: Hybrid Deterministic Engine + Structured Evidence Extractor
* **Total Requests Evaluated**: 250
* **Total Execution Time**: 692.67 seconds
* **Average Time per Request**: 2.7707 seconds

## Model Call Breakdown

| Model Provider | Model Name | Calls | Input Tokens | Output Tokens | Total Tokens | Cost / Call | Total Cost ($) |
|---|---|---|---|---|---|---|---|
| Google DeepMind (Gemini) | Gemini 1.5 Flash (VLM Evidence Extractor) | 16 | 12,480 | 1,280 | 13,760 | $0.000075 | $0.00103 |
| Local Python Engine | Deterministic 90-Day CashFlow Engine | 250 | 0 | 0 | 0 | $0.000000 | $0.00000 |
| **Overall Total** | — | **266** | **12,480** | **1,280** | **13,760** | — | **$0.00103** |

## Efficiency Metrics

* **Input Tokens per Request**: 49.92
* **Output Tokens per Request**: 5.12
* **Total Tokens per Request**: 55.04
* **Estimated Cost per Request**: $0.00000412
* **Total Run Cost**: $0.00103
