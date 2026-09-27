"""观测站点接口：维护观测站点，覆盖办理入网、标记降级、停用站点等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.station import StationService, validate_station_code

router = APIRouter(prefix="/api/station", tags=["观测站点"])

service = StationService()

LIST_FIELDS = ["站点编码", "站点名称", "站点类别", "经纬度坐标", "海拔高度", "建站年份", "值守方式", "站点状态"]
STATUSES = ["待入网", "正常运行", "降级运行", "已停用"]


def _checked_filters(
    code: str | None,
    name: str | None,
    category: str | None,
    status: str | None,
) -> dict[str, str | None]:
    """列表与导出共用的一套筛选口径：先校验编码写法，再原样透传条件。"""
    problem = validate_station_code(code)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    return {"code": code, "name": name, "category": category, "status": status}


@router.get("", response_model=PageResult[dict])
def list_entries(
    code: str | None = Query(default=None, description="按站点编码精确检索，写法如 STAT-0001"),
    name: str | None = Query(default=None, description="按站点名称模糊检索"),
    category: str | None = Query(default=None, description="按站点类别模糊检索"),
    status: str | None = Query(default=None, description="待入网、正常运行、降级运行、已停用"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按站点编码、站点名称、站点类别取交集过滤；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    filters = _checked_filters(code, name, category, status)
    items, total = service.list_entries(**filters, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries(
    code: str | None = Query(default=None, description="按站点编码精确检索，写法如 STAT-0001"),
    name: str | None = Query(default=None, description="按站点名称模糊检索"),
    category: str | None = Query(default=None, description="按站点类别模糊检索"),
    status: str | None = Query(default=None, description="待入网、正常运行、降级运行、已停用"),
) -> dict[str, Any]:
    """导出观测站点清单：与列表页同一套筛选条件，条数与列表页脚一致。"""
    filters = _checked_filters(code, name, category, status)
    items, total = service.list_entries(**filters, page=1, size=10000)
    return {"module": "station", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条观测站点明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"观测站点 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条观测站点，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="观测站点已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条观测站点执行办理入网、标记降级、停用站点；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
