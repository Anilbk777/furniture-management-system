"""Nepali / English display names for the enums.

The API and the database always use the stable `value` ("employee_advance").
Only the label changes with the language, and it is looked up here, in ONE place,
for both the React and the Flutter app.

To add a language: add its code to SUPPORTED_LANGUAGES and a text to every entry.
The app refuses to start if any enum member is missing a label.
"""

from enum import StrEnum
from typing import Literal

from ..transaction_enums import PaymentMethod, TxKind, UserRole

Language = Literal["ne", "en"]
SUPPORTED_LANGUAGES: tuple[str, ...] = ("ne", "en")
DEFAULT_LANGUAGE: Language = "ne"

LABELS: dict[type[StrEnum], dict[StrEnum, dict[str, str]]] = {
    TxKind: {
        TxKind.INCOME: {"ne": "आम्दानी", "en": "Income"},
        TxKind.EXPENSE: {"ne": "खर्च", "en": "Expense"},
        TxKind.EMPLOYEE_ADVANCE: {"ne": "कर्मचारीलाई पेस्की", "en": "Advance to employee"},
        TxKind.EMPLOYEE_SALARY: {"ne": "तलब भुक्तानी", "en": "Salary paid"},
        TxKind.CREDIT_SALE: {"ne": "उधारो बिक्री", "en": "Sale on credit"},
        TxKind.CREDIT_PURCHASE: {"ne": "उधारो खरिद", "en": "Purchase on credit"},
        TxKind.PAYMENT_RECEIVED: {"ne": "रकम प्राप्त", "en": "Payment received"},
        TxKind.PAYMENT_MADE: {"ne": "रकम भुक्तानी", "en": "Payment made"},
        TxKind.LOAN_GIVEN: {"ne": "उधार दिएको", "en": "Lent (money or goods)"},
        TxKind.LOAN_TAKEN: {"ne": "उधार लिएको", "en": "Borrowed (money or goods)"},
        TxKind.ADVANCE_RECEIVED: {"ne": "पेस्की प्राप्त", "en": "Advance received"},
    },
    PaymentMethod: {
        PaymentMethod.CASH: {"ne": "नगद", "en": "Cash"},
        PaymentMethod.BANK_TRANSFER: {"ne": "बैंक ट्रान्सफर", "en": "Bank transfer"},
        PaymentMethod.ESEWA: {"ne": "इसेवा", "en": "eSewa"},
        PaymentMethod.KHALTI: {"ne": "खल्ती", "en": "Khalti"},
        PaymentMethod.CHEQUE: {"ne": "चेक", "en": "Cheque"},
        PaymentMethod.OTHER: {"ne": "अन्य", "en": "Other"},
    },
    UserRole: {
        UserRole.OWNER: {"ne": "मालिक", "en": "Owner"},
        UserRole.MANAGER: {"ne": "व्यवस्थापक", "en": "Manager"},
        UserRole.STAFF: {"ne": "कर्मचारी", "en": "Staff"},
    },
}


def _validate() -> None:
    """Fail at startup (not in front of the user) if a label is missing."""
    for enum_cls, labels in LABELS.items():
        for member in enum_cls:
            texts = labels.get(member, {})
            missing = [code for code in SUPPORTED_LANGUAGES if not texts.get(code)]
            if missing:
                raise RuntimeError(
                    f"Missing {missing} label for {enum_cls.__name__}.{member.name}"
                )


_validate()


def label(member: StrEnum, lang: str = DEFAULT_LANGUAGE) -> str:
    return LABELS[type(member)][member][lang]


def resolve_language(lang: str | None, accept_language: str | None) -> Language:
    """?lang=ne|en wins, then the Accept-Language header, then Nepali."""
    if lang in SUPPORTED_LANGUAGES:
        return lang  # type: ignore[return-value]
    if accept_language:
        for part in accept_language.split(","):
            code = part.split(";")[0].strip().lower()[:2]
            if code in SUPPORTED_LANGUAGES:
                return code  # type: ignore[return-value]
    return DEFAULT_LANGUAGE
