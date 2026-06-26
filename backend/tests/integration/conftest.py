"""集成测试共享配置.

集成测试需要真实数据库连接等外部依赖，默认在普通测试运行时跳过，
仅当通过 ``pytest -m integration`` 显式启用时才执行。
"""

from __future__ import annotations

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """未显式选择 integration 标记时，自动跳过集成测试.

    通过 ``pytest -m integration`` 启用；其余运行方式（含默认全量运行）
    一律跳过，避免在无外部依赖的环境下产生误报。
    """
    markexpr = config.getoption("markexpr") or ""
    # 当 -m 表达式中显式包含 integration 时放行，交由 pytest 的 marker 过滤处理
    if "integration" in markexpr:
        return

    skip = pytest.mark.skip(
        reason="集成测试默认跳过；使用 `pytest -m integration` 显式启用"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
