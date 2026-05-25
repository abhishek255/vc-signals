# VC Signals Sourcing-Yield Sprint

Date: 2026-05-25

## Verdict

The highest-leverage low-risk source-yield improvement was the structured GitHub momentum lane. It improved top-of-funnel memory and produced credible OSS Watch rows, but it did not create net-new Assign Owner rows or enough company-ready Research Deeper rows by itself.

This sprint therefore proves the current limitation is not the owner gate. The limiting factor is source/enrichment quality: GitHub finds projects with momentum, while the current web/provider path is still weak at turning those projects into source-backed company, founder, stage, and customer evidence.

Safety held:

- Voker remains the only Assign Owner.
- Unsafe promotions remain 0.
- Attio remained read-only.
- Arize and other mature/context rows stayed out of owner flow.
- GitHub/package-momentum rows stayed incomplete until company-formation evidence appears.

## Baseline Reconfirmed

Baseline artifact:

- `docs/radar-runs/current-product-completion-sprint-2026-05-24/README.md`

Baseline final ledger action report and partner packet:

- `docs/radar-runs/current-product-completion-sprint-2026-05-24/final-ledger-action-report/ledger-action-report.json`
- `docs/radar-runs/current-product-completion-sprint-2026-05-24/final-partner-packet/partner-decision-packet.json`

Baseline state:

- Owner follow-up: 1, Voker.
- Continue Research: 3, Hypercubic, Runtime, Zencoder.
- Unsafe promotions: 0.
- Product-completion conclusion: workflow is trustworthy as weekly memory/routing/partner packet, but source-yield constrained.

## Loop 1: Weekly With GitHub Momentum

Command shape:

- Weekly run with existing trust gates unchanged.
- `--github-limit 15`
- Normal bounded web discovery still enabled.

Artifacts:

- `docs/radar-runs/current-sourcing-yield-sprint-2026-05-25/loop-1-github-momentum/`
- `docs/radar-runs/current-sourcing-yield-sprint-2026-05-25/loop-1-ledger-action-report/`
- `docs/radar-runs/current-sourcing-yield-sprint-2026-05-25/loop-1-partner-packet/`

Measured yield:

- Controlled web discovery saw 57 provider items, accepted 3, rejected 37.
- Web accepted Entro Security, LangChain, and Temporal-related Durable Execution Solutions.
- LangChain was flagged too late/category anchor.
- GitHub completed in 12.42 seconds with 15 fresh items and 8 GitHub evidence rows.
- Weekly output had 1 Assign Owner, 9 Research Deeper rows, and 8 OSS Project Watch rows.
- Voker remained Assign Owner with no missing evidence.
- OSS rows stayed owner-incomplete with `OSS/project-only row`.

Useful rows surfaced:

- Entro Security: Research Deeper, but missing founder/team, stage/funding, and customer/buyer pull evidence.
- redwoodjs/agent-ci: OSS/company-formation watch, `agent-ci.dev`, missing company-owner evidence.
- affaan-m/agentshield: OSS Watch, agent security scanner, missing verified company identity.
- kuberik/kuberik: OSS/company-formation watch, `kuberik.com`, missing company-owner evidence.

## Code Change

One narrow identity fix was made in `signal_ledger.py`:

- GitHub verification rows that retain `candidate_key` as `owner/repo` now merge into `project:github.com/owner/repo`.
- This prevents duplicate `entity:name` product/context rows from appearing beside the real GitHub project row.
- It does not alter ranking thresholds, Assign Owner gates, Attio behavior, HN behavior, or owner-readiness logic.

Test added:

- `test_github_candidate_key_merges_with_project_row`

Targeted verification:

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest .claude/skills/vc-signals/tests/test_signal_ledger.py -q`
- Result: 17 passed, 1 warning.

## Loop 2: GitHub-Only Structured Source

Command shape:

- Weekly run with web-discovery query budget set to zero.
- `--github-limit 30`
- Trust gates unchanged.

Artifacts:

- `docs/radar-runs/current-sourcing-yield-sprint-2026-05-25/loop-2-github-only/`
- `docs/radar-runs/current-sourcing-yield-sprint-2026-05-25/final-ledger-action-report/`
- `docs/radar-runs/current-sourcing-yield-sprint-2026-05-25/final-partner-packet/`

Measured yield:

- GitHub completed in 23.28 seconds.
- GitHub reported 30 fresh items and 18 evidence rows.
- Seed diagnostics: 18 signals, 18 candidate-eligible signals, 18 candidates, all from OSS.
- Owner readiness: 0 eligible, 18 skipped as project-only.
- Weekly output had 1 Assign Owner, 10 Research Deeper rows, and 10 OSS Project Watch rows.

Representative structured-source rows:

- redwoodjs/agent-ci: local GitHub Actions for agents, `agent-ci.dev`.
- affaan-m/agentshield: AI agent security scanner.
- boostsecurityio/smokedmeat: CI/CD red-team framework.
- kuberik/kuberik: Kubernetes-native continuous delivery, `kuberik.com`.
- peakoss/anti-slop: GitHub Action for low-quality AI PRs.

Noise/limitation observed:

- GitHub momentum also returned learning/template/utility/action repositories, including Rankistan, Epic freebies automation, copier templates, and GitHub Action helpers.
- These are useful for market memory and package/project watching, but are not enough for owner routing without company identity, founder/team, stage/funding, and customer/commercial proof.

## Final Ledger And Packet

Final ledger summary:

- Entities: 64.
- Sightings: 340.
- Current Assign Owner: 1.
- Current routes: Assign Owner 1, Category Context 6, OSS Watch 19, Research Deeper 38.
- Current actions: Assign owner 1, Monitor only 6, Research deeper 57.
- Unsafe promotions: 0.

Final partner packet:

- Owner follow-up: 1, Voker.
- Continue Research: 2, Hypercubic and Runtime.
- Category/project/context: 24, including GitHub OSS watch rows and mature/context rows.
- Stale/skipped: 35.
- Unsafe promotions: 0.

Final interpretation:

- The sprint did not produce new owner-ready companies.
- It did produce a better structured watch surface for OSS/package-like momentum.
- The next yield improvement should add a company-formation source adjacent to GitHub momentum, preferably Product Hunt launches or package-registry publisher/homepage momentum, rather than another broad web search.

## Recommendation

Keep GitHub momentum enabled for weekly memory, but treat it as an OSS Watch and company-formation trigger lane.

For the next sprint, add one structured company-formation adapter:

- Preferred: Product Hunt launches with official domain, maker/company identity, and launch timing.
- Second choice: package-registry momentum with homepage/domain extraction and maintainer organization identity.
- Avoid broad web expansion until a second provider can prove better company/founder/stage evidence yield than the current path.
