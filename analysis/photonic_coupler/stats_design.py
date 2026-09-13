"""Experiment sizing. The experimental unit is a *device*, not a wafer.

A grating coupler is measured per device, and a single MPW die holds
hundreds of copies. Wafer-level binomials are the wrong unit. Below are
the textbook formulae (Fleiss / Chow for two proportions; standard two-sample t).
"""

from __future__ import annotations

import math

from scipy.stats import beta, norm


def two_proportion_n(
    p1: float,
    p2: float,
    alpha: float = 0.05,
    power: float = 0.80,
    two_sided: bool = True,
) -> int:
    """Sample size per arm, two independent binomials, unpooled."""
    if not (0 < p1 < 1 and 0 < p2 < 1):
        raise ValueError("p1, p2 must be in (0,1)")
    z_a = norm.ppf(1.0 - alpha / (2.0 if two_sided else 1.0))
    z_b = norm.ppf(power)
    q1, q2 = 1.0 - p1, 1.0 - p2
    num = (z_a + z_b) ** 2 * (p1 * q1 + p2 * q2)
    den = (p1 - p2) ** 2
    return int(math.ceil(num / den))


def two_sample_t_n(
    delta: float,
    sigma: float,
    alpha: float = 0.05,
    power: float = 0.80,
    two_sided: bool = True,
) -> int:
    """Per-arm n for a two-sample t-test, equal variance, large-sample z."""
    z_a = norm.ppf(1.0 - alpha / (2.0 if two_sided else 1.0))
    z_b = norm.ppf(power)
    n = 2.0 * ((z_a + z_b) * sigma / delta) ** 2
    return int(math.ceil(n))


def paired_t_n(
    delta: float,
    sigma_diff: float,
    alpha: float = 0.05,
    power: float = 0.80,
) -> int:
    """Paired (same-die baseline vs candidate) sample size."""
    z_a = norm.ppf(1.0 - alpha / 2.0)
    z_b = norm.ppf(power)
    n = ((z_a + z_b) * sigma_diff / delta) ** 2
    return int(math.ceil(n))


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact binomial CI for a yield k/n."""
    if k == 0:
        lo = 0.0
    else:
        lo = float(beta.ppf(alpha / 2.0, k, n - k + 1))
    if k == n:
        hi = 1.0
    else:
        hi = float(beta.ppf(1.0 - alpha / 2.0, k + 1, n - k))
    return lo, hi
