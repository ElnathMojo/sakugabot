import requests
from celery import shared_task

from underworld.models import IP


@shared_task(soft_time_limit=5)
def get_ip_info(*addrs):
    errors = list()
    for addr in addrs:
        info = requests.get('http://ip-api.com/json/{}'.format(addr)).json()
        if info['status'] == 'success':
            IP.objects.update_or_create(defaults={
                'country': info.get('country', None),
                'country_code': info.get('countryCode', None),
                'region': info.get('region', None),
                'region_name': info.get('regionName', None),
                'city': info.get('city', None),
                'zip': info.get('zip', None),
                'lat': info.get('lat', None),
                'lon': info.get('lon', None),
                'timezone': info.get('timezone', None),
                'isp': info.get('isp', None),
                'org': info.get('org', None),
                '_as': info.get('as', None),
            }, address=addr)
        else:
            errors.append(info)
    return errors
