"""企业微信机器人适配器.

参考企业微信官方文档：
- 回调消息加解密：AES-256-CBC，密钥为 EncodingAESKey Base64 解码后的 32 字节
- 消息体签名：SHA1(sort(token, timestamp, nonce, encrypt))
- 回调消息格式为 XML
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import struct
import xml.etree.ElementTree as ET
from typing import Any

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from app.config import get_settings
from app.im.base import BaseIMBot, IMMessage


def _sha1_hex(data: bytes) -> str:
    """计算 SHA-1 并返回十六进制字符串."""
    return hashlib.sha1(data).hexdigest()


class WeComBot(BaseIMBot):
    """企业微信机器人适配器."""

    def __init__(self, token: str | None = None, encoding_aes_key: str | None = None) -> None:
        """初始化.

        Args:
            token: 企业微信回调 Token；未提供则从 Settings 读取。
            encoding_aes_key: 企业微信 EncodingAESKey；未提供则从 Settings 读取。
        """
        settings = get_settings()
        self.token = token or settings.wecom_token
        self.encoding_aes_key = encoding_aes_key or settings.wecom_encoding_aes_key

    def verify_signature(
        self,
        _payload: dict[str, Any],
        headers: dict[str, str],
        raw_body: bytes | None = None,
    ) -> bool:
        """验证企业微信回调签名.

        企业微信签名基于 token + timestamp + nonce + encrypt/msg_signature，
        对四个字段排序后拼接，再计算 SHA1 十六进制。
        """
        if not self.token:
            return False

        timestamp = headers.get("timestamp", "")
        nonce = headers.get("nonce", "")
        signature = headers.get("msg_signature", "")
        if not timestamp or not nonce or not signature or raw_body is None:
            return False

        # 从原始 XML body 中提取 Encrypt 字段
        encrypt = self.extract_encrypt(raw_body)
        if not encrypt:
            return False

        expected = self._compute_signature(timestamp, nonce, encrypt)
        return hmac.compare_digest(expected, signature)

    def _compute_signature(self, timestamp: str, nonce: str, encrypt: str) -> str:
        """计算企业微信回调签名."""
        if not self.token:
            return ""
        parts = [self.token, timestamp, nonce, encrypt]
        parts.sort()
        return _sha1_hex("".join(parts).encode("utf-8"))

    def extract_encrypt(self, raw_body: bytes) -> str:
        """从 XML 原始请求体中提取 Encrypt 字段."""
        try:
            root = ET.fromstring(raw_body.decode("utf-8"))
            encrypt_elem = root.find("Encrypt")
            return encrypt_elem.text or "" if encrypt_elem is not None else ""
        except ET.ParseError:
            return ""

    def decrypt(self, encrypt_str: str) -> dict[str, Any]:
        """解密企业微信加密消息体.

        企业微信使用 AES-256-CBC，密钥为 EncodingAESKey Base64 解码后的 32 字节，
        密文前 16 字节为 IV，使用 PKCS7 填充。
        解密后格式：random(16B) + msg_len(4B, 网络序) + msg + receiveid + pad
        """
        if not self.encoding_aes_key:
            raise WeComDecryptError("缺少 EncodingAESKey")

        try:
            key = base64.b64decode(self.encoding_aes_key + "=")
        except Exception as exc:
            raise WeComDecryptError(f"EncodingAESKey 解码失败: {exc}") from exc

        if len(key) != 32:
            raise WeComDecryptError("EncodingAESKey 解码后长度应为 32 字节")

        ciphertext = base64.b64decode(encrypt_str)
        if len(ciphertext) < 16:
            raise WeComDecryptError("密文过短")

        iv = ciphertext[:16]
        data = ciphertext[16:]
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        plaintext = decryptor.update(data) + decryptor.finalize()

        # PKCS7 去填充
        pad_len = plaintext[-1]
        if pad_len > 32:
            raise WeComDecryptError("填充长度异常")
        plaintext = plaintext[:-pad_len]

        if len(plaintext) < 20:
            raise WeComDecryptError("解密后数据过短")

        # 解析长度前缀
        msg_len = struct.unpack(">I", plaintext[16:20])[0]
        msg_start = 20
        msg_end = msg_start + msg_len
        if msg_end > len(plaintext):
            raise WeComDecryptError("消息长度异常")

        msg_xml = plaintext[msg_start:msg_end].decode("utf-8")
        decrypted: dict[str, Any] = {"xml": msg_xml}
        return decrypted

    def parse_message(self, payload: dict[str, Any]) -> IMMessage:
        """解析企业微信 text 消息事件.

        payload 中应包含 decrypt 后的 xml 字符串。
        """
        xml_str = payload.get("xml", "")
        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError:
            return IMMessage(raw_payload=payload)

        msg_type = self._xml_text(root, "MsgType")
        content = self._xml_text(root, "Content") if msg_type == "text" else ""
        return IMMessage(
            user_id=self._xml_text(root, "FromUserName"),
            username=self._xml_text(root, "FromUserName"),
            tenant_id=self._xml_text(root, "ToUserName"),
            text=content.strip(),
            raw_payload=payload,
        )

    def _xml_text(self, root: ET.Element, tag: str) -> str:
        """安全获取 XML 子元素文本."""
        elem = root.find(tag)
        return elem.text or "" if elem is not None else ""

    def build_response(self, content: str, msg_type: str = "text") -> dict[str, Any]:
        """构建企业微信响应消息（XML 格式）."""
        if msg_type == "markdown":
            return {
                "msg_type": "markdown",
                "content": content,
            }
        return {
            "msg_type": "text",
            "content": {"content": content},
        }


class WeComDecryptError(Exception):
    """企业微信解密失败."""

    pass
