from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Ticket:
    service: str
    opened_at: pd.Timestamp
    closed_at: pd.Timestamp
    severity: str


def _quarter_start(ts: pd.Timestamp) -> pd.Timestamp:
    return ts.to_period("Q").to_timestamp(how="start")


def _clamp(x: float, lo: float, hi: float) -> float:
    return float(min(max(x, lo), hi))


def _weekly_seasonality(day: pd.Timestamp) -> float:
    # Mild weekday effect: slightly higher mid-week.
    dow = int(day.dayofweek)  # 0=Mon
    weights = [1.05, 1.10, 1.12, 1.08, 1.00, 0.85, 0.80]
    return float(weights[dow])


def _payments_rate(day: pd.Timestamp) -> float:
    # Force a three-quarter crisis arc: 2024-Q1 -> 2024-Q2 -> 2024-Q3
    q = _quarter_start(day)
    if q == pd.Timestamp("2024-01-01"):
        # Low volume, flat: should sit in Q3
        base = 0.15
        slope = 0.0
    elif q == pd.Timestamp("2024-04-01"):
        # Still low-ish volume, but clear ramp: should move to Q2
        base = 0.20
        slope = 3.0
    elif q == pd.Timestamp("2024-07-01"):
        # High volume + strong ramp: should move to Q1
        base = 4.0
        slope = 28.0
    else:
        # otherwise modest baseline with small drift
        base = 0.55
        slope = 0.15

    next_q = q + pd.offsets.QuarterBegin(1)  # type: ignore[arg-type]
    days_in_q = int((next_q - q).days)
    t = (day - q).days / max(days_in_q, 1)
    return _clamp(base + slope * t, 0.01, 60.0)


def _fraud_rate(day: pd.Timestamp) -> float:
    # Low volume but strong, steady growth across the full range.
    start = pd.Timestamp("2023-01-01")
    end = pd.Timestamp("2026-01-01")
    t = (day - start).days / max((end - start).days, 1)
    return _clamp(0.15 + 1.10 * t, 0.05, 2.0)


def _default_rate(day: pd.Timestamp, base: float, annual_drift: float = 0.0) -> float:
    start = pd.Timestamp("2023-01-01")
    years = (day - start).days / 365.25
    return _clamp(base * (1.0 + annual_drift * years), 0.02, 50.0)


def _severity_weights(service: str, opened_at: pd.Timestamp) -> dict[str, float]:
    # Baseline mix
    w = {"low": 0.45, "medium": 0.35, "high": 0.15, "critical": 0.05}

    if service == "Payments Service":
        q = _quarter_start(opened_at)
        if q in {pd.Timestamp("2024-04-01"), pd.Timestamp("2024-07-01")}:
            w = {"low": 0.25, "medium": 0.35, "high": 0.25, "critical": 0.15}
        elif q == pd.Timestamp("2024-01-01"):
            w = {"low": 0.40, "medium": 0.35, "high": 0.18, "critical": 0.07}
    elif service == "Database":
        w = {"low": 0.35, "medium": 0.35, "high": 0.20, "critical": 0.10}
    elif service == "Fraud Detection":
        w = {"low": 0.40, "medium": 0.35, "high": 0.18, "critical": 0.07}

    s = sum(w.values())
    return {k: v / s for k, v in w.items()}


def _duration_hours(severity: str, rng: np.random.Generator) -> float:
    # Lognormal-ish with clamps.
    params = {
        "low": (np.log(6.0), 0.6),
        "medium": (np.log(16.0), 0.7),
        "high": (np.log(48.0), 0.8),
        "critical": (np.log(96.0), 0.9),
    }
    mu, sigma = params[severity]
    hours = float(rng.lognormal(mean=mu, sigma=sigma))
    return _clamp(hours, 0.5, 24.0 * 10)


def _generate_candidates(
    *,
    start_date: str,
    end_date_exclusive: str,
    seed: int,
) -> list[Ticket]:
    rng = np.random.default_rng(seed)

    services: dict[str, callable] = {
        "API Gateway": lambda d: _default_rate(d, 5.5, annual_drift=0.02),
        "Auth Service": lambda d: _default_rate(d, 4.2, annual_drift=0.03),
        "Payments Service": _payments_rate,
        "Notification Service": lambda d: _default_rate(d, 3.8, annual_drift=0.01),
        "Storage Service": lambda d: _default_rate(d, 4.8, annual_drift=-0.01),
        "Search Service": lambda d: _default_rate(d, 3.0, annual_drift=0.00),
        "Cache Service": lambda d: _default_rate(d, 3.6, annual_drift=0.00),
        "Database": lambda d: _default_rate(d, 4.0, annual_drift=0.00),
        "Analytics Service": lambda d: _default_rate(d, 2.6, annual_drift=0.02),
        "Fraud Detection": _fraud_rate,
        "Billing API": lambda d: _default_rate(d, 2.2, annual_drift=0.01),
        "Web Frontend": lambda d: _default_rate(d, 2.9, annual_drift=0.01),
        "Mobile API": lambda d: _default_rate(d, 1.8, annual_drift=0.03),
        "Data Pipeline": lambda d: _default_rate(d, 1.6, annual_drift=0.04),
        "Reporting": lambda d: _default_rate(d, 1.2, annual_drift=0.02),
        "Observability": lambda d: _default_rate(d, 0.9, annual_drift=0.06),
    }

    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date_exclusive)
    days = pd.date_range(start=start, end=end - pd.Timedelta(days=1), freq="D")

    tickets: list[Ticket] = []
    for day in days:
        season = _weekly_seasonality(day)
        for service, rate_fn in services.items():
            lam = _clamp(float(rate_fn(day)) * season, 0.0, 200.0)
            n = int(rng.poisson(lam=lam))
            if n <= 0:
                continue

            weights = _severity_weights(service, day)
            sev_levels = np.array(list(weights.keys()))
            sev_p = np.array(list(weights.values()), dtype=float)

            opened_seconds = rng.integers(0, 24 * 60 * 60, size=n)
            severities = rng.choice(sev_levels, size=n, p=sev_p)

            for i in range(n):
                opened_at = day + pd.Timedelta(seconds=int(opened_seconds[i]))
                duration_h = _duration_hours(str(severities[i]), rng)
                closed_at = opened_at + pd.Timedelta(hours=duration_h)
                tickets.append(
                    Ticket(
                        service=service,
                        opened_at=opened_at,
                        closed_at=closed_at,
                        severity=str(severities[i]),
                    )
                )

    return tickets


def generate_incidents_csv(
    *,
    output_path: Path,
    n_tickets: int = 15_000,
    start_date: str = "2023-01-01",
    end_date_exclusive: str = "2026-01-01",
    seed: int = 42,
) -> pd.DataFrame:
    candidates = _generate_candidates(
        start_date=start_date,
        end_date_exclusive=end_date_exclusive,
        seed=seed,
    )

    rng = np.random.default_rng(seed)

    if len(candidates) >= n_tickets:
        keep_idx = rng.choice(len(candidates), size=n_tickets, replace=False)
        chosen = [candidates[int(i)] for i in keep_idx]
    else:
        chosen = list(candidates)
        while len(chosen) < n_tickets:
            extra = _generate_candidates(
                start_date=start_date,
                end_date_exclusive=end_date_exclusive,
                seed=int(seed + len(chosen) // 10 + 1),
            )
            if not extra:
                break
            needed = n_tickets - len(chosen)
            take = extra if len(extra) <= needed else extra[:needed]
            chosen.extend(take)

        if len(chosen) > n_tickets:
            chosen = chosen[:n_tickets]

    df = pd.DataFrame(
        {
            "ticket_id": [f"INC-{i:06d}" for i in range(1, len(chosen) + 1)],
            "service": [t.service for t in chosen],
            "opened_at": [t.opened_at for t in chosen],
            "closed_at": [t.closed_at for t in chosen],
            "severity": [t.severity for t in chosen],
        }
    )

    df = df.sort_values(["opened_at", "service", "ticket_id"]).reset_index(drop=True)

    # Re-assign IDs after sorting for stable output.
    df["ticket_id"] = [f"INC-{i:06d}" for i in range(1, len(df) + 1)]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return df


def main() -> None:
    here = Path(__file__).resolve().parent
    out = here / "incidents.csv"

    df = generate_incidents_csv(output_path=out)
    opened_min = df["opened_at"].min()
    opened_max = df["opened_at"].max()
    print(f"Wrote {len(df)} tickets to {out}")
    print(f"Services: {df['service'].nunique()} | Date range: {opened_min} → {opened_max}")


if __name__ == "__main__":
    main()
