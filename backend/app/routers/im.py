"""IM 机器人 Webhook 路由."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.im.commands import parse_command
from app.im.dingtalk import DingTalkBot
from app.models.user import User
from app.security import create_access_token
from app.services.im_service import handle_command

router = APIRouter(prefix="/api/v1/im", tags=["IM Bot"])


def _get_user_by_im_id(db: Session, im_user_id: str) -> User | None:
    """根据 IM 用户 ID 查找系统用户.

    优先匹配用户 attributes 中配置的 dingtalk_user_id；未命中时回退到 username，
    方便 MVP 阶段快速配置。生产环境建议维护独立的 IM 用户映射表。
    """
    if not im_user_id:
        return None

    # 精确匹配 attributes 中保存的 dingtalk_user_id（内存过滤，兼容 SQLite/Postgres）
    for user in db.query(User).filter(User.is_active == "Y").all():
        attributes = user.attributes or {}
        if attributes.get("dingtalk_user_id") == im_user_id:
            return user

    # 兜底：按 username 匹配
    return db.query(User).filter(User.username == im_user_id, User.is_active == "Y").first()


@router.post("/dingtalk")
async def dingtalk_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """钉钉机器人 Webhook 入口."""
    bot = DingTalkBot()
    payload = await request.json()
    headers = dict(request.headers)

    if not bot.verify_signature(payload, headers):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )

    message = bot.parse_message(payload)
    if not message.text:
        return bot.build_response("收到空消息，请输入 /help 查看支持的命令。")

    if message.text.startswith("/help"):
        help_text = (
            "可用命令：\n"
            "/query <问题>\n"
            "/report <类型> [title=标题] [year=年份] [period=期间]\n"
            "/approve report_id=<ID> [action=approve|reject] [comment=意见]"
        )
        return bot.build_response(help_text)

    try:
        command = parse_command(message.text)
    except ValueError as exc:
        return bot.build_response(str(exc))

    user = _get_user_by_im_id(db, message.user_id)
    if user is None:
        return bot.build_response("未找到对应的系统用户，请联系管理员绑定账号。")

    token = create_access_token({"sub": user.id})
    try:
        reply = handle_command(command, token)
    except Exception as exc:  # noqa: BLE001
        return bot.build_error_response(str(exc))

    return bot.build_response(reply)
