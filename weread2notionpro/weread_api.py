import hashlib
import os
import re

import requests
from dotenv import load_dotenv
from requests.utils import cookiejar_from_dict
from retrying import retry

load_dotenv()
WEREAD_URL = "https://weread.qq.com/"
WEREAD_NOTEBOOKS_URL = "https://weread.qq.com/api/user/notebook"
WEREAD_BOOKMARKLIST_URL = "https://weread.qq.com/web/book/bookmarklist"
WEREAD_CHAPTER_INFO = "https://weread.qq.com/web/book/chapterInfos"
WEREAD_READ_INFO_URL = "https://weread.qq.com/web/book/getProgress"
WEREAD_REVIEW_LIST_URL = "https://weread.qq.com/web/review/list"
WEREAD_BOOK_INFO = "https://weread.qq.com/api/book/info"
WEREAD_READDATA_DETAIL = "https://i.weread.qq.com/readdata/detail"
WEREAD_HISTORY_URL = "https://i.weread.qq.com/readdata/summary?synckey=0"
WEREAD_SHELF_SYNC_URL = "https://weread.qq.com/web/shelf/sync"
WEREAD_BEST_REVIEW_URL = "https://weread.qq.com/web/review/list/best"


class WeReadApi:
    def __init__(self):
        self.cookie = self.get_cookie()
        self.session = requests.Session()
        self.session.cookies = self.parse_cookie_string()

    def try_get_cloud_cookie(self, url, id, password):
        """从CookieCloud获取微信读书Cookie"""
        if url.endswith("/"):
            url = url[:-1]
        req_url = f"{url}/get/{id}"
        data = {"password": password}

        try:
            response = requests.post(req_url, data=data, timeout=30)

            if response.status_code == 200:
                response_data = response.json()

                if response_data.get("cookie_data"):
                    cookie_data = response_data["cookie_data"]
                    domains = list(cookie_data.keys())

                    # 首先尝试 "weread.qq.com" 域名
                    if "weread.qq.com" in cookie_data:
                        return self.extract_cookies_from_domain(
                            cookie_data, "weread.qq.com"
                        )

                    # 然后尝试 "weread" 域名
                    if "weread" in cookie_data:
                        weread_cookies = cookie_data["weread"]
                        # 检查这些Cookie是否真的是weread.qq.com的Cookie
                        valid_weread_cookies = [
                            cookie
                            for cookie in weread_cookies
                            if cookie.get("domain")
                            in [".weread.qq.com", "weread.qq.com"]
                        ]

                        if valid_weread_cookies:
                            cookie_items = [
                                f"{cookie['name']}={cookie['value']}"
                                for cookie in valid_weread_cookies
                            ]
                            return "; ".join(cookie_items)
                        else:
                            print("警告：weread域名下的Cookie不属于微信读书")

                    # 最后尝试遍历所有域名，寻找包含weread.qq.com域名的Cookie
                    print("尝试从所有域名中查找微信读书Cookie")
                    for domain in domains:
                        cookies_in_domain = cookie_data[domain]
                        if isinstance(cookies_in_domain, list):
                            weread_cookies = [
                                cookie
                                for cookie in cookies_in_domain
                                if cookie.get("domain")
                                in [".weread.qq.com", "weread.qq.com"]
                            ]

                            if weread_cookies:
                                print(
                                    f"在{domain}域名下找到{len(weread_cookies)}个微信读书Cookie"
                                )
                                cookie_items = [
                                    f"{cookie['name']}={cookie['value']}"
                                    for cookie in weread_cookies
                                ]
                                return "; ".join(cookie_items)
                else:
                    print("警告：响应中没有cookie_data字段")

            print("从Cookie Cloud获取数据成功，但未找到微信读书Cookie")
        except Exception as error:
            print(f"从Cookie Cloud获取Cookie失败: {error}")
            if hasattr(error, "response") and error.response:
                print(f"响应状态: {error.response.status_code}")

        return None

    def extract_cookies_from_domain(self, cookie_data, domain):
        """从指定域名提取Cookie"""
        cookies = cookie_data.get(domain)

        if not isinstance(cookies, list) or not cookies:
            return None

        cookie_items = []
        for cookie in cookies:
            if cookie.get("name") and cookie.get("value"):
                cookie_items.append(f"{cookie['name']}={cookie['value']}")

        if not cookie_items:
            return None

        return "; ".join(cookie_items)

    def get_cookie(self):
        """获取微信读书Cookie，优先级：环境变量Cookie Cloud > 环境变量WEREAD_COOKIE"""
        cookie = None

        # 1. 尝试环境变量中的Cookie Cloud配置
        url = os.getenv("CC_URL")
        if not url:
            url = "https://cc.chenge.ink"  # 使用默认服务器
        id = os.getenv("CC_ID")
        password = os.getenv("CC_PASSWORD")

        if url and id and password:
            try:
                cookie = self.try_get_cloud_cookie(url, id, password)
                if cookie:
                    print("成功从Cookie Cloud获取微信读书Cookie")
                    return cookie
            except Exception as error:
                print(f"使用Cookie Cloud获取Cookie失败: {error}")

        # 2. 回退到环境变量中的直接Cookie
        env_cookie = os.getenv("WEREAD_COOKIE")
        if not env_cookie or not env_cookie.strip():
            raise Exception("没有找到cookie，请按照文档填写cookie或配置Cookie Cloud")

        return env_cookie

    def parse_cookie_string(self):
        cookies_dict = {}

        # 使用正则表达式解析 cookie 字符串
        pattern = re.compile(r"([^=]+)=([^;]+);?\s*")
        matches = pattern.findall(self.cookie)

        for key, value in matches:
            cookies_dict[key] = value.encode("unicode_escape").decode("ascii")
        # 直接使用 cookies_dict 创建 cookiejar
        cookiejar = cookiejar_from_dict(cookies_dict)

        return cookiejar

    def get_standard_headers(self):
        """获取标准请求头"""
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
            "Connection": "keep-alive",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "sec-ch-ua": '"Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "upgrade-insecure-requests": "1",
        }

    def visit_homepage(self):
        """访问主页以初始化会话"""
        try:
            self.session.get(
                WEREAD_URL, headers=self.get_standard_headers(), timeout=30
            )
        except Exception as error:
            print(f"访问主页失败: {error}")

    def get_bookshelf(self):
        """获取书架信息（存在笔记的书籍）"""
        self.visit_homepage()
        headers = self.get_standard_headers()
        headers["Accept"] = "application/json, text/plain, */*"

        r = self.session.get(WEREAD_NOTEBOOKS_URL, headers=headers)
        if r.ok:
            return r.json()
        else:
            errcode = r.json().get("errcode", 0)
            self.handle_errcode(errcode)
            raise Exception(f"Could not get bookshelf {r.text}")

    def get_entire_shelf(self):
        """获取所有书架书籍信息"""
        self.visit_homepage()
        headers = self.get_standard_headers()
        headers["Accept"] = "application/json, text/plain, */*"

        r = self.session.get(WEREAD_SHELF_SYNC_URL, headers=headers)
        if r.ok:
            return r.json()
        else:
            errcode = r.json().get("errcode", 0)
            self.handle_errcode(errcode)
            raise Exception(f"Could not get entire shelf {r.text}")

    def handle_errcode(self, errcode):
        if errcode == -2012 or errcode == -2010:
            print(
                "::error::微信读书Cookie过期了，请参考文档重新设置。https://mp.weixin.qq.com/s/B_mqLUZv7M1rmXRsMlBf7A"
            )

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def get_notebooklist(self):
        """获取笔记本列表"""
        self.visit_homepage()
        headers = self.get_standard_headers()
        headers["Accept"] = "application/json, text/plain, */*"

        r = self.session.get(WEREAD_NOTEBOOKS_URL, headers=headers)
        if r.ok:
            data = r.json()
            books = data.get("books", [])
            books.sort(key=lambda x: x.get("sort", 0))
            return books
        else:
            errcode = r.json().get("errcode", 0)
            self.handle_errcode(errcode)
            raise Exception(f"Could not get notebook list {r.text}")

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def get_bookinfo(self, bookId):
        """获取书的详情"""
        self.visit_homepage()
        headers = self.get_standard_headers()
        headers["Accept"] = "application/json, text/plain, */*"

        params = dict(bookId=bookId)
        r = self.session.get(WEREAD_BOOK_INFO, params=params, headers=headers)
        if r.ok:
            return r.json()
        else:
            errcode = r.json().get("errcode", 0)
            self.handle_errcode(errcode)
            print(f"Could not get book info {r.text}")

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def get_bookmark_list(self, bookId):
        """获取书籍的划线记录"""
        self.visit_homepage()
        headers = self.get_standard_headers()
        headers["Accept"] = "application/json, text/plain, */*"

        params = dict(bookId=bookId)
        r = self.session.get(WEREAD_BOOKMARKLIST_URL, params=params, headers=headers)
        if r.ok:
            data = r.json()
            bookmarks = data.get("updated", [])
            # 确保每个划线对象格式一致
            bookmarks = [
                mark
                for mark in bookmarks
                if mark.get("markText") and mark.get("chapterUid")
            ]
            return bookmarks
        else:
            errcode = r.json().get("errcode", 0)
            self.handle_errcode(errcode)
            raise Exception(f"Could not get {bookId} bookmark list")

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def get_read_info(self, bookId):
        """获取阅读进度"""
        self.visit_homepage()
        headers = self.get_standard_headers()
        headers["Accept"] = "application/json, text/plain, */*"

        params = dict(bookId=bookId)
        r = self.session.get(WEREAD_READ_INFO_URL, headers=headers, params=params)
        if r.ok:
            return r.json()
        else:
            errcode = r.json().get("errcode", 0)
            self.handle_errcode(errcode)
            raise Exception(f"get {bookId} read info failed {r.text}")

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def get_review_list(self, bookId):
        """获取笔记/想法列表"""
        self.visit_homepage()
        headers = self.get_standard_headers()
        headers["Accept"] = "application/json, text/plain, */*"

        params = dict(
            bookId=bookId, listType=4, maxIdx=0, count=0, listMode=2, syncKey=0
        )
        r = self.session.get(WEREAD_REVIEW_LIST_URL, params=params, headers=headers)
        if r.ok:
            data = r.json()
            reviews = data.get("reviews", [])
            # 转换成正确的格式
            reviews = [x.get("review") for x in reviews if x.get("review")]

            # 为书评添加chapterUid
            reviews = [
                {"chapterUid": 1000000, **x} if x.get("type") == 4 else x
                for x in reviews
            ]
            return reviews
        else:
            errcode = r.json().get("errcode", 0)
            self.handle_errcode(errcode)
            raise Exception(f"get {bookId} review list failed {r.text}")

    def get_best_reviews(self, bookId, count=10, maxIdx=0, synckey=0):
        """获取热门书评"""
        self.visit_homepage()
        headers = self.get_standard_headers()
        headers["Accept"] = "application/json, text/plain, */*"

        params = dict(bookId=bookId, synckey=synckey, maxIdx=maxIdx, count=count)
        r = self.session.get(WEREAD_BEST_REVIEW_URL, params=params, headers=headers)
        if r.ok:
            return r.json()
        else:
            errcode = r.json().get("errcode", 0)
            self.handle_errcode(errcode)
            raise Exception(f"get {bookId} best reviews failed {r.text}")

    def get_api_data(self):
        self.session.get(WEREAD_URL)
        r = self.session.get(WEREAD_HISTORY_URL)
        if r.ok:
            return r.json()
        else:
            errcode = r.json().get("errcode", 0)
            self.handle_errcode(errcode)
            raise Exception(f"get history data failed {r.text}")

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def get_chapter_info(self, bookId):
        """获取章节信息"""
        try:
            # 1. 首先访问主页，确保会话有效
            self.visit_homepage()

            # 2. 获取笔记本列表，进一步初始化会话
            self.get_notebooklist()

            # 3. 添加随机延迟，模拟真实用户行为
            import random
            import time

            delay = 1 + random.random() * 2  # 1-3秒随机延迟
            time.sleep(delay)

            # 4. 准备请求头 - 模拟浏览器行为
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
                "Content-Type": "application/json;charset=UTF-8",
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://weread.qq.com",
                "Referer": f"https://weread.qq.com/web/reader/{bookId}",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
            }

            # 5. 使用正确的请求体格式
            body = {"bookIds": [bookId]}

            # 6. 发送请求
            r = self.session.post(
                WEREAD_CHAPTER_INFO, json=body, headers=headers, timeout=60
            )

            if r.ok:
                data = r.json()

                # 7. 处理结果 - 增加多种可能的响应格式处理
                update = None

                # 格式1: {data: [{bookId: "xxx", updated: []}]}
                if (
                    data.get("data")
                    and len(data["data"]) == 1
                    and data["data"][0].get("updated")
                ):
                    update = data["data"][0]["updated"]
                # 格式2: {updated: []}
                elif data.get("updated") and isinstance(data["updated"], list):
                    update = data["updated"]
                # 格式3: [{bookId: "xxx", updated: []}]
                elif (
                    isinstance(data, list) and len(data) > 0 and data[0].get("updated")
                ):
                    update = data[0]["updated"]
                # 格式4: 数组本身就是章节列表
                elif (
                    isinstance(data, list)
                    and len(data) > 0
                    and data[0].get("chapterUid")
                ):
                    update = data

                if update:
                    # 添加点评章节
                    update.append(
                        {
                            "chapterUid": 1000000,
                            "chapterIdx": 1000000,
                            "updateTime": 1683825006,
                            "readAhead": 0,
                            "title": "点评",
                            "level": 1,
                        }
                    )

                    # 确保chapterUid始终以字符串形式作为键
                    result = {str(item["chapterUid"]): item for item in update}
                    return result
                elif data.get("errCode"):
                    self.handle_errcode(data["errCode"])
                    raise Exception(
                        f"API返回错误: {data.get('errMsg', 'Unknown error')} (code: {data['errCode']})"
                    )
                elif data.get("errcode"):
                    self.handle_errcode(data["errcode"])
                    raise Exception(
                        f"API返回错误: {data.get('errmsg', 'Unknown error')} (code: {data['errcode']})"
                    )
                else:
                    raise Exception("获取章节信息失败，返回格式不符合预期")
            else:
                raise Exception(f"get {bookId} chapter info failed {r.text}")

        except Exception as error:
            print(f"获取章节信息失败: {error}")
            if hasattr(error, "response"):
                print(f"状态码: {error.response.status_code}")
            raise error

    def transform_id(self, book_id):
        id_length = len(book_id)
        if re.match("^\\d*$", book_id):
            ary = []
            for i in range(0, id_length, 9):
                ary.append(format(int(book_id[i : min(i + 9, id_length)]), "x"))
            return "3", ary

        result = ""
        for i in range(id_length):
            result += format(ord(book_id[i]), "x")
        return "4", [result]

    def calculate_book_str_id(self, book_id):
        md5 = hashlib.md5()
        md5.update(book_id.encode("utf-8"))
        digest = md5.hexdigest()
        result = digest[0:3]
        code, transformed_ids = self.transform_id(book_id)
        result += code + "2" + digest[-2:]

        for i in range(len(transformed_ids)):
            hex_length_str = format(len(transformed_ids[i]), "x")
            if len(hex_length_str) == 1:
                hex_length_str = "0" + hex_length_str

            result += hex_length_str + transformed_ids[i]

            if i < len(transformed_ids) - 1:
                result += "g"

        if len(result) < 20:
            result += digest[0 : 20 - len(result)]

        md5 = hashlib.md5()
        md5.update(result.encode("utf-8"))
        result += md5.hexdigest()[0:3]
        return result

    def get_url(self, book_id):
        return f"https://weread.qq.com/web/reader/{self.calculate_book_str_id(book_id)}"
