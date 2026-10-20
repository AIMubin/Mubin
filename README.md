# Mubin — مُبين

Evidence-grounded infrastructure for Islamic knowledge, verification, and reasoning.

Mubin is a system composed of independently maturing knowledge and reasoning engines. System releases use semantic versioning; engine milestones use namespaced internal milestones.

## Current status

- **Mubin system:** `0.1.0-alpha` — foundation stage
- **Quran Engine:** `Q0.3` — engineering-qualified for pinned import/read-path scope; public content clearance not granted
- **Hadith Engine:** `H3.9.2` — qualification stage
- **Usul Engine:** `U0.1` — experimental, one-step simulator (not qualified)
- **Fiqh Engine:** `F0.0` — planned

`H3.9.2` is **not** the version of Mubin as a whole. It is the Hadith Engine's internal qualification milestone.

## Repository layout

```text
Mubin/
├── VERSION.yaml
├── core/
├── engines/
│   ├── quran/
│   ├── hadith/
│   ├── usul/
│   └── fiqh/
├── evaluation/
├── schemas/
└── docs/
```

## Core invariant

No derived claim should exist without a traceable path back to its evidence, method, and interpretive context.

## Review and qualification

Risk-proportionate gates: [engineering and source/action review](docs/RISK_BASED_ASSURANCE.md). Thematic human scholarly review does not block routine engineering; human editorial approval, frozen H3.9.2 qualification decisions and publication rights remain specific requirements where applicable. No system-version bump has been made.

## Sourced research and citation

Use established sources with mandatory attribution and exact provenance (work, edition, locator and hashes). [Source-use policy](docs/SOURCE_ATTRIBUTION_POLICY.md) permits bounded internal research without blanket scholarly gates; attribution does not grant redistribution rights or attest text authenticity.

## Development rule

Subsystem milestone numbers never imply Mubin system maturity. A system release is cut only from integrated, qualified capabilities across the required engines.

## Workstream progress (2026-10-20)

- Quran Q0.3 technical qualification has a [reproducible pinned-vault replay](engines/quran/Q0.3-ENGINEERING-EXIT.md); the local operator completed a 9/9 pinned source-and-linked-database replay and recorded [limited-scope engineering qualification](corpus/reviews/q03-engineering-qualification.json); public text and editorial review gates remain separate. The original tafsir and Quran bytes are preserved.
- Usul U0.1 has an [explicitly non-juristic one-step rule simulator](engines/usul/README.md) with negative tests. It is *not* a full rule formalization, qiyas or fatwa engine.
- Historical H3.9.2 frozen review requirements, rights restrictions and Mubin system version are unchanged.
