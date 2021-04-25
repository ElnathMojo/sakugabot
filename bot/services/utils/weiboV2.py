import hashlib
import json
import logging
import os
import re
import uuid
from base64 import b64decode
from base64 import b64encode
from datetime import datetime
from typing import Dict
from urllib.parse import urljoin

import pytz
import requests
from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA
from bs4 import BeautifulSoup
from requests.cookies import create_cookie, RequestsCookieJar
from retrying import retry

from bot.services.utils.tools import unix_time_seconds

logger = logging.getLogger('bot.services.utils.WeiboClientV2')


def log_response_error(operation: str, response: requests.Response):
    logger.error(f'{operation} failed, code: {response.text}, body: {response.text}')


PIN = "g4c8CKKdwh3LE1mRX7uxyx7AafXUkJsh"
PUBLIC_KEY = "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDHHM0Fi2Z6+QYKXqFUX2Cy6AaWq3cPi" \
             "+GSn9oeAwQbPZR75JB7Netm0HtBVVbtPhzT7UO2p1JhFUKWqrqoYuAjkgMVPmA0sFrQohns5EE44Y86XQopD4ZO" \
             "+dE5KjUZFE6vrPO3rWW3np2BqlgKpjnYZri6TJApmIpGcQg9/G/3zQIDAQAB "
LOGIN_KEY = "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC46y69c1rmEk6btBLCPgxJkCxdDcAH9k7kBLffgG1KWqUErjdv" \
            "+aMkEZmBaprEW846YEwBn60gyBih3KU518fL3F+sv2b6xEeOxgjWO+NPgSWmT3q1up95HmmLHlgVwqTKqRUHd8+Tr43D5h" \
            "+J8T69etX0YNdT5ACvm+Ar0HdarwIDAQAB "
FROM = "2599295010"
C = "weibofastios"
UA = "Google_6.0_weibolite_4550"
I = "1234567"
APPKEY = "7501641714"
SOURCE = "902784192"
WM = "2468_90035"
STATUS = "wifi"

WEIBO_API_BASE = "https://api.weibo.cn"
WEIBO_API_VERSION = 2
GUEST_LOGIN = f"{WEIBO_API_BASE}/{WEIBO_API_VERSION}/guest/login"
LOGIN = f"{WEIBO_API_BASE}/{WEIBO_API_VERSION}/account/login"
MULTI_DISCOVERY = f"{WEIBO_API_BASE}/{WEIBO_API_VERSION}/multimedia/multidiscovery"
STATUSES_SEND = f"{WEIBO_API_BASE}/{WEIBO_API_VERSION}/statuses/send"


def rsa_encrypt(s, public_key):
    key = b64decode(public_key)
    key = RSA.importKey(key)

    cipher = PKCS1_v1_5.new(key)
    ciphertext = b64encode(cipher.encrypt(bytes(s, "utf-8"))).decode('utf-8')
    return ciphertext


def convert_byte_to_int(b):
    if b - 48 <= 9:
        return b - 48
    if b - 65 > 5:
        return b - 87
    return b - 55


def calculate_s(content, g_from=FROM, g_pin=PIN):
    key1 = g_pin + content + g_from
    key2 = g_from
    key1_s = hashlib.sha512(key1.encode('utf-8')).hexdigest()
    key2_s = hashlib.sha512(key2.encode('utf-8')).hexdigest()
    ret = ""
    j = 0
    for _ in range(8):
        k = convert_byte_to_int(ord(key2_s[j]))
        j += k
        ret += key1_s[j]
    return ret


class CookieExpiredException(Exception):
    pass


def generate_cookiejar(cookies):
    jar = RequestsCookieJar()
    for domain, content in cookies.items():
        for line in content.split("\n"):
            name, value = None, None
            kwargs = {}
            for i, record in enumerate(line.split(";")):
                columns = record.split("=")
                if len(columns) == 2:
                    key = columns[0].strip()
                    value_ = columns[1].strip()
                    if i == 0:
                        name = key
                        value = value_
                        continue
                    if key == "expires":
                        try:
                            dt = datetime.strptime(value_, "%A, %d-%b-%Y %H:%M:%S GMT").replace(tzinfo=pytz.UTC)
                            expire = unix_time_seconds(dt)
                        except ValueError:
                            try:
                                dt = datetime.strptime(value_, "%a, %d-%b-%Y %H:%M:%S GMT").replace(tzinfo=pytz.UTC)
                                expire = unix_time_seconds(dt)
                            except ValueError:
                                logger.warniing("Can't parse datetime [{}]".format(value_))
                                expire = unix_time_seconds() + 100
                        kwargs[key] = expire
                        continue
                    kwargs[key] = value_
                    continue
                if len(columns) == 1:
                    value_ = columns[0].strip()
                    kwargs["secure"] = value_ == "secure"
            jar.set_cookie(create_cookie(name, value, **kwargs))
    return jar


class WeiboAuthClient(object):
    def __init__(self, aid=None):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'okhttp/3.12.1',
            'X-Sessionid': str(uuid.uuid4()),
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        })
        self.uid = self.gsid = None
        self.aid = aid
        if not self.aid:
            self.aid = self.get_aid()

    def get_aid(self):
        did = self.gen_did()
        uid = ""
        data = {
            "i": I,
            "uid": uid,
            "appkey": APPKEY,
            "mfp": self.gen_mfp(),
            "checktoken": self.gen_checktoken(uid, did),
            "did": did
        }
        r = self.session.post(GUEST_LOGIN, data=data)
        logger.debug(f'Guest Login Response: {r.text}')
        r.raise_for_status()
        r = r.json()
        self.uid = r["uid"]
        self.gsid = r["gsid"]
        return r["aid"]

    def gen_mfp(self):
        return "01" + rsa_encrypt("{}", PUBLIC_KEY)

    @staticmethod
    def gen_did():
        # seems working
        return "0f60a92b9e13c65db7cd3c9f887254fc"

    @staticmethod
    def gen_checktoken(uid, did):
        return hashlib.md5(f"{uid}/{did}/obiew".encode("utf-8")).hexdigest()

    @staticmethod
    def verify(url):
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Google Build/MRA58K; wv) AppleWebKit/537.36 (KHTML, "
                          "like Gecko) Version/4.0 Chrome/44.0.2403.119 Mobile Safari/537.36Google_6.0_weibolite_4550",
            "Accept-Language": "en-US",
            "X-Requested-With": "com.sina.weibolite"
        })
        res = session.get(url)
        logger.debug(f"Verify Response: {res.url}\n{res.headers}\n{res.text}")

        session.headers.update({
            "Referer": res.url
        })

        send_url = urljoin(res.url, re.search(r'ajaxUrl: "(.*)",', res.text).group(1))
        phone_list = json.loads(re.search(r'phoneList: JSON.parse\(\'(.*)\'\),', res.text).group(1))
        mask_mobile = phone_list[0]["maskMobile"]
        number = phone_list[0]["number"]

        res = session.get(send_url, params={
            "number": number,
            "mask_mobile": mask_mobile,
            "msg_type": "sms"
        })

        logger.debug(f"Send Response: {res.status_code}\n{res.url}\n{res.headers}\n{res.text}")

        check_url = urljoin(res.url, res.json()["data"]["url"])

        res = session.get(check_url)
        logger.debug(f"Check Response: {res.status_code}\n{res.url}\n{res.headers}\n{res.text}")

        return {"url": urljoin(res.url, re.search(r'verifyCodeLogin: {\s*ajaxUrl: "(.*)",', res.text).group(1)),
                "referer": res.url,
                "cookies": session.cookies.get_dict()}

    def check(self, code, info):
        res = requests.get(info["url"],
                           params={"msg_type": "sms",
                                   "code": code},
                           headers={
                               "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Google Build/MRA58K; wv) "
                                             "AppleWebKit/537.36 (KHTML, "
                                             "like Gecko) Version/4.0 Chrome/44.0.2403.119 Mobile "
                                             "Safari/537.36Google_6.0_weibolite_4550",
                               "Accept-Language": "en-US",
                               "X-Requested-With": "com.sina.weibolite",
                               "Referer": info["referer"]
                           }, cookies=info["cookies"])

        logger.debug(f"Code Response: {res.status_code}\n{res.url}\n{res.headers}\n{res.text}")
        try:
            return self.login_with_alt(res.json()["data"]["alt"])
        except KeyError:
            return -1, res.json()

    def _login(self, params):
        data = {
            "i": I,
            "c": C,
            "s": "",
            "getuser": 1,
            "getauth": 1,
            "getcookie": 1,
            "lang": "en_US",
            "aid": self.aid,
            "from": FROM
        }
        data.update(params)
        r = self.session.post(LOGIN, data=data)
        logger.debug(f'Login Response: {r.status_code}\n{r.url}\n{r.headers}\n{r.text}')
        r.raise_for_status()
        r = r.json()
        gsid = r.get("gsid", None)
        if gsid:
            return 0, r
        errurl = r.get("errurl", None)
        if errurl:
            try:
                return 1, self.verify(errurl)
            except Exception as e:
                return -1, str(e)
        return -1, f"{r.get('errno', '')}: {r.get('errmsg', '')}"

    def login_with_password(self, account, password):
        return self._login({
            "s": calculate_s(f"{account}{password}".strip()),
            "p": rsa_encrypt(password, LOGIN_KEY),
            "u": account
        })

    def login_with_encrypt_password(self, account, password, s):
        return self._login({
            "s": s,
            "p": password,
            "u": account
        })

    def login_with_gsid(self, uid, gsid):
        return self._login({
            "s": calculate_s(uid),
            "uid": uid,
            "gsid": gsid,
            "ua": UA
        })

    def login_with_alt(self, alt):
        return self._login({
            "alt": alt,
            "gsid": "",
            "ua": UA
        })

    def scan(self, url, raw_cookies):
        cookies = generate_cookiejar(raw_cookies)
        now = unix_time_seconds()
        for cookie in cookies:
            if cookie.domain in url and cookie.expires <= now:
                raise CookieExpiredException()
        print(url)
        response = self.session.get(url, cookies=cookies)
        logger.debug(f"Scan Response: {response.status_code}\n{response.url}\n{response.headers}\n{response.text}")

        soup = BeautifulSoup(response.content, "html.parser")
        data = {}
        for node in soup.find_all("input", attrs={"type": "hidden"}):
            data[node["id"]] = node["value"]

        confirm = urljoin(url, "/signin/qrcode/confirm")
        response = self.session.post(confirm, cookies=cookies, params={"aid": self.aid}, data=data)
        logger.debug(f"Confirm Response: {response.status_code}\n{response.url}\n{response.headers}\n{response.text}")
        return response.json()


class WeiboClientV2(object):
    screen_name = ''

    def __init__(self, credentials):
        self.aid = credentials.get("aid", None)
        self.gsid = credentials.get("gsid", None)
        self.uid = credentials.get("uid", None)
        self.s = calculate_s(self.uid)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'okhttp/3.12.1',
            'X-Sessionid': str(uuid.uuid4())
        })
        self.multi_discovery = {
            "image": {
                "internal_init_url": "http://i.unistore.weibo.cn/2/statuses/upload_file?act=init",
                "bypass": "unistore.image",
                "init_url": "https://unistore.weibo.cn/2/statuses/upload_file?act=init&need_https=1",
                "internal_check_url": "http://i.unistore.weibo.cn/2/statuses/upload_file?act=check",
                "merge_url": "https://fileplatform.api.weibo.com/2/multimedia/merge.json",
                "upload_url": "https://unistore.weibo.cn/2/statuses/upload_file?act=send",
                "check_url": "https://unistore.weibo.cn/2/statuses/upload_file?act=check"
            }}

    def _parse_response(self, response):
        response.raise_for_status()
        d = response.json()
        if 'error_code' in d and 'error' in d:
            raise RuntimeError("{0} {1}".format(
                d.get("error_code", "") or d.get("errno"), d.get("error", "") or d.get("errmsg", "")))
        return d

    def _common_params(self) -> Dict[str, str]:
        return {
            'c': C,
            'from': FROM,
            'aid': self.aid,
            'gsid': self.gsid,
            'uid': self.uid,
            'ua': UA,
            'lang': 'en_US',
            'status': 'wifi',
            'wm': '2468_1001',
            'source': SOURCE,
            's': self.s
        }

    def _renew_multi_discovery(self) -> None:
        """
        更新图片上传地址，理论上说这个应该不怎么会变？
        :return:
        """
        params = {
            **self._common_params(),
            'size': '11111',
            'moduleID': 'composer'
        }
        response = self.session.get(MULTI_DISCOVERY, params=params)
        logger.debug(
            f'Multi discovery renew response: {response.status_code}\n{response.url}\n{response.headers}\n{response.text}')
        data = self._parse_response(response)
        self.multi_discovery = data

    @retry(stop_max_attempt_number=3,
           wait_fixed=1000,
           retry_on_exception=lambda x: isinstance(x, OSError) or '3022401' in str(x))
    def upload_pic(self, file) -> dict:
        """
        上传本地图片
        :param file: 文件
        :return: {"pic_id": str, "original_pic": url}
        """
        upload_url, file_token = self._upload_pic_init(file)
        return self._upload_pic_send(upload_url, file_token, file)

    def _upload_pic_init(self, file) -> (str, str):
        """
        图片上传init步骤
        :param file: 文件
        :return: (upload_url, file_token)
        """
        file.seek(0)
        file_data = file.read()
        file_md5 = hashlib.md5(file_data).hexdigest()
        params = {
            **self._common_params(),
            'length': len(file_data),
            'check': file_md5,
            'name': os.path.basename(file.name),
            'type': 'pic',
            'mediaprops':
                json.dumps({
                    "raw_md5": file_md5,
                    "createtype": "localfile",
                    "ori": "1",
                    "print_mark": "0",
                    # "watermark": {"logo": 1, "version": 1, "markpos": 1, "nick": f"@{self.screen_name}", "url": ""}
                })
        }

        response = self.session.get(self.multi_discovery['image']['init_url'], params=params)
        logger.debug(
            f'Upload init response: {response.status_code}\n{response.url}\n{response.headers}\n{response.text}')
        res_data = self._parse_response(response)
        if 'fileToken' not in res_data:
            log_response_error('Upload init', response)
            raise RuntimeError('Upload init failed')
        return res_data['upload_url'], res_data['fileToken']

    def _upload_pic_send(self, upload_url: str, file_token: str, file) -> dict:
        """
        图片上传send步骤
        :param upload_url:
        :param file_token:
        :param file:
        :return:
        """
        file.seek(0)
        file_data = file.read()
        params = {
            **self._common_params(),
            'chunksize': len(file_data),
            'filetoken': file_token,
            'i': I,
            'urltag': 0,
            'chunkindex': 0,
            'sectioncheck': hashlib.md5(file_data).hexdigest(),
            'startloc': 0,
            'chunkcount': 1
        }
        headers = {
            'Content-Type': 'application/octet-stream'
        }
        response = requests.post(upload_url, data=file_data, params=params, headers=headers)
        logger.debug(
            f'Upload send response: {response.status_code}\n{response.url}\n{response.headers}\n{response.text}')
        res_data = self._parse_response(response)
        if 'pic_id' not in res_data:
            log_response_error('Upload send', response)
            raise RuntimeError('Upload send failed')
        return res_data

    def send_weibo_with_pic(self, content: str, pic_id: str):
        """
        发送附带一张图片的微博
        :param content:
        :param pic_id:
        :return:
        """
        common_text_plain_type = 'text/plain; charset=UTF-8'
        common_json_type = 'application/json; charset=UTF-8'
        multi_part = {
            's': (None, self.s, common_text_plain_type),
            'source': (None, SOURCE, common_text_plain_type),
            'gsid': (None, self.gsid, common_text_plain_type),
            'wm': (None, WM, common_text_plain_type),
            # 'visible': (None, '1', common_json_type),
            'from': (None, FROM, common_text_plain_type),
            'content': (None, content, common_text_plain_type),
            'c': (None, C, common_text_plain_type),
            'lang': (None, 'en_US', common_text_plain_type),
            'ua': (None, UA, common_text_plain_type),
            'media': (None,
                      json.dumps(
                          [{"fid": pic_id,
                            "bypass": self.multi_discovery["image"]["bypass"],
                            "type": "pic",
                            "picStatus": 0,
                            "createtype": "localfile"}]
                      ),
                      common_text_plain_type),
            'aid': (None, self.aid, common_text_plain_type),
        }

        payload = {
            **self._common_params(),
            # 'visible': '1'
        }
        payload.pop("status")

        response = requests.post(STATUSES_SEND, files=multi_part, params=payload)
        logger.debug(
            f'Weibo send response: {response.status_code}\n{response.url}\n{response.headers}\n{response.text}')
        res_json = self._parse_response(response)
        if any(
                [res_json.get("idstr", None) is None, res_json.get("original_pic", None) is None]
        ):
            raise RuntimeError("{0} {1}".format(
                res_json.get("error_code", ""), res_json.get("error", "")))
        return response.json()

    def share(self, content, pic):
        try:
            self._renew_multi_discovery()
        except Exception as ignore:
            logger.error("Renew Multi Discovery Failed: " + str(ignore), exc_info=True, stack_info=True)
        res = self.upload_pic(pic)
        return self.send_weibo_with_pic(content, res["pic_id"])
