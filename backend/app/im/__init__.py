"""IM 机器人集成模块."""

from app.im.base import BaseIMBot, IMMessage
from app.im.dingtalk import DingTalkBot

__all__ = ["BaseIMBot", "DingTalkBot", "IMMessage"]
