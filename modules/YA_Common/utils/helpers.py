from art import text2art
from .config import (
    get_server_name,
    get_server_author,
    get_server_description,
    get_server_version,
)
from .logger import get_logger

logger = get_logger("helpers")


def print_server_banner():
    """
    打印 MCP banner，包括：
    - MCP 名称（大字）
    - 作者
    - 版本号
    - 描述
    """
    name = get_server_name()
    author = get_server_author()
    version = get_server_version()
    description = get_server_description()

    ascii_name = text2art(name, font="bubble")
    logger.info("\n" + ascii_name)
    logger.info(f"Author: {author}")
    logger.info(f"Version: {version}")
    logger.info(f"{description}")
    logger.info("=" * 60)
