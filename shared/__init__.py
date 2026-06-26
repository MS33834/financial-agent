"""共享模块.

放置跨服务共享的 schemas、events、constants，定义服务边界契约。
当前项目为单体架构，本模块为未来微服务化预留统一契约入口。
"""

from shared import constants, events, schemas

__all__ = ["constants", "events", "schemas"]
