import asyncio
import os
from sqlalchemy import Column, String, DateTime, BigInteger, func, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.future import select
from sqlalchemy.sql import insert, delete
from dotenv import load_dotenv

import uuid

load_dotenv()

BasePNL = declarative_base()

from datetime import datetime, timedelta
from datetime import datetime, timezone


def get_start_of_day_utc():
    # Устанавливаем время на начало дня (00:00:00) и преобразуем в UTC
    return datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)

class PNL(BasePNL):
    """
    Represents daily budget snapshots.
    """
    __tablename__ = 'PNL'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(BigInteger, nullable=False)
    #created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0))
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_start_of_day_utc)

    total_budget = Column(String, nullable=False)

class PNLManager:
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
        if not await self.table_exists(PNL.__tablename__):
            async with self.engine.begin() as conn:
                await conn.run_sync(BasePNL.metadata.create_all)
            print(f"Table '{PNL.__tablename__}' created successfully.")
        else:
            print(f"Table '{PNL.__tablename__}' already exists, skipping creation.")

    async def add_pnl_entry(self, pnl_data: dict):
        async with self.async_session() as session:
            async with session.begin():
                stmt = insert(PNL).values(pnl_data)
                await session.execute(stmt)
            await session.commit()

    async def delete_entries_by_user_id(self, user_id: int):
        async with self.async_session() as session:
            async with session.begin():
                stmt = delete(PNL).where(PNL.user_id == user_id)
                await session.execute(stmt)
            await session.commit()

    async def calculate_percentage_difference(self, user_id: int) -> dict:
        async with self.async_session() as session:
            async with session.begin():
                query = select(PNL).where(PNL.user_id == user_id).order_by(PNL.created_at)
                result = await session.execute(query)
                pnl_records = result.scalars().all()

                if len(pnl_records) < 2:
                    return {}  # Недостаточно данных для вычисления

                latest = pnl_records[-1]
                initial = pnl_records[0]

                data = {}
                data['initial_vs_latest_percent'] = (float(latest.total_budget) - float(initial.total_budget)) / float(initial.total_budget) * 100
                data['initial_vs_latest'] = (float(latest.total_budget) - float(initial.total_budget))

                # Проверка на день назад
                day_ago = [record for record in pnl_records if (latest.created_at - record.created_at).days >= 1]
                if day_ago:
                    data['day_ago_vs_latest_percent'] = (float(latest.total_budget) - float(day_ago[-1].total_budget)) / float(day_ago[-1].total_budget) * 100
                    data['day_ago_vs_latest'] = (float(latest.total_budget) - float(day_ago[-1].total_budget))

                # Проверка на неделю назад
                week_ago = [record for record in pnl_records if (latest.created_at - record.created_at).days >= 7]
                if week_ago:
                    data['week_ago_vs_percent'] = (float(latest.total_budget) - float(week_ago[-1].total_budget)) / float(week_ago[-1].total_budget) * 100
                    data['week_ago_vs'] = (float(latest.total_budget) - float(week_ago[-1].total_budget))

                # Проверка на месяц назад
                month_ago = [record for record in pnl_records if (latest.created_at - record.created_at).days >= 30]
                if month_ago:
                    data['month_ago_vs_latest_percent'] = (float(latest.total_budget) - float(month_ago[-1].total_budget)) / float(month_ago[-1].total_budget) * 100
                    data['month_ago_vs_latest'] = (float(latest.total_budget) - float(month_ago[-1].total_budget))
                return data


async def main():
    DATABASE_URL = str(os.getenv('database_url'))
    pnl_manager = PNLManager(DATABASE_URL)
    await pnl_manager.create_table()

    # Удаление старых записей
    await pnl_manager.delete_entries_by_user_id(1)

    # Создание записей для тестирования с положительными и отрицательными значениями
    current_time = datetime.utcnow()
    pnl_data = [
        { 'user_id': 666038149, 'created_at': get_start_of_day_utc() - timedelta(days=365), 'total_budget': '1000.00'},
        { 'user_id': 666038149, 'created_at': get_start_of_day_utc() - timedelta(days=30), 'total_budget': '1100.00'},  # Положительное изменение
        { 'user_id': 666038149, 'created_at': get_start_of_day_utc() - timedelta(days=7), 'total_budget': '1050.00'},  # Отрицательное изменение
        { 'user_id': 666038149, 'created_at': get_start_of_day_utc() - timedelta(days=1), 'total_budget': '1200.00'},  # Положительное изменение
        { 'user_id': 666038149, 'created_at': get_start_of_day_utc(), 'total_budget': '1100.00'},  # Отрицательное изменение
    ]

    for entry in pnl_data:
        await pnl_manager.add_pnl_entry(entry)

    # Пример вычисления разницы в процентах
    differences = await pnl_manager.calculate_percentage_difference(user_id=666038149)
    print(differences)

if __name__ == '__main__':
    asyncio.run(main())

