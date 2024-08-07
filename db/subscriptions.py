
import os
import asyncio
from dotenv import load_dotenv
from sqlalchemy import Column, String, DateTime, func, insert, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.future import select

from sqlalchemy.dialects.postgresql import insert

# Загрузка переменных окружения из .env файла
load_dotenv()

# Получение URL базы данных из переменной окружения
DATABASE_URL = os.getenv('database_url')

BaseSubscriptions = declarative_base()

class Subscriptions(BaseSubscriptions):
    """
    Represents subscriptions with its tariffs.
    """
    __tablename__ = 'subscriptions'

    name = Column(String, primary_key=True, nullable=False)
    duration_days = Column(String, nullable=True) # 1m, 6m, 1year, forever
    cost = Column(String, nullable=True)
    created = Column(DateTime, server_default=func.now())

class SubscriptionsOperations:
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
        if not await self.table_exists(Subscriptions.__tablename__):
            async with self.engine.begin() as conn:
                await conn.run_sync(BaseSubscriptions.metadata.create_all)
            print(f"Table '{Subscriptions.__tablename__}' created successfully.")
        else:
            print(f"Table '{Subscriptions.__tablename__}' already exists, skipping creation.")

    async def get_subscription_data(self, name: str) -> dict:
        async with self.async_session() as session:
            async with session.begin():
                query = select(Subscriptions).where(Subscriptions.name == name)
                result = await session.execute(query)
                subscription = result.scalar_one_or_none()
                return subscription.__dict__ if subscription else {}

    async def get_all_subscriptions_data(self) -> dict:
        async with self.async_session() as session:
            async with session.begin():
                query = select(Subscriptions)
                result = await session.execute(query)
                subscriptions = result.scalars().all()
                return {subscription.name: subscription.__dict__ for subscription in subscriptions}


    async def upsert_subscription(self, subscription_data: dict):
        async with self.async_session() as session:
            async with session.begin():
                stmt = insert(Subscriptions).values(subscription_data).on_conflict_do_update(
                    index_elements=['name'],
                    set_=subscription_data
                )
                await session.execute(stmt)
            await session.commit()

    async def update_subscription_fields(self, name: str, fields: dict):
        async with self.async_session() as session:
            async with session.begin():
                query = select(Subscriptions).where(Subscriptions.name == name)
                result = await session.execute(query)
                subscription = result.scalar_one_or_none()
                if subscription:
                    for key, value in fields.items():
                        setattr(subscription, key, value)
                    session.add(subscription)
            await session.commit()


if __name__ == '__main__':
    async def main():
        db_subscriptions = SubscriptionsOperations(DATABASE_URL)
        await db_subscriptions.create_table()

        subscriptions_data = [
            {
                'name': '1 МЕСЯЦ',
                'duration_days': '30',
                'cost': '10'
            },
            {
                'name': '6 МЕСЯЦЕВ',
                'duration_days': '365',
                'cost': '20.00'
            },
            {
                'name': '1 ГОД',
                'duration_days': 'forever',
                'cost': '30.00'
            },
            {
                'name': 'НАВСЕГДА',
                'duration_days': 'forever',
                'cost': '30.00'
            }
        ]

        for subscription_data in subscriptions_data:
            await db_subscriptions.upsert_subscription(subscription_data)

    asyncio.run(main())