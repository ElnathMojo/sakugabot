import collections
import difflib
import logging
from urllib import parse

import regex
import requests
from bs4 import BeautifulSoup
from django.conf import settings
from retrying import retry

from bot.constants import ATWIKI_SEARCH_URI, ANIMEWIKI_URL_PATTERN, SAKUGAWIKI_URL_PATTERN, ASDB_SEARCH_URI, \
    SYNONYM_DICT, ANN_URL, ANN_SEARCH_ENDPOINT, ANN_PEOPLE_ENDPOINT, MAL_URL, MAL_SEARCH_ENDPOINT, MAL_ANIME_ENDPOINT, \
    BANGUMI_API_URL, BANGUMI_SEARCH_ENDPOINT, BANGUMI_SUBJECT_ENDPOINT, GOOGLE_KGS_URL, GOOGLE_KGS_SEARCH_ENDPOINT, \
    GOOGLE_KGS_ENTITY_URI
from bot.services.ultils.decorators import default_if_exception, retry_if_network_error_or_parse_error

logger = logging.getLogger('bot.services.info')


class InfoServiceBase(object):
    NAME = "Info"
    BASE_URL = ""

    SEARCH_ENDPOINT = ""
    SEARCH_MAX_NUMBER = 10

    ENTITY_PK_NAME = ""
    ENTITY_NAME_KEYS = ()

    MIN_RATIO = 0.95
    CONTAIN_WEIGHT = 0.3
    CONTAIN_WEIGHT_REVERSED = 0.5

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/67.0.3396.99 Safari/537.36'
    }

    def __init__(self):
        self.session = requests.session()
        self.session.headers.update(self.HEADERS)

    @property
    def search_url(self):
        return '{}{}'.format(self.BASE_URL, self.SEARCH_ENDPOINT)

    def _get(self, url, **kwargs):
        kwargs.setdefault('timeout', 10)
        response = self.session.get(url, **kwargs)
        response.raise_for_status()
        return response

    def _get_search_requests_params(self, name):
        return self.search_url, {"params": {'q': name}}

    def _get_search_response(self, name):
        url, params = self._get_search_requests_params(name)
        return self._get(url, **params)

    def _generate_search_results(self, response):
        """
        :param response: requests.models.Response
        :return: list of info_dict
        """
        raise NotImplemented

    def _get_entity_pk_from_info_dict(self, info_dict):
        return info_dict.get(self.ENTITY_PK_NAME, None)

    @staticmethod
    def _replace_synonym(name):
        for k, v in SYNONYM_DICT.items():
            if k in name:
                name = name.replace(k, v)
        return name

    def _get_diff_ratio(self, original, target):
        process_str = lambda x: "".join(InfoServiceBase._replace_synonym(x).lower().split()) if x else ""
        original = process_str(original)
        target = process_str(target)
        ratio = difflib.SequenceMatcher(None,
                                        original,
                                        target).ratio()
        if ratio == 1:
            ratio = 2
        elif original in target:
            ratio += self.CONTAIN_WEIGHT
        elif target in original:
            ratio += self.CONTAIN_WEIGHT_REVERSED
        return ratio

    @retry(stop_max_attempt_number=3,
           wait_fixed=1000,
           retry_on_exception=retry_if_network_error_or_parse_error)
    def _get_search_results(self, name):
        response = self._get_search_response(name)
        logger.info('Name[{}] got search response from {}.'.format(name, self.NAME))
        return self._generate_search_results(response)

    @default_if_exception(default=list(),
                          logger=logger,
                          msg="Getting Search Results Failed.")
    def get_search_results(self, *names):
        """
        :param names: names to be searched
        :return: list of info_dict
        """
        results = collections.OrderedDict()
        for name in names:
            item_list = self._get_search_results(name)[:self.SEARCH_MAX_NUMBER]
            results.update(collections.OrderedDict([(self._get_entity_pk_from_info_dict(x), x) for x in item_list]))
        return list(results.values())

    def _get_names_from_info_dict(self, info_dict):
        return [value for key, value in info_dict.items() if key in self.ENTITY_NAME_KEYS]

    @staticmethod
    def _generate_name_pair(original_names, target_names):
        for original_name in original_names:
            for target_name in target_names:
                yield original_name, target_name

    def _get_item_weight(self, item):
        return 0

    def _get_most_likely_item(self, items, *original_names):
        max_ratio = 0
        target_item = dict()
        for item in items:
            target_names = self._get_names_from_info_dict(item)
            ratio = max(self._get_diff_ratio(x, y) for x, y in
                        self._generate_name_pair(original_names, target_names))
            ratio += self._get_item_weight(item)
            logger.debug("ratio: {}; original_names: {}; target_names: {}; {}: {}, ".format(
                ratio,
                original_names,
                target_names,
                self.ENTITY_PK_NAME,
                self._get_entity_pk_from_info_dict(item)
            ))
            if ratio < self.MIN_RATIO:
                continue
            if ratio > max_ratio:
                max_ratio = ratio
                target_item = item
        if 0 < max_ratio < 2:
            logger.warning("Inexact match for original_names[{}]. "
                           "ratio: {}, {}: {}, target_names: {}".format(original_names,
                                                                        max_ratio,
                                                                        self.ENTITY_PK_NAME,
                                                                        self._get_entity_pk_from_info_dict(target_item),
                                                                        self._get_names_from_info_dict(target_item)))
        return target_item

    @default_if_exception(default=dict(),
                          logger=logger,
                          msg="Getting Information Failed.")
    def get_info(self, *names):
        """
        :param name: str
        :return: info dict
        """
        info_items = self.get_search_results(*names)
        logger.info("Names[{}] got {} search results from {}.".format(names, len(info_items), self.NAME))
        info_item = self._get_most_likely_item(info_items, *names)
        if not info_item:
            logger.info("Names[{}] got no matching result in "
                        "{} search results.".format(names,
                                                    self.NAME))
        else:
            logger.info("Names[{}] got one matching result in "
                        "{} search results. info_dict: {}".format(names,
                                                                  self.NAME,
                                                                  info_item))
        return info_item


class RetrieveEntityFromRemoteMixin(object):
    ENTITY_ENDPOINT = ""

    @property
    def entity_url(self):
        return "{}{}".format(self.BASE_URL, self.ENTITY_ENDPOINT)

    def _get_entity_requests_params(self, entity_pk):
        return "{}{}".format(self.entity_url, entity_pk), dict()

    def _get_entity_response(self, entity_pk):
        url, params = self._get_entity_requests_params(entity_pk)
        return self._get(url, **params)

    def _generate_entity_info(self, response):
        raise NotImplemented

    @default_if_exception(default=dict(),
                          logger=logger,
                          msg="Getting Information By Entity_PK Failed.")
    @retry(stop_max_attempt_number=3,
           wait_fixed=1000,
           retry_on_exception=retry_if_network_error_or_parse_error)
    def get_entity_info(self, entity_pk):
        """
        :return: info dict
        """
        return self._generate_entity_info(self._get_entity_response(entity_pk))

    @default_if_exception(default=dict(),
                          logger=logger,
                          msg="Getting Information Failed.")
    def get_info(self, *names):
        """
        :param name: str
        :return: info dict
        """
        info_items = self.get_search_results(*names)
        logger.info("Names[{}] got {} search results from {}.".format(names, len(info_items), self.NAME))
        info_item = self._get_most_likely_item(info_items, *names)
        if info_item:
            entity_info = self.get_entity_info(self._get_entity_pk_from_info_dict(info_item))
            info_item.update(entity_info)
            logger.info("Names[{}] got one matching result in "
                        "{} search results. info_dict: {}".format(names,
                                                                  self.NAME,
                                                                  info_item))
        else:
            logger.info("Names[{}] got no matching result in "
                        "{} search results.".format(names,
                                                    self.NAME))
        return info_item


class ANNArtistInfoService(RetrieveEntityFromRemoteMixin,
                           InfoServiceBase):
    """
        :return: keys:(ann_pid, name_ja, name_en)
    """
    NAME = "Anime News Network"
    BASE_URL = ANN_URL

    SEARCH_ENDPOINT = ANN_SEARCH_ENDPOINT

    ENTITY_ENDPOINT = ANN_PEOPLE_ENDPOINT
    ENTITY_PK_NAME = "ann_pid"
    ENTITY_NAME_KEYS = ("name_en",)

    MIN_RATIO = 1
    CONTAIN_WEIGHT = 0.1
    CONTAIN_WEIGHT_REVERSED = 0.1

    def _get_item_weight(self, item):
        description = item.get("description", None)
        if description and "animator" in description.lower():
            return 0.03
        return 0

    def _get_search_requests_params(self, name):
        return self.search_url, {"params": {'only': 'person',
                                            'q': name}
                                 }

    def _generate_search_results(self, response):
        info_list = list()

        soup = BeautifulSoup(response.content, 'lxml')
        search_results = soup.find_all('a', href=regex.compile(r"/encyclopedia/people.php\?id="))
        for result in search_results:
            info_dict = dict()
            try:
                description = result.i.get_text(strip=True)
                result.i.clear()
                if description:
                    info_dict["description"] = description
            except AttributeError:
                pass
            info_dict.update(
                {
                    self.ENTITY_PK_NAME: int(regex.findall(r"\d+", result.get('href'))[0]),
                    self.ENTITY_NAME_KEYS[0]: result.get_text(strip=True)
                }
            )
            info_list.append(info_dict)
        return info_list

    def _get_entity_requests_params(self, entity_pk):
        return self.entity_url, {"params": {'id': entity_pk}}

    def _generate_entity_info(self, response):
        info_dict = dict()
        soup = BeautifulSoup(response.content, 'lxml')
        title_block = soup.find(id="page-title")
        title_block.h1.clear()
        original_name = title_block.get_text().strip()
        pattern = regex.compile(r".*[\da-zA-Z]+.*")
        if not regex.match(pattern, original_name):  # remove space between ja_name
            if original_name.count(' ') == 1:
                original_name = original_name.replace(' ', '')
        if original_name:
            info_dict.update(
                {
                    "name_ja": original_name
                }
            )
        return info_dict


class MALCopyrightInfoService(RetrieveEntityFromRemoteMixin,
                              InfoServiceBase):
    """
        :return: keys:(mal_aid, name_ja, name_en)
    """
    NAME = "MyAnimeList"
    BASE_URL = MAL_URL

    SEARCH_ENDPOINT = MAL_SEARCH_ENDPOINT

    ENTITY_ENDPOINT = MAL_ANIME_ENDPOINT
    ENTITY_PK_NAME = "mal_aid"
    ENTITY_NAME_KEYS = ("name_en",)

    MIN_RATIO = 0.9
    CONTAIN_WEIGHT = 0.5
    CONTAIN_WEIGHT_REVERSED = 0.5

    def _generate_search_results(self, response):
        info_list = list()

        soup = BeautifulSoup(response.content, 'lxml', from_encoding='utf-8')
        search_results = soup.find_all('a', 'hoverinfo_trigger fw-b fl-l')
        for result in search_results:
            anime_id = int(result['id'].replace('sinfo', ''))
            anime_name = result.strong.get_text()
            if anime_id and anime_name:
                info_list.append(
                    {
                        self.ENTITY_PK_NAME: anime_id,
                        self.ENTITY_NAME_KEYS[0]: anime_name
                    }
                )
        return info_list

    def _generate_entity_info(self, response):
        info_dict = dict()
        soup = BeautifulSoup(response.content, 'lxml', from_encoding='utf-8')
        title_tag = soup.find("span", text='Japanese:')
        if title_tag:
            original_name = title_tag.parent.get_text(strip=True).replace("Japanese:", "")
            if original_name:
                info_dict.update(
                    {
                        "name_ja": original_name
                    }
                )
        return info_dict


class BangumiCopyrightInfoService(RetrieveEntityFromRemoteMixin,
                                  InfoServiceBase):
    """
        :return: keys:(bgm_sid, name_ja, name_zh, description)
    """
    NAME = "Bangumi"
    BASE_URL = BANGUMI_API_URL

    SEARCH_ENDPOINT = BANGUMI_SEARCH_ENDPOINT

    ENTITY_ENDPOINT = BANGUMI_SUBJECT_ENDPOINT
    ENTITY_PK_NAME = "bgm_sid"
    ENTITY_NAME_KEYS = ("name_ja", "name_zh")

    SEARCH_MAX_NUMBER = 20

    MIN_RATIO = 0.95
    CONTAIN_WEIGHT = 0.07
    CONTAIN_WEIGHT_REVERSED = 0.3

    def _get_search_requests_params(self, name):
        return "{}{}".format(self.search_url, parse.quote_plus(name)), {'params':
                                                                            {'type': 2,
                                                                             'max_results': self.SEARCH_MAX_NUMBER}}

    def _get_search_response(self, name):
        url, params = self._get_search_requests_params(name)
        try:
            return self._get(url, **params).json()['list']
        except KeyError:
            logger.warning("Name[{}] got incorrect result from bangumi.".format(name))
            return list()

    def _generate_search_results(self, response):
        info_list = list()
        for subject in response:
            bgm_sid = subject["id"]
            name = subject["name"].strip()
            name_zh = subject["name_cn"].strip()
            if bgm_sid and name:
                info_dict = {
                    self.ENTITY_PK_NAME: bgm_sid,
                    self.ENTITY_NAME_KEYS[0]: name
                }
                if name_zh:
                    info_dict.update(
                        {
                            self.ENTITY_NAME_KEYS[1]: name_zh
                        }
                    )
                info_list.append(info_dict)
        return info_list

    def _generate_entity_info(self, response):
        info_dict = dict()
        subject = response.json()
        description = subject["summary"].strip()
        if description:
            info_dict = {
                "description": description
            }
        return info_dict

    def get_info(self, *names):
        # remove katakana between brackets
        pattern = regex.compile(r'[\(\[〈]([^\p{isHan}]?)*\p{IsKatakana}([^\p{isHan}]?)*[\)\]〉]$')
        names = map(lambda x: pattern.sub('', x).strip(), names)
        return super(BangumiCopyrightInfoService, self).get_info(*names)


class GoogleKGSInfoService(InfoServiceBase):
    """
        :return: keys:(kgs_url, name_{language_code}, description, wiki_{language_code})
    """
    NAME = "Google KGS"
    BASE_URL = GOOGLE_KGS_URL
    SEARCH_ENDPOINT = GOOGLE_KGS_SEARCH_ENDPOINT
    SEARCH_MAX_NUMBER = 5

    ENTITY_PK_NAME = "kgs_url"

    MIN_RATIO = 0.93
    CONTAIN_WEIGHT = 0.07
    CONTAIN_WEIGHT_REVERSED = 0.3

    SEARCH_TYPE = None
    EXCLUDE_TYPES = []
    TYPE_FILTERS = []
    DESCRIPTION_FILTER = []

    def __init__(self):
        super().__init__()
        assert self.SEARCH_TYPE not in self.EXCLUDE_TYPES
        assert not any(x in self.EXCLUDE_TYPES for x in self.TYPE_FILTERS)
        self._language_codes = ("zh", "ja", "en")

    def _get_names_from_info_dict(self, info_dict):
        return [value for key, value in info_dict.items() if key[:4] == "name"]

    def _get_search_requests_params(self, name):
        return self.search_url, dict(params={
            "key": settings.GOOGLE_KGRAPH_API_KEY,
            "query": name,
            "languages": ",".join(self._language_codes),
            "limit": self.SEARCH_MAX_NUMBER
        })

    @staticmethod
    def _retrieve_info_from_item(items, value_keys, language_key, language, raw_language):
        for i in range(len(items)):
            item = items.pop(0)
            if language == item.get(language_key, None):
                values = dict()

                for value_key in value_keys:
                    value = item.get(value_key, None)
                    if value:
                        values[value_key] = value

                if values:
                    return (raw_language, values.popitem()[1] if len(value_keys) == 1 else values)
            items.append(item)
        return None

    def _retrieve_info(self, items, value_keys, language_key, languages):
        """
        return info by the order of languages
        """
        info = list()
        if len(languages) <= 1:
            return [(languages[0], items)]

        for raw_language in languages:
            language_list = [raw_language]
            if raw_language == 'zh':
                language_list += ['zh-TW', 'zh-HK']
            for language in language_list:
                item = self._retrieve_info_from_item(items, value_keys, language_key, language, raw_language)
                if item:
                    info.append(item)
                    break

        return info

    def _generate_search_results(self, response):
        info_list = list()
        for item in response.json()['itemListElement']:
            item_info = dict()

            result = item['result']
            kgs_id = result['@id']
            item_info['kgs_url'] = "{}{}".format(GOOGLE_KGS_ENTITY_URI, kgs_id[4:])
            if item['resultScore'] < 20:
                logger.debug("KGS[{}] resultScore is too low. Abandoned.".format(kgs_id))
                continue

            if any(x in self.EXCLUDE_TYPES for x in result['@type']):
                logger.debug("KGS[{}]'s search result got incorrect type. Abandoned.".format(kgs_id))
                continue

            if self.TYPE_FILTERS and not any(x in self.TYPE_FILTERS for x in result['@type']):
                logger.debug("KGS[{}] got filtered"
                             " by TYPES[{}]. Abandoned.".format(kgs_id,
                                                                self.TYPE_FILTERS))
                continue

            description_info = self._retrieve_info(result.get('description', list()),
                                                   ['@value'],
                                                   '@language',
                                                   self._language_codes)
            summary = ",".join([y[1] for y in description_info])
            if self.DESCRIPTION_FILTER and not any(x in summary for x in self.DESCRIPTION_FILTER):
                logger.debug("KGS[{}]'s search result got filtered"
                             " by DESCRIPTIONS[{}]. Abandoned.".format(kgs_id,
                                                                       self.DESCRIPTION_FILTER))
                continue
            item_info.update(dict(description=description_info[0][1]))

            name_info = self._retrieve_info(result.get('name', list()),
                                            ['@value'],
                                            '@language',
                                            self._language_codes)
            name_info = {"name_{}".format(x[0]): x[1] for x in name_info}
            item_info.update(name_info)

            wiki_info = self._retrieve_info(result.get('detailedDescription', list()),
                                            ['articleBody', 'url'],
                                            'inLanguage',
                                            self._language_codes)
            if wiki_info:
                item_info.update({'description': wiki_info[0][1].get("articleBody", None)})
                item_info.update(
                    {"wiki_{}".format(x[0]): x[1].get('url', None) for x in wiki_info}
                )

            info_list.append(item_info)
        return info_list

    def get_info(self, *names, language_codes=("zh", "ja", "en")):
        self._language_codes = language_codes
        return super(GoogleKGSInfoService, self).get_info(*names)


class GoogleKGSArtistInfoService(GoogleKGSInfoService):
    SEARCH_TYPE = 'Person'
    EXCLUDE_TYPES = ['City', 'Event', 'Organization', 'Place']
    DESCRIPTION_FILTER = ['动画师', '動畫師', 'アニメーター', 'Animator']


class GoogleKGSCopyrightInfoService(GoogleKGSInfoService):
    SEARCH_TYPE = 'Thing'
    EXCLUDE_TYPES = ['Person', 'City', 'Event', 'Organization', 'Place']


class AtwikiInfoService(InfoServiceBase):
    """
    :return: keys:(atwiki_id, sakuga_wiki_id, anime_wiki_id, name_ja)
    """
    NAME = "AtWiki"
    BASE_URL = ATWIKI_SEARCH_URI

    MIN_RATIO = 2

    PATTERNS = {
        'sakuga_wiki_id': SAKUGAWIKI_URL_PATTERN,
        'anime_wiki_id': ANIMEWIKI_URL_PATTERN
    }

    @retry(stop_max_attempt_number=3,
           wait_fixed=1000,
           retry_on_exception=retry_if_network_error_or_parse_error)
    def _get_search_results(self, name):
        response = self._get_search_response(name)
        logger.info('Name[{}] got search response from {}.'.format(name, self.NAME))
        info_dict = dict()
        for info in self._generate_search_results(response):
            if info['name_ja'] == name:
                info_dict.update(info)
        info_dict.pop("name_ja", None)
        return [info_dict]

    def _get_search_requests_params(self, name):
        return '{}{}'.format(self.search_url, parse.quote(name)), dict()

    def _generate_search_results(self, response):
        soup = BeautifulSoup(response.content, 'lxml')
        for result in soup.find_all('a', 'atwiki_search_title'):
            link = result['href']
            result_name = result.get_text().split('-')[-1].strip()
            for code, pattern in self.PATTERNS.items():
                ids = regex.compile(pattern).findall(link)
                if len(ids) == 1:
                    yield {
                        code: ids[0],
                        'name_ja': result_name
                    }

    def _get_most_likely_item(self, items, *original_names):
        for item in items:
            return item
        return dict()


class ASDBCopyrightInfoService(InfoServiceBase):
    """
        :return: keys:(anime_staff_database_link, name_ja)
    """
    NAME = "Anime Staff Database"
    BASE_URL = ASDB_SEARCH_URI

    ENTITY_PK_NAME = "anime_staff_database_link"
    ENTITY_NAME_KEYS = ("name_ja",)

    def _get_search_requests_params(self, name):
        return '{}{}'.format(self.BASE_URL, parse.quote(name, encoding='EUC-JP')), dict()

    def _generate_search_results(self, response):
        info_list = list()
        soup = BeautifulSoup(response.content, 'lxml', from_encoding='EUC-JP')
        for result in soup.find_all('h3', 'keyword'):
            link = result.a['href']
            result_name = result.a.get_text().strip()
            info_list.append(
                {
                    self.ENTITY_PK_NAME: link,
                    self.ENTITY_NAME_KEYS[0]: result_name
                }
            )
        return info_list
