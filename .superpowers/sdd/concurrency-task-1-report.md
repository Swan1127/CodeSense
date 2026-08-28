# 并发评估计划 Task 1 报告

## 实现内容

- 新增 `RequestRecord`、`LevelSummary` 和 `StopDecision` 三个 `frozen=True` dataclass；`RequestRecord.to_dict()` 使用 `asdict` 输出记录。
- 新增 `summarize_level(records)`：计算成功数、成功率、错误率、限流率、吞吐、均值、p50/p95/p99、重试率和网关错误数。
- 新增 `evaluate_stop(summary)`：按固定顺序检查错误率、限流率、p95 延迟和网关错误，并返回停止原因元组。
- 错误率直接按失败请求数除以总请求数计算；错误率和限流率停止条件分别严格使用 `> 0.05` 与 `> 0.10`。
- 实现仅依赖 Python 标准库和 pytest 测试，不调用网络或智谱服务。

## TDD 记录

### RED

命令：

```powershell
py -m pytest tests/test_concurrency_metrics.py -v
```

关键输出：

```text
collecting ... collected 0 items / 1 error
ModuleNotFoundError: No module named 'research_eval'
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
```

该失败发生在生产包尚未创建时，符合预期的缺失包 RED。

### GREEN

命令：

```powershell
py -m pytest tests/test_concurrency_metrics.py -v
```

关键输出：

```text
collected 9 items
============================== 9 passed in 0.06s ==============================
```

覆盖内容包括不可变记录、序列化、p95、错误/限流边界、429 与 1305、504 与 `worker_timeout`、重试率、吞吐率和空输入。

## 文件列表

- `research_eval/__init__.py`
- `research_eval/concurrency/__init__.py`
- `research_eval/concurrency/models.py`
- `research_eval/concurrency/metrics.py`
- `tests/test_concurrency_metrics.py`
- `.superpowers/sdd/concurrency-task-1-report.md`

## 自审与顾虑

- 已逐项对照任务简报中的字段、函数名、百分位插值和停止原因；没有修改简报以外的业务文件。
- `git diff --check` 未发现空白错误。
- 工作树中原有的 `.tmp/`、`static/uploads/` 和 `research/guided_learning_paper/~$per_core_zh.docx` 保持未跟踪且未触碰。
- 本任务只运行了聚焦的离线测试，未运行全仓库测试，以避免引入应用启动、模型加载或外部服务副作用；后续任务接入时仍应补充跨模块集成验证。

## 审查修复：level 一致性校验

### 问题与修复

审查发现 `summarize_level()` 原先直接使用 `records[0].level`，未验证同一汇总中的其他请求记录是否属于同一 level。新增混合 level 回归测试，并在汇总前检查 level 集合；发现多个 level 时抛出 `ValueError("records must have the same level; got levels: ...")`。其他接口和汇总规则未改动。

### TDD RED

命令：

```powershell
py -m pytest tests/test_concurrency_metrics.py -v
```

关键输出：

```text
collected 10 items
FAILED tests/test_concurrency_metrics.py::test_summary_rejects_mixed_levels
Failed: DID NOT RAISE <class 'ValueError'>
========================= 1 failed, 9 passed in 0.14s =========================
```

### TDD GREEN

同一命令重新运行，关键输出：

```text
collected 10 items
tests/test_concurrency_metrics.py::test_summary_rejects_mixed_levels PASSED [100%]
============================= 10 passed in 0.07s ==============================
```

本次修复只涉及 `research_eval/concurrency/metrics.py`、`tests/test_concurrency_metrics.py` 和本报告；未触碰原有 `.tmp/`、`static/uploads/` 或 Word 锁文件。
