import os
import asyncio
from dotenv import load_dotenv

from typing import List, Dict, Optional


from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import Column, String, DateTime, func, text, delete, select
from sqlalchemy.dialects.postgresql import insert
from datetime import datetime, timedelta, timezone


from code.api.market import get_announcements

# Загрузка переменных окружения из .env файла
load_dotenv()

# Получение URL базы данных из переменной окружения
DATABASE_URL = os.getenv('database_url')

Base = declarative_base()


class NewPairs(Base):
    """
    Represents new pairs
    """
    __tablename__ = 'new_pairs'

    name = Column(String, primary_key=True, nullable=False)
    created = Column(DateTime, server_default=func.now())


class NewPairsOperations:
    def __init__(self, database_url: str):
        self.engine = create_async_engine(database_url, echo=False)
        self.async_session = sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

    async def table_exists(self, table_name: str) -> bool:
        async with self.engine.connect() as conn:
            result = await conn.scalar(
                text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = :table_name)"),
                {"table_name": table_name}
            )
            return result

    async def create_table(self):
        if not await self.table_exists(NewPairs.__tablename__):
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            print(f"Table '{NewPairs.__tablename__}' created successfully.")
        else:
            print(f"Table '{NewPairs.__tablename__}' already exists, skipping creation.")

    async def insert_new_pairs(self):
        # Вычисляем дату шесть месяцев назад
        six_months_ago = datetime.now(timezone.utc) - timedelta(days=180)
        # Приводим её к offset-naive (без временной зоны)
        six_months_ago = six_months_ago.replace(tzinfo=None)

        pairs = await get_announcements()

        async with self.async_session() as session:
            async with session.begin():
                # Удаляем записи старше 6 месяцев
                await session.execute(
                    delete(NewPairs).where(NewPairs.created < six_months_ago)
                )

                # Вставляем новые пары
                for pair_name in pairs:
                    stmt = insert(NewPairs).values(
                        name=pair_name
                    ).on_conflict_do_nothing(index_elements=['name'])
                    await session.execute(stmt)

            await session.commit()


    async def get_all_names(self) -> List[str]:
        async with self.async_session() as session:
            result = await session.execute(select(NewPairs.name))
            names = result.scalars().all()
        return names

if __name__ == '__main__':

    async def main_assync():
        new_pairs_op = NewPairsOperations(DATABASE_URL)
        #new = await new_pairs_op.get_all_names()
        ups = await new_pairs_op.insert_new_pairs()

        print(ups)

    asyncio.run(main_assync())



