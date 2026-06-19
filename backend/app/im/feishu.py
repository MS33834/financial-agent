"""飞书/Lark 机器人适配器.

参考飞书官方文档：
- 事件订阅签名：SHA-256(timestamp + nonce + encrypt_key + body)，十六进制
- URL 验证：原样返回 challenge
- 事件解密：AES-256-CBC，密钥为 SHA-256(encrypt_key) 前 32 字节
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from app.config import get_settings
from app.im.base import BaseIMBot, IMMessage, send_webhook_with_retry


def _sha256_hex(data: bytes) -> str:
    """计算 SHA-256 并返回十六进制字符串."""
    return hashlib.sha256(data).hexdigest()


class FeishuBot(BaseIMBot):
    """飞书/Lark 机器人适配器."""

    def __init__(self, encrypt_key: str | None = None) -> None:
        """初始化.

        Args:
            encrypt_key: 飞书事件订阅 Encrypt Key；未提供则从 Settings 读取。
        """
        settings = get_settings()
        self.encrypt_key = encrypt_key or settings.feishu_encrypt_key

    def verify_signature(
        self,
        _payload: dict[str, Any],
        headers: dict[str, str],
        raw_body: bytes | None = None,
    ) -> bool:
        """验证飞书事件订阅签名.

        Args:
            _payload: 已解析的 JSON 负载（飞书签名基于原始 body，此参数未使用）。
            headers: 请求头。
            raw_body: 原始请求体字节，签名计算需要。
        """
        if not self.encrypt_key or raw_body is None:
            return False

        normalized = {k.lower(): v for k, v in headers.items()}
        timestamp = normalized.get("x-lark-request-timestamp", "")
        nonce = normalized.get("x-lark-request-nonce", "")
        signature = normalized.get("x-lark-signature", "")
        if not timestamp or not nonce or not signature:
            return False

        sign_str = f"{timestamp}{nonce}{self.encrypt_key}{raw_body.decode('utf-8')}"
        expected = _sha256_hex(sign_str.encode("utf-8"))
        return hmac.compare_digest(expected, signature)

    def decrypt(self, encrypt_str: str) -> dict[str, Any]:
        """解密飞书加密事件体.

        飞书使用 AES-256-CBC 加密，密钥为 SHA-256(encrypt_key) 的前 32 字节，
        密文前 16 字节为 IV，使用 PKCS7 填充。
        """
        if not self.encrypt_key:
            raise FeishuDecryptError("缺少 encrypt_key")

        key = hashlib.sha256(self.encrypt_key.encode("utf-8")).digest()
        ciphertext = base64.b64decode(encrypt_str)
        if len(ciphertext) < 16:
            raise FeishuDecryptError("密文过短")

        iv = ciphertext[:16]
        data = ciphertext[16:]
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        plaintext = decryptor.update(data) + decryptor.finalize()

        # PKCS7 去填充
        pad_len = plaintext[-1]
        if pad_len > 16:
            raise FeishuDecryptError("填充长度异常")
        plaintext = plaintext[:-pad_len]

        decrypted: dict[str, Any] = json.loads(plaintext.decode("utf-8"))
        return decrypted

    def parse_message(self, payload: dict[str, Any]) -> IMMessage:
        """解析飞书 text 消息事件.

        支持 2.0 版本事件格式：
        {"schema":"2.0","header":{...},"event":{"message":{...}}}
        """
        event = payload.get("event", {})
        message = event.get("message", {})
        sender = event.get("sender", {})
        sender_id = sender.get("sender_id", {})

        content_str = message.get("content", "{}")
        try:
            content = json.loads(content_str)
        except json.JSONDecodeError:
            content = {}

        return IMMessage(
            user_id=sender_id.get("user_id", ""),
            username=sender.get("sender_type", ""),
            tenant_id=payload.get("header", {}).get("tenant_key", ""),
            text=content.get("text", "").strip(),
            raw_payload=payload,
        )

    def build_response(self, content: str, msg_type: str = "text") -> dict[str, Any]:
        """构建飞书响应消息.

        事件订阅通常只需返回 HTTP 200，但处理消息卡片或回复时可用此结构。
        """
        if msg_type == "markdown":
            return {"msg_type": "interactive", "card": {"elements": [{"tag": "markdown", "content": content}]}}
        return {"msg_type": "text", "content": {"text": content}}

    def send_message(self, content: str, msg_type: str = "text") -> bool:
        """通过飞书机器人 Webhook 主动推送消息."""
        settings = get_settings()
        webhook = settings.feishu_webhook
        if not webhook:
            return False

        body = json.dumps(self.build_response(content, msg_type)).encode("utf-8")
        return send_webhook_with_retry(webhook, body)


class FeishuDecryptError(Exception):
    """飞书解密失败."""

    pass
