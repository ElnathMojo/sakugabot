# import logging
# from urllib import parse
#
# import regex as re
# from bs4 import BeautifulSoup
# from django.conf import settings
#
# from bot.constants import ANN_URL, ANN_SEARCH_ENDPOINT, ANN_PEOPLE_ENDPOINT, MAL_URL, MAL_SEARCH_ENDPOINT, \
#     MAL_ANIME_ENDPOINT, BANGUMI_API_URL, BANGUMI_SEARCH_ENDPOINT, \
#     GOOGLE_KGS_URL, GOOGLE_KGS_SEARCH_ENDPOINT, GOOGLE_KGS_ENTITY_URI
# from bot.services.info_service import InfoServiceBase
# from bot.services.ultils.decorators import default_if_exception
#
# logger = logging.getLogger("bot.services.translation")
#
#
# class ANNArtistTranslationService(InfoServiceBase):
#     NAME = "ANN"
#     BASE_URL = ANN_URL
#     SEARCH_ENDPOINT = ANN_SEARCH_ENDPOINT
#     ENTITY_ENDPOINT = ANN_PEOPLE_ENDPOINT
#     PATTERN = r"/encyclopedia/people.php\?id="
#
#     def get_search_results(self, name_en, **kwargs):
#         """
#         :param name_en:
#         :return: [(person_id, person_name, job), ...]
#         """
#         r = self._get(self.BASE_URL + self.SEARCH_ENDPOINT,
#                       params={'only': 'person',
#                               'q': name_en})
#         soup = BeautifulSoup(r.content, 'lxml')
#         search_results = soup.find_all('a', href=re.compile(self.PATTERN))
#
#         results = list()
#         for result in search_results:
#             try:
#                 job = result.i.get_text().strip()
#                 result.i.clear()
#             except:
#                 job = ""
#             person_id = int(re.findall(r"\d+", result.get('href'))[0])
#             person_name = result.get_text().strip()
#             results.append(tuple([person_id, person_name, job]))
#         return results
#
#     def _get_probably_result(self, original_name, items, **kwargs):
#         max_ratio = 0
#         target_item = (None, None)
#         for person_id, person_name, job in items[:10]:
#             ratio = self._get_diff_ratio(original_name, person_name)
#             if "animator" in "".join(job.lower().split()):
#                 ratio += 0.03
#             logger.debug("original: {}, search_result: {}, ann_id: {}, ratio: {}".format(
#                 original_name, person_name, person_id, ratio
#             ))
#             if ratio < 1:
#                 continue
#             if ratio > max_ratio:
#                 max_ratio = ratio
#                 target_item = (person_id, person_name)
#         if 0 < max_ratio < 2:
#             logger.warning("Inexact match for name[{}]."
#                            " Ratio: {} ANN-Person-ID: {} Name: {}".format(original_name,
#                                                                           max_ratio,
#                                                                           target_item[0],
#                                                                           target_item[1]))
#         return target_item
#
#     @default_if_exception(default=None, logger=logger, msg="Something went wrong while getting ann person name.")
#     def get_entity_name(self, id):
#         r = self._get(self.BASE_URL + self.ENTITY_ENDPOINT,
#                       params={'id': id})
#         soup = BeautifulSoup(r.content, 'lxml')
#         title_block = soup.find(id="page-title")
#         title_block.h1.clear()
#         original_name = title_block.get_text(strip=True)
#         pattern = re.compile(r".*[\da-zA-Z]+.*")
#         if not re.match(pattern, original_name):  # remove space between ja_name
#             if original_name.count(' ') == 1:
#                 original_name = original_name.replace(' ', '')
#         if original_name:
#             return original_name
#         return None
#
#     def translate(self, name_en):
#         try:
#             res = self.get_search_results(name_en)
#             logger.info("Name[{}] got {} search results from ANN.".format(name_en, len(res)))
#             person_id, person_name = self._get_probably_result(name_en, res)
#             if not person_id:
#                 logger.info("Name[{}] got no match result in ANN search results.".format(name_en))
#                 return dict()
#             return {"ann_pid": person_id,
#                     "name_en": person_name,
#                     "name_ja": self.get_entity_name(person_id)}
#         except:
#             logger.exception("ANN translation failed. name[{}]".format(name_en))
#             return dict()
#
#
# class MALAnimeTranslationService(InfoServiceBase):
#     NAME = "MyAnimeList"
#     BASE_URL = MAL_URL
#     SEARCH_ENDPOINT = MAL_SEARCH_ENDPOINT
#     ENTITY_ENDPOINT = MAL_ANIME_ENDPOINT
#
#     def get_search_results(self, name_en):
#         r = self._get(self.BASE_URL + self.SEARCH_ENDPOINT,
#                       params={'q': name_en})
#         soup = BeautifulSoup(r.content, 'lxml', from_encoding='utf-8')
#         search_results = soup.find_all('a', 'hoverinfo_trigger fw-b fl-l')
#
#         results = list()
#         for result in search_results:
#             anime_id = int(result['id'].replace('sinfo', ''))
#             anime_name = result.strong.get_text()
#             results.append(tuple([anime_id, anime_name]))
#         return results
#
#     def _get_probably_result(self, original_name, res):
#         max_ratio = 0
#         result = (None, None)
#         for anime_id, anime_name in res[:10]:
#             ratio = self._get_diff_ratio(original_name, anime_name, contain_weight=0.5)
#             logger.debug("original: {}, search_result: {}, mal_id: {}, ratio: {}".format(
#                 original_name, anime_name, anime_id, ratio
#             ))
#             if ratio < 0.9:
#                 continue
#             if ratio > max_ratio:
#                 max_ratio = ratio
#                 result = (anime_id, anime_name)
#         if 0 < max_ratio < 2:
#             logger.warning("Inexact match for name[{}]."
#                            " Ratio: {} MAL-Anime-ID: {} Name: {}".format(original_name,
#                                                                          max_ratio,
#                                                                          result[0],
#                                                                          result[1]))
#         return result
#
#     @default_if_exception(default=None, logger=logger, msg="Something went wrong while getting mal anime name.")
#     def get_entity_name(self, id):
#         r = self._get("{}{}".format(self.BASE_URL + self.ENTITY_ENDPOINT, id))
#         soup = BeautifulSoup(r.content, 'lxml', from_encoding='utf-8')
#         original_name = soup.find("span", text='Japanese:').parent.get_text(strip=True).replace("Japanese:", "").strip()
#         if original_name:
#             return original_name
#         return None
#
#     def translate(self, name_en, **kwargs):
#         try:
#             res = self.get_search_results(name_en)
#             logger.info("Name[{}] got {} search results from MAL.".format(name_en, len(res)))
#             anime_id, anime_name = self._get_probably_result(name_en, res)
#             if not anime_id:
#                 logger.info("Name[{}] got no match result in MAL search results.".format(name_en))
#                 return dict()
#             return {"mal_aid": anime_id,
#                     "name_en": anime_name,
#                     "name_ja": self.get_entity_name(anime_id)}
#         except:
#             logger.exception("MAL translation failed. name[{}]".format(name_en))
#             return dict()
#
#
# class BangumiAnimeTranslationService(InfoServiceBase):
#     NAME = "Bangumi"
#     BASE_URL = BANGUMI_API_URL
#     SEARCH_ENDPOINT = BANGUMI_SEARCH_ENDPOINT
#
#     def get_search_results(self, name_ja, name_en=None, **kwargs):
#         # remove katakana between brackets
#         pattern = re.compile(r'[\(\[〈]([^\p{isHan}]?)*\p{IsKatakana}([^\p{isHan}]?)*[\)\]〉]$')
#         name_ja = pattern.sub('', name_ja).strip()
#         results = list()
#         ids = set()
#         for name in (name_ja, name_en):
#             response = self._get("{}{}".format(self.BASE_URL + self.SEARCH_ENDPOINT, parse.quote_plus(name)),
#                                  params={'type': 2,
#                                          'max_results': 20}).json()
#             try:
#                 res = response["list"]
#             except KeyError:
#                 logger.warning("Name[{}] got incorrect result from bangumi.".format(name))
#                 continue
#             for r in res:
#                 if r["id"] in ids:
#                     continue
#                 ids.add(r["id"])
#                 results.append(tuple([r["id"], r["name"], r["name_cn"]]))
#
#         return results
#
#     def _get_probably_result(self, name_ja, name_en, res):
#         max_ratio = 0
#         result = (None, None, None)
#         for anime_id, anime_name, anime_name_cn in res[:10]:
#             ratio = max((self._get_diff_ratio(name_ja, anime_name, contain_weight=0.3),
#                          self._get_diff_ratio(name_en, anime_name, contain_weight=0.3)))
#             logger.debug("original_ja: {}, original_en: {}, search_result: {}, bgm_id: {}, ratio: {}".format(
#                 name_ja, name_en, anime_name, anime_id, ratio
#             ))
#             if ratio < 0.95:
#                 continue
#             if ratio > max_ratio:
#                 max_ratio = ratio
#                 result = (anime_id, anime_name_cn, anime_name)
#         if 0 < max_ratio < 2:
#             logger.warning("Inexact match for name[{}]."
#                            " Ratio: {} Bangumi-Subject-ID: {} Name: {}".format(name_ja,
#                                                                                max_ratio,
#                                                                                result[0],
#                                                                                result[1]))
#         return result
#
#     def translate(self, name_ja, name_en=None, **kwargs):
#         try:
#             res = self.get_search_results(name_ja, name_en)
#             logger.info("Name[{}] got {} search results from Bangumi.".format(name_ja, len(res)))
#             anime_id, anime_name, anime_name_ja = self._get_probably_result(name_ja, name_en, res)
#             if not anime_id:
#                 logger.info("Name[{}] got no match result in Bangumi search results.".format(name_ja))
#                 return dict()
#             return {"bgm_sid": anime_id,
#                     "name_ja": anime_name_ja,
#                     "name_zh": anime_name}
#         except:
#             logger.exception("Bangumi translation failed. name[{}]".format(name_ja))
#             return dict()
#
#
# class GoogleTranslateService(InfoServiceBase):
#     NAME = "Google"
#     BASE_URL = GOOGLE_KGS_URL
#     ENTITY_ENDPOINT = GOOGLE_KGS_SEARCH_ENDPOINT
#     SEARCH_TYPE = None
#     EXCLUDE_TYPES = []
#     TYPE_FILTERS = []
#     DESCRIPTION_FILTER = []
#
#     def __init__(self):
#         super().__init__()
#         assert self.SEARCH_TYPE not in self.EXCLUDE_TYPES
#         assert not any(x in self.EXCLUDE_TYPES for x in self.TYPE_FILTERS)
#
#     @staticmethod
#     def _retrieve_info_from_item(items, value_keys, language_key, language, raw_language):
#         for i in range(len(items)):
#             item = items.pop(0)
#             if language == item.get(language_key, None):
#                 values = dict()
#
#                 for value_key in value_keys:
#                     value = item.get(value_key, None)
#                     if value:
#                         values[value_key] = value
#
#                 if values:
#                     return (raw_language, values.popitem()[1] if len(value_keys) == 1 else values)
#             items.append(item)
#         return None
#
#     def _retrieve_info(self, items, value_keys, language_key, languages):
#         """
#         return info by the order of languages
#         """
#         info = list()
#         if len(languages) <= 1:
#             return [(languages[0], items)]
#
#         for raw_language in languages:
#             language_list = [raw_language]
#             if raw_language == 'zh':
#                 language_list += ['zh-TW', 'zh-HK']
#             for language in language_list:
#                 item = self._retrieve_info_from_item(items, value_keys, language_key, language, raw_language)
#                 if item:
#                     info.append(item)
#                     break
#
#         return info
#
#     def get_search_results(self, name, language_codes=("zh", "en", "ja"), limit=10):
#         """
#
#         :param name: str
#         :param language_codes: list of str, only support zh, en and ja
#         :param kwargs:
#         :return: a list of dict or an empty list if failed.
#         """
#         results = list()
#         try:
#             response = self._get(self.BASE_URL + self.ENTITY_ENDPOINT,
#                                  params={
#                                      "key": settings.GOOGLE_KGRAPH_API_KEY,
#                                      "query": name,
#                                      "languages": ",".join(language_codes),
#                                      "limit": limit
#                                  }).json()
#
#             for item in response['itemListElement']:
#                 item_info = dict()
#
#                 result = item['result']
#                 kgs_id = result['@id']
#                 item_info['kgs_url'] = "{}{}".format(GOOGLE_KGS_ENTITY_URI, kgs_id[4:])
#                 if response['itemListElement'][0]['resultScore'] < 20:
#                     logger.debug("KGS[{}] resultScore is too low. Abandoned.".format(kgs_id))
#                     continue
#
#                 if any(x in self.EXCLUDE_TYPES for x in result['@type']):
#                     logger.debug("KGS[{}]'s search result got incorrect type. Abandoned.".format(kgs_id))
#                     continue
#
#                 if self.TYPE_FILTERS and not any(x in self.TYPE_FILTERS for x in result['@type']):
#                     logger.debug("KGS[{}]'s search result got filtered"
#                                  " by TYPES[{}]. Abandoned.".format(kgs_id,
#                                                                     self.TYPE_FILTERS))
#                     continue
#
#                 description_info = self._retrieve_info(result.get('description', list()),
#                                                        ['@value'],
#                                                        '@language',
#                                                        language_codes)
#                 des = ",".join([y[1] for y in description_info])
#                 a = [x in des for x in self.DESCRIPTION_FILTER]
#                 if self.DESCRIPTION_FILTER and not any(a):
#                     logger.debug("KGS[{}]'s search result got filtered"
#                                  " by DESCRIPTIONS[{}]. Abandoned.".format(kgs_id,
#                                                                            self.DESCRIPTION_FILTER))
#                     continue
#                 item_info.update(dict(description=description_info[0][1]))
#
#                 name_info = self._retrieve_info(result.get('name', list()),
#                                                 ['@value'],
#                                                 '@language',
#                                                 language_codes)
#                 name_info = {"name_{}".format(x[0]): x[1] for x in name_info}
#                 item_info.update(name_info)
#
#                 wiki_info = self._retrieve_info(result.get('detailedDescription', list()),
#                                                 ['articleBody', 'url'],
#                                                 'inLanguage',
#                                                 language_codes)
#                 if wiki_info:
#                     item_info.update({'description': wiki_info[0][1].get("articleBody", None)})
#                     item_info.update(
#                         {"wiki_{}".format(x[0]): x[1].get('url', None) for x in wiki_info}
#                     )
#
#                 results.append(item_info)
#
#             return results
#         except:
#             logger.exception("Something went wrong while getting google search results. Search Name[{}]".format(name))
#             return results
#
#     def _get_probably_result(self, name, res, **kwargs):
#         max_ratio = 0
#         result = dict()
#         for r in res[:10]:
#             names = [x[1] for x in r.items() if x[0][:4] == "name"]
#             ratio = max(self._get_diff_ratio(name, x, contain_weight=0.3) for x in names)
#             logger.debug("original_name: {}, names: {}, kgs_url: {}, ratio: {}".format(
#                 name, names, r.get("kgs_url", None), ratio
#             ))
#             if ratio < 0.93:
#                 continue
#             if ratio > max_ratio:
#                 max_ratio = ratio
#                 result = r
#         if 0 < max_ratio < 2:
#             logger.warning("Inexact match for name[{}]."
#                            " Ratio: {} KGS_URL: {} Name: {}".format(name,
#                                                                     max_ratio,
#                                                                     result[0],
#                                                                     result[1]))
#         return result
#
#     def translate(self, name, language_codes=("zh", "ja", "en"), **kwargs):
#         try:
#             results = self.get_search_results(name, language_codes=("zh", "ja", "en"))
#             return self._get_probably_result(name, results)
#         except:
#             logger.exception("Google translation failed. name[{}]".format(name))
#             return dict()
#
#
# class GoogleArtistTranslateService(GoogleTranslateService):
#     SEARCH_TYPE = 'Person'
#     EXCLUDE_TYPES = ['City', 'Event', 'Organization', 'Place']
#     DESCRIPTION_FILTER = ['动画师', '動畫師', 'アニメーター', 'Animator']
#
#
# class GoogleAnimeTranslateService(GoogleTranslateService):
#     SEARCH_TYPE = 'Thing'
#     EXCLUDE_TYPES = ['Person', 'City', 'Event', 'Organization', 'Place']
