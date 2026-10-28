# Mubin — مُبين

Evidence-grounded infrastructure for Islamic knowledge, verification, and reasoning.

Mubin is a system composed of independently maturing knowledge and reasoning engines. System releases use semantic versioning; engine milestones use namespaced internal milestones.

## Current status

- **Mubin system:** `0.1.0-alpha` — foundation stage
- **Quran Engine:** `Q0.3` — engineering-qualified for pinned import/read-path scope; public content clearance not granted
- **Tafsir Engine:** `T0.2.3` — source-grounded, unverified interpretation cues and unresolved relations; no verified exegetical opinions, editions or rights
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


## Public preview: ship the safe slice, not the research backlog

A **read-only Arabic-first metadata preview** now lives at [docs/index.html](docs/index.html) with [reproducible public JSON](docs/preview-data.json), [launch instructions](docs/PUBLIC_PREVIEW_LAUNCH.md) and an independent [cross-OS public-preview gate](.github/workflows/public-preview.yml). It displays only named sources, search counts, research-stage provenance, and explicit capability limitations. It does **not** contain original Quran/Tafsir/Hadith text, copyrighted editions or auto-generated juristic conclusions.

~~~bash
python -m release.public_preview --check
python -m unittest discover -s release/tests -v
python -m http.server 8765 --directory docs
~~~

The first two commands validate the public metadata artifact. The third serves it locally at http://localhost:8765/ for a browser smoke test. **Hosting is not implied by CI:** an authorized maintainer must enable GitHub Pages from the main branch /docs folder (or upload docs to another static host) and verify the live URL. No system-version bump is implied by this preview.

**Nonblocking release rule:** incomplete Hadith H3.9.2 human adjudications, wider al-Waraqat coverage, Stage09 P0 semantics and unfinished Fiqh features do NOT prevent publication of the carefully bounded, safe metadata preview. Protected text, authentic canonical Quran display and authoritative scholarship retain their own feature-specific publication gates.

## Stage09 research, separate from the preview

The [typed evidence proposal contract](engines/usul/typed_evidence_binding.py) and [runbook](engines/usul/pilots/STAGE09_TYPED_EVIDENCE_BINDING.md) connect an exact SHA-pinned Stage08 text occurrence to an existing P0 Source/Evidence record **as an unassessed byte-correspondence proposal**. They never promote P0 verification, invoke a rule, certify interpretation or produce a fatwa. This remains experimental and is not a blocker for the metadata preview.

## Development fast lanes

The [engineering throughput policy](docs/DEVELOPMENT_FAST_LANES.md) separates
synthetic/CI qualification, private source & rights gates, and scholarly
adjudication. Safe research-only code can proceed with automated
`UNASSESSED`/`UNVERIFIED` labels while protected text and normative
claims retain strict independent approval. Avoid rerunning frozen source
pilots or duplicating core inference engines for unrelated changes.

## Internal verified-source development

[Development-first verified-source admission](docs/INTERNAL_SOURCE_DEVELOPMENT_POLICY.md)
allows appropriately sourced and independently byte-pinned originals to
support **private** research and AI development under an evaluated legal
basis even when separate permission to **redistribute** an edition
publicly is still pending. The gate uses operator-maintained use records
and never grants scholarly attribution, public text rights, juristic
inference or fatwa status. Existing public release safeguards remain.
