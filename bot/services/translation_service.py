import difflib
import logging
from functools import wraps
from urllib import parse

import regex as re
import requests
from bs4 import BeautifulSoup
from django.conf import settings
from retrying import retry

from bot.constants import ANN_URL, ANN_SEARCH_ENDPOINT, ANN_PEOPLE_ENDPOINT, MAL_URL, MAL_SEARCH_ENDPOINT, \
    MAL_ANIME_ENDPOINT, BANGUMI_API_URL, BANGUMI_SEARCH_ENDPOINT, GOOGLE_KGRAPH_ENTITY_ENDPOINT, \
    GOOGLE_KGRAPH_SEARCH_API, SYNONYM_DICT

logger = logging.getLogger("bot.services.translation")


def retry_if_network_error(exception):
    return isinstance(exception, OSError)


def retry_if_network_error_or_value_error(exception):
    return retry_if_network_error(exception) or isinstance(exception, ValueError)


def none_if_exception(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except:
            logger.exception("{} went wrong.".format(f.__name__))
            return None

    return decorated


class TranslationServiceBase(object):
    BASE_URL = None
    SEARCH_ENDPOINT = None
    ENTITY_ENDPOINT = None

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/42.0.2311.152 Safari/537.36'
    }

    def __init__(self):
        self.session = requests.session()
        self.session.headers.update(self.HEADERS)

    @retry(stop_max_attempt_number=3,
           wait_fixed=1000,
           retry_on_exception=retry_if_network_error)
    def _get(self, url, **kwargs):
        kwargs.setdefault('timeout', 10)
        return self.session.get(url, **kwargs)

    def translate(self, name, **kwargs):
        """
        :return: info_dict
        """
        raise NotImplementedError

    @staticmethod
    def _replace_synonym(name):
        for k, v in SYNONYM_DICT.items():
            if k in name:
                name = name.replace(k, v)
        return name

    @staticmethod
    def _get_diff_ratio(first, second, contain_weight=0.1):
        process_str = lambda x: TranslationServiceBase._replace_synonym("".join(x.lower().split())) if x else ""
        first = process_str(first)
        second = process_str(second)
        ratio = difflib.SequenceMatcher(None,
                                        first,
                                        second).ratio()
        if ratio == 1:
            ratio = 2
        elif first in second:
            ratio += contain_weight
        elif second in first:
            ratio += contain_weight / 2
        return ratio


class ANNArtistTranslationService(TranslationServiceBase):
    NAME = "ANN"
    BASE_URL = ANN_URL
    SEARCH_ENDPOINT = ANN_SEARCH_ENDPOINT
    ENTITY_ENDPOINT = ANN_PEOPLE_ENDPOINT
    PATTERN = r"/encyclopedia/people.php\?id="

    def get_search_results(self, name_en):
        """
        :param name_en:
        :return: [(person_id, person_name, job), ...]
        """
        r = self._get(self.BASE_URL + self.SEARCH_ENDPOINT,
                      params={'only': 'person',
                              'q': name_en})
        soup = BeautifulSoup(r.content, 'lxml')
        search_results = soup.find_all('a', href=re.compile(self.PATTERN))

        results = list()
        for result in search_results:
            try:
                job = result.i.get_text().strip()
                result.i.clear()
            except:
                job = ""
            person_id = int(re.findall(r"\d+", result.get('href'))[0])
            person_name = result.get_text().strip()
            results.append(tuple([person_id, person_name, job]))
        return results

    def _get_probably_result(self, original_name, res):
        max_ratio = 0
        result = (None, None)
        for person_id, person_name, job in res[:10]:
            ratio = self._get_diff_ratio(original_name, person_name)
            if "animator" in "".join(job.lower().split()):
                ratio += 0.03
            logger.debug("original: {}, search_result: {}, ann_id: {}, ratio: {}".format(
                original_name, person_name, person_id, ratio
            ))
            if ratio < 1:
                continue
            if ratio > max_ratio:
                max_ratio = ratio
                result = (person_id, person_name)
        if 0 < max_ratio < 2:
            logger.warning("Inexact match for name[{}]."
                           " Ratio: {} ANN-Person-ID: {} Name: {}".format(original_name,
                                                                          max_ratio,
                                                                          result[0],
                                                                          result[1]))
        return result

    @none_if_exception
    def get_entity_name(self, id):
        r = self._get(self.BASE_URL + self.ENTITY_ENDPOINT,
                      params={'id': id})
        soup = BeautifulSoup(r.content, 'lxml')
        title_block = soup.find(id="page-title")
        title_block.h1.clear()
        original_name = title_block.get_text().strip()
        pattern = re.compile(r".*[\da-zA-Z]+.*")
        if not re.match(pattern, original_name):
            if original_name.count(' ') == 1:
                original_name = original_name.replace(' ', '')
        if original_name:
            return original_name
        return None

    def translate(self, name_en, **kwargs):
        try:
            res = self.get_search_results(name_en)
            logger.info("Name[{}] got {} search results from ANN.".format(name_en, len(res)))
            person_id, person_name = self._get_probably_result(name_en, res)
            if not person_id:
                logger.info("Name[{}] got no match result in ANN search results.".format(name_en))
                return dict()
            return {"ann_pid": person_id,
                    "name_en": person_name,
                    "name_ja": self.get_entity_name(person_id)}
        except:
            logger.exception("ANN translation failed. name[{}]".format(name_en))
            return dict()


class MALAnimeTranslationService(TranslationServiceBase):
    NAME = "MyAnimeList"
    BASE_URL = MAL_URL
    SEARCH_ENDPOINT = MAL_SEARCH_ENDPOINT
    ENTITY_ENDPOINT = MAL_ANIME_ENDPOINT

    def get_search_results(self, name_en):
        r = self._get(self.BASE_URL + self.SEARCH_ENDPOINT,
                      params={'q': name_en})
        soup = BeautifulSoup(r.content, 'lxml', from_encoding='utf-8')
        search_results = soup.find_all('a', 'hoverinfo_trigger fw-b fl-l')

        results = list()
        for result in search_results:
            anime_id = int(result['id'].replace('sinfo', ''))
            anime_name = result.strong.get_text()
            results.append(tuple([anime_id, anime_name]))
        return results

    def _get_probably_result(self, original_name, res):
        max_ratio = 0
        result = (None, None)
        for anime_id, anime_name in res[:10]:
            ratio = self._get_diff_ratio(original_name, anime_name, contain_weight=0.5)
            logger.debug("original: {}, search_result: {}, mal_id: {}, ratio: {}".format(
                original_name, anime_name, anime_id, ratio
            ))
            if ratio < 0.9:
                continue
            if ratio > max_ratio:
                max_ratio = ratio
                result = (anime_id, anime_name)
        if 0 < max_ratio < 2:
            logger.warning("Inexact match for name[{}]."
                           " Ratio: {} MAL-Anime-ID: {} Name: {}".format(original_name,
                                                                         max_ratio,
                                                                         result[0],
                                                                         result[1]))
        return result

    @none_if_exception
    def get_entity_name(self, id):
        r = self._get("{}{}".format(self.BASE_URL + self.ENTITY_ENDPOINT, id))
        soup = BeautifulSoup(r.content, 'lxml', from_encoding='utf-8')
        original_name = soup.find("span", text='Japanese:').parent.get_text(strip=True).replace("Japanese:", "").strip()
        if original_name:
            return original_name
        return None

    def translate(self, name_en, **kwargs):
        try:
            res = self.get_search_results(name_en)
            logger.info("Name[{}] got {} search results from MAL.".format(name_en, len(res)))
            anime_id, anime_name = self._get_probably_result(name_en, res)
            if not anime_id:
                logger.info("Name[{}] got no match result in MAL search results.".format(name_en))
                return dict()
            return {"mal_aid": anime_id,
                    "name_en": anime_name,
                    "name_ja": self.get_entity_name(anime_id)}
        except:
            logger.exception("MAL translation failed. name[{}]".format(name_en))
            return dict()


class BangumiAnimeTranslationService(TranslationServiceBase):
    NAME = "Bangumi"
    BASE_URL = BANGUMI_API_URL
    SEARCH_ENDPOINT = BANGUMI_SEARCH_ENDPOINT

    @retry(stop_max_attempt_number=3,
           wait_fixed=1000,
           retry_on_exception=retry_if_network_error_or_value_error)
    def get_search_results(self, name_ja, name_en=None, **kwargs):
        # remove katakana between brackets
        pattern = re.compile(r'[\(\[〈]([^\p{isHan}]?)*\p{IsKatakana}([^\p{isHan}]?)*[\)\]〉]$')
        name_ja = pattern.sub('', name_ja).strip()
        results = list()
        ids = set()
        for name in (name_ja, name_en):
            response = self._get("{}{}".format(self.BASE_URL + self.SEARCH_ENDPOINT, parse.quote_plus(name)),
                                 params={'type': 2,
                                         'max_results': 20}).json()
            try:
                res = response["list"]
            except KeyError:
                logger.warning("Name[{}] got incorrect result from bangumi.".format(name))
                continue
            for r in res:
                if r["id"] in ids:
                    continue
                ids.add(r["id"])
                results.append(tuple([r["id"], r["name"], r["name_cn"]]))

        return results

    def _get_probably_result(self, name_ja, name_en, res):
        max_ratio = 0
        result = (None, None, None)
        for anime_id, anime_name, anime_name_cn in res[:10]:
            ratio = max((self._get_diff_ratio(name_ja, anime_name, contain_weight=0.3),
                         self._get_diff_ratio(name_en, anime_name, contain_weight=0.3)))
            logger.debug("original_ja: {}, original_en: {}, search_result: {}, bgm_id: {}, ratio: {}".format(
                name_ja, name_en, anime_name, anime_id, ratio
            ))
            if ratio < 0.95:
                continue
            if ratio > max_ratio:
                max_ratio = ratio
                result = (anime_id, anime_name_cn, anime_name)
        if 0 < max_ratio < 2:
            logger.warning("Inexact match for name[{}]."
                           " Ratio: {} Bangumi-Subject-ID: {} Name: {}".format(name_ja,
                                                                               max_ratio,
                                                                               result[0],
                                                                               result[1]))
        return result

    def translate(self, name_ja, name_en=None, **kwargs):
        try:
            res = self.get_search_results(name_ja, name_en)
            logger.info("Name[{}] got {} search results from Bangumi.".format(name_ja, len(res)))
            anime_id, anime_name, anime_name_ja = self._get_probably_result(name_ja, name_en, res)
            if not anime_id:
                logger.info("Name[{}] got no match result in Bangumi search results.".format(name_ja))
                return dict()
            return {"bgm_sid": anime_id,
                    "name_ja": anime_name_ja,
                    "name_zh": anime_name}
        except:
            logger.exception("Bangumi translation failed. name[{}]".format(name_ja))
            return dict()


class GoogleTranslateService(TranslationServiceBase):
    NAME = "Google"
    BASE_URL = GOOGLE_KGRAPH_SEARCH_API
    ENTITY_ENDPOINT = GOOGLE_KGRAPH_ENTITY_ENDPOINT
    EXCLUDE_TYPES = []

    def translate(self, name, language_codes=("en", "ja", "zh"), **kwargs):
        try:
            response = self._get(self.BASE_URL + self.ENTITY_ENDPOINT,
                                 params={
                                     "key": settings.GOOGLE_KGRAPH_API_KEY,
                                     "query": name,
                                     "languages": ",".join(language_codes),
                                     "indent": True,
                                     "limit": 1
                                 }).json()
            if len(response['itemListElement']) < 1:
                logger.info("Name[{}] got no search result from google "
                            "with language_codes[{}].".format(name, ','.join(language_codes)))
                return dict()

            result = response['itemListElement'][0]['result']
            logger.debug("Name[{}] got one search result from google. ID[{}]".format(name, result['@id']))

            if response['itemListElement'][0]['resultScore'] < 20:
                logger.info("Name[{}]'s search resultScore is too low. Abandoned.".format(name))
                return dict()

            if any(x in self.EXCLUDE_TYPES for x in result['@type']):
                logger.info("Name[{}]'s search result got incorrect type. Abandoned.".format(name))
                return dict()

            if len(language_codes) <= 1:
                name_dict = {[language_codes[0]]: result['name']}
            else:
                name_dict = {x['@language']: x['@value'] for x in result['name']}

            result = dict()
            for key in ('name_en', 'name_ja', 'name_zh'):
                value = name_dict.get(key[-2:], None)
                if value:
                    result[key] = value
                    continue

                if key == 'name_zh':
                    for language_code in ('zh-TW', 'zh-HK'):
                        value = name_dict.get(language_code, None)
                        if value:
                            result[key] = value
                            break
            return result
        except:
            logger.exception("Google translation failed. name[{}]".format(name))
            return {}


class GoogleArtistTranslateService(GoogleTranslateService):
    EXCLUDE_TYPES = ['City', 'Event', 'Organization', 'Place']


class GoogleAnimeTranslateService(GoogleTranslateService):
    EXCLUDE_TYPES = ['Person', 'City', 'Event', 'Organization', 'Place']
