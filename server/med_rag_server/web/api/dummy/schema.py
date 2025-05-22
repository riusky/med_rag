from typing import Optional
from pydantic import BaseModel, ConfigDict


class DummyModelDTO(BaseModel):
    """
    DTO for dummy models.

    It returned when accessing dummy models from the API.
    """

    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class DummyModelInputDTO(BaseModel):
    """
    DTO for creating new dummy model.
    """
    name: str


class DummyModelUpdateDTO(BaseModel):
    """
    DTO for updating existing dummy model.
    """
    name: Optional[str] = None
