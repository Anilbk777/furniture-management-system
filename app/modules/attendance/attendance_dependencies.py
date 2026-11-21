from typing import Annotated

from app.core.database import get_db
from app.modules.attendance.attendance_repository import AttendanceRepository
from app.modules.attendance.attendance_service import AttendanceService
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession


def get_attendance_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AttendanceService:
    return AttendanceService(session, AttendanceRepository(session))


AttendanceServiceDep = Annotated[AttendanceService, Depends(get_attendance_service)]
