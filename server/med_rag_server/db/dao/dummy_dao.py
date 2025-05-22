from typing import List, Optional

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from med_rag_server.db.dependencies import get_db_session
from med_rag_server.db.models.dummy_model import DummyModel


class DummyDAO:
    """Class for accessing dummy table."""

    def __init__(self, session: AsyncSession = Depends(get_db_session)) -> None:
        self.session = session

    async def create_dummy_model(self, name: str) -> DummyModel:
        """Create a new dummy model and return it"""
        async with self.session.begin():
            dummy = DummyModel(name=name)
            self.session.add(dummy)
            # 不需要显式调用 commit，begin() 会自动处理
            await self.session.flush()  # 确保生成ID
            return dummy

    async def get_all_dummies(self, limit: int, offset: int) -> List[DummyModel]:
        """
        Get all dummy models with limit/offset pagination.

        :param limit: limit of dummies.
        :param offset: offset of dummies.
        :return: stream of dummies.
        """
        raw_dummies = await self.session.execute(
            select(DummyModel).limit(limit).offset(offset),
        )

        return list(raw_dummies.scalars().fetchall())

    async def filter(self, name: Optional[str] = None) -> List[DummyModel]:
        """
        Get specific dummy model.

        :param name: name of dummy instance.
        :return: dummy models.
        """
        query = select(DummyModel)
        if name:
            query = query.where(DummyModel.name == name)
        rows = await self.session.execute(query)
        return list(rows.scalars().fetchall())
      
      
    async def get_dummy_by_id(self, dummy_id: int) -> Optional[DummyModel]:
        """
        Get a single dummy model by ID.
        
        :param dummy_id: ID of the dummy model to retrieve.
        :return: The requested dummy model or None if not found.
        """
        result = await self.session.execute(
            select(DummyModel).where(DummyModel.id == dummy_id)
        )
        return result.scalars().first()
      
      
    async def update_dummy_model(
        self, 
        dummy_id: int, 
        name: Optional[str] = None
    ) -> Optional[DummyModel]:
        """
        Update a dummy model in the database.
        
        :param dummy_id: ID of the dummy model to update.
        :param name: New name for the dummy model.
        :return: Updated dummy model or None if not found.
        """
        dummy = await self.get_dummy_by_id(dummy_id)
        if not dummy:
            return None
            
        if name is not None:
            dummy.name = name
            self.session.add(dummy)
            await self.session.commit()
            await self.session.refresh(dummy)
            
        return dummy
      
      
    async def delete_dummy_model(self, dummy_id: int) -> bool:
        """
        Delete a dummy model from the database.
        
        :param dummy_id: ID of the dummy model to delete
        :return: True if deleted, False if not found
        """
        dummy = await self.get_dummy_by_id(dummy_id)
        if not dummy:
            return False
            
        # 使用begin_nested()而不是begin()来避免事务冲突
        async with self.session.begin_nested():
            await self.session.delete(dummy)
            await self.session.commit()
        return True