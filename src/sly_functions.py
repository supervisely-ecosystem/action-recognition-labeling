import datetime

import sly_globals as g

from sly_fields_names import ItemsStatusField


def get_current_time():
    return str(datetime.datetime.now().strftime("%H:%M:%S"))

