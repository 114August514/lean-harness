"""Lean Harness 工作连续性能力的本地参考实现。

权威契约见同目录 ``contract.md``。本包只负责保存和读取记录、
绑定 worktree、定位检查点、提供恢复事实；工作流编排与目标判断
属于 Skills，不在本包内。
"""

from .context import ResumeContext
from .recovery import RecoveryLog
from .store import JsonlStore, StoreError
from .worklog import WorkLog

__all__ = [
    "JsonlStore",
    "RecoveryLog",
    "ResumeContext",
    "StoreError",
    "WorkLog",
]
