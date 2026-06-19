"""IM 机器人 Webhook 路由."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.im.base import BaseIMBot, IMMessage
from app.im.commands import parse_command
from app.im.dingtalk import DingTalkBot
from app.im.feishu import FeishuBot
from app.im.wecom import WeComBot
from app.models.im_user_mapping import IMUserMapping
from app.models.user import User
from app.security import create_access_token
from app.services.im_service import handle_command

router = APIRouter(prefix="/api/v1/im", tags=["IM Bot"])


def _get_user_by_im_id(db: Session, im_user_id: str, platform: str = "dingtalk") -> User | None:
    """根据 IM 用户 ID 查找系统用户.

    优先查询独立的 IM 用户映射表；未命中时回退到 user.attributes 中的
    `{platform}_user_id`，兼容 MVP 阶段的快速配置方式。
    """
    if not im_user_id:
        return None

    mapping: IMUserMapping | None = (
        db.query(IMUserMapping)
        .filter(
            IMUserMapping.platform == platform,
            IMUserMapping.im_user_id == im_user_id,
        )
        .first()
    )
    if mapping is not None:
        user: User | None = db.query(User).filter(
            User.id == mapping.user_id, User.is_active == "Y"
        ).first()
        if user is not None:
            return user

    # 兼容 attributes 方式
    attr_key = f"{platform}_user_id"
    users: list[User] = db.query(User).filter(User.is_active == "Y").all()
    for user in users:
        attributes = user.attributes or {}
        if attributes.get(attr_key) == im_user_id:
            return user

    matched: User | None = db.query(User).filter(
        User.username == im_user_id, User.is_active == "Y"
    ).first()
    return matched


def _handle_message(message: IMMessage, platform: str, db: Session) -> dict[str, Any]:
    """统一处理 IM 消息并返回平台响应."""
    bot = _get_bot(platform)

    if not message.text:
        return bot.build_response("收到空消息，请输入 /help 查看支持的命令。")

    if message.text.startswith("/help"):
        help_text = (
            "可用命令：\n"
            "/query <问题>\n"
            "/report <类型> [title=标题] [year=年份] [period=期间]\n"
            "/pending\n"
            "/approve report_id=<ID> [action=approve|reject|modify] [comment=意见]\n"
            "/reject report_id=<ID> [comment=意见]\n"
            "/modify report_id=<ID> [comment=意见]"
        )
        return bot.build_response(help_text)

    try:
        command = parse_command(message.text)
    except ValueError as exc:
        return bot.build_response(str(exc))

    user = _get_user_by_im_id(db, message.user_id, platform)
    if user is None:
        return bot.build_response("未找到对应的系统用户，请联系管理员绑定账号。")

    token = create_access_token({"sub": user.id})
    try:
        reply = handle_command(command, token)
    except Exception as exc:  # noqa: BLE001
        return bot.build_error_response(str(exc))

    return bot.build_response(reply)


def _get_bot(platform: str) -> BaseIMBot:
    """根据平台名称获取机器人实例."""
    if platform == "feishu":
        return FeishuBot()
    if platform == "wecom":
        return WeComBot()
    return DingTalkBot()


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
    return _handle_message(message, "dingtalk", db)


@router.post("/feishu")
async def feishu_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """飞书/Lark 机器人事件订阅入口."""
    bot = FeishuBot()
    raw_body = await request.body()
    payload = await request.json()
    headers = dict(request.headers)

    if not bot.verify_signature(payload, headers, raw_body=raw_body):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )

    # URL 验证
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge", "")}

    # 解密加密事件体
    if "encrypt" in payload:
        try:
            payload = bot.decrypt(payload["encrypt"])
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Decrypt failed: {exc!s}",
            ) from exc

    message = bot.parse_message(payload)
    return _handle_message(message, "feishu", db)


@router.api_route("/wecom", methods=["GET", "POST"])
async def wecom_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any] | str:
    """企业微信机器人事件订阅入口（GET 用于 URL 验证，POST 用于事件推送）."""
    bot = WeComBot()
    headers = dict(request.headers)

    # GET 请求为 URL 验证，echostr 在 query 参数中
    if request.method == "GET":
        query_params = dict(request.query_params)
        raw_body = f"<xml><Encrypt><![CDATA[{query_params.get('echostr', '')}]]></Encrypt></xml>".encode()
        if not bot.verify_signature({}, headers, raw_body=raw_body):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature",
            )
        try:
            decrypted = bot.decrypt(query_params["echostr"])
            return str(decrypted.get("xml", ""))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Decrypt failed: {exc!s}",
            ) from exc

    # POST 请求为事件推送
    raw_body = await request.body()
    if not bot.verify_signature({}, headers, raw_body=raw_body):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )

    encrypt = bot.extract_encrypt(raw_body)
    if encrypt:
        try:
            payload = bot.decrypt(encrypt)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Decrypt failed: {exc!s}",
            ) from exc
    else:
        payload = {}

    message = bot.parse_message(payload)
    return _handle_message(message, "wecom", db)
