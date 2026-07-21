# 并发评测 Task 4 实现报告

日期：2026-07-21

## 实现范围

本任务新增智谱上游评测目标 `ZhipuTarget`，没有改动 Task 1–3 的接口。目标使用固定的短、长提示词，请求模型默认为 `glm-4.5-flash`，关闭思考模式，单次请求超时沿用评测框架的 120 秒常量。

适配器最多尝试 5 次。HTTP 429、响应错误码 1305、超时和连接类异常会按 2、4、8、16 秒退避；最后一次失败后返回 `RequestRecord`，不向阶梯执行器抛出请求异常。普通非 JSON 响应直接记为 `non_json_response`。记录中只保留状态码、归一化错误码、耗时和字符数，不保存请求头、响应正文、异常原文或 API key。

本轮只使用 fake Session 和测试密钥，没有发出网络请求，也没有读取环境变量中的真实密钥。

## TDD 记录

RED 命令：

```powershell
py -m pytest tests/test_concurrency_upstream.py -v
```

首次运行在测试收集阶段失败，错误为：

```text
ModuleNotFoundError: No module named 'research_eval.concurrency.upstream'
```

GREEN 命令相同。实现后结果为 `10 passed`，耗时 0.49 秒。

Task 1–4 回归命令：

```powershell
py -m pytest tests/test_concurrency_metrics.py tests/test_concurrency_runner.py tests/test_concurrency_resources.py tests/test_concurrency_upstream.py -v
```

结果为 `52 passed`，耗时 1.02 秒。

## 修改文件

- `research_eval/concurrency/upstream.py`
- `tests/test_concurrency_upstream.py`
- `.superpowers/sdd/concurrency-task-4-report.md`

## 已覆盖的行为

- 429 与 1305 的识别和重试计数；
- 5 次尝试上限及 2、4、8、16 秒退避；
- 超时、连接失败、其他 Requests 异常和非 JSON 响应；
- 短、长请求的 payload、token 上限、认证头和 120 秒 timeout；
- API key 及异常原文不进入 `RequestRecord`；
- 非法请求类型在发起调用前被拒绝。

## 风险与后续边界

当前证据只说明离线适配逻辑符合测试契约，不能说明智谱线上接口可用，也不能据此判断并发容量。真实 smoke 测试仍须执行计划 Task 8 的审批门禁。响应解析目前按智谱聊天补全接口的 JSON 结构实现；若服务端字段发生变化，调用会被记为 `invalid_response`，不会误报成功。

提交 SHA 以代理最终交接信息为准。
