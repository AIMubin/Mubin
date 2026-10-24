"""Restricted internal-research adapters; not part of the public Quran reader."""

from .private_adapters import PrivateResearchAdapters, ResearchAdapterError

__all__ = ("PrivateResearchAdapters", "ResearchAdapterError")
