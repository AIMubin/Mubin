"""S0.1 bibliographic-only provider catalog; not an edition authority."""
from .shamela import validate_shamela_catalog, assess_shamela_catalog

__all__ = ["validate_shamela_catalog", "assess_shamela_catalog"]
