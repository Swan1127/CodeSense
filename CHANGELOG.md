# 更新日志 / Changelog

本文件只记录面向使用者和维护者有意义的版本信息。版本号遵循语义化版本规范，最新内容放在前面。

This file records release-level information for users and maintainers. Versions follow Semantic Versioning, with the newest entries first.

## [Unreleased]

后续尚未发布的变更记录在这里。

Future unreleased changes will be listed here.

## [1.1.0] - 2026-09-14

### Added

- 增加学习会话连续性与可解释状态投影，支持 `active`、`idle`、`completed`、`abandoned` 四种状态。
- 学生端增加最近会话的“继续学习”入口；教师端增加会话概览、阶段进度和状态筛选。
- 阶段 1/2/3 接口统一携带生命周期状态、下一步动作和可恢复信息。
- 增加对象级会话授权检查，并用单次聚合查询补充列表中的最后活动时间。

### Verification

- 合并后的主分支通过 643 项已跟踪测试。
- 390px 窄屏浏览器 smoke 验证通过，无横向溢出。

## [1.0.0] - 2026-08-28

CodeSense 标准版首个正式版本。

First formal release of the CodeSense Standard Edition.

[Unreleased]: https://github.com/XiaoCow666/CodeSense/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/XiaoCow666/CodeSense/releases/tag/v1.1.0
[1.0.0]: https://github.com/XiaoCow666/CodeSense/releases/tag/v1.0.0
