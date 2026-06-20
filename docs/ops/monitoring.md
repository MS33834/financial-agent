# 监控与告警

## 健康检查端点

| 端点 | 说明 |
|------|------|
| `GET /api/v1/health` | 服务存活 |
| `GET /api/v1/health/ready` | 服务就绪 |
| `GET /metrics` | Prometheus 指标 |

## Prometheus 指标

后端已内置 `prometheus-client`，暴露以下指标：

- `fa_http_requests_total`：HTTP 请求总量与耗时分布（按 method/path/status_code）
- `fa_process_*`：进程级指标（CPU、内存、打开文件数等）

## 示例 Prometheus 配置

```yaml
scrape_configs:
  - job_name: "financial-agent-backend"
    static_configs:
      - targets: ["backend:8000"]
    metrics_path: "/metrics"
    scrape_interval: 15s
```

## 建议告警规则

| 规则 | 阈值 | 级别 |
|------|------|------|
| 后端 health 失败 | 连续 3 次 | P1 |
| P95 响应时间 | > 3s 持续 5 分钟 | P2 |
| 5xx 错误率 | > 1% 持续 5 分钟 | P1 |
| 容器内存使用率 | > 80% | P2 |

## 安全加固

- `/metrics` 不进入 API 文档
- 生产环境建议通过 Nginx/网关限制 `/metrics` 仅允许监控网络访问
