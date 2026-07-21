# 并发评测 Task 4 实现报告

日期：2026-07-21

## 实现范围

本任务新增智谱上游评测目标 `ZhipuTarget`，没有改动 Task 1–3 的接口。目标使用固定的短、长提示词，请求模型默认为 `glm-4.5-flash`，关闭思考模式，单次请求超时沿用评测框架的 120 秒常量。

适配器只对 HTTP 429 和响应错误码 1305 重试，最多尝试 5 次，退避时间为 2、4、8、16 秒。超时、连接失败和其他 Requests 异常只请求一次，不等待、不重试。失败会转换成 `RequestRecord`，不会把请求异常抛给阶梯执行器。

`error_code` 采用严格允许列表：成功时为空，1305 限流保留为 `1305`，其余失败统一记为 `upstream_error`。HTTP 状态码单独保留。记录不包含请求头、响应正文、异常原文或 API key。

默认模式和 `session_factory` 模式通过 `threading.local` 为每个工作线程保存独立 Session，不使用包围 `post()` 的全局锁。原有单 Session 构造方式只作为串行测试兼容入口保留。

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
- 超时、连接失败和其他 Requests 异常均只请求一次；
- 非 JSON 响应和任意服务端错误码的允许列表映射；
- 短、长请求的 payload、token 上限、认证头和 120 秒 timeout；
- API key 及异常原文不进入 `RequestRecord`；
- 每个并发工作线程使用不同 Session，两个 `post()` 可并行进入；
- 非法请求类型在发起调用前被拒绝。

## 风险与后续边界

当前证据只说明离线适配逻辑符合测试契约，不能说明智谱线上接口可用，也不能据此判断并发容量。真实 smoke 测试仍须执行计划 Task 8 的审批门禁。响应解析目前按智谱聊天补全接口的 JSON 结构实现；若服务端字段发生变化，调用会被记为 `invalid_response`，不会误报成功。

提交 SHA 以代理最终交接信息为准。

## 审查修复记录

审查指出三个问题：传输异常被重复请求，服务端 code 会原样进入结果，共享 Session 不符合并发评测的线程隔离要求。

先修改测试，再运行：

```powershell
py -m pytest tests/test_concurrency_upstream.py -v
```

RED 结果为 `8 failed, 7 passed`。失败项覆盖三类传输异常、非 JSON 响应、三种任意服务端错误结构，以及缺失的 `session_factory` 接口。

实现修复后，同一命令得到 `15 passed`。并发测试使用双线程屏障：两个 Session 必须同时进入 `post()` 才能通过，因此它同时检验了线程隔离和请求未被全局锁串行化。

并发全套通过 PowerShell 枚举后运行：

```powershell
$tests = Get-ChildItem -LiteralPath 'tests' -Filter 'test_concurrency_*.py' |
  Sort-Object Name | Select-Object -ExpandProperty FullName
py -m pytest $tests -v
```

结果为 `57 passed`。测试仍全部使用 fake Session，没有网络调用。
