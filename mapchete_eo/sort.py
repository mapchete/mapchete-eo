"""
This module holds all code required to sort products or slices.
"""

from typing import Callable, List, Optional

from pydantic import BaseModel

from mapchete_eo.protocols import DateTimeProtocol
from mapchete_eo.time import timedelta, to_datetime
from mapchete_eo.types import DateTimeLike


class SortMethodConfig(BaseModel):
    func: Callable


def sort_objects_by_target_date(
    objects: List[DateTimeProtocol],
    target_date: Optional[DateTimeLike] = None,
    reverse: bool = False,
    **kwargs,
) -> List[DateTimeProtocol]:
    """
    Return sorted list of onjects according to their distance to the target_date.

    Default for target date is the middle between the objects start date and end date.
    """
    if len(objects) == 0:
        return objects

    if target_date is None:
        time_list = [to_datetime(object.datetime) for object in objects]
        start_time = min(time_list)
        end_time = max(time_list)
        target_datetime = start_time + (end_time - start_time) / 2
    else:
        target_datetime = to_datetime(target_date)

    objects.sort(key=lambda x: timedelta(x.datetime, target_datetime), reverse=reverse)

    return objects


class TargetDateSort(SortMethodConfig):
    func: Callable = sort_objects_by_target_date
    target_date: Optional[DateTimeLike] = None
    reverse: bool = False
