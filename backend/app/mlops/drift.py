"""Data drift detection via PSI (Population Stability Index).

PSI is a standard, widely-used statistic (originating in credit-risk model
monitoring, now common MLOps practice generally) for comparing two
distributions of the same variable. Its conventional published thresholds -
not values invented for this project - are:

    PSI < 0.10              -> no significant distribution change
    0.10 <= PSI < 0.25      -> moderate change, worth investigating
    PSI >= 0.25             -> significant change, action recommended

This module maps those to "stable" / "warning" / "drift" respectively (see
Settings.drift_psi_warning_threshold / drift_psi_severe_threshold - the
defaults are exactly the conventional values above, expressed as
configuration rather than hardcoded so a deployment can tune sensitivity).

PSI formula, for a set of bins with baseline proportion b_i and current
proportion c_i in each bin:

    PSI = sum_i (c_i - b_i) * ln(c_i / b_i)

Numeric features are binned by the *baseline's* quantiles (10 bins,
deduplicated - fewer if the baseline doesn't have enough distinct values to
support that many); the outermost bin edges are -inf/+inf so a current
value outside the baseline's observed range still lands in a bin rather
than being dropped. Categorical features use the union of both sides'
actual categories as "bins" directly - no artificial binning needed, and an
unseen category naturally gets a baseline proportion of ~0 (smoothed by
EPSILON below, otherwise PSI would divide by zero).

A baseline column with only one distinct value can't be quantile-binned at
all (every quantile collapses to the same edge) - PSI is undefined for a
single-point distribution, so that case is handled separately: statistic is
the fraction of *current* values that differ from the constant baseline
value, using the same threshold numbers (documented as a deliberate
simplification, not a claim that this fraction is statistically
comparable to PSI - see `compute_numeric_feature_drift`).
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.config import Settings

EPSILON = 1e-4
NUMERIC_BINS = 10


@dataclass
class FeatureDriftResult:
    feature: str
    feature_type: str  # "numeric" | "categorical"
    method: str  # "psi" | "constant_value_deviation" | "insufficient_data"
    statistic: float | None
    status: str  # "stable" | "warning" | "drift" | "unknown"
    baseline_summary: dict
    current_summary: dict
    explanation: str


@dataclass
class DriftResult:
    overall_status: str
    total_features_checked: int
    drifted_feature_count: int
    warning_feature_count: int
    features: list[FeatureDriftResult]


def _missing_rate(series: pd.Series) -> float:
    return round(float(series.isna().mean()), 4) if len(series) else 0.0


def _classify(statistic: float, warning: float, severe: float) -> str:
    if statistic >= severe:
        return "drift"
    if statistic >= warning:
        return "warning"
    return "stable"


def _psi(baseline_props: np.ndarray, current_props: np.ndarray) -> float:
    baseline = np.clip(baseline_props, EPSILON, None)
    current = np.clip(current_props, EPSILON, None)
    return float(np.sum((current - baseline) * np.log(current / baseline)))


def compute_numeric_feature_drift(
    name: str, baseline: pd.Series, current: pd.Series, settings: Settings, bins: int = NUMERIC_BINS
) -> FeatureDriftResult:
    baseline_missing = _missing_rate(baseline)
    current_missing = _missing_rate(current)
    baseline_clean = pd.to_numeric(baseline, errors="coerce").dropna()
    current_clean = pd.to_numeric(current, errors="coerce").dropna()

    baseline_summary = {
        "count": int(len(baseline_clean)),
        "missing_rate": baseline_missing,
        "mean": round(float(baseline_clean.mean()), 4) if len(baseline_clean) else None,
        "std": round(float(baseline_clean.std()), 4) if len(baseline_clean) > 1 else 0.0,
        "min": round(float(baseline_clean.min()), 4) if len(baseline_clean) else None,
        "max": round(float(baseline_clean.max()), 4) if len(baseline_clean) else None,
    }
    current_summary = {
        "count": int(len(current_clean)),
        "missing_rate": current_missing,
        "mean": round(float(current_clean.mean()), 4) if len(current_clean) else None,
        "std": round(float(current_clean.std()), 4) if len(current_clean) > 1 else 0.0,
        "min": round(float(current_clean.min()), 4) if len(current_clean) else None,
        "max": round(float(current_clean.max()), 4) if len(current_clean) else None,
    }

    if len(baseline_clean) == 0:
        return FeatureDriftResult(
            name, "numeric", "insufficient_data", None, "unknown",
            baseline_summary, current_summary,
            "No non-missing baseline values were available to compare against.",
        )

    if baseline_clean.nunique() <= 1:
        constant_value = float(baseline_clean.iloc[0])
        differing_fraction = (
            float((current_clean != constant_value).mean()) if len(current_clean) else 0.0
        )
        status = _classify(
            differing_fraction, settings.drift_psi_warning_threshold,
            settings.drift_psi_severe_threshold,
        )
        return FeatureDriftResult(
            name, "numeric", "constant_value_deviation", round(differing_fraction, 4), status,
            baseline_summary, current_summary,
            f"Baseline is constant ({constant_value}) - PSI/binning isn't defined for a "
            f"single-value distribution, so this reports the fraction of new values that "
            f"differ from it instead, judged against the same thresholds as PSI.",
        )

    quantiles = np.linspace(0, 1, bins + 1)
    edges = np.unique(np.quantile(baseline_clean, quantiles))
    edges[0], edges[-1] = -np.inf, np.inf
    if len(edges) < 3:
        edges = np.array([-np.inf, float(baseline_clean.median()), np.inf])

    baseline_bins = np.digitize(baseline_clean, edges[1:-1], right=True)
    baseline_counts = np.bincount(baseline_bins, minlength=len(edges) - 1)
    baseline_props = baseline_counts / len(baseline_clean)

    if len(current_clean) == 0:
        current_props = np.zeros_like(baseline_props)
    else:
        current_bins = np.digitize(current_clean, edges[1:-1], right=True)
        current_counts = np.bincount(current_bins, minlength=len(edges) - 1)
        current_props = current_counts / len(current_clean)

    psi = _psi(baseline_props, current_props)
    status = _classify(
        psi, settings.drift_psi_warning_threshold, settings.drift_psi_severe_threshold
    )
    return FeatureDriftResult(
        name, "numeric", "psi", round(psi, 4), status, baseline_summary, current_summary,
        f"PSI={round(psi, 4)} across {len(edges) - 1} baseline-quantile bins "
        f"(warning >= {settings.drift_psi_warning_threshold}, "
        f"drift >= {settings.drift_psi_severe_threshold}).",
    )


def compute_categorical_feature_drift(
    name: str, baseline: pd.Series, current: pd.Series, settings: Settings
) -> FeatureDriftResult:
    baseline_missing = _missing_rate(baseline)
    current_missing = _missing_rate(current)
    baseline_clean = baseline.dropna().astype(str)
    current_clean = current.dropna().astype(str)

    baseline_freq = baseline_clean.value_counts(normalize=True)
    baseline_summary = {
        "count": int(len(baseline_clean)),
        "missing_rate": baseline_missing,
        "distinct_categories": int(baseline_clean.nunique()),
        "top_categories": baseline_freq.head(5).round(4).to_dict(),
    }
    current_freq = (
        current_clean.value_counts(normalize=True) if len(current_clean) else pd.Series(dtype=float)
    )
    unseen_categories = sorted(set(current_clean.unique()) - set(baseline_clean.unique()))
    current_summary = {
        "count": int(len(current_clean)),
        "missing_rate": current_missing,
        "distinct_categories": int(current_clean.nunique()),
        "top_categories": current_freq.head(5).round(4).to_dict(),
        "unseen_categories": unseen_categories[:10],
    }

    if len(baseline_clean) == 0:
        return FeatureDriftResult(
            name, "categorical", "insufficient_data", None, "unknown",
            baseline_summary, current_summary,
            "No non-missing baseline values were available to compare against.",
        )

    # Union of every category either side has ever seen - an unseen category
    # naturally gets a ~0 baseline proportion (smoothed by EPSILON in _psi,
    # otherwise it would divide by zero) rather than being dropped.
    all_categories = sorted(set(baseline_clean.unique()) | set(current_clean.unique()))
    baseline_props = baseline_freq.reindex(all_categories, fill_value=0.0).to_numpy()
    current_props = current_freq.reindex(all_categories, fill_value=0.0).to_numpy()

    psi = _psi(baseline_props, current_props)
    status = _classify(
        psi, settings.drift_psi_warning_threshold, settings.drift_psi_severe_threshold
    )
    return FeatureDriftResult(
        name, "categorical", "psi", round(psi, 4), status, baseline_summary, current_summary,
        f"PSI={round(psi, 4)} across {len(all_categories)} categories seen in either dataset "
        f"(warning >= {settings.drift_psi_warning_threshold}, "
        f"drift >= {settings.drift_psi_severe_threshold}).",
    )


def compute_drift(
    baseline_df: pd.DataFrame,
    current_df: pd.DataFrame,
    feature_columns: list[str],
    column_types: dict[str, str],
    settings: Settings,
) -> DriftResult:
    """`column_types` maps feature name -> "numeric" | "categorical" (the
    caller already knows this from DatasetColumn.detected_type - drift.py
    itself never re-infers types, keeping the two responsibilities apart)."""
    features: list[FeatureDriftResult] = []
    for name in feature_columns:
        baseline_series = (
            baseline_df[name] if name in baseline_df.columns else pd.Series(dtype=object)
        )
        current_series = (
            current_df[name] if name in current_df.columns else pd.Series(dtype=object)
        )
        if column_types.get(name) == "numeric":
            result = compute_numeric_feature_drift(name, baseline_series, current_series, settings)
        else:
            result = compute_categorical_feature_drift(
                name, baseline_series, current_series, settings
            )
        features.append(result)

    drifted = sum(1 for f in features if f.status == "drift")
    warning = sum(1 for f in features if f.status == "warning")
    overall = "drift" if drifted > 0 else "warning" if warning > 0 else "stable"

    return DriftResult(
        overall_status=overall,
        total_features_checked=len(features),
        drifted_feature_count=drifted,
        warning_feature_count=warning,
        features=features,
    )
