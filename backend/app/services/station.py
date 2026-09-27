"""观测站点业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

import re
from typing import Any

from app.store import store

MODULE = "station"
REQUIRED_FIELDS = ["站点编码", "站点名称", "站点类别"]
STATUS_ORDER = ["待入网", "正常运行", "降级运行", "已停用"]
ACTION_RULES = {"办理入网": "正常运行", "标记降级": "降级运行", "停用站点": "已停用"}
NEGATIVE_ACTIONS = ["停用站点"]

# 站点编码写法：2-6 位字母 + 短横线 + 4 位数字，例如 STAT-0001。
CODE_PATTERN = re.compile(r"^[A-Za-z]{2,6}-\d{4}$")
CODE_FORMAT_HINT = "站点编码写法不对：应为「字母-四位数字」，例如 STAT-0001"


def validate_station_code(code: str | None) -> str | None:
    """校验站点编码写法；返回 None 表示通过，否则返回可直接展示的原因。"""
    if code is None or not code.strip():
        return None
    if not CODE_PATTERN.fullmatch(code.strip()):
        return f"{CODE_FORMAT_HINT}（当前填写：{code.strip()}）"
    return None


class StationService:
    def list_entries(
        self,
        *,
        code: str | None = None,
        name: str | None = None,
        category: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """按站点编码、站点名称、站点类别、状态取交集过滤，再分页。"""
        rows = store.rows(MODULE)
        if code and code.strip():
            rows = [
                row
                for row in rows
                if str(row.get("站点编码", "")).lower() == code.strip().lower()
            ]
        if name and name.strip():
            rows = [
                row
                for row in rows
                if name.strip().lower() in str(row.get("站点名称", "")).lower()
            ]
        if category and category.strip():
            rows = [
                row
                for row in rows
                if category.strip().lower() in str(row.get("站点类别", "")).lower()
            ]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"观测站点 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于观测站点可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"观测站点已{action}"
