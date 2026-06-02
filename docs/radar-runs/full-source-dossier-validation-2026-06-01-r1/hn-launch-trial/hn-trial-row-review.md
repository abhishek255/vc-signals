# HN Trial Row Review

Row-level review for the bounded HN launch lane. Weekly CLI enables it by default; use --no-hn-launch-trial to disable.

- Rows reviewed: 8
- Priority split: high_priority=4, normal_priority=4
- Completion split: completed_clean=5, completed_with_stage_failure=3
- Action split: Assign owner=1, Research deeper=7
- Attio skipped rows: 6
- Attio skip reasons: owner_actionable_evidence_incomplete=6
- Unsafe promotions: 0
- Project-only rows summarized: 14
- Product/context rows separated: 1

## Candidate Rows

### Voker

- Domain: voker.ai
- Priority: high_priority (accelerator_hint, official_domain_url, company_looking_domain, hn_engagement)
- Completion: completed_clean
- Stage failures: none
- Final action: Assign owner
- Evidence dimensions: customer, founder, stage
- Attio status: no_match
- Missing evidence: none
- Unsafe promotion: False
- HN source: https://news.ycombinator.com/item?id=48109962
- Official/company source: https://voker.ai
- Founder evidence: https://www.ycombinator.com/companies/voker
- Stage/funding evidence: https://www.ycombinator.com/companies/voker
- Commercial/customer evidence: https://voker.ai
- Attio status evidence: no_match via attio_read

### Runtime (YC P26)

- Domain: runtm.com
- Priority: high_priority (official_domain_url, company_looking_domain, hn_engagement)
- Completion: completed_with_stage_failure
- Stage failures: maturity_query_timeout
- Final action: Research deeper
- Evidence dimensions: customer
- Attio status: unknown
- Missing evidence: no founder/team evidence, no stage/funding evidence, Attio status unknown, maturity_query_timeout
- Unsafe promotion: False
- Attio skipped: owner-actionable evidence incomplete

### Hypercubic

- Domain: hypercubic.ai
- Priority: high_priority (official_domain_url, company_looking_domain, hn_engagement)
- Completion: completed_with_stage_failure
- Stage failures: maturity_query_timeout
- Final action: Research deeper
- Evidence dimensions: customer
- Attio status: unknown
- Missing evidence: no founder/team evidence, no stage/funding evidence, no commercial/funding evidence, Attio status unknown, maturity_query_timeout
- Unsafe promotion: False
- Attio skipped: owner-actionable evidence incomplete

### Noada

- Domain: noada.app
- Priority: normal_priority (official_domain_url, company_looking_domain)
- Completion: completed_clean
- Stage failures: none
- Final action: Research deeper
- Evidence dimensions: none
- Attio status: unknown
- Missing evidence: no founder/team evidence, no stage/funding evidence, no commercial/funding evidence, Attio status unknown, no customer/buyer pull evidence
- Unsafe promotion: False
- Attio skipped: owner-actionable evidence incomplete

### Datapoint AI

- Domain: trydatapoint.com
- Priority: normal_priority (official_domain_url, company_looking_domain)
- Completion: completed_clean
- Stage failures: none
- Final action: Research deeper
- Evidence dimensions: none
- Attio status: unknown
- Missing evidence: no founder/team evidence, no stage/funding evidence, no customer/buyer pull evidence, no commercial/funding evidence, Attio status unknown
- Unsafe promotion: False
- Attio skipped: owner-actionable evidence incomplete

### AI Doctor Notes

- Domain: aidoctornotes.app
- Priority: normal_priority (official_domain_url, company_looking_domain)
- Completion: completed_clean
- Stage failures: none
- Final action: Research deeper
- Evidence dimensions: none
- Attio status: unknown
- Missing evidence: no founder/team evidence, no stage/funding evidence, no commercial/funding evidence, Attio status unknown, no customer/buyer pull evidence
- Unsafe promotion: False
- Attio skipped: owner-actionable evidence incomplete

### Triyambakam Apex Corp

- Domain: triyambakam-apex-corp.hf.space
- Priority: normal_priority (official_domain_url, company_looking_domain)
- Completion: completed_clean
- Stage failures: none
- Final action: Research deeper
- Evidence dimensions: none
- Attio status: unknown
- Missing evidence: official_domain_identity_not_confirmed, no verified Attio-safe company identity, no founder/team evidence, no stage/funding evidence, no commercial/funding evidence, Attio status unknown, no customer/buyer pull evidence
- Unsafe promotion: False

### 3D-Agent

- Domain: 3d-agent.com
- Priority: high_priority (official_domain_url, company_looking_domain, hn_engagement)
- Completion: completed_with_stage_failure
- Stage failures: maturity_query_timeout
- Final action: Research deeper
- Evidence dimensions: none
- Attio status: unknown
- Missing evidence: no founder/team evidence, no stage/funding evidence, no commercial/funding evidence, Attio status unknown, no customer/buyer pull evidence, maturity_query_timeout
- Unsafe promotion: False
- Attio skipped: owner-actionable evidence incomplete
