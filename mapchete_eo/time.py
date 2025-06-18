import datetime
from typing import List, Tuple, Union

import dateutil.parser

from mapchete_eo.types import DateTimeLike

_time = {"min": datetime.datetime.min.time(), "max": datetime.datetime.max.time()}


def to_datetime(t: DateTimeLike, append_time="min") -> datetime.datetime:
    """Convert input into datetime object."""
    if isinstance(t, datetime.datetime):
        return t
    elif isinstance(t, datetime.date):
        return datetime.datetime.combine(t, _time[append_time])
    else:
        return dateutil.parser.parse(t)


def time_ranges_intersect(
    t1: Tuple[DateTimeLike, DateTimeLike],
    t2: Tuple[DateTimeLike, DateTimeLike],
) -> bool:
    """Check if two time ranges intersect."""
    t1_start = to_datetime(t1[0], "min").replace(tzinfo=None)
    t1_end = to_datetime(t1[1], "max").replace(tzinfo=None)
    t2_start = to_datetime(t2[0], "min").replace(tzinfo=None)
    t2_end = to_datetime(t2[1], "max").replace(tzinfo=None)
    return (t1_start <= t2_start <= t1_end) or (t2_start <= t1_start <= t2_end)


def timedelta(date: DateTimeLike, target: DateTimeLike, seconds: bool = True):
    """Return difference between two time stamps."""
    delta = to_datetime(date) - to_datetime(target)
    if seconds:
        return abs(delta.total_seconds())
    else:
        return abs(delta.days)


def day_range(
    start_date: Union[datetime.datetime, datetime.date],
    end_date: Union[datetime.datetime, datetime.date],
) -> List[datetime.date]:
    start_date = (
        start_date.date() if isinstance(start_date, datetime.datetime) else start_date
    )
    end_date = end_date.date() if isinstance(end_date, datetime.datetime) else end_date
    return [
        start_date + datetime.timedelta(n)
        for n in range(int((end_date - start_date).days) + 1)
    ]
