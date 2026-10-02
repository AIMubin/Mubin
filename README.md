# Mubin — مُبين

Evidence-grounded infrastructure for Islamic knowledge, verification, and reasoning.

Mubin is a system composed of independently maturing knowledge and reasoning engines. System releases use semantic versioning; engine milestones use namespaced internal milestones.

## Current status

- **Mubin system:** `0.1.0-alpha` — foundation stage
- **Quran Engine:** `Q0.0` — planned
- **Hadith Engine:** `H3.9.2` — qualification stage
- **Usul Engine:** `U0.0` — planned
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

## Development rule

Subsystem milestone numbers never imply Mubin system maturity. A system release is cut only from integrated, qualified capabilities across the required engines.
