import os
import uuid


from dotenv import load_dotenv

import asyncio
from sqlalchemy import Column, String, DateTime, insert, select, text, delete
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.sql import func


# Загрузка переменных окружения из .env файла
load_dotenv()


Base = declarative_base()

DATABASE_URL = os.getenv('database_url')

class Signals(Base):
    """
    Represents signals with its settings.
    """
    __tablename__ = 'signals'

    # signal_id = Column(String, primary_key=True)
    signal_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    direction = Column(String, nullable=False)
    channel_id = Column(String, nullable=True)
    coin = Column(String, nullable=False)
    created = Column(DateTime, server_default=func.now())


class SignalsOperations:
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
        if not await self.table_exists(Signals.__tablename__):
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            print(f"Table '{Signals.__tablename__}' created successfully.")
        else:
            print(f"Table '{Signals.__tablename__}' already exists, skipping creation.")

    async def upsert_signal(self, signal_data: dict):
        async with self.async_session() as session:
            async with session.begin():
                stmt = insert(Signals).values(signal_data).on_conflict_do_update(
                    index_elements=['signal_id'],
                    set_=signal_data
                )
                await session.execute(stmt)
            await session.commit()

    async def get_and_clear_all_signals(self) -> dict:
        async with self.async_session() as session:
            async with session.begin():
                # Получаем все сигналы
                query = select(Signals)
                result = await session.execute(query)
                signals = result.scalars().all()
                signal_data = {signal.signal_id: signal.__dict__ for signal in signals}

                # Удаляем все сигналы
                if signals:
                    await session.execute(delete(Signals))
                    await session.commit()

                return signal_data



async def main():
    db_signals = SignalsOperations(DATABASE_URL)

    # Создание таблицы
    await db_signals.create_table()

    # Добавление или обновление сигналов
    await db_signals.upsert_signal({
       #"signal_id": "1",
       "direction": "buy",
       "coin": "BTC",
       "channel_id": '202'

    })
    await db_signals.upsert_signal({
       #"signal_id": "2",
       "direction": "sell",
       "coin": "ETH",
       "channel_id": '202'
    })

    # Получение и удаление всех сигналов
    #all_signals = await db_signals.get_and_clear_all_signals()
    #print("All signals:", all_signals)


if __name__ == "__main__":
    asyncio.run(main())



