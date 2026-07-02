# 管理员操作手册

## 部署

参见 [docs/ops/deployment.md](./ops/deployment.md)。

## 用户与权限

系统内置四种角色：

- `admin`：系统管理员，可管理用户、策略、审计日志。
- `finance_manager`：可上传文档、生成报告、审批报告。
- `auditor`：审计员，可查看审计日志、IM 用户映射、错误自省记录，但不可修改业务数据。
- `viewer`：只读用户，可查看报告、使用智能问答。

可通过数据库或管理接口创建用户。角色与接口权限的映射通过 ABAC（属性访问控制）策略实现，详见「访问策略」管理页面与 [deployment.md](./ops/deployment.md#配置热加载) 中的配置热加载说明。

## 监控

- Prometheus 指标：`/metrics`
- 健康检查：`/health`、`/health/live`、`/health/ready`
- Grafana 看板模板：[docs/ops/grafana-dashboard.json](./ops/grafana-dashboard.json)
- 详细指标、告警规则与日志收集见 [docs/ops/monitoring.md](./ops/monitoring.md)

## 告警建议

| 规则 | 阈值 | 级别 |
|------|------|------|
| health 失败 | 连续 3 次 | P1 |
| P95 响应时间 | > 3s 持续 5 分钟 | P2 |
| 5xx 错误率 | > 1% 持续 5 分钟 | P1 |
| 内存使用率 | > 80% | P2 |

## 安全加固

- 生产环境修改 `SECRET_KEY`（≥32 字符随机值）和数据库密码。
- 限制 `/metrics` 仅允许监控网络访问。
- 启用 HTTPS 并配置 `CORS_ORIGINS` 为具体前端域名（禁止 `*`）。
- 启用速率限制（`RATE_LIMIT_ENABLED=true`）。
- 配置 ABAC 访问策略，按角色 / 资源 / 操作粒度授权。
- 启用审计日志并持久化（默认开启，存储于数据库 `audit_logs` 表）。

完整的上线前检查项见 [deployment.md 的生产环境检查清单](./ops/deployment.md#生产环境检查清单)。

## 备份

- 数据库：使用 PostgreSQL 原生备份工具 pg_dump。
- 文件：MinIO / S3 对象存储提供多副本或异地备份。

## 性能基线

```bash
cd backend
python scripts/run_benchmark_with_server.py
```

目标：所有接口 P95 < 3s。
