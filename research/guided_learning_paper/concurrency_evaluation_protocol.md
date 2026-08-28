# 三阶段引导式学习并发评测运行协议

## 1. 适用范围

本协议用于评估两条工程链路：一是智谱接口本身的响应表现，二是从 CodeSense 登录、业务路由到模型调用的完整 HTTP 链路。结果只能说明特定部署、特定模型和特定时段下的工程性能，不证明学习效果，也不能据此推断教学优越性。

仿真学生和仿真教师不属于本协议。本协议不会生成虚拟学习结果。

## 2. 执行前提

所有外部测试都由操作人员手动启动。满足以下条件后才可运行：

- 已获得本次外部调用的明确批准，并约定低峰期；
- 平台测试只使用名称以 `research_load_` 开头的专用测试账号；
- 选用已配置完整 ready preset 的专用作业，不使用正在授课的作业；
- 已确认无正在进行的课程、考试或教师演示；
- 已备份运行所需配置，但凭据、Cookie、API key 和完整 Authorization 头不写入仓库或结果目录；
- 已确定一名操作人员观察服务日志，并能随时按 Ctrl+C 中止。

第一次平台 canary 的最高并发 8。没有审阅 canary 日志前，不得使用 `--allow-validated-ramp`。

## 3. 停止条件

工具在下列任一情况出现时停止后续阶梯：错误率超过 5%，429/1305 比例超过 10%，P95 超过 60 秒，出现 502、504 或 worker timeout，CPU 或内存连续 30 秒高于 90%，以及操作人员中断。停止后的记录仍应保留，不得删去失败轮次或只报告表现较好的重复实验。

如果预热请求失败，正式轮次不会启动。此时先排查账号、CSRF、反向代理、模型配置和网络状态，不要直接扩大并发。

## 4. 执行顺序

### 4.1 离线检查

离线检查不会登录平台，也不会调用智谱：

```powershell
py -m pytest tests/test_concurrency_*.py -q
py scripts/run_guided_learning_concurrency.py --help
```

确认测试通过后，检查环境变量是否存在即可，不要在终端打印密钥值。外部测试需再次取得用户批准。

### 4.2 智谱上游烟雾测试

这一步会产生真实智谱请求，用于确认认证、模型和结果写入链路。命令固定为：

```powershell
py scripts/run_guided_learning_concurrency.py --mode upstream --request-kind short --levels 1,2 --requests-per-level 3 --output-dir research/guided_learning_paper/experiments/concurrency/smoke
```

烟雾测试完成后检查 `run_config.json`、`raw_requests.jsonl` 和 `level_summary.csv`。若出现认证错误、限流或响应结构变化，停止后续测试。

### 4.3 平台 canary

先确认 CodeSense 服务状态正常、没有真实学生使用，再执行：

```powershell
py scripts/run_guided_learning_concurrency.py --mode platform --request-kind short --levels 1,2,4,8 --requests-per-level 20 --base-url http://127.0.0.1:5000 --credentials-file /var/www/codesense/research_load_users.json --assignment-id 85 --output-dir research_exports/concurrency/canary
```

命令中的 `85` 只是占位值。执行时必须替换为现场选定、使用专用 ready preset 的作业 ID。canary 结束后核对应用日志、Gunicorn 日志、反向代理日志和资源采样 CSV，确认没有账号串用、重定向、CSRF、网关错误或持续高资源占用。

### 4.4 经验证的升阶测试

只有在 canary 日志已审阅、停止条件均未触发，并再次确认无正在进行的课程后，才可执行完整阶梯：

```powershell
py scripts/run_guided_learning_concurrency.py --mode platform --request-kind long --levels 1,2,4,8,16,24,32 --requests-per-level 20 --allow-validated-ramp --base-url http://127.0.0.1:5000 --credentials-file /var/www/codesense/research_load_users.json --assignment-id 85 --output-dir research_exports/concurrency/validated
```

这里的 `85` 同样必须替换。参数 `--allow-validated-ramp` 只表示操作人员完成了 canary 审阅，不代表系统已经具备 32 并发能力。工具仍会按停止条件提前终止。

短请求、长请求应分开运行。混合负载只作为补充，在二者均完成后使用 `--request-kind mixed`，其请求比例固定为 60% 短请求、40% 长请求。

## 5. 结果核验

每个正式结果目录至少应包含：

- `run_config.json`：运行环境、参数和状态；
- `raw_requests.jsonl`：逐请求记录；
- `level_summary.csv`：按轮次和并发档位汇总；
- 三张 200 DPI 图片；
- 按轮次和档位拆分的资源采样 CSV。

核验时保留三个重复轮次，不先合并原始请求。图中只画实际测得的并发点，不向停止档位以外外推。若使用 `--overwrite`，先人工确认目标目录；不要覆盖需要审计的既有正式结果。

## 6. 论文表述边界

可以报告吞吐量、延迟分位数、错误率、限流率、重试率和资源占用，并写明测试时间、模型、部署配置、请求类型与停止档位。不得把离线 fake target 的输出写成线上性能，也不得把工程并发结果解释为学习增益、认知负荷改善或框架优越性的证据。
