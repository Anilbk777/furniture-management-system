import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status
from fastapi.responses import JSONResponse

from app.modules.attendance.attendance_schemas import (
    AttendanceCreate,
    AttendanceList,
    AttendanceRead,
    AttendanceUpdate,
    EmployeeAttendanceDetails,
    EmployeeBrief,
    Pagination,
)
from app.modules.attendance.attendance_types import BsDate

# adjust this import to wherever your CurrentOrganization dependency lives
from ..organization.organization_dependencies import CurrentOrganization
from app.utils.response import APIResponse, success_response
from .attendance_dependencies import AttendanceServiceDep

router = APIRouter(prefix="/attendance", tags=["Staff Attendance"])


FromDate = Annotated[BsDate, Query(description="BS date, e.g. 2081-04-01")]
ToDate = Annotated[BsDate, Query(description="BS date, e.g. 2081-04-30")]


# ---------- one employee over a date range (declared first: more specific paths) ----------
@router.get(
    "/employees/{employee_id}/details",
    response_model=APIResponse[EmployeeAttendanceDetails],
)
async def employee_attendance_details(
    employee_id: uuid.UUID,
    from_date: FromDate,
    to_date: ToDate,
    org: CurrentOrganization,
    service: AttendanceServiceDep,
) -> JSONResponse:
    """Day-by-day attendance records of one employee between two BS dates, oldest first."""
    employee, summary, records = await service.employee_details(
        org.id, employee_id, from_date, to_date
    )
    data = EmployeeAttendanceDetails(
        employee=EmployeeBrief.model_validate(employee),
        from_date=from_date,
        to_date=to_date,
        total_records=len(records),
        summary=summary,
        records=[AttendanceRead.model_validate(r) for r in records],
    )
    return success_response(data, "Attendance details fetched")


# ---------- CRUD ----------
@router.post(
    "", status_code=status.HTTP_201_CREATED, response_model=APIResponse[AttendanceRead]
)
async def create_attendance(
    data: AttendanceCreate, org: CurrentOrganization, service: AttendanceServiceDep
) -> JSONResponse:
    record = await service.create(org.id, data)
    return success_response(
        AttendanceRead.model_validate(record),
        "Attendance recorded",
        status.HTTP_201_CREATED,
    )


@router.get("", response_model=APIResponse[AttendanceList])
async def list_attendance(
    org: CurrentOrganization,
    service: AttendanceServiceDep,
    employee_id: uuid.UUID | None = None,
    attendance_status: Annotated[
        str | None, Query(alias="status", max_length=20)
    ] = None,
    from_date: Annotated[BsDate | None, Query(description="BS date")] = None,
    to_date: Annotated[BsDate | None, Query(description="BS date")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> JSONResponse:
    records, total = await service.list(
        org.id,
        employee_id=employee_id,
        status=attendance_status,
        from_date=from_date,
        to_date=to_date,
        page=page,
        limit=limit,
    )
    data = AttendanceList(
        attendances=[AttendanceRead.model_validate(r) for r in records],
        pagination=Pagination.build(total=total, page=page, limit=limit),
    )
    return success_response(data, "Attendance fetched")


@router.get("/{attendance_id}", response_model=APIResponse[AttendanceRead])
async def get_attendance(
    attendance_id: uuid.UUID, org: CurrentOrganization, service: AttendanceServiceDep
) -> JSONResponse:
    record = await service.get(org.id, attendance_id)
    return success_response(AttendanceRead.model_validate(record), "Attendance fetched")


@router.patch("/{attendance_id}", response_model=APIResponse[AttendanceRead])
async def update_attendance(
    attendance_id: uuid.UUID,
    data: AttendanceUpdate,
    org: CurrentOrganization,
    service: AttendanceServiceDep,
) -> JSONResponse:
    record = await service.update(org.id, attendance_id, data)
    return success_response(AttendanceRead.model_validate(record), "Attendance updated")


@router.delete("/{attendance_id}", response_model=APIResponse[None])
async def delete_attendance(
    attendance_id: uuid.UUID, org: CurrentOrganization, service: AttendanceServiceDep
) -> JSONResponse:
    await service.delete(org.id, attendance_id)
    return success_response(None, "Attendance deleted")
