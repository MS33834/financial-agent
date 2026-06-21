"""轻量性能基线测试脚本.

用于验证后端关键接口的响应时间，不依赖复杂压测工具。
建议在本机或测试环境运行，避免影响生产。
"""

import os
import sys
import time

import httpx

BASELINE_SECONDS = 3.0


def login(client: httpx.Client, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    if response.status_code != 200:
        print(f"Login failed: {response.status_code} {response.text}")
        sys.exit(1)
    return response.json()["data"]["access_token"]


def run_benchmark(
    client: httpx.Client,
    endpoints: list[tuple[str, str, int, dict | None]],
    requests_per_endpoint: int = 10,
) -> dict[str, float]:
    """对每个端点发起多次请求，返回 P95 耗时."""
    results: dict[str, float] = {}
    for path, method, expected_status, json_body in endpoints:
        latencies: list[float] = []
        for _ in range(requests_per_endpoint):
            start = time.perf_counter()
            response = client.request(method, path, json=json_body)
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)
            if response.status_code != expected_status:
                print(f"FAIL {method} {path}: {response.status_code} {response.text}")
                sys.exit(1)
        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)] or latencies[-1]
        results[path] = p95
        print(f"{method} {path}: P95={p95:.3f}s")
    return results


def main() -> None:
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    username = os.getenv("BENCH_USERNAME", "demo_admin")
    password = os.getenv("BENCH_PASSWORD", "demo123")
    requests_per_endpoint = int(os.getenv("BENCH_REQUESTS", "10"))

    public_endpoints = [
        ("/health", "GET", 200, None),
        ("/health/ready", "GET", 200, None),
        ("/metrics", "GET", 200, None),
    ]

    print(f"Benchmarking {base_url} ...")
    with httpx.Client(base_url=base_url, timeout=30) as client:
        results = run_benchmark(client, public_endpoints, requests_per_endpoint)

        token = login(client, username, password)
        headers = {"Authorization": f"Bearer {token}"}
        with httpx.Client(base_url=base_url, timeout=30, headers=headers) as auth_client:
            auth_endpoints = [
                ("/api/v1/auth/me", "GET", 200, None),
                ("/api/v1/queries/nl2sql", "POST", 200, {"question": "2025 年 Q1 净利润是多少"}),
                ("/api/v1/reports", "GET", 200, None),
                ("/api/v1/documents", "GET", 200, None),
                ("/api/v1/approvals", "GET", 200, None),
                ("/api/v1/audit/logs", "GET", 200, None),
            ]
            auth_results = run_benchmark(auth_client, auth_endpoints, requests_per_endpoint)
            results.update(auth_results)

    failed = [path for path, p95 in results.items() if p95 > BASELINE_SECONDS]
    if failed:
        print(f"\nFAILED: P95 > {BASELINE_SECONDS}s for {failed}")
        sys.exit(1)
    print(f"\nAll endpoints meet P95 < {BASELINE_SECONDS}s baseline.")


if __name__ == "__main__":
    main()
