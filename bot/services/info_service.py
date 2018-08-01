import logging
from urllib import parse

import regex
import requests
from bs4 import BeautifulSoup
from retrying import retry

from bot.constants import ATWIKI_SEARCH_URI, ANIMEWIKI_URL_PATTERN, SAKUGAWIKI_URL_PATTERN, ASDB_SEARCH_URI

logger = logging.getLogger('bot.services.info')


class InfoServiceBase(object):
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/42.0.2311.152 Safari/537.36'
    }

    def __init__(self):
        self.session = requests.session()
        self.session.headers.update(self.HEADERS)

    @retry(stop_max_attempt_number=3,
           wait_fixed=1000,
           retry_on_exception=lambda e: isinstance(e, OSError))
    def _get(self, url, **kwargs):
        kwargs.setdefault('timeout', 10)
        return self.session.get(url, **kwargs)

    def get_info(self, name, **kwargs):
        """
        :param name: str
        :return: info dict
        """
        raise NotImplemented


class AtwikiInfoService(InfoServiceBase):
    SEARCH_URI = ATWIKI_SEARCH_URI
    PATTERNS = {
        'sakuga_wiki_id': SAKUGAWIKI_URL_PATTERN,
        'anime_wiki_id': ANIMEWIKI_URL_PATTERN
    }

    def get_info(self, name, **kwargs):
        info = {}
        try:
            res = self._get('{}{}'.format(self.SEARCH_URI, parse.quote(name)))
            soup = BeautifulSoup(res.content, 'lxml')

            logger.info('Name[{}] got search results from atwiki.'.format(name))

            for result in soup.find_all('a', 'atwiki_search_title'):
                link = result['href']
                result_name = result.get_text().split('-')[-1].strip()
                if result_name == name:
                    for code, pattern in self.PATTERNS.items():
                        ids = regex.compile(pattern).findall(link)
                        if len(ids) == 1:
                            logger.info('Name[{}] got matching id[{}] on site[{}]'.format(name, ids[0], code[:-3]))
                            info[code] = ids[0]
        except:
            logger.exception("Some thing went wrong while getting Name[{}] info from atwiki.".format(name))
        finally:
            return info


class ASDBInfoService(InfoServiceBase):
    SEARCH_URI = ASDB_SEARCH_URI

    def get_info(self, name, **kwargs):
        info = {}
        try:
            res = self._get('{}{}'.format(self.SEARCH_URI, parse.quote(name, encoding='EUC-JP')))
            soup = BeautifulSoup(res.content, 'lxml', from_encoding='EUC-JP')

            logger.info('Name[{}] got search results from anime staff db.'.format(name))

            for result in soup.find_all('h3', 'keyword'):
                link = result.a['href']
                result_name = result.a.get_text().strip()
                if result_name == name:
                    logger.info('Name[{}] got matching result on anime staff db'.format(name))
                    info['anime_staff_database_link'] = link
        except:
            logger.exception("Some thing went wrong while getting Name[{}] info from anime staff db.".format(name))
        finally:
            return info
