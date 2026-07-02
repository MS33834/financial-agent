"""OpenTelemetry 链路追踪模块测试.

tracing.py 通过 ``_OTEL_AVAILABLE`` 标志位做软依赖降级，单元测试覆盖三种情况：
1) otel 未安装：所有函数为 no-op；
2) otel 已安装但未提供 endpoint：仅记录日志不执行 set_tracer_provider；
3) otel 已安装且提供 endpoint：配置 TracerProvider 并标记已初始化。

注：sandbox 中未安装 opentelemetry，因此通过向模块注入 stub 模块来模拟"已安装"路径。
"""

# mypy: disable-error-code="attr-defined"

import types
from collections.abc import Generator

import pytest


@pytest.fixture
def with_otel_installed() -> Generator[None, None, None]:
    """向 app.tracing 模块注入 otel 子模块 stub，模拟 otel 已安装."""
    import app.tracing as tracing_mod

    # 在模块上挂载 otel 名称空间 stub
    class _FakeTrace:
        @staticmethod
        def set_tracer_provider(provider: object) -> None:
            _FakeTrace.last = provider

        last: object | None = None

    fake_trace = _FakeTrace()
    tracing_mod.trace = fake_trace

    fake_resource = types.SimpleNamespace()
    fake_resource.create = lambda attrs: ("resource", attrs)
    tracing_mod.Resource = fake_resource

    class _FakeProvider:
        def __init__(self, resource: object) -> None:
            self.resource = resource
            self.processors: list[object] = []

        def add_span_processor(self, processor: object) -> None:
            self.processors.append(processor)

    class _FakeTracerProvider:
        instances: list["_FakeTracerProvider"] = []

        def __init__(self, resource: object) -> None:
            self.resource = resource
            self.processors: list[object] = []
            type(self).instances.append(self)

        def add_span_processor(self, processor: object) -> None:
            self.processors.append(processor)

    class _FakeExporter:
        def __init__(self, endpoint: str) -> None:
            self.endpoint = endpoint

    class _FakeBatchSpanProcessor:
        def __init__(self, exporter: object) -> None:
            self.exporter = exporter

    class _FakeFastAPIInstrumentor:
        @staticmethod
        def instrument_app(app: object) -> None:
            pass

    tracing_mod.TracerProvider = _FakeTracerProvider
    tracing_mod.OTLPSpanExporter = _FakeExporter
    tracing_mod.BatchSpanProcessor = _FakeBatchSpanProcessor
    tracing_mod.FastAPIInstrumentor = _FakeFastAPIInstrumentor

    # 重置单例状态
    tracing_mod._OTEL_AVAILABLE = True
    tracing_mod._TRACING_INITIALIZED = False
    _FakeTracerProvider.instances = []

    try:
        yield
    finally:
        # 清理
        tracing_mod._OTEL_AVAILABLE = False
        tracing_mod._TRACING_INITIALIZED = False
        for attr in (
            "trace",
            "Resource",
            "TracerProvider",
            "OTLPSpanExporter",
            "BatchSpanProcessor",
            "FastAPIInstrumentor",
        ):
            if hasattr(tracing_mod, attr):
                delattr(tracing_mod, attr)


def test_setup_tracing_skips_when_otel_not_installed() -> None:
    """otel 未安装时 setup_tracing 应仅记录日志并返回."""
    import app.tracing as tracing_mod

    assert tracing_mod._OTEL_AVAILABLE is False
    tracing_mod.setup_tracing("app", otlp_endpoint="http://otel:4318/v1/traces")
    assert tracing_mod._TRACING_INITIALIZED is False


def test_setup_tracing_skips_when_endpoint_missing(with_otel_installed: None) -> None:
    """otel 已安装但未提供 endpoint 时应跳过配置."""
    import app.tracing as tracing_mod

    tracing_mod.setup_tracing("app", otlp_endpoint=None)
    assert tracing_mod._TRACING_INITIALIZED is False

    tracing_mod.setup_tracing("app", otlp_endpoint="")
    assert tracing_mod._TRACING_INITIALIZED is False


def test_setup_tracing_full_path(with_otel_installed: None) -> None:
    """otel + endpoint 齐备时应完成 provider/exporter 配置."""
    import app.tracing as tracing_mod

    tracing_mod.setup_tracing("svc-name", otlp_endpoint="http://otel:4318/v1/traces")

    # 验证 TracerProvider 被创建并配置
    assert len(tracing_mod.TracerProvider.instances) == 1
    provider = tracing_mod.TracerProvider.instances[0]
    # Resource.create 被调用过，参数为 {service.name: ...}
    assert provider.resource == ("resource", {"service.name": "svc-name"})
    # add_span_processor 被调用
    assert len(provider.processors) == 1
    assert provider.processors[0].exporter.endpoint == "http://otel:4318/v1/traces"
    assert tracing_mod._TRACING_INITIALIZED is True


def test_setup_tracing_skips_when_already_initialized(with_otel_installed: None) -> None:
    """重复调用时不应再次执行配置."""
    import app.tracing as tracing_mod

    tracing_mod.setup_tracing("svc", otlp_endpoint="http://x")
    assert len(tracing_mod.TracerProvider.instances) == 1

    # 第二次调用：不应再创建 provider
    tracing_mod.setup_tracing("svc", otlp_endpoint="http://x")
    assert len(tracing_mod.TracerProvider.instances) == 1
    assert tracing_mod._TRACING_INITIALIZED is True


def test_instrument_fastapi_no_op_when_otel_missing() -> None:
    """otel 未安装时 instrument_fastapi 为空操作."""
    import app.tracing as tracing_mod

    assert tracing_mod._OTEL_AVAILABLE is False
    # 不应抛异常
    tracing_mod.instrument_fastapi(object())


def test_instrument_fastapi_when_otel_available(with_otel_installed: None) -> None:
    """otel 已安装时 instrument_fastapi 应被调用（不抛异常即可）."""
    import app.tracing as tracing_mod

    # _FakeFastAPIInstrumentor.instrument_app 是 no-op，不会抛异常
    tracing_mod.instrument_fastapi(object())


def test_module_exposes_availability_flag() -> None:
    """_OTEL_AVAILABLE 标志位在导入后存在且为 bool."""
    import app.tracing as tracing_mod

    assert isinstance(tracing_mod._OTEL_AVAILABLE, bool)
    # 模块导出 setup_tracing 与 instrument_fastapi
    assert callable(tracing_mod.setup_tracing)
    assert callable(tracing_mod.instrument_fastapi)
