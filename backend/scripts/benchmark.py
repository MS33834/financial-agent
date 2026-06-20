"""轻量性能基线测试脚本.

用于验证后端关键接口的响应时间，不依赖复杂压测工具。
建议在本机或测试环境运行，避免影响生产。
"""

import sys
import time

import httpx

# 测试接口列表（路径、方法、预期状态码）
ENDPOINTS = [
    ("/api/v1/health", "GET", 200),
    ("/api/v1/health/ready", "GET", 200),
    ("/metrics", "GET", 200),
]


def run_benchmark(base_url: str, requests_per_endpoint: int = 10) -> dict[str, float]:
    """对每个端点发起多次请求，返回 P95 耗时."""
    results: dict[str, float] = {}
    with httpx.Client(base_url=base_url, timeout=10) as client:
        for path, method, expected_status in ENDPOINTS:
            latencies: list[float] = []
            for _ in range(requests_per_endpoint):
                start = time.perf_counter()
                response = client.request(method, path)
                elapsed = time.perf_counter() - start
                latencies.append(elapsed)
                if response.status_code != expected_status:
                    print(f"FAIL {method} {path}: {response.status_code}")
                    sys.exit(1)
            latencies.sort()
            p95 = latencies[int(len(latencies) * 0.95)]
            results[path] = p95
            print(f"{method} {path}: P95={p95:.3f}s")
    return results


def main() -> None:
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    print(f"Benchmarking {base_url} ...")
    results = run_benchmark(base_url)

    # MVP 验收标准：简单查询 < 3s
    failed = [path for path, p95 in results.items() if p95 > 3.0]
    if failed:
        print(f"\nFAILED: P95 > 3s for {failed}")
        sys.exit(1)
    print("\nAll endpoints meet P95 < 3s baseline.")


if __name__ == "__main__":
    main()
