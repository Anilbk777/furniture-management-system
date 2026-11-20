import uuid
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from .transaction_models import Transaction


def _with_people():
    """Always load the employee / party names (async: no lazy loading)."""
    return (joinedload(Transaction.employee), joinedload(Transaction.party))


class TransactionRepository:
    """Database access only. Every read is scoped to ONE organization. No commits."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _fetch(self, transaction_id: uuid.UUID) -> Transaction:
        """Reload one row with its employee/party, refreshing every column (timestamps)."""
        stmt = (
            select(Transaction)
            .options(*_with_people())
            .where(Transaction.id == transaction_id)
            .execution_options(populate_existing=True)
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def create(
        self, organization_id: uuid.UUID, created_by: uuid.UUID | None, **values
    ) -> Transaction:
        transaction = Transaction(
            organization_id=organization_id, created_by=created_by, **values
        )
        self.session.add(transaction)
        await self.session.flush()
        return await self._fetch(transaction.id)

    async def get(
        self, organization_id: uuid.UUID, transaction_id: uuid.UUID
    ) -> Transaction | None:
        stmt = (
            select(Transaction)
            .options(*_with_people())
            .where(
                Transaction.id == transaction_id,
                Transaction.organization_id == organization_id,
                Transaction.deleted_at.is_(None),
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    @staticmethod
    def _conditions(
        organization_id: uuid.UUID,
        *,
        kinds: Sequence[str] | None,
        employee_id: uuid.UUID | None,
        party_id: uuid.UUID | None,
        payment_method: str | None,
        date_from: str | None,
        date_to: str | None,
        search: str | None,
    ) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = [
            Transaction.organization_id == organization_id,
            Transaction.deleted_at.is_(None),
        ]
        if kinds:
            conditions.append(Transaction.kind.in_(kinds))
        if employee_id is not None:
            conditions.append(Transaction.employee_id == employee_id)
        if party_id is not None:
            conditions.append(Transaction.party_id == party_id)
        if payment_method is not None:
            conditions.append(Transaction.payment_method == payment_method)
        # BS dates are zero-padded text, so string comparison is date comparison
        if date_from is not None:
            conditions.append(Transaction.bs_date >= date_from)
        if date_to is not None:
            conditions.append(Transaction.bs_date <= date_to)
        if search:
            conditions.append(Transaction.note.ilike(f"%{search}%"))
        return conditions

    async def list(
        self,
        organization_id: uuid.UUID,
        *,
        kinds: Sequence[str] | None = None,
        employee_id: uuid.UUID | None = None,
        party_id: uuid.UUID | None = None,
        payment_method: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[Transaction], int]:
        """One page of transactions (newest first) and the total number of matches."""
        conditions = self._conditions(
            organization_id,
            kinds=kinds,
            employee_id=employee_id,
            party_id=party_id,
            payment_method=payment_method,
            date_from=date_from,
            date_to=date_to,
            search=search,
        )
        total = (
            await self.session.execute(
                select(func.count()).select_from(Transaction).where(*conditions)
            )
        ).scalar_one()
        if total == 0:
            return [], 0

        stmt = (
            select(Transaction)
            .options(*_with_people())
            .where(*conditions)
            .order_by(
                Transaction.bs_date.desc(),
                Transaction.created_at.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return rows, total

    async def totals(
        self,
        organization_id: uuid.UUID,
        *,
        kinds: Sequence[str] | None = None,
        employee_id: uuid.UUID | None = None,
        party_id: uuid.UUID | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> tuple[int, dict[str, Decimal]]:
        """Count and per-kind sums for the same filters the list endpoint uses."""
        conditions = self._conditions(
            organization_id,
            kinds=kinds,
            employee_id=employee_id,
            party_id=party_id,
            payment_method=None,
            date_from=date_from,
            date_to=date_to,
            search=None,
        )
        count = (
            await self.session.execute(
                select(func.count()).select_from(Transaction).where(*conditions)
            )
        ).scalar_one()
        rows = (
            await self.session.execute(
                select(Transaction.kind, func.sum(Transaction.amount))
                .where(*conditions)
                .group_by(Transaction.kind)
            )
        ).all()
        return count, {kind: amount for kind, amount in rows}

    async def update(self, transaction: Transaction, values: dict) -> Transaction:
        for field, value in values.items():
            setattr(transaction, field, value)
        await self.session.flush()
        return await self._fetch(transaction.id)  # fresh updated_at and employee/party

    async def delete(self, transaction: Transaction) -> None:
        await self.session.delete(transaction)
        await self.session.flush()
