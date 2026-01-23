import logging
import os
import re
import time

from notion_client import Client
import pendulum
from retrying import retry
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()
from weread2notionpro.utils  import (
    format_date,
    get_date,
    get_first_and_last_day_of_month,
    get_first_and_last_day_of_week,
    get_first_and_last_day_of_year,
    get_icon,
    get_number,
    get_relation,
    get_rich_text,
    get_title,
    timestamp_to_date,
    get_property_value,
)

TAG_ICON_URL = "https://www.notion.so/icons/tag_gray.svg"
USER_ICON_URL = "https://www.notion.so/icons/user-circle-filled_gray.svg"
TARGET_ICON_URL = "https://www.notion.so/icons/target_red.svg"
BOOKMARK_ICON_URL = "https://www.notion.so/icons/bookmark_gray.svg"


class NotionHelper:
    database_name_dict = {
        "BOOK_DATABASE_NAME": "书架",
        "REVIEW_DATABASE_NAME": "笔记",
        "BOOKMARK_DATABASE_NAME": "划线",
        "DAY_DATABASE_NAME": "日",
        "WEEK_DATABASE_NAME": "周",
        "MONTH_DATABASE_NAME": "月",
        "YEAR_DATABASE_NAME": "年",
        "CATEGORY_DATABASE_NAME": "分类",
        "AUTHOR_DATABASE_NAME": "作者",
        "CHAPTER_DATABASE_NAME": "章节",
        "READ_DATABASE_NAME": "阅读记录",
        "SETTING_DATABASE_NAME": "设置",
    }
    database_id_dict = {}
    heatmap_block_id = None
    show_color = True
    block_type = "callout"
    sync_bookmark = True
    def __init__(self):
        self.client = Client(auth=os.getenv("NOTION_TOKEN"), log_level=logging.ERROR)
        self.__cache = {}
        self.page_id = self.extract_page_id(os.getenv("NOTION_PAGE"))

        # 添加日志：开始搜索数据库
        logging.info(f"开始搜索数据库，页面ID: {self.page_id}")
        self.search_database(self.page_id)
        logging.info(f"找到 {len(self.database_id_dict)} 个数据库: {list(self.database_id_dict.keys())}")

        # 检查环境变量覆盖
        for key in self.database_name_dict.keys():
            env_value = os.getenv(key)
            if env_value:  # 简化检查，None 和空字符串都视为未设置
                old_name = self.database_name_dict[key]
                self.database_name_dict[key] = env_value
                logging.info(f"环境变量覆盖: {key} = '{env_value}' (原值: '{old_name}')")

        self.book_database_id = self.database_id_dict.get(
            self.database_name_dict.get("BOOK_DATABASE_NAME")
        )
        self.review_database_id = self.database_id_dict.get(
            self.database_name_dict.get("REVIEW_DATABASE_NAME")
        )
        self.bookmark_database_id = self.database_id_dict.get(
            self.database_name_dict.get("BOOKMARK_DATABASE_NAME")
        )
        self.day_database_id = self.database_id_dict.get(
            self.database_name_dict.get("DAY_DATABASE_NAME")
        )
        self.week_database_id = self.database_id_dict.get(
            self.database_name_dict.get("WEEK_DATABASE_NAME")
        )
        self.month_database_id = self.database_id_dict.get(
            self.database_name_dict.get("MONTH_DATABASE_NAME")
        )
        self.year_database_id = self.database_id_dict.get(
            self.database_name_dict.get("YEAR_DATABASE_NAME")
        )
        self.category_database_id = self.database_id_dict.get(
            self.database_name_dict.get("CATEGORY_DATABASE_NAME")
        )
        self.author_database_id = self.database_id_dict.get(
            self.database_name_dict.get("AUTHOR_DATABASE_NAME")
        )
        self.chapter_database_id = self.database_id_dict.get(
            self.database_name_dict.get("CHAPTER_DATABASE_NAME")
        )
        self.read_database_id = self.database_id_dict.get(
            self.database_name_dict.get("READ_DATABASE_NAME")
        )
        self.setting_database_id = self.database_id_dict.get(
            self.database_name_dict.get("SETTING_DATABASE_NAME")
        )

        # 添加日志：检查关键数据库是否找到
        logging.info(f"书架数据库 '{self.database_name_dict.get('BOOK_DATABASE_NAME')}' ID: {self.book_database_id}")

        # 解析所有数据库的同步关系（如果是同步数据库，获取源数据库 ID）
        self.resolve_synced_databases()

        self.update_book_database()
        if self.read_database_id is None:
            self.create_database()
        if self.setting_database_id is None:
            self.create_setting_database()
        if self.setting_database_id:
            self.insert_to_setting_database()

    def extract_page_id(self, notion_url):
        # 正则表达式匹配 32 个字符的 Notion page_id
        match = re.search(
            r"([a-f0-9]{32}|[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})",
            notion_url,
        )
        if match:
            return match.group(0)
        else:
            raise Exception(f"获取NotionID失败，请检查输入的Url是否正确")

    def search_database(self, block_id, depth=0, max_depth=10):
        """递归搜索数据库，添加深度限制防止无限递归"""
        if depth > max_depth:
            logging.warning(f"达到最大递归深度 {max_depth}，停止搜索")
            return

        try:
            children = self.client.blocks.children.list(block_id=block_id)["results"]
        except Exception as e:
            logging.error(f"获取 block children 失败 (depth={depth}): {str(e)}")
            return

        # 遍历子块
        for child in children:
            # 检查子块的类型
            if child["type"] == "child_database":
                self.database_id_dict[child.get("child_database").get("title")] = (
                    child.get("id")
                )
            elif child["type"] == "embed" and child.get("embed").get("url"):
                if child.get("embed").get("url").startswith("https://heatmap.malinkang.com/"):
                    self.heatmap_block_id = child.get("id")
            # 如果子块有子块，递归调用函数
            if "has_children" in child and child["has_children"]:
                self.search_database(child["id"], depth + 1, max_depth)

    def resolve_synced_databases(self):
        """解析同步数据库，将同步数据库的 ID 替换为源数据库的 ID（如果有权限）"""
        database_attrs = [
            'book_database_id', 'review_database_id', 'bookmark_database_id',
            'day_database_id', 'week_database_id', 'month_database_id', 'year_database_id',
            'category_database_id', 'author_database_id', 'chapter_database_id',
            'read_database_id', 'setting_database_id'
        ]

        for attr in database_attrs:
            db_id = getattr(self, attr, None)
            if db_id:
                try:
                    response = self.client.databases.retrieve(database_id=db_id)
                    # 检查是否是同步数据库
                    if response.get("data_sources") and len(response.get("data_sources", [])) > 0:
                        source_db_id = response["data_sources"][0]["id"]
                        logging.info(f"{attr} 是同步数据库，源数据库 ID: {source_db_id}")

                        # 尝试访问源数据库
                        try:
                            source_response = self.client.databases.retrieve(database_id=source_db_id)
                            # 只有在能成功访问源数据库时才替换 ID
                            if source_response.get("properties"):
                                setattr(self, attr, source_db_id)
                                logging.info(f"{attr} 已更新为源数据库 ID（有权限）")
                            else:
                                logging.warning(f"{attr} 源数据库无 properties，保持使用同步数据库")
                        except Exception as e:
                            logging.warning(f"{attr} 源数据库无访问权限，保持使用同步数据库: {str(e)}")
                            # 保持使用原来的同步数据库 ID
                except Exception as e:
                    logging.warning(f"检查数据库 {attr} 时出错: {str(e)}")

    def update_book_database(self):
        """更新数据库"""
        # 检查 book_database_id 是否有效
        if self.book_database_id is None:
            error_msg = f"书架数据库未找到！请检查：\n" \
                       f"1. Notion 页面中是否存在名为 '{self.database_name_dict.get('BOOK_DATABASE_NAME')}' 的数据库\n" \
                       f"2. NOTION_TOKEN 对应的 integration 是否有访问权限\n" \
                       f"3. 环境变量 BOOK_DATABASE_NAME 是否正确设置"
            logging.error(error_msg)
            raise Exception(error_msg)

        try:
            response = self.client.databases.retrieve(database_id=self.book_database_id)
        except Exception as e:
            error_msg = f"获取书架数据库失败：{str(e)}\n" \
                       f"database_id: {self.book_database_id}"
            logging.error(error_msg)
            raise Exception(error_msg) from e

        id = response.get("id")
        properties = response.get("properties")

        # 检查 properties 是否存在
        if properties is None:
            # 检查是否是同步数据库（没有 properties 但可以继续使用）
            if response.get("data_sources"):
                logging.warning(f"书架数据库是同步数据库且源数据库无权限，跳过属性更新")
                logging.warning(f"提示：如需更新数据库属性，请将 integration 添加到源数据库所在页面")
                return  # 跳过属性更新，但不抛出异常
            else:
                error_msg = f"数据库响应中缺少 properties 字段！\n" \
                           f"database_id: {id}\n" \
                           f"response keys: {list(response.keys())}"
                logging.error(error_msg)
                logging.error(f"完整响应: {response}")
                raise Exception(error_msg)

        update_properties = {}
        if (
            properties.get("阅读时长") is None
            or properties.get("阅读时长").get("type") != "number"
        ):
            update_properties["阅读时长"] = {"number": {}}
        if (
            properties.get("书架分类") is None
            or properties.get("书架分类").get("type") != "select"
        ):
            update_properties["书架分类"] = {"select": {}}
        if (
            properties.get("豆瓣链接") is None
            or properties.get("豆瓣链接").get("type") != "url"
        ):
            update_properties["豆瓣链接"] = {"url": {}}
        if (
            properties.get("我的评分") is None
            or properties.get("我的评分").get("type") != "select"
        ):
            update_properties["我的评分"] = {"select": {}}
        if (
            properties.get("豆瓣短评") is None
            or properties.get("豆瓣短评").get("type") != "rich_text"
        ):
            update_properties["豆瓣短评"] = {"rich_text": {}}
        """NeoDB先不添加了，现在受众还不广，可能有的小伙伴不知道是干什么的"""
        if len(update_properties) > 0:
            self.client.databases.update(database_id=id, properties=update_properties)

    def create_database(self):
        title = [
            {
                "type": "text",
                "text": {
                    "content": self.database_name_dict.get("READ_DATABASE_NAME"),
                },
            },
        ]
        properties = {
            "标题": {"title": {}},
            "时长": {"number": {}},
            "时间戳": {"number": {}},
            "日期": {"date": {}},
            "书架": {
                "relation": {
                    "database_id": self.book_database_id,
                    "single_property": {},
                }
            },
        }
        parent = parent = {"page_id": self.page_id, "type": "page_id"}
        self.read_database_id = self.client.databases.create(
            parent=parent,
            title=title,
            icon=get_icon("https://www.notion.so/icons/target_gray.svg"),
            properties=properties,
        ).get("id")    
        
    def create_setting_database(self):
        title = [
            {
                "type": "text",
                "text": {
                    "content": self.database_name_dict.get("SETTING_DATABASE_NAME"),
                },
            },
        ]
        properties = {
            "标题": {"title": {}},
            "NotinToken": {"rich_text": {}},
            "NotinPage": {"rich_text": {}},
            "WeReadCookie": {"rich_text": {}},
            "根据划线颜色设置文字颜色": {"checkbox": {}},
            "同步书签": {"checkbox": {}},
            # "Cookie状态": {
            #     "select": {
            #         "options": [
            #             {"name": "可用", "color": "green"},
            #             {"name": "过期", "color": "red"},
            #         ]
            #     }
            # },
            "样式": {
                "select": {
                    "options": [
                        {"name": "callout", "color": "blue"},
                        {"name": "quote", "color": "green"},
                        {"name": "paragraph", "color": "purple"},
                        {"name": "bulleted_list_item", "color": "yellow"},
                        {"name": "numbered_list_item", "color": "pink"},
                    ]
                }
            },
            "最后同步时间": {"date": {}},
        }
        parent = parent = {"page_id": self.page_id, "type": "page_id"}
        self.setting_database_id = self.client.databases.create(
            parent=parent,
            title=title,
            icon=get_icon("https://www.notion.so/icons/gear_gray.svg"),
            properties=properties,
        ).get("id")

    def insert_to_setting_database(self):
        # 直接调用 client.databases.query 而不是通过 wrapper
        filter_params = {"property": "标题", "title": {"equals": "设置"}}
        response = self.client.databases.query(
            database_id=self.setting_database_id,
            filter=filter_params
        )
        existing_pages = response.get("results")
        properties = {
            "标题": {"title": [{"type": "text", "text": {"content": "设置"}}]},
            "最后同步时间": {"date": {"start": pendulum.now("Asia/Shanghai").isoformat()}},
            "NotinToken": {"rich_text": [{"type": "text", "text": {"content": os.getenv("NOTION_TOKEN")}}]},
            "NotinPage": {"rich_text": [{"type": "text", "text": {"content": os.getenv("NOTION_PAGE")}}]},
            "WeReadCookie": {"rich_text": [{"type": "text", "text": {"content": os.getenv("WEREAD_COOKIE")}}]},
        }
        if existing_pages:
            remote_properties = existing_pages[0].get("properties")
            self.show_color = get_property_value(remote_properties.get("根据划线颜色设置文字颜色"))
            self.sync_bookmark = get_property_value(remote_properties.get("同步书签"))
            self.block_type = get_property_value(remote_properties.get("样式"))
            page_id = existing_pages[0].get("id")
            self.client.pages.update(page_id=page_id, properties=properties)
        else:
            properties["根据划线颜色设置文字颜色"] = {"checkbox": True}
            properties["同步书签"] = {"checkbox": True}
            properties["样式"] = {"select": {"name": "callout"}}
            self.client.pages.create(
                parent={"database_id": self.setting_database_id},
                properties=properties,
            )
  
        

    def update_heatmap(self, block_id, url):
        # 更新 image block 的链接
        return self.client.blocks.update(block_id=block_id, embed={"url": url})

    def get_week_relation_id(self, date):
        year = date.isocalendar().year
        week = date.isocalendar().week
        week = f"{year}年第{week}周"
        start, end = get_first_and_last_day_of_week(date)
        properties = {"日期": get_date(format_date(start), format_date(end))}
        return self.get_relation_id(
            week, self.week_database_id, TARGET_ICON_URL, properties
        )

    def get_month_relation_id(self, date):
        month = date.strftime("%Y年%-m月")
        start, end = get_first_and_last_day_of_month(date)
        properties = {"日期": get_date(format_date(start), format_date(end))}
        return self.get_relation_id(
            month, self.month_database_id, TARGET_ICON_URL, properties
        )

    def get_year_relation_id(self, date):
        year = date.strftime("%Y")
        start, end = get_first_and_last_day_of_year(date)
        properties = {"日期": get_date(format_date(start), format_date(end))}
        return self.get_relation_id(
            year, self.year_database_id, TARGET_ICON_URL, properties
        )

    def get_day_relation_id(self, date):
        new_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
        timestamp = (new_date - timedelta(hours=8)).timestamp()
        day = new_date.strftime("%Y年%m月%d日")
        properties = {
            "日期": get_date(format_date(date)),
            "时间戳": get_number(timestamp),
        }
        properties["年"] = get_relation(
            [
                self.get_year_relation_id(new_date),
            ]
        )
        properties["月"] = get_relation(
            [
                self.get_month_relation_id(new_date),
            ]
        )
        properties["周"] = get_relation(
            [
                self.get_week_relation_id(new_date),
            ]
        )
        return self.get_relation_id(
            day, self.day_database_id, TARGET_ICON_URL, properties
        )

    def get_relation_id(self, name, id, icon, properties={}):
        key = f"{id}{name}"
        if key in self.__cache:
            return self.__cache.get(key)
        filter = {"property": "标题", "title": {"equals": name}}
        response = self.client.databases.query(database_id=id, filter=filter)
        if len(response.get("results")) == 0:
            parent = {"database_id": id, "type": "database_id"}
            properties["标题"] = get_title(name)
            page_id = self.client.pages.create(
                parent=parent, properties=properties, icon=get_icon(icon)
            ).get("id")
        else:
            page_id = response.get("results")[0].get("id")
        self.__cache[key] = page_id
        return page_id

    def insert_bookmark(self, id, bookmark):
        icon = get_icon(BOOKMARK_ICON_URL)
        properties = {
            "Name": get_title(bookmark.get("markText", "")),
            "bookId": get_rich_text(bookmark.get("bookId")),
            "range": get_rich_text(bookmark.get("range")),
            "bookmarkId": get_rich_text(bookmark.get("bookmarkId")),
            "blockId": get_rich_text(bookmark.get("blockId")),
            "chapterUid": get_number(bookmark.get("chapterUid")),
            "bookVersion": get_number(bookmark.get("bookVersion")),
            "colorStyle": get_number(bookmark.get("colorStyle")),
            "type": get_number(bookmark.get("type")),
            "style": get_number(bookmark.get("style")),
            "书籍": get_relation([id]),
        }
        if "createTime" in bookmark:
            create_time = timestamp_to_date(int(bookmark.get("createTime")))
            properties["Date"] = get_date(create_time.strftime("%Y-%m-%d %H:%M:%S"))
            self.get_date_relation(properties, create_time)
        parent = {"database_id": self.bookmark_database_id, "type": "database_id"}
        self.create_page(parent, properties, icon)

    def insert_review(self, id, review):
        time.sleep(0.1)
        icon = get_icon(TAG_ICON_URL)
        properties = {
            "Name": get_title(review.get("content", "")),
            "bookId": get_rich_text(review.get("bookId")),
            "reviewId": get_rich_text(review.get("reviewId")),
            "blockId": get_rich_text(review.get("blockId")),
            "chapterUid": get_number(review.get("chapterUid")),
            "bookVersion": get_number(review.get("bookVersion")),
            "type": get_number(review.get("type")),
            "书籍": get_relation([id]),
        }
        if "range" in review:
            properties["range"] = get_rich_text(review.get("range"))
        if "star" in review:
            properties["star"] = get_number(review.get("star"))
        if "abstract" in review:
            properties["abstract"] = get_rich_text(review.get("abstract"))
        if "createTime" in review:
            create_time = timestamp_to_date(int(review.get("createTime")))
            properties["Date"] = get_date(create_time.strftime("%Y-%m-%d %H:%M:%S"))
            self.get_date_relation(properties, create_time)
        parent = {"database_id": self.review_database_id, "type": "database_id"}
        self.create_page(parent, properties, icon)

    def insert_chapter(self, id, chapter):
        time.sleep(0.1)
        icon = {"type": "external", "external": {"url": TAG_ICON_URL}}
        properties = {
            "Name": get_title(chapter.get("title")),
            "blockId": get_rich_text(chapter.get("blockId")),
            "chapterUid": {"number": chapter.get("chapterUid")},
            "chapterIdx": {"number": chapter.get("chapterIdx")},
            "readAhead": {"number": chapter.get("readAhead")},
            "updateTime": {"number": chapter.get("updateTime")},
            "level": {"number": chapter.get("level")},
            "书籍": {"relation": [{"id": id}]},
        }
        parent = {"database_id": self.chapter_database_id, "type": "database_id"}
        self.create_page(parent, properties, icon)

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def update_book_page(self, page_id, properties):
        return self.client.pages.update(page_id=page_id, properties=properties)

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def update_page(self, page_id, properties, cover):
        return self.client.pages.update(
            page_id=page_id, properties=properties, cover=cover
        )


    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def create_page(self, parent, properties, icon):
        return self.client.pages.create(parent=parent, properties=properties, icon=icon)

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def create_book_page(self, parent, properties, icon):
        return self.client.pages.create(
            parent=parent, properties=properties, icon=icon, cover=icon
        )

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def query(self, **kwargs):
        # 过滤掉 None 值的参数
        kwargs = {k: v for k, v in kwargs.items() if v is not None}
        return self.client.databases.query(**kwargs)

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def get_block_children(self, id):
        response = self.client.blocks.children.list(id)
        return response.get("results")

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def append_blocks(self, block_id, children):
        return self.client.blocks.children.append(block_id=block_id, children=children)

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def append_blocks_after(self, block_id, children, after):
        #奇怪不知道为什么会多插入一个children，没找到问题，先暂时这么解决，搜索是否有parent
        parent = self.client.blocks.retrieve(after).get("parent")
        if(parent.get("type")=="block_id"):
            after = parent.get("block_id")
        return self.client.blocks.children.append(
            block_id=block_id, children=children, after=after
        )

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def delete_block(self, block_id):
        return self.client.blocks.delete(block_id=block_id)

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def get_all_book(self):
        """从Notion中获取所有的书籍"""
        results = self.query_all(self.book_database_id)
        books_dict = {}
        for result in results:
            bookId = get_property_value(result.get("properties").get("BookId"))
            books_dict[bookId] = {
                "pageId": result.get("id"),
                "readingTime": get_property_value(
                    result.get("properties").get("阅读时长")
                ),
                "category": get_property_value(
                    result.get("properties").get("书架分类")
                ),
                "Sort": get_property_value(result.get("properties").get("Sort")),
                "douban_url": get_property_value(
                    result.get("properties").get("豆瓣链接")
                ),
                "cover": result.get("cover"),
                "myRating": get_property_value(
                    result.get("properties").get("我的评分")
                ),
                "comment": get_property_value(result.get("properties").get("豆瓣短评")),
                "status": get_property_value(result.get("properties").get("阅读状态")),
            }
        return books_dict

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def query_all_by_book(self, database_id, filter):
        results = []
        has_more = True
        start_cursor = None
        while has_more:
            response = self.client.databases.query(
                database_id=database_id,
                filter=filter,
                start_cursor=start_cursor,
                page_size=100,
            )
            start_cursor = response.get("next_cursor")
            has_more = response.get("has_more")
            results.extend(response.get("results"))
        return results

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def query_all(self, database_id):
        """获取database中所有的数据"""
        results = []
        has_more = True
        start_cursor = None
        while has_more:
            response = self.client.databases.query(
                database_id=database_id,
                start_cursor=start_cursor,
                page_size=100,
            )
            start_cursor = response.get("next_cursor")
            has_more = response.get("has_more")
            results.extend(response.get("results"))
        return results

    def get_date_relation(self, properties, date):
        properties["年"] = get_relation(
            [
                self.get_year_relation_id(date),
            ]
        )
        properties["月"] = get_relation(
            [
                self.get_month_relation_id(date),
            ]
        )
        properties["周"] = get_relation(
            [
                self.get_week_relation_id(date),
            ]
        )
        properties["日"] = get_relation(
            [
                self.get_day_relation_id(date),
            ]
        )