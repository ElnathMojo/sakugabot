from datetime import datetime

import pytz

epoch = datetime.utcfromtimestamp(0).replace(tzinfo=pytz.UTC)


def unix_time_seconds(dt=None):
    if not dt:
        dt = datetime.now(pytz.UTC)
    return (dt - epoch).total_seconds()
