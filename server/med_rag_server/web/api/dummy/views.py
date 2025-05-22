from typing import List

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.param_functions import Depends

from med_rag_server.db.dao.dummy_dao import DummyDAO
from med_rag_server.db.models.dummy_model import DummyModel
from med_rag_server.web.api.dummy.schema import DummyModelDTO, DummyModelInputDTO, DummyModelUpdateDTO

router = APIRouter()


@router.get("/", response_model=List[DummyModelDTO])
async def get_dummy_models(
    limit: int = 10,
    offset: int = 0,
    dummy_dao: DummyDAO = Depends(),
) -> List[DummyModel]:
    """
    Retrieve all dummy objects from the database with pagination.
    
    :param limit: Maximum number of items to return, defaults to 10.
    :param offset: Number of items to skip, defaults to 0.
    :param dummy_dao: DAO for dummy models.
    :return: List of dummy objects from database.
    """
    return await dummy_dao.get_all_dummies(limit=limit, offset=offset)


@router.get("/{dummy_id}", response_model=DummyModelDTO)
async def get_dummy_model(
    dummy_id: int,
    dummy_dao: DummyDAO = Depends(),
) -> DummyModel:
    """
    Retrieve a single dummy object by ID.
    
    :param dummy_id: ID of the dummy model to retrieve.
    :param dummy_dao: DAO for dummy models.
    :return: The requested dummy object.
    :raises HTTPException: 404 if dummy model not found.
    """
    dummy = await dummy_dao.get_dummy_by_id(dummy_id)
    if not dummy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dummy model with ID {dummy_id} not found",
        )
    return dummy


@router.post("/", response_model=DummyModelDTO, status_code=status.HTTP_201_CREATED)
async def create_dummy_model(
    new_dummy_object: DummyModelInputDTO,
    dummy_dao: DummyDAO = Depends(),
) -> DummyModel:
    """
    Create a new dummy model in the database.
    
    :param new_dummy_object: Data for the new dummy model.
    :param dummy_dao: DAO for dummy models.
    :return: The created dummy object.
    """
    return await dummy_dao.create_dummy_model(name=new_dummy_object.name)


@router.put("/{dummy_id}", response_model=DummyModelDTO)
async def update_dummy_model(
    dummy_id: int,
    update_data: DummyModelUpdateDTO,
    dummy_dao: DummyDAO = Depends(),
) -> DummyModel:
    """
    Update an existing dummy model.
    
    :param dummy_id: ID of the dummy model to update.
    :param update_data: Data to update the dummy model with.
    :param dummy_dao: DAO for dummy models.
    :return: The updated dummy object.
    :raises HTTPException: 404 if dummy model not found.
    """
    dummy = await dummy_dao.get_dummy_by_id(dummy_id)
    if not dummy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dummy model with ID {dummy_id} not found",
        )
    
    return await dummy_dao.update_dummy_model(
        dummy_id=dummy_id,
        name=update_data.name,
    )


@router.delete("/{dummy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dummy_model(
    dummy_id: int,
    dummy_dao: DummyDAO = Depends(),
) -> None:
    """
    Delete a dummy model from the database.
    
    :param dummy_id: ID of the dummy model to delete.
    :param dummy_dao: DAO for dummy models.
    :raises HTTPException: 404 if dummy model not found.
    """
    dummy = await dummy_dao.get_dummy_by_id(dummy_id)
    if not dummy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dummy model with ID {dummy_id} not found",
        )
    
    await dummy_dao.delete_dummy_model(dummy_id)