from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict


@dataclass(frozen=True)
class Economics:
    price_usd: float
    fees_usd: float
    chargeback_reserve_usd: float
    cogs_usd: float
    labor_usd: float
    support_usd: float
    profit_usd: float
    margin: float

    def to_dict(self) -> Dict:
        return asdict(self)


def estimate_digital_pack(
    *,
    price_usd: float,
    platform_fee_rate: float = 0.10,
    payment_fee_rate: float = 0.03,
    chargeback_rate: float = 0.02,
    support_minutes: float = 10.0,
    labor_usd_per_hour: float = 20.0,
) -> Economics:
    fees = price_usd * (platform_fee_rate + payment_fee_rate)
    chargeback = price_usd * chargeback_rate
    support = (support_minutes / 60.0) * labor_usd_per_hour
    profit = price_usd - fees - chargeback - support
    margin = profit / max(1e-6, price_usd)
    return Economics(
        price_usd=price_usd,
        fees_usd=round(fees, 2),
        chargeback_reserve_usd=round(chargeback, 2),
        cogs_usd=0.0,
        labor_usd=0.0,
        support_usd=round(support, 2),
        profit_usd=round(profit, 2),
        margin=round(margin, 3),
    )


def estimate_kit(
    *,
    price_usd: float,
    cogs_usd: float,
    assembly_minutes: float,
    support_minutes: float,
    platform_fee_rate: float = 0.10,
    payment_fee_rate: float = 0.03,
    chargeback_rate: float = 0.02,
    labor_usd_per_hour: float = 20.0,
) -> Economics:
    fees = price_usd * (platform_fee_rate + payment_fee_rate)
    chargeback = price_usd * chargeback_rate
    labor = (assembly_minutes / 60.0) * labor_usd_per_hour
    support = (support_minutes / 60.0) * labor_usd_per_hour
    profit = price_usd - fees - chargeback - cogs_usd - labor - support
    margin = profit / max(1e-6, price_usd)
    return Economics(
        price_usd=price_usd,
        fees_usd=round(fees, 2),
        chargeback_reserve_usd=round(chargeback, 2),
        cogs_usd=round(cogs_usd, 2),
        labor_usd=round(labor, 2),
        support_usd=round(support, 2),
        profit_usd=round(profit, 2),
        margin=round(margin, 3),
    )

