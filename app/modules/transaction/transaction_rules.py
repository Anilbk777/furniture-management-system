"""Which combinations of kind / employee / party / payment method are valid.

One place, used by the create schema AND by the service (for PATCH, after merging the
changes into the existing row), so create and update can never disagree.
"""

import uuid

from .transaction_enums import  TxKind

# who an entry is about
OWN_KINDS = frozenset({TxKind.INCOME, TxKind.EXPENSE})
EMPLOYEE_KINDS = frozenset({TxKind.EMPLOYEE_ADVANCE, TxKind.EMPLOYEE_SALARY})
PARTY_KINDS = frozenset(
    {
        TxKind.CREDIT_SALE,
        TxKind.CREDIT_PURCHASE,
        TxKind.PAYMENT_RECEIVED,
        TxKind.PAYMENT_MADE,
        TxKind.LOAN_GIVEN,
        TxKind.LOAN_TAKEN,
        TxKind.ADVANCE_RECEIVED,
    }
)

# payment_method: real money moved -> required; udharo -> forbidden;
# loans (LOAN_GIVEN / LOAN_TAKEN) -> optional: money has a method, goods have none.
METHOD_REQUIRED = frozenset(
    {
        TxKind.INCOME,
        TxKind.EXPENSE,
        TxKind.EMPLOYEE_ADVANCE,
        TxKind.EMPLOYEE_SALARY,
        TxKind.PAYMENT_RECEIVED,
        TxKind.PAYMENT_MADE,
        TxKind.ADVANCE_RECEIVED,
    }
)
METHOD_FORBIDDEN = frozenset({TxKind.CREDIT_SALE, TxKind.CREDIT_PURCHASE})


def check_shape(
    kind: str,
    employee_id: uuid.UUID | None,
    party_id: uuid.UUID | None,
    payment_method: str | None,
) -> str | None:
    """Return an error message, or None when the combination is valid."""
    if kind in OWN_KINDS:
        if employee_id is not None or party_id is not None:
            return f"{kind} cannot be linked to an employee or a party"
    elif kind in EMPLOYEE_KINDS:
        if employee_id is None or party_id is not None:
            return f"{kind} needs an employee_id and cannot have a party_id"
    elif kind in PARTY_KINDS:
        if party_id is None or employee_id is not None:
            return f"{kind} needs a party_id and cannot have an employee_id"

    if kind in METHOD_REQUIRED and payment_method is None:
        return f"{kind} needs a payment_method"
    if kind in METHOD_FORBIDDEN and payment_method is not None:
        return f"{kind} must not have a payment_method (no money moved)"
    return None


def counterparty_of(kind: TxKind) -> str:
    """Which person the form must ask for: 'none', 'employee' or 'party'."""
    if kind in EMPLOYEE_KINDS:
        return "employee"
    if kind in PARTY_KINDS:
        return "party"
    return "none"


def method_rule_of(kind: TxKind) -> str:
    """Does the form need a payment method? 'required', 'optional' or 'forbidden'."""
    if kind in METHOD_REQUIRED:
        return "required"
    if kind in METHOD_FORBIDDEN:
        return "forbidden"
    return "optional"
