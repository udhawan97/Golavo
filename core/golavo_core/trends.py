"""The checkpoint series every trend line is sampled at.

Golavo Ratings and competition analytics both draw a twelve-point trend, and
both need the points to mean the same thing: eleven prior month ends, then the
exact anchor the data actually reaches. The function was byte-identical in the
two modules, with one docstring saying it "mirrors analytics" — so the fact that
a ratings sparkline and an analytics sparkline share an x-axis rested on nobody
editing one of them.
"""

from __future__ import annotations

import pandas as pd

TREND_CHECKPOINTS = 12


def month_end_checkpoints(anchor: pd.Timestamp) -> list[pd.Timestamp]:
    """Eleven prior month ends, then ``anchor`` itself.

    The final point is the anchor rather than its month end so the last value on
    a trend line is the real latest-data instant, not a future month boundary
    the data has not reached.
    """
    month_start = anchor.normalize().replace(day=1)
    previous_month_end = month_start - pd.Timedelta(seconds=1)
    prior = list(pd.date_range(end=previous_month_end, periods=TREND_CHECKPOINTS - 1, freq="ME"))
    return [*prior, anchor]
