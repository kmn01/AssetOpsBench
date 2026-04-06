"""Common LLM/planner argument aliases for skill ``arguments`` objects."""

from pydantic import AliasChoices, Field


def site_name_field():
    return Field(min_length=1, validation_alias=AliasChoices("site_name", "site"))


def asset_id_field():
    return Field(
        min_length=1,
        validation_alias=AliasChoices("asset_id", "asset", "equipment_id"),
    )


def asset_name_field():
    """``asset`` is not an alias here — it maps to ``asset_id`` only."""
    return Field(
        min_length=1,
        validation_alias=AliasChoices("asset_name", "name", "equipment_name"),
    )
