# Credit Policy — FAgentLLM Directive

## Purpose
This directive defines how the Credit Agent scores customer payment risk and
what collection actions are triggered at each risk tier.

## Credit Risk Score Formula
```
R = max(0, min(100, base_score - (w1 × f1) - (w2 × f2)))
```
Where:
- `base_score` = 100
- `f1` = payment_delay_avg (average days late on historical invoices)
- `f2` = total_outstanding / 1,000 (outstanding balance in thousands)
- `w1` = 2.0 (penalty per day of average delay)
- `w2` = 1.5 (penalty per $1,000 outstanding)

**Higher R = higher risk.**

## Risk Tiers
| Score | Risk Level | Recommended Action |
|---|---|---|
| < 40 | **High** | Formal notice; trigger cash position refresh |
| 40–69 | **Medium** | Payment reminder; monitor closely |
| ≥ 70 | **Low** | Standard monitoring |

## Collection Stage Escalation
| Stage | Trigger | Action |
|---|---|---|
| `reminder` | First overdue flag | Automated email reminder |
| `formal_notice` | 15+ days overdue or medium risk | Formal written notice |
| `escalate` | 30+ days overdue or high risk | Account management escalation |
| `legal_referral` | 60+ days overdue | Legal team referral |
| `monitor` | Risk improving | Watchlist only |

## Trigger Conditions
- Triggered automatically when Reconciliation Agent detects systematic anomalies
- Can be triggered manually via dashboard "Assess" button per customer
- High-risk outcome triggers a Cash Position Refresh to adjust AR forecasts

## Interpretation Note
The credit score reflects current payment behaviour. A score of 0 does not mean
the customer is fraudulent — it means they have significant outstanding debt or
very poor payment timing. Context matters.
