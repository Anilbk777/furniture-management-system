from typing import Literal

from pydantic import BaseModel

from .meta_labels import Language


class Option(BaseModel):
    value: str  # stable id, send this to the API
    label: str  # text to show, in the requested language


class TxKindOption(Option):
    """Also tells the form which fields to show for this kind."""

    counterparty: Literal["none", "employee", "party"]
    payment_method: Literal["required", "optional", "forbidden"]


class OptionsRead(BaseModel):
    language: Language
    tx_kinds: list[TxKindOption]
    payment_methods: list[Option]
    user_roles: list[Option]
