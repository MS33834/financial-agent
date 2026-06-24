"""集成测试：真实 MinIO 存储客户端.

本测试需要在本地启动 MinIO 服务，典型运行方式见：
  tests/integration/run_integration_tests.sh
"""

import uuid

import pytest

from app.storage import StorageClient, StorageClientError


@pytest.fixture
def storage() -> StorageClient:
    """使用环境变量配置的真实 StorageClient 实例."""
    client = StorageClient()
    client.ensure_bucket()
    return client


class TestStorageIntegration:
    """StorageClient 真实 MinIO 集成测试."""

    def test_upload_and_download_roundtrip(self, storage: StorageClient) -> None:
        """上传后应能原样下载."""
        key = f"integration-test/{uuid.uuid4().hex}.txt"
        content = b"hello integration test"

        url = storage.upload_bytes(key, content, content_type="text/plain")
        assert url.endswith(f"/{storage.bucket}/{key}")

        downloaded = storage.download_bytes(key)
        assert downloaded == content

    def test_upload_with_metadata(self, storage: StorageClient) -> None:
        """上传带元数据的对象."""
        key = f"integration-test/{uuid.uuid4().hex}.txt"
        content = b"with metadata"

        url = storage.upload_bytes(
            key, content, content_type="text/plain", metadata={"tenant-id": "t1"}
        )
        assert storage.bucket in url

        downloaded = storage.download_bytes(key)
        assert downloaded == content

    def test_download_missing_object_raises(self, storage: StorageClient) -> None:
        """下载不存在的对象应抛出 StorageClientError."""
        key = f"integration-test/{uuid.uuid4().hex}-missing.txt"
        with pytest.raises(StorageClientError):
            storage.download_bytes(key)
