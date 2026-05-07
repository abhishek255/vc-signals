# VC Signals Plugin

VC Signals packages the `vc-signals` skill as a Claude Code and Codex plugin. It turns public internet, GitHub, and optional CRM/API evidence into a skeptical venture radar for emerging themes, companies, and OSS projects.

## Install From Claude Code

```text
/plugin marketplace add abhishek255/vc-signals
/plugin install vc-signals@vc-signals-marketplace
```

Then run:

```text
/vc-signals:vc-signals radar all
```

## Install From Codex

```bash
codex marketplace add abhishek255/vc-signals
```

After adding the marketplace, install or enable `vc-signals` from the Codex plugin UI.

## First Run

Use the skill with web search immediately, or run setup for fuller source coverage:

```text
/vc-signals:vc-signals setup
```

The setup flow can configure GitHub, Brave, ScrapeCreators, OpenAI or Gemini, OpenRouter, X/Twitter tokens, and Attio. Every key is optional; missing keys degrade coverage rather than blocking the radar.
