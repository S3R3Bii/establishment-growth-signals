"""Fixed convex partial pooling and exact arithmetic on declared decimal scores."""

from fractions import Fraction as F
from decimal import Decimal, localcontext, ROUND_HALF_EVEN

PLACES = 12
SCALE = 10**PLACES


def source_number(token):
    if token in ["", "D", "S", "X", "N"]:
        return None
    return F(token)


def valid_target(row):
    if row is None:
        return False
    a = source_number(row["job_creation_continuers"])
    b = source_number(row["denom"])
    return a is not None and b is not None and a >= 0 and b > 0


def quantize(value):
    value = F(value)
    sign = -1 if value < 0 else 1
    value = abs(value) * SCALE
    integer, remainder = divmod(value.numerator, value.denominator)
    if 2 * remainder > value.denominator or (
        2 * remainder == value.denominator and integer % 2
    ):
        integer += 1
    return sign * integer


def fixed(integer, places=PLACES):
    scale = 10**places
    sign = "-" if integer < 0 else ""
    integer = abs(integer)
    return f"{sign}{integer//scale}.{integer%scale:0{places}d}"


def ratio_text(value):
    value = F(value)
    with localcontext() as ctx:
        ctx.prec = len(str(abs(value.numerator))) + len(str(value.denominator)) + 60
        return format(
            (Decimal(value.numerator) / Decimal(value.denominator)).quantize(
                Decimal("1e-12"), rounding=ROUND_HALF_EVEN
            ),
            "f",
        )


def predict(own_count, own_denom, donor_count, donor_denom, weight):
    if (
        own_denom <= 0
        or donor_denom <= 0
        or not 0 <= weight <= 1
        or own_count < 0
        or donor_count < 0
    ):
        raise ValueError("Invalid fixed predictor inputs")
    return quantize(
        weight * 100 * own_count / own_denom
        + (1 - weight) * 100 * donor_count / donor_denom
    )


def summarize(rows):
    if not rows:
        return dict(n=0, series=0, mae="", mse="", rmse="", weighted_mae="")
    groups = {}
    for row in rows:
        groups.setdefault((row["st"], row["sector"]), []).append(row)
    mae = sum(
        (
            F(sum(abs(r["error_scaled"]) for r in group), len(group) * SCALE)
            for group in groups.values()
        ),
        F(0),
    ) / len(groups)
    mse = sum(
        (
            F(sum(r["error_scaled"] ** 2 for r in group), len(group) * SCALE * SCALE)
            for group in groups.values()
        ),
        F(0),
    ) / len(groups)
    weighted = sum((abs(r["error_scaled"]) * r["target_denom"] for r in rows), F(0)) / (
        sum((r["target_denom"] for r in rows), F(0)) * SCALE
    )
    with localcontext() as ctx:
        ctx.prec = 100
        rmse = (
            (Decimal(mse.numerator) / Decimal(mse.denominator))
            .sqrt()
            .quantize(Decimal("1e-12"), rounding=ROUND_HALF_EVEN)
        )
    return dict(
        n=len(rows),
        series=len(groups),
        mae=str(mae),
        mse=str(mse),
        rmse=format(rmse, "f"),
        weighted_mae=str(weighted),
    )
