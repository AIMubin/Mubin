# Mubin System Architecture

Mubin is organized as four domain engines over shared system infrastructure.

```text
                   Mubin System
                       │
      ┌────────────────┼────────────────┐
      │                │                │
   Quran            Hadith            Usul
  Engine             Engine           Engine
      │                │                │
      └────────────────┼────────────────┘
                       │
                    Fiqh Engine
                       │
              Applications / Research

Shared beneath all engines:
provenance · evidence · identity · reasoning · evaluation · governance
```

The Hadith Engine is currently the most mature component. Its maturity must not be projected onto the Quran, Usul, or Fiqh engines.
