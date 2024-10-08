import os
import asyncio
import pandas as pd

from typing import Dict, Optional, List

from dotenv import load_dotenv
from sqlalchemy import (Column, String, BigInteger, Boolean, DateTime,
                        func, text, delete, select)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import and_
from sqlalchemy import update

from datetime import datetime, timedelta

# Загрузка переменных окружения из .env файла
load_dotenv()

# Получение URL базы данных из переменной окружения
DATABASE_URL = os.getenv('database_url')

BasePositions = declarative_base()


class Positions(BasePositions):
    """
    Represents positions with its settings.
    """
    __tablename__ = 'positions'

    bybit_id = Column(String, primary_key=True, nullable=False)  # bybit_id as primary key
    owner_id = Column(BigInteger, nullable=False)
    type = Column(String, default='main') # main / tp / averaging / trailing_lin
    tp_opened = Column(Boolean, nullable=False, default=False) # if open - stop processing
    market = Column(String, nullable=True) # demo / real
    order_type =  Column(String, nullable=True) # spot / linear
    symbol = Column(String, nullable=True)
    depends_on = Column(String, default='-1')  # bybit_id
    created = Column(DateTime, server_default=func.now())
    side = Column(String, nullable=False) # Buy / Sell

    # performance fileds
    orderStatus = Column(Boolean, default=False) # if Filled = true
    avgPrice = Column(String, nullable=True)   #  execution price
    cumExecValue = Column(String, nullable=True) # in USDT
    cumExecQty = Column(String, nullable=True) # '0.683'  QUANTITY in BASECOIN
    cumExecFee = Column(String, nullable=True) # fee in basecoin
    triggerPrice = Column(String, nullable=True)  # adding to TP to trail
    finished = Column(Boolean, default=False)

    #
    user_notified = Column(Boolean, default=False) # upon final performance


class PositionsOperations:
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
        if not await self.table_exists(Positions.__tablename__):
            async with self.engine.begin() as conn:
                await conn.run_sync(BasePositions.metadata.create_all)
            print(f"Table '{Positions.__tablename__}' created successfully.")
        else:
            print(f"Table '{Positions.__tablename__}' already exists, skipping creation.")

    async def upsert_position(self, position_data: dict):
        async with self.async_session() as session:
            async with session.begin():
                # Попытка найти существующую запись по bybit_id
                existing_position = await session.execute(
                    select(Positions).where(Positions.bybit_id == position_data["bybit_id"])
                )
                existing_position = existing_position.scalars().first()

                if existing_position:
                    # Обновление существующей записи (только тех полей, которые присутствуют в position_data)
                    for key, value in position_data.items():
                        if key != "bybit_id" and hasattr(existing_position, key):
                            setattr(existing_position, key, value)
                else:
                    # Вставка новой записи
                    stmt = insert(Positions).values(position_data)
                    await session.execute(stmt)

            await session.commit()

    async def delete_position_by_bybit_id(self, bybit_id: str):
        async with self.async_session() as session:
            async with session.begin():
                # Удаление основной записи
                await session.execute(
                    delete(Positions).where(Positions.bybit_id == bybit_id)
                )

                # Удаление зависимых записей
                await session.execute(
                    delete(Positions).where(Positions.depends_on == bybit_id)
                )

            await session.commit()

    async def get_position_by_bybit_id(self, bybit_id: str) -> Optional[Dict]:
        async with self.async_session() as session:
            result = await session.execute(
                select(Positions).where(Positions.bybit_id == bybit_id)
            )
            position = result.scalars().first()
            return self._position_to_dict(position)

    async def get_positions_by_owner_id(self, owner_id: int) -> List[Dict]:
        async with self.async_session() as session:
            result = await session.execute(
                select(Positions).where(Positions.owner_id == owner_id)
            )
            positions = result.scalars().all()
            return [self._position_to_dict(position) for position in positions]

    async def get_position_with_dependents(self, bybit_id: str) -> Dict[str, List[Dict]]:
        async with self.async_session() as session:
            # Получение основной позиции
            result = await session.execute(
                select(Positions).where(Positions.bybit_id == bybit_id)
            )
            main_position = result.scalars().first()

            # Получение зависимых позиций
            dependent_positions_result = await session.execute(
                select(Positions).where(Positions.depends_on == bybit_id)
            )
            dependent_positions = dependent_positions_result.scalars().all()

            # Возврат основной позиции и всех зависимых позиций в виде словаря
            return {
                "main_position": self._position_to_dict(main_position),
                "dependent_positions": [self._position_to_dict(dep_pos) for dep_pos in dependent_positions]
            }

    def _position_to_dict(self, position) -> Optional[Dict]:
        if position:
            return {
                "bybit_id": position.bybit_id,
                "owner_id": position.owner_id,
                "type": position.type,
                "tp_opened": position.tp_opened,
                "market": position.market,
                "order_type": position.order_type,
                "symbol": position.symbol,
                "depends_on": position.depends_on,
                "created": position.created.isoformat() if position.created else None,
                "side": position.side,
                "orderStatus": position.orderStatus,
                "avgPrice": position.avgPrice,
                "cumExecValue": position.cumExecValue,
                "cumExecQty": position.cumExecQty,
                "cumExecFee": position.cumExecFee,
                "triggerPrice": position.triggerPrice,
                "finished": position.finished,
            }
        return None

    async def get_positions_by_field_value(self, field: str, value) -> pd.DataFrame:
        async with self.async_session() as session:
            result = await session.execute(
                select(Positions).where(getattr(Positions, field) == value)
            )
            positions = result.scalars().all()

            # Преобразуем список объектов в список словарей
            positions_dicts = [self._position_to_dict(position) for position in positions]

            # Преобразуем список словарей в DataFrame
            return pd.DataFrame(positions_dicts)


    async def get_positions_by_fields(self, filters: dict) -> pd.DataFrame:
        async with self.async_session() as session:
            # Создаем список условий для фильтрации
            conditions = [getattr(Positions, field) == value for field, value in filters.items()]

            # Объединяем условия с помощью оператора AND
            query = select(Positions).where(and_(*conditions))

            # Выполняем запрос
            result = await session.execute(query)
            positions = result.scalars().all()

            # Преобразуем список объектов в список словарей
            positions_dicts = [self._position_to_dict(position) for position in positions]

            # Преобразуем список словарей в DataFrame
            return pd.DataFrame(positions_dicts)


    async def get_old_unfilled_positions(self) -> List[str]:
        async with self.async_session() as session:
            time_threshold = datetime.now() - timedelta(minutes=300)

            result = await session.execute(
                select(Positions.bybit_id)
                .where(
                    Positions.orderStatus == False,
                    Positions.created <= time_threshold
                )
            )

            bybit_ids = result.scalars().all()
            return bybit_ids

    async def update_position(self, position_data: dict):
        async with self.async_session() as session:
            async with session.begin():
                print("Starting upsert operation...")

                # Попытка найти существующую запись по bybit_id
                existing_position = await session.execute(
                    select(Positions).where(Positions.bybit_id == position_data["bybit_id"])
                )
                existing_position = existing_position.scalars().first()

                if existing_position:
                    print(f"Found existing position with bybit_id: {position_data['bybit_id']}")
                    # Обновление существующей записи
                    for key, value in position_data.items():
                        if key != "bybit_id" and hasattr(existing_position, key):
                            setattr(existing_position, key, value)
                    print("Updated existing position.")
                else:
                    print(
                        f"No existing position found, inserting new position with bybit_id: {position_data['bybit_id']}")
                    # Вставка новой записи
                    stmt = insert(Positions).values(position_data)
                    await session.execute(stmt)
                    print("Inserted new position.")

            await session.commit()
            print("Upsert operation committed.")

if __name__ == "__main__":
    async def main():
        positions_manager = PositionsOperations(DATABASE_URL)

        # Создание таблицы
        #await positions_manager.create_table()

        # Добавление или обновление первой позиции
        first_position = {'bybit_id': '666038149_demo_linear_2df7bb5e074a', 'owner_id': 666038149,
                          'type': 'main', 'market': 'demo', 'order_type': 'linear',
                          'symbol': 'VIDTUSDT', 'side': 'Buy',
                          'orderStatus': True, 'avgPrice': '0.04845', 'cumExecValue': '49.9035',
                          'cumExecQty': '1030', 'cumExecFee': '1.03'}
        #res = await positions_manager.upsert_position(first_position)
        res = await positions_manager.get_positions_by_fields({'bybit_id': '666038149_demo_linear_2df7bb5e074a'})
        print(res[['finished', 'bybit_id']])


    # Запуск асинхронного кода
    asyncio.run(main())
