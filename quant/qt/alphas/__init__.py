"""Alpha library. Importing this module registers every alpha."""

from .base import Alpha, by_family, compute_all, describe, register_alpha, registry  # noqa: F401
from . import library  # noqa: F401  (import side effect: registration)
from .ensemble import (  # noqa: F401
    EnsembleSpec,
    alpha_report,
    combine,
    information_coefficient,
    orthogonalise,
    signal_returns,
)
