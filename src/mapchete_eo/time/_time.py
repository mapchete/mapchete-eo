import datetime

import dateutil.parser

_time = {"min": datetime.datetime.min.time(), "max": datetime.datetime.max.time()}


def to_datetime(t, append_time="min"):
    """Convert input into datetime object."""
    if isinstance(t, datetime.datetime):
        return t
    elif isinstance(t, datetime.date):
        return datetime.datetime.combine(t, _time[append_time])
    else:
        return dateutil.parser.parse(t)


def time_ranges_intersect(t1, t2):
    """Check if two time ranges intersect."""
    t1_start = to_datetime(t1[0], "min").replace(tzinfo=None)
    t1_end = to_datetime(t1[1], "max").replace(tzinfo=None)
    t2_start = to_datetime(t2[0], "min").replace(tzinfo=None)
    t2_end = to_datetime(t2[1], "max").replace(tzinfo=None)
    return (t1_start <= t2_start <= t1_end) or (t2_start <= t1_start <= t2_end)
