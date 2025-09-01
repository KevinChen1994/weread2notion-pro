#!/usr/bin/env python3
"""
本地调试运行器
用于本地调试微信读书同步程序
"""

import logging
import os
import sys

from dotenv import load_dotenv

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "weread2notionpro"))

# 加载环境变量
load_dotenv()

# 设置日志级别
log_level = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("debug.log", encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)


def check_environment():
    """检查环境配置"""
    logger.info("🔍 检查环境配置...")

    required_vars = ["NOTION_TOKEN", "NOTION_PAGE"]
    optional_vars = ["WEREAD_COOKIE", "CC_URL", "CC_ID", "CC_PASSWORD"]

    missing_required = []
    for var in required_vars:
        if not os.getenv(var):
            missing_required.append(var)

    if missing_required:
        logger.error(f"❌ 缺少必需的环境变量: {', '.join(missing_required)}")
        logger.error("请复制 .env.example 为 .env 并填写相应配置")
        return False

    logger.info("✅ 必需环境变量检查通过")

    # 检查可选变量
    missing_optional = []
    for var in optional_vars:
        if not os.getenv(var):
            missing_optional.append(var)

    if missing_optional:
        logger.warning(f"⚠️  缺少可选环境变量: {', '.join(missing_optional)}")
        logger.warning("这可能影响某些功能的使用")

    return True


def test_weread_api():
    """测试微信读书API连接"""
    logger.info("🔗 测试微信读书API连接...")

    try:
        from weread2notionpro.weread_api import WeReadApi

        api = WeReadApi()
        logger.info("✅ WeReadApi 初始化成功")

        # 测试获取书架
        try:
            bookshelf = api.get_bookshelf()
            book_count = len(bookshelf.get("books", []))
            logger.info(f"✅ 成功获取书架，共 {book_count} 本书")
            return True
        except Exception as e:
            logger.error(f"❌ 获取书架失败: {str(e)}")
            if "cookie" in str(e).lower():
                logger.error("提示：可能是Cookie过期或无效")
            return False

    except Exception as e:
        logger.error(f"❌ WeReadApi 初始化失败: {str(e)}")
        return False


def test_notion_connection():
    """测试Notion连接"""
    logger.info("📝 测试Notion连接...")

    try:
        from notion_helper import NotionHelper

        notion = NotionHelper()
        logger.info("✅ NotionHelper 初始化成功")
        return True
    except Exception as e:
        logger.error(f"❌ Notion连接失败: {str(e)}")
        return False


def run_debug_mode():
    """运行调试模式"""
    logger.info("🚀 启动调试模式")

    if not check_environment():
        return False

    # 测试连接
    weread_ok = test_weread_api()
    notion_ok = test_notion_connection()

    if not weread_ok:
        logger.error("❌ 微信读书API测试失败，无法继续")
        return False

    if not notion_ok:
        logger.error("❌ Notion连接测试失败，无法继续")
        return False

    logger.info("✅ 所有连接测试通过，可以开始同步")
    return True


def run_book_sync():
    """运行书籍同步"""
    logger.info("📚 开始书籍同步...")
    try:
        from book import main as book_main

        book_main()
        logger.info("✅ 书籍同步完成")
    except Exception as e:
        logger.error(f"❌ 书籍同步失败: {str(e)}")
        raise


def run_weread_sync():
    """运行微信读书同步"""
    logger.info("📖 开始微信读书同步...")
    try:
        from weread import main as weread_main

        weread_main()
        logger.info("✅ 微信读书同步完成")
    except Exception as e:
        logger.error(f"❌ 微信读书同步失败: {str(e)}")
        raise


def run_read_time_sync():
    """运行阅读时间同步"""
    logger.info("⏰ 开始阅读时间同步...")
    try:
        from read_time import main as read_time_main

        read_time_main()
        logger.info("✅ 阅读时间同步完成")
    except Exception as e:
        logger.error(f"❌ 阅读时间同步失败: {str(e)}")
        raise


def main():
    """主函数"""
    print("🔧 微信读书同步程序 - 本地调试器")
    print("=" * 50)

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "test":
            print("🧪 运行连接测试...")
            success = run_debug_mode()
            sys.exit(0 if success else 1)

        elif command == "book":
            print("📚 运行书籍同步...")
            if run_debug_mode():
                run_book_sync()

        elif command == "weread":
            print("📖 运行微信读书同步...")
            if run_debug_mode():
                run_weread_sync()

        elif command == "readtime":
            print("⏰ 运行阅读时间同步...")
            if run_debug_mode():
                run_read_time_sync()

        elif command == "all":
            print("🚀 运行完整同步...")
            if run_debug_mode():
                run_book_sync()
                run_weread_sync()
                run_read_time_sync()
        else:
            print(f"❌ 未知命令: {command}")
            print_usage()
    else:
        print_usage()


def print_usage():
    """打印使用说明"""
    print("\n使用方法:")
    print("  python debug_runner.py test      # 测试连接")
    print("  python debug_runner.py book      # 同步书籍")
    print("  python debug_runner.py weread    # 同步划线和笔记")
    print("  python debug_runner.py readtime  # 同步阅读时间")
    print("  python debug_runner.py all       # 完整同步")
    print("\n首次使用请先运行测试:")
    print("  python debug_runner.py test")


if __name__ == "__main__":
    main()
