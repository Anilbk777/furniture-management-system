import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from ...utils.exceptions import BadRequestException, NotFoundException
# from .transaction_enums import PaymentMethod, TxKind
from .transaction_models import Transaction
from app.modules.employees.employees_repository import EmployeeRepository
from app.modules.party.party_repository import PartyRepository
from app.modules.transaction.transaction_repository import TransactionRepository
# from app.modules.transaction.transaction_rules import check_shape
from app.modules.transaction.transaction_schemas import (
    TransactionCreate,
    TransactionUpdate,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TransactionService:
    """Business rules + the commit. `org_id` is always the logged-in user's organization."""

    def __init__(
        self,
        session: AsyncSession,
        repo: TransactionRepository,
        employee_repo: EmployeeRepository,
        party_repo: PartyRepository,
    ) -> None:
        self.session = session
        self.repo = repo
        self.employee_repo = employee_repo
        self.party_repo = party_repo

    # ---------------------------------- helpers --------------------------------------
    async def _check_counterparties(
        self,
        org_id: uuid.UUID,
        employee_id: uuid.UUID | None,
        party_id: uuid.UUID | None,
    ) -> None:
        """The employee / party must exist in THIS organization (a database foreign key
        cannot check that). A foreign id looks exactly like a missing one."""
        if (
            employee_id is not None
            and await self.employee_repo.get(org_id, employee_id) is None
        ):
            logger.warning(
                "Employee %s not found in organization %s", employee_id, org_id
            )
            raise BadRequestException(message="Employee not found")
        if party_id is not None and await self.party_repo.get(org_id, party_id) is None:
            logger.warning("Party %s not found in organization %s", party_id, org_id)
            raise BadRequestException(message="Party not found")

    # @staticmethod
    # def _plain_enums(values: dict) -> dict:
    #     """The database stores plain text, so turn enum members into their string values."""
    #     if values.get("kind") is not None:
    #         values["kind"] = values["kind"].value
    #     if values.get("payment_method") is not None:
    #         values["payment_method"] = values["payment_method"].value
    #     return values


    async def create(
        self, org_id: uuid.UUID, user_id: uuid.UUID | None, data: TransactionCreate
    ) -> Transaction:
        await self._check_counterparties(org_id, data.employee_id, data.party_id)
        # values = self._plain_enums(data.model_dump())
        values = data.model_dump()
        try:
            transaction = await self.repo.create(org_id, user_id, **values)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            logger.exception(
                "Failed to create transaction org=%s kind=%s user=%s",
                org_id,
                values["kind"],
                user_id,
            )
            raise
        logger.info(
            "Transaction created id=%s kind=%s amount=%s org=%s user=%s",
            transaction.id,
            transaction.kind,
            transaction.amount,
            org_id,
            user_id,
        )
        return transaction

    async def get(self, org_id: uuid.UUID, transaction_id: uuid.UUID) -> Transaction:
        transaction = await self.repo.get(org_id, transaction_id)
        if transaction is None:  # also what another organization's id looks like
            logger.info(
                "Transaction %s not found in organization %s", transaction_id, org_id
            )
            raise NotFoundException(message="Transaction not found")
        return transaction

    async def list(
        self,
        org_id: uuid.UUID,
        *,
        kinds: str | None,
        employee_id: uuid.UUID | None,
        party_id: uuid.UUID | None,
        payment_method: str | None,
        date_from: str | None,
        date_to: str | None,
        search: str | None,
        page: int,
        limit: int,
    ) -> tuple[Sequence[Transaction], int]:
        if (
            date_from and date_to and date_from > date_to
        ):  # zero-padded text compares as dates
            raise BadRequestException("date from cannot be after date to")
        logger.debug(
            "Listing transactions org=%s page=%s limit=%s", org_id, page, limit
        )
        return await self.repo.list(
            org_id,
            # kinds=[k.value for k in kinds] if kinds else None,
            kinds=kinds,
            employee_id=employee_id,
            party_id=party_id,
            # payment_method=payment_method.value if payment_method else None,
            payment_method=payment_method,
            date_from=date_from,
            date_to=date_to,
            search=search,
            limit=limit,
            offset=(page - 1) * limit,
        )

    async def update(
        self, org_id: uuid.UUID, transaction_id: uuid.UUID, data: TransactionUpdate
    ) -> Transaction:
        transaction = await self.get(org_id, transaction_id)
        values = data.model_dump(exclude_unset=True)  # only what the client sent
        if not values:
            return transaction

        # Validate the FINAL combination (existing row + the changes), same rules as create.
        # kind = values.get("kind") or TxKind(transaction.kind)
        # kind = values.get("kind") 
        # employee_id = (
        #     values["employee_id"]
        #     if "employee_id" in values
        #     else transaction.employee_id
        # )
        # party_id = values["party_id"] if "party_id" in values else transaction.party_id
        # if "payment_method" in values:
        #     payment_method = values["payment_method"]
        # else:
        #     payment_method = (
        #         PaymentMethod(transaction.payment_method)
        #         if transaction.payment_method
        #         else None
        #     )
        # error = check_shape(kind, employee_id, party_id, payment_method)
        # if error:
        #     logger.warning(
        #         "Rejected update of transaction %s: %s", transaction_id, error
        #     )
        #     raise BadRequestException(message=error)

        # Only look up people that are being SET now, so old entries stay editable even if
        # their employee / party was deleted since.
        await self._check_counterparties(
            org_id,
            values.get("employee_id"),
            values.get("party_id"),
        )

        changed = sorted(values)
        # values = self._plain_enums(values)

        try:
            transaction = await self.repo.update(transaction, values)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            logger.exception(
                "Failed to update transaction %s org=%s", transaction_id, org_id
            )
            raise
        logger.info(
            "Transaction updated id=%s fields=%s org=%s",
            transaction_id,
            changed,
            org_id,
        )
        return transaction

    async def delete(self, org_id: uuid.UUID, transaction_id: uuid.UUID) -> None:
        """Soft delete: hidden from every list, the row is kept."""
        transaction = await self.get(org_id, transaction_id)
        try:
            await self.repo.soft_delete(transaction)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            logger.exception(
                "Failed to delete transaction %s org=%s", transaction_id, org_id
            )
            raise
        logger.info("Transaction deleted id=%s org=%s", transaction_id, org_id)
