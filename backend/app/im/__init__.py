"""IM 机器人集成模块."""

from app.im.base import BaseIMBot, IMMessage
from app.im.dingtalk import DingTalkBot
from app.im.feishu import FeishuBot
from app.im.wecom import WeComBot

__all__ = ["BaseIMBot", "DingTalkBot", "FeishuBot", "IMMessage", "WeComBot"]
