from enum import StrEnum

class UserRole(StrEnum):
    OWNER = "owner"
    MANAGER = "manager"
    STAFF = "staff"


class PaymentMethod(StrEnum):
    CASH = "cash"
    BANK_TRANSFER = "bank_transfer"  # mobile banking
    ESEWA = "esewa"
    KHALTI = "khalti"
    CHEQUE = "cheque"
    OTHER = "other"


class TxKind(StrEnum):
    """What happened. Validated in the API (Pydantic), stored as plain text."""

    INCOME = "income"
    EXPENSE = "expense"
    EMPLOYEE_ADVANCE = "employee_advance"  
    EMPLOYEE_SALARY = "employee_salary"
    CREDIT_SALE = "credit_sale"
    CREDIT_PURCHASE = "credit_purchase"
    PAYMENT_RECEIVED = "payment_received"
    PAYMENT_MADE = "payment_made"
    LOAN_GIVEN = "loan_given"
    LOAN_TAKEN = "loan_taken"
    ADVANCE_RECEIVED = "advance_received"
    