"""Feature library. Importing this module registers every feature group."""

from .base import assert_causal, build, group_names, register, registry  # noqa: F401
from . import (  # noqa: F401  (import side effect: registration)
    microstructure,
    price,
    regime,
    statistical,
    technical,
    volatility,
)
from .cross_sectional import build_panel_features  # noqa: F401
from .external import funding_features, macro_features  # noqa: F401
from .pipeline import FeatureMatrix, align_columns, build_features, build_panel  # noqa: F401
