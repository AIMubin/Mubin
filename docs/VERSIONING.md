# Versioning and Milestone Policy

Mubin distinguishes system releases from internal engine milestones.

## System releases

The system uses Semantic Versioning: `Mubin X.Y.Z[-prerelease]`. The current system version is `0.1.0-alpha`.

## Engine milestones

- `Qx.y[.z]` — Quran Engine
- `Hx.y[.z]` — Hadith Engine
- `Ux.y[.z]` — Usul Engine
- `Fx.y[.z]` — Fiqh Engine

These are internal maturity coordinates, not SemVer releases and not claims about whole-system maturity.

## Historical mapping

The implementation milestones that led through the mature Hadith workstream (notably the M2.x/M3.x sequence culminating in former `M3.9.2`) are henceforth interpreted in the Hadith namespace. For example, former `M3.9.2` is `H3.9.2`. Early project-wide foundation package numbers are historical package versions and are not retroactively treated as Hadith milestones. No implementation history is discarded; the operational milestone namespace is corrected.

## Release invariant

No engine milestone can, by itself, advance the Mubin system major version. System release gates must be defined at the integration level and may depend on multiple engines plus shared provenance, evaluation, and governance contracts.
