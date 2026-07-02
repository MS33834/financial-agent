# 监控与告警

## 健康检查端点

后端健康检查路由挂载在 `/health` 下（无 `/api/v1` 前缀；若网关统一加前缀，则实际路径为 `/api/v1/health*`）：

| 端点 | 说明 |
|------|------|
| `GET /health` | 服务存活，返回 `BaseResponse`（`code=0, message=ok`） |
| `GET /health/live` | 存活探针（liveness），仅校验进程可响应 |
| `GET /health/ready` | 就绪探针（readiness），检查 DB / Redis / MinIO，任一不可用返回 HTTP 503 |
| `GET /metrics` | Prometheus 指标 |

各端点的返回结构与 Kubernetes 探针配置见 [deployment.md](./deployment.md#健康检查端点) 的「健康检查端点」一节。

## Prometheus 指标

后端已内置 `prometheus-client`，暴露以下指标：

### HTTP 与进程指标

- `fa_http_requests_total`：HTTP 请求总量与耗时分布（按 method/path/status_code）
- `fa_process_*`：进程级指标（CPU、内存、打开文件数等）

### Celery 任务指标

| 指标名 | 类型 | 标签 | 含义 |
|--------|------|------|------|
| `fa_task_runs_total` | Counter | `task_name` | 任务开始执行总数 |
| `fa_task_success_total` | Counter | `task_name` | 任务成功总数 |
| `fa_task_failures_total` | Counter | `task_name` | 任务最终失败总数（重试不算） |
| `fa_task_retries_total` | Counter | `task_name` | 任务重试次数 |
| `fa_task_duration_seconds` | Histogram | `task_name` | 任务执行耗时分布 |

### 队列与错误指标

| 指标名 | 类型 | 标签 | 含义 |
|--------|------|------|------|
| `fa_queue_length` | Gauge | `queue_name` | Redis broker 中各队列当前深度 |
| `fa_errors_classified_total` | Counter | `error_category` | 错误自省服务分类后的错误数，类别包括 `retryable`/`business`/`config`/`security`/`unknown` |

### 业务操作指标

| 指标名 | 类型 | 标签 | 含义 |
|--------|------|------|------|
| `fa_business_operations_total` | Counter | `operation` | 业务操作次数，目前包括 `document_created`、`report_created`、`approval_approve`、`approval_reject`、`approval_modify` |

## 示例 Prometheus 配置

```yaml
scrape_configs:
  - job_name: "financial-agent-backend"
    static_configs:
      - targets: ["backend:8000"]
    metrics_path: "/metrics"
    scrape_interval: 15s
```

## Grafana 看板

- 看板模板：[grafana-dashboard.json](./grafana-dashboard.json)
- 导入方式：Grafana UI → Dashboards → Import → 上传 JSON 文件
- 数据源：选择已配置的 Prometheus

## 建议告警规则

```yaml
groups:
  - name: financial-agent
    rules:
      - alert: FinancialAgentTaskFailureRateHigh
        expr: |
          sum(rate(fa_task_failures_total[5m]))
            /
          sum(rate(fa_task_runs_total[5m])) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Financial Agent 任务失败率过高"
          description: "过去 5 分钟任务失败率超过 5%，请检查 Celery Worker 与依赖服务。"

      - alert: FinancialAgentQueueDepthHigh
        expr: fa_queue_length > 100
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Financial Agent 队列堆积"
          description: "队列 {{ $labels.queue_name }} 当前深度 {{ $value }}，Consumer 可能不足。"

      - alert: FinancialAgentErrorsSpike
        expr: |
          sum(rate(fa_errors_classified_total[5m]))
            >
          5 * avg_over_time(sum(rate(fa_errors_classified_total[1h]))[1h:5m])
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Financial Agent 错误数突增"
          description: "错误分类计数较近期均值显著上升，请检查业务异常与外部依赖。"

      - alert: FinancialAgentHighLatency
        expr: histogram_quantile(0.95, sum(rate(fa_http_requests_total_bucket[5m])) by (le)) > 3
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Financial Agent P95 响应时间过高"

      - alert: FinancialAgent5xxRateHigh
        expr: |
          sum(rate(fa_http_requests_total_count{status_code=~"5.."}[5m]))
            /
          sum(rate(fa_http_requests_total_count[5m])) > 0.01
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Financial Agent 5xx 错误率超过 1%"
```

## 安全加固

- `/metrics` 不进入 API 文档
- 生产环境建议通过 Nginx/网关限制 `/metrics` 仅允许监控网络访问

## 日志收集

后端使用结构化日志（JSON），便于日志聚合系统采集。建议生产环境接入集中式日志平台：

### 推荐方案：Loki + Promtail

```yaml
# promtail-config.yml 片段
scrape_configs:
  - job_name: financial-agent
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        filters:
          - name: label
            values: ["com.docker.compose.project=financial-agent"]
    pipeline_stages:
      - json:
          expressions:
            level: level
            request_id: request_id
            event: event
      - labels:
          level:
          event:
```

- 日志查询示例（LogQL）：`{container="financial-agent-backend"} |= "unhandled_exception"`
- 通过 `X-Request-ID` 串联单次请求的全链路日志。

### 备选方案

ELK（Elasticsearch + Logstash + Kibana）或云厂商日志服务（阿里云 SLS / AWS CloudWatch）亦可，采集容器 stdout 即可，无需修改应用代码。

## Alertmanager 路由建议

Prometheus 告警触发后经 Alertmanager 路由分发，建议按 severity 分级：

| severity | 接收渠道 | 响应时效 |
|----------|----------|----------|
| `critical` | 钉钉/飞书机器人 + 电话值班 | 15 分钟内 |
| `warning` | 钉钉/飞书机器人 | 1 小时内 |

Alertmanager 路由示例：

```yaml
route:
  receiver: default
  group_by: ["alertname", "severity"]
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
routes:
  - matchers: ["severity=critical"]
    receiver: critical-pager
  - matchers: ["severity=warning"]
    receiver: warning-channel
receivers:
  - name: critical-pager
    webhook_configs:
      - url: "https://oapi.dingtalk.com/robot/send?access_token=<critical-token>"
        send_resolved: true
  - name: warning-channel
    webhook_configs:
      - url: "https://oapi.dingtalk.com/robot/send?access_token=<warning-token>"
        send_resolved: true
```

## Grafana 看板变量

导入看板后建议配置以下变量以便多维度筛选：

- `$datasource`：选择 Prometheus 数据源
- `$job`：`label_values(fa_http_requests_total, job)`，默认 `financial-agent-backend`
- `$status_code`：`label_values(fa_http_requests_total, status_code)`，用于按 HTTP 状态码筛选
