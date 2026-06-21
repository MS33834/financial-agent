"""启动本地服务并运行性能基线测试。"""

import os
import subprocess
import sys
import time

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///./bench.db")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("SECRET_KEY", "bench-secret-key-32-char-long-xx")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
os.environ.setdefault("MINIO_ACCESS_KEY", "bench")
os.environ.setdefault("MINIO_SECRET_KEY", "bench12345678")


def main() -> int:
    # 重新初始化演示数据
    subprocess.run(
        [sys.executable, "scripts/seed_demo_data.py"],
        cwd="/workspace/financial-agent/backend",
        check=True,
    )

    # 启动 uvicorn
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd="/workspace/financial-agent/backend",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # 等待服务就绪
    deadline = time.time() + 30
    ready = False
    while time.time() < deadline:
        try:
            import httpx

            resp = httpx.get("http://127.0.0.1:8000/health", timeout=2)
            if resp.status_code == 200:
                ready = True
                break
        except Exception:
            pass
        time.sleep(0.5)

    if not ready:
        proc.terminate()
        print(proc.communicate(timeout=5)[0])
        print("Server did not start")
        return 1

    try:
        result = subprocess.run(
            [sys.executable, "scripts/benchmark.py", "http://127.0.0.1:8000"],
            cwd="/workspace/financial-agent/backend",
        )
        return result.returncode
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
