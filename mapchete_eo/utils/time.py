import datetime
import pytz


def str_to_date(date_str):
    """
    Convert simple date string into date object.

    If no timezone is given, UTC is assumed and datetime object is created accordingly.
    """
    if isinstance(date_str, str):
        if "T" in date_str:
            try:
                return datetime.datetime.strptime(
                    date_str, "%Y-%m-%dT%H:%M:%S.%fZ"
                ).replace(tzinfo=pytz.utc)
            except ValueError:
                return datetime.datetime.strptime(
                    date_str, "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=pytz.utc)
        else:
            return datetime.datetime(*map(int, date_str.split("-")), tzinfo=pytz.utc)
    elif isinstance(date_str, datetime.datetime):
        if date_str.tzinfo is None or date_str.tzinfo.utcoffset(date_str) is None:
            return date_str.replace(tzinfo=pytz.utc)
        else:
            return date_str
    elif isinstance(date_str, datetime.date):
        return datetime.datetime.combine(date_str, datetime.time()).replace(
            tzinfo=pytz.utc
        )
    else:
        raise TypeError("invalid date given: %s" % date_str)


def timedelta(date=None, target=None, seconds=True, **kwargs):
    """Return difference between two time stamps."""
    delta = str_to_date(date) - str_to_date(target)
    if seconds:
        return abs(delta.total_seconds())
    else:
        return abs(delta.days)


def daterange(start_date, end_date, n=1):
    """Return number of days between start and end."""
    start_date = str_to_date(start_date)
    end_date = str_to_date(end_date)
    for x in range(int((end_date - start_date).days) + 1):
        begin = start_date + datetime.timedelta(x)
        end = begin + datetime.timedelta(1)
        yield begin, end
