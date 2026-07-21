# Task 3 并发评估恢复报告

日期：2026-07-21

## 接管背景

前一代理在控制器等待期间中断。接管时，工作树位于分支 `codex/guided-learning-paper-revision`，基线提交为 `2f0996d`；以下 Task 3 改动均未提交：

- 已修改：`research_eval/concurrency/models.py`、`research_eval/concurrency/runner.py`、`tests/test_concurrency_runner.py`
- 未跟踪：`research_eval/concurrency/resources.py`、`tests/test_concurrency_resources.py`

指定报告原先不存在。工作树中另有 `.tmp/` 与 `static/uploads/`，它们不属于 Task 3，也没有纳入本次提交。

接管前运行：

```powershell
py -m pytest tests/test_concurrency_resources.py tests/test_concurrency_runner.py tests/test_concurrency_metrics.py -v
```

结果为 33 passed。该结果只能证明遗留实现与遗留测试相符；目录中没有 RED 命令输出或旧报告，不能视为已验证的 RED 证据。

## 补建的 RED 到 GREEN 证据

接管检查发现 `sustained_saturation` 只累计高值样本数，不检查样本秒数是否连续。采样若中断，30 条高值记录仍会被误判为持续 30 秒饱和。

新增回归测试 `test_saturation_requires_consecutive_one_second_samples`：前 29 个样本的秒数为 0 至 28，第 30 个样本跳到 31；所有 CPU 值均为 95%。

RED 命令：

```powershell
py -m pytest tests/test_concurrency_resources.py::test_saturation_requires_consecutive_one_second_samples -v
```

首次运行按预期失败：`sustained_saturation(..., seconds=30)` 返回 `True`，测试要求 `False`。

随后在 `sustained_saturation` 中记录前一秒，仅在当前秒等于前一秒加一时延续计数；时间跳跃或安全样本都会重新开始计数。相同命令在修正后通过。

## 实现核查

| 需求 | 实现与测试证据 |
| --- | --- |
| 可注入 reader 和时钟 | `ResourceSampler(reader, clock)`；`run_staircase` 透传 `resource_reader`、`resource_clock`；资源测试使用自定义 reader 和推进式时钟。 |
| 严格大于 90% | `cpu_percent > threshold or memory_percent > threshold`；恰好 90 的 30 条样本不触发。 |
| 连续 30 个一秒样本 | 饱和样本连续计数；新增时间跳跃回归测试防止误判。 |
| 不等待真实 30 秒 | 注入时钟的测试只推进逻辑秒数；未执行真实 30 秒等待。 |
| 每档启动、停止与保存 | runner 在提交该档 future 前启动，在 executor 完成或中断清理后于 `finally` 停止；样本追加到与 JSONL 同目录的 `resource_samples.csv`。 |
| 将资源饱和写入停止原因 | `LevelSummary.stop_reasons` 保留原指标原因；资源饱和时追加 `resource_saturation`，并阻止后续并发档。 |
| 离线运行 | 测试只使用本地 fake worker、临时路径和注入 reader/clock。 |

生产 reader 优先使用 `psutil`；不可用时使用 Linux `/proc`。在不具备这两种来源的平台上，fallback 返回 0，不会伪造饱和结果。

## 自审

- `git diff --check` 没有空白错误。
- `research_eval/concurrency/output.py` 未改动；Task 1/2 的中断 future 清理和 JSONL 事务化、安全序列化保留在原实现中。
- 已有 runner 与 metrics 断言连同新增资源断言全部通过。
- 本次仅提交 Task 3 的五个代码/测试文件和本报告；不包含 `.tmp/`、`static/uploads/`。

## 最终验证

```powershell
py -m pytest tests/test_concurrency_resources.py tests/test_concurrency_runner.py tests/test_concurrency_metrics.py -v
```

结果：34 passed，0 failed，耗时 0.36s。

## 顾虑

遗留改动的原始 RED 输出已随前一代理中断而缺失，无法倒推或伪造。报告保留了这一事实，并用新增的时间连续性测试补建了可重复的 RED/GREEN 证据。短时并发档可能自然收集不到 30 条一秒样本；这种情况下资源停止条件不会触发，符合“连续 30 个样本”这一门槛。

## 审查整改：采样时序与监控错误

日期：2026-07-21

### RED

先新增以下测试，再运行：

```powershell
py -m pytest \
  tests/test_concurrency_resources.py::test_start_waits_for_initial_sample_and_stop_prevents_new_samples \
  tests/test_concurrency_resources.py::test_sampler_preserves_background_reader_error \
  tests/test_concurrency_resources.py::test_sampler_preserves_proc_parse_value_error \
  tests/test_concurrency_runner.py::test_short_worker_starts_after_real_sampler_initial_sample \
  tests/test_concurrency_runner.py::test_runner_stops_on_resource_monitor_error_and_writes_prior_samples \
  tests/test_concurrency_runner.py::test_real_sampler_combines_metric_and_resource_saturation_and_writes_csv -v
```

初次结果为 6 failed。失败点分别是：`start()` 在线程启动后立即返回；`ResourceSampler` 没有 `error` 状态；`/proc` 解析的 `ValueError` 在线程中未处理；极短 worker 可先于首样本开始；监控失败后 runner 仍进入下一档。原实现还产生了 `PytestUnhandledThreadExceptionWarning`。集成测试随后修正了其 30 个样本的时钟门槛，避免在第 30 个样本写入前提前停止。

### GREEN

- `start()` 在创建后台线程前同步写入首样本。极短 worker 测试用阻塞 reader 证明 worker 不会先开始。
- `stop()` 与记录操作使用同一把采样锁。停止事件设置后，即使 `wait()` 随后返回，循环也不会再写入样本。
- `ResourceSampler.error` 保留首个 `Exception`；首样本、reader、时钟等待和 `/proc` 解析的异常都会落入该状态并停止采样循环。
- runner 仍将已有样本写入 CSV；若 `error` 非空，会把 `resource_monitor_error` 加入 `stop_reasons`，并停止后续并发档。
- 真实 sampler 集成测试注入 reader 与时钟，在不等待真实 30 秒的情况下生成秒数 0 至 29 的 30 条高负载样本，验证 CSV、`resource_saturation`，以及与 `error_rate` 并存的停止原因。
- 删除未使用的 `os` 导入。

完整回归命令：

```powershell
py -m pytest tests/test_concurrency_resources.py tests/test_concurrency_runner.py tests/test_concurrency_metrics.py -v
```

最终结果：41 passed，0 failed，0 warnings，耗时 0.63s。
