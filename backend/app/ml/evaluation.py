"""Shared evaluation helpers: seed resolution and metric formatting."""

from app.config import Settings


def resolve_seed(requested: int | None, settings: Settings) -> int:
    """A caller-supplied seed always wins; otherwise the app-wide default -
    either way, the seed actually used is returned so it can be recorded in
    the run's configuration (reproducibility requires knowing which seed was
    used, not just that *some* seed was)."""
    return requested if requested is not None else settings.ml_default_random_seed


def round_metrics(metrics: dict[str, float], ndigits: int = 4) -> dict[str, float]:
    return {k: round(float(v), ndigits) for k, v in metrics.items()}
