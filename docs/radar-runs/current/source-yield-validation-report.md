# Source Yield Validation

- Goal reached: yes
- Assign Owner rows: Voker
- Assign Owner bar preserved: yes
- Net-new credible Review-Worthy rows: 16 / 5

## Review-Worthy Rows

| Company | Domain | Action | Stage | Raised | Headcount | Source |
| --- | --- | --- | --- | --- | --- | --- |
| Superunit | superunit.com | research deeper | PRE_SEED | 500000 | 2 | YC Directory |
| Goldbridge | goldbridgebanking.com | research deeper | PRE_SEED | 500000 | 5 | YC Directory |
| Simplex | simplex.sh | research deeper | PRE_SEED | 500000 | 5 | YC Directory |
| Miru | mirurobotics.com | research deeper | PRE_SEED | 500000 | 4 | YC Directory |
| Apten | apten.ai | research deeper | PRE_SEED | 500000 | 4 | YC Directory |
| Doublezero | doublezero.tech | research deeper | PRE_SEED | 500000 | 1 | YC Directory |
| Menza | menza.ai | research deeper | PRE_SEED | 500000 | 6 | YC Directory |
| jo | askjo.ai | research deeper | PRE_SEED | 500000 | 2 | YC Directory |
| Poka Labs | pokalabs.com | research deeper | PRE_SEED | 2500000 | 5 | YC Directory |
| Spur | spurtest.com | research deeper | SEED | 5000000 | 76 | YC Directory |
| Coval | coval.dev | research deeper | SEED | 3800000 | 20 | YC Directory |
| Ångström AI | angstrom-ai.com | research deeper | PRE_SEED | 500000 | 4 | YC Directory |
| Ultra | ultra.tech | research deeper | SEED | 4250000 | 20 | YC Directory |
| Roger | hireroger.com | research deeper | PRE_SEED | 500000 | 19 | YC Directory |
| Undermind | undermind.ai | research deeper | PRE_SEED | 500000 | 4 | YC Directory |
| Evolvere BioSciences | evolverebiosciences.com | research deeper | PRE_SEED | 500000 | 6 | YC Directory |

## Source Diversity

- Non-YC review-worthy rows: 1
- Review-worthy lanes: hn, yc_directory
- product_hunt: launches=20, resolved_domains=5, unresolved_domains=15
- x: launches=4, resolved_domains=1, unresolved_domains=3

## Source Health

- last30days:devtools: complete, fresh_items=0, duration_seconds=34.27
- last30days:cybersecurity: complete, fresh_items=1, duration_seconds=35.75
- last30days:ai-infra: degraded, fresh_items=0, duration_seconds=73.55
- last30days:vertical-ai: degraded, fresh_items=0, duration_seconds=88.27
- last30days:data-infra: degraded, fresh_items=0, duration_seconds=76.0
- last30days:oss: degraded, fresh_items=0, duration_seconds=76.46
- github: complete, fresh_items=25, duration_seconds=19.46
- product_hunt: complete, fresh_items=20, duration_seconds=183.33
- yc_directory: complete, fresh_items=23, duration_seconds=9.48
- x_launches: complete, fresh_items=4, duration_seconds=404.4
- hn_launch_trial: complete, fresh_items=5, duration_seconds=0

## Caveats

- last30days sector queries were degraded or errored, mostly from Safari cookie permissions and timeouts.
- Product Hunt API worked, but several launch redirects still needed fallback domain resolution or stayed unresolved.
- X worked as a launch signal, but evidence was thin and still needs domain enrichment for some rows.
