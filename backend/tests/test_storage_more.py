"""存储层（app.storage）补全测试.

覆盖：
- LocalStorageClient: 路径穿越防御、上传/下载、目录创建、读不存在文件、resolve 失败
- MinioStorageClient: ensure_bucket、上传/下载、S3Error 包装
- get_storage_client: local / minio 后端分发
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, _patch, patch

import pytest

from app.storage import (
    BaseStorageClient,
    LocalStorageClient,
    MinioStorageClient,
    StorageClientError,
    get_storage_client,
)

# ------------------------------------------------------------------
# LocalStorageClient
# ------------------------------------------------------------------


def test_local_upload_and_download_bytes(tmp_path: Path) -> None:
    """正常上传/下载应能完整往返."""
    with patch("app.storage.get_settings") as mock_settings:
        mock_settings.return_value.storage_local_root = str(tmp_path / "store")
        client = LocalStorageClient()
    url = client.upload_bytes("docs/a.txt", b"hello world", content_type="text/plain")
    assert url.endswith("docs/a.txt")
    assert client.download_bytes("docs/a.txt") == b"hello world"


def test_local_upload_strips_leading_slash(tmp_path: Path) -> None:
    """key 以 / 开头应被去除."""
    with patch("app.storage.get_settings") as mock_settings:
        mock_settings.return_value.storage_local_root = str(tmp_path / "store")
        client = LocalStorageClient()
    url = client.upload_bytes("/x.txt", b"x")
    assert url.endswith("x.txt")


def test_local_upload_rejects_dotdot_in_key(tmp_path: Path) -> None:
    """key 中含 .. 路径段应抛 StorageClientError."""
    with patch("app.storage.get_settings") as mock_settings:
        mock_settings.return_value.storage_local_root = str(tmp_path / "store")
        client = LocalStorageClient()
    with pytest.raises(StorageClientError) as exc_info:
        client.upload_bytes("docs/../escape.txt", b"x")
    assert "不允许包含 '..'" in str(exc_info.value)


def test_local_upload_rejects_path_escape_via_resolve(tmp_path: Path) -> None:
    """resolve 逃逸到 root 之外应抛 StorageClientError.

    通过 monkey-patch 实际的 file_path 对象的 resolve，让它返回外部路径，
    而 root.resolve() 走真实实现，从而让 relative_to 检查失败。
    """
    with patch("app.storage.get_settings") as mock_settings:
        mock_settings.return_value.storage_local_root = str(tmp_path / "store")
        client = LocalStorageClient()
    # 触发一次生成 file_path，再 monkey-patch 它的 resolve
    file_path = client.root / "safe.txt"
    real_root_resolve = client.root.resolve  # 保留真实方法
    with patch.object(type(file_path), "resolve", autospec=True) as mock_resolve:

        def _side_effect(instance: Path, *args: Any, **kwargs: Any) -> Path:
            # instance 是 file_path → 返回外部路径
            if instance == file_path:
                return tmp_path / "outside"
            # instance 是 client.root → 走真实解析
            return real_root_resolve()

        mock_resolve.side_effect = _side_effect
        with pytest.raises(StorageClientError) as exc_info:
            client.upload_bytes("safe.txt", b"x")
    assert "非法" in str(exc_info.value)


def test_local_upload_wraps_oserror(tmp_path: Path) -> None:
    """写文件 OSError 应被包装为 StorageClientError."""
    with patch("app.storage.get_settings") as mock_settings:
        mock_settings.return_value.storage_local_root = str(tmp_path / "store")
        client = LocalStorageClient()
    # 直接 monkey-patch 实际文件路径
    target = tmp_path / "store" / "a.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    with patch("pathlib.Path.write_bytes", side_effect=OSError("disk full")), \
         pytest.raises(StorageClientError) as exc_info:
        client.upload_bytes("a.txt", b"x")
    assert "本地存储写入失败" in str(exc_info.value)


def test_local_download_rejects_dotdot_in_key(tmp_path: Path) -> None:
    """download 中含 .. 应抛 StorageClientError."""
    with patch("app.storage.get_settings") as mock_settings:
        mock_settings.return_value.storage_local_root = str(tmp_path / "store")
        client = LocalStorageClient()
    with pytest.raises(StorageClientError):
        client.download_bytes("a/../b.txt")


def test_local_download_rejects_path_escape_via_resolve(tmp_path: Path) -> None:
    """download resolve 逃逸应抛 StorageClientError.

    同样用 file_path vs root 的 side_effect 区分。
    """
    with patch("app.storage.get_settings") as mock_settings:
        mock_settings.return_value.storage_local_root = str(tmp_path / "store")
        client = LocalStorageClient()
    file_path = client.root / "a.txt"
    real_root_resolve = client.root.resolve
    with patch.object(type(file_path), "resolve", autospec=True) as mock_resolve:

        def _side_effect(instance: Path, *args: Any, **kwargs: Any) -> Path:
            if instance == file_path:
                return tmp_path / "outside"
            return real_root_resolve()

        mock_resolve.side_effect = _side_effect
        with pytest.raises(StorageClientError):
            client.download_bytes("a.txt")


def test_local_download_nonexistent_raises(tmp_path: Path) -> None:
    """下载不存在的文件应抛 StorageClientError."""
    with patch("app.storage.get_settings") as mock_settings:
        mock_settings.return_value.storage_local_root = str(tmp_path / "store")
        client = LocalStorageClient()
    with pytest.raises(StorageClientError) as exc_info:
        client.download_bytes("missing.txt")
    assert "对象不存在" in str(exc_info.value)


def test_local_download_wraps_oserror(tmp_path: Path) -> None:
    """download OSError 应被包装."""
    with patch("app.storage.get_settings") as mock_settings:
        mock_settings.return_value.storage_local_root = str(tmp_path / "store")
        client = LocalStorageClient()
    target = tmp_path / "store" / "a.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"x")
    with patch("pathlib.Path.read_bytes", side_effect=OSError("io")), \
         pytest.raises(StorageClientError):
        client.download_bytes("a.txt")


# ------------------------------------------------------------------
# MinioStorageClient
# ------------------------------------------------------------------


def _patch_minio(fake_minio: MagicMock) -> _patch[MagicMock]:
    """为延迟导入的 minio 提供 patch.

    app.storage.MinioStorageClient.__init__ 中使用了 ``from minio import Minio``，
    直接 patch ``app.storage.Minio`` 会被忽略。这里采用先 import minio，再 patch
    ``minio.Minio`` 的方式拦截延迟导入。
    """
    import minio  # noqa: F401  触发 minio 包导入，让后续 patch 生效
    return patch("minio.Minio", return_value=fake_minio)


def test_minio_init_without_endpoint_raises() -> None:
    """未配置 minio_endpoint 应抛 StorageClientError."""
    with patch("app.storage.get_settings") as mock_settings:
        mock_settings.return_value.minio_endpoint = ""
        with pytest.raises(StorageClientError):
            MinioStorageClient()


def test_minio_ensure_bucket_creates_when_missing() -> None:
    """bucket 不存在时应创建."""
    fake_minio = MagicMock()
    fake_minio.bucket_exists.return_value = False
    with _patch_minio(fake_minio), patch("app.storage.get_settings") as mock_settings:
        mock_settings.return_value.minio_endpoint = "minio.local:9000"
        mock_settings.return_value.minio_access_key = "ak"
        mock_settings.return_value.minio_secret_key = "sk"
        mock_settings.return_value.minio_bucket = "test-bucket"
        mock_settings.return_value.minio_public_url = "https://cdn.example.com"
        client = MinioStorageClient()
    client.ensure_bucket()
    fake_minio.make_bucket.assert_called_once_with("test-bucket")


def test_minio_ensure_bucket_already_exists() -> None:
    """bucket 已存在时不应重复创建."""
    fake_minio = MagicMock()
    fake_minio.bucket_exists.return_value = True
    with _patch_minio(fake_minio), patch("app.storage.get_settings") as mock_settings:
        mock_settings.return_value.minio_endpoint = "minio.local:9000"
        mock_settings.return_value.minio_access_key = "ak"
        mock_settings.return_value.minio_secret_key = "sk"
        mock_settings.return_value.minio_bucket = "b"
        mock_settings.return_value.minio_public_url = "https://cdn"
        client = MinioStorageClient()
    client.ensure_bucket()
    fake_minio.make_bucket.assert_not_called()


def test_minio_ensure_bucket_s3_error_raises() -> None:
    """S3Error 应被包装为 StorageClientError."""
    from minio.error import S3Error

    fake_minio = MagicMock()
    fake_minio.bucket_exists.side_effect = S3Error("x", "x", "x", "x", "x", "x")  # type: ignore[arg-type]
    with _patch_minio(fake_minio), patch("app.storage.get_settings") as mock_settings:
        mock_settings.return_value.minio_endpoint = "minio.local:9000"
        mock_settings.return_value.minio_access_key = "ak"
        mock_settings.return_value.minio_secret_key = "sk"
        mock_settings.return_value.minio_bucket = "b"
        mock_settings.return_value.minio_public_url = ""
        client = MinioStorageClient()
    with pytest.raises(StorageClientError):
        client.ensure_bucket()


def test_minio_upload_bytes_success() -> None:
    """成功上传应返回 public_url 拼接的访问地址."""
    fake_minio = MagicMock()
    fake_minio.bucket_exists.return_value = True
    fake_endpoint = MagicMock()
    fake_endpoint.url.netloc = "minio.local:9000"
    fake_minio._endpoint = fake_endpoint
    with _patch_minio(fake_minio), patch("app.storage.get_settings") as mock_settings:
        mock_settings.return_value.minio_endpoint = "minio.local:9000"
        mock_settings.return_value.minio_access_key = "ak"
        mock_settings.return_value.minio_secret_key = "sk"
        mock_settings.return_value.minio_bucket = "reports"
        mock_settings.return_value.minio_public_url = "https://cdn.example.com"
        client = MinioStorageClient()
    url = client.upload_bytes("x.pdf", b"abc", content_type="application/pdf")
    assert url == "https://cdn.example.com/reports/x.pdf"
    fake_minio.put_object.assert_called_once()


def test_minio_upload_bytes_uses_endpoint_as_fallback() -> None:
    """未配置 public_url 时应回退到 endpoint 拼装."""
    fake_minio = MagicMock()
    fake_minio.bucket_exists.return_value = True
    fake_endpoint = MagicMock()
    fake_endpoint.url.netloc = "minio.local:9000"
    fake_minio._endpoint = fake_endpoint
    with _patch_minio(fake_minio), patch("app.storage.get_settings") as mock_settings:
        mock_settings.return_value.minio_endpoint = "minio.local:9000"
        mock_settings.return_value.minio_access_key = "ak"
        mock_settings.return_value.minio_secret_key = "sk"
        mock_settings.return_value.minio_bucket = "reports"
        mock_settings.return_value.minio_public_url = ""
        client = MinioStorageClient()
    url = client.upload_bytes("x.pdf", b"abc")
    assert url == "http://minio.local:9000/reports/x.pdf"


def test_minio_upload_s3_error_raises() -> None:
    """S3Error 应被包装为 StorageClientError."""
    from minio.error import S3Error

    fake_minio = MagicMock()
    fake_minio.bucket_exists.return_value = True
    fake_minio.put_object.side_effect = S3Error("x", "x", "x", "x", "x", "x")  # type: ignore[arg-type]
    with _patch_minio(fake_minio), patch("app.storage.get_settings") as mock_settings:
        mock_settings.return_value.minio_endpoint = "minio.local:9000"
        mock_settings.return_value.minio_access_key = "ak"
        mock_settings.return_value.minio_secret_key = "sk"
        mock_settings.return_value.minio_bucket = "b"
        mock_settings.return_value.minio_public_url = ""
        client = MinioStorageClient()
    with pytest.raises(StorageClientError):
        client.upload_bytes("k", b"v")


def test_minio_download_bytes_success() -> None:
    """成功下载应返回字节内容并释放连接."""
    fake_response = MagicMock()
    fake_response.read.return_value = b"hello"
    fake_minio = MagicMock()
    fake_minio.bucket_exists.return_value = True
    fake_minio.get_object.return_value = fake_response
    with _patch_minio(fake_minio), patch("app.storage.get_settings") as mock_settings:
        mock_settings.return_value.minio_endpoint = "minio.local:9000"
        mock_settings.return_value.minio_access_key = "ak"
        mock_settings.return_value.minio_secret_key = "sk"
        mock_settings.return_value.minio_bucket = "b"
        mock_settings.return_value.minio_public_url = ""
        client = MinioStorageClient()
    result = client.download_bytes("x.txt")
    assert result == b"hello"
    fake_response.close.assert_called_once()
    fake_response.release_conn.assert_called_once()


def test_minio_download_s3_error_raises() -> None:
    """下载 S3Error 应被包装."""
    from minio.error import S3Error

    fake_minio = MagicMock()
    fake_minio.bucket_exists.return_value = True
    fake_minio.get_object.side_effect = S3Error("x", "x", "x", "x", "x", "x")  # type: ignore[arg-type]
    with _patch_minio(fake_minio), patch("app.storage.get_settings") as mock_settings:
        mock_settings.return_value.minio_endpoint = "minio.local:9000"
        mock_settings.return_value.minio_access_key = "ak"
        mock_settings.return_value.minio_secret_key = "sk"
        mock_settings.return_value.minio_bucket = "b"
        mock_settings.return_value.minio_public_url = ""
        client = MinioStorageClient()
    with pytest.raises(StorageClientError):
        client.download_bytes("x.txt")


# ------------------------------------------------------------------
# get_storage_client
# ------------------------------------------------------------------


def test_get_storage_client_local_default() -> None:
    """默认 backend=local 应返回 LocalStorageClient."""
    with patch("app.storage.get_settings") as mock_settings, \
         patch("app.storage.LocalStorageClient") as fake_local:
        mock_settings.return_value.storage_backend = "local"
        get_storage_client.cache_clear()
        get_storage_client()
    fake_local.assert_called_once()
    get_storage_client.cache_clear()


def test_get_storage_client_minio_backend() -> None:
    """backend=minio 应返回 MinioStorageClient."""
    with patch("app.storage.get_settings") as mock_settings, \
         patch("app.storage.MinioStorageClient") as fake_minio:
        mock_settings.return_value.storage_backend = "minio"
        get_storage_client.cache_clear()
        get_storage_client()
    fake_minio.assert_called_once()
    get_storage_client.cache_clear()


def test_base_storage_client_abstract_methods_raise() -> None:
    """基类抽象方法应抛 NotImplementedError."""

    class _Impl(BaseStorageClient):
        pass

    with pytest.raises(TypeError):
        # 抽象类不能直接实例化
        _Impl()  # type: ignore[abstract]
