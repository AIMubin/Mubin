"""Q0.1 byte-exact local Quran snapshot lookup, not source certification."""
from .engine import QuranIndex, SnapshotError, load_snapshot, assess_snapshot, verse_counts
__all__=['QuranIndex','SnapshotError','load_snapshot','assess_snapshot','verse_counts']
