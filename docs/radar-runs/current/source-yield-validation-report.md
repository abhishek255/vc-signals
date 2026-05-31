# Source Yield Validation

- Goal reached: yes
- Assign Owner rows: Voker
- Assign Owner bar preserved: yes
- Net-new credible Review-Worthy rows: 9 / 5

## Review-Worthy Rows

| Company | Domain | Action | Stage | Raised | Headcount | Source |
| --- | --- | --- | --- | --- | --- | --- |
| Goldbridge | goldbridgebanking.com | research deeper | PRE_SEED | 500000 | 5 | YC Directory |
| Simplex | simplex.sh | research deeper | PRE_SEED | 500000 | 5 | YC Directory |
| Miru | mirurobotics.com | research deeper | PRE_SEED | 500000 | 4 | YC Directory |
| Menza | menza.ai | research deeper | PRE_SEED | 500000 | 6 | YC Directory |
| jo | askjo.ai | research deeper | PRE_SEED | 500000 | 2 | YC Directory |
| Poka Labs | pokalabs.com | research deeper | PRE_SEED | 2500000 | 5 | YC Directory |
| Spur | spurtest.com | research deeper | SEED | 5000000 | 76 | YC Directory |
| Coval | coval.dev | research deeper | SEED | 3800000 | 20 | YC Directory |
| Ångström AI | angstrom-ai.com | research deeper | PRE_SEED | 500000 | 4 | YC Directory |

## Source Health

- last30days:devtools: error, fresh_items=0, duration_seconds=83.39
- last30days:cybersecurity: degraded, fresh_items=0, duration_seconds=102.38
- last30days:ai-infra: degraded, fresh_items=0, duration_seconds=86.65
- last30days:vertical-ai: error, fresh_items=0, duration_seconds=84.33
- last30days:data-infra: degraded, fresh_items=0, duration_seconds=81.65
- last30days:oss: degraded, fresh_items=0, duration_seconds=83.25
- github: complete, fresh_items=25, duration_seconds=19.76
- product_hunt: complete, fresh_items=10, duration_seconds=113.17
- yc_directory: complete, fresh_items=18, duration_seconds=6.47
- x_launches: complete, fresh_items=2, duration_seconds=355.72
- hn_launch_trial: complete, fresh_items=5, duration_seconds=0

## Caveats

- last30days sector queries were degraded or errored, mostly from Safari cookie permissions and timeouts.
- Product Hunt API worked, but several launch redirects still needed fallback domain resolution or stayed unresolved.
- X worked as a launch signal, but evidence was thin and still needs domain enrichment for some rows.
