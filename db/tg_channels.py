import os
import asyncio
from dotenv import load_dotenv
from sqlalchemy import Column, String, Boolean, BigInteger, Float, Integer, text, DateTime, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.dialects.postgresql import insert
from typing import List, Dict, Optional
from sqlalchemy.future import select



# Загрузка переменных окружения из .env файла
load_dotenv()


# Получение URL базы данных из переменной окружения
DATABASE_URL = os.getenv('database_url')



BaseChannels = declarative_base()


class TgChannels(BaseChannels):
    """
    Represents tg channels with its settings.
    """
    __tablename__ = 'tg_channels'

    token = Column(String, primary_key=True, nullable=False)
    telegram_id = Column(String, nullable=False)
    name = Column(String, nullable=True)
    channel_type = Column(String, default='trade_signals') # averaging_signals also available
    created = Column(DateTime, server_default=func.now())  # Automatically set to current timestamp


class TgChannelsOperations:
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
        if not await self.table_exists(TgChannels.__tablename__):
            async with self.engine.begin() as conn:
                await conn.run_sync(BaseChannels.metadata.create_all)
            print(f"Table '{TgChannels.__tablename__}' created successfully.")
        else:
            print(f"Table '{TgChannels.__tablename__}' already exists, skipping creation.")

    async def get_channel_data(self, token: str) -> dict:
        async with self.async_session() as session:
            async with session.begin():
                query = select(TgChannels).where(TgChannels.token == token)
                result = await session.execute(query)
                channel = result.scalar_one_or_none()
                return channel.__dict__ if channel else {}

    async def get_all_channels_data(self) -> dict:
        async with self.async_session() as session:
            async with session.begin():
                query = select(TgChannels)
                result = await session.execute(query)
                channels = result.scalars().all()
                return {channel.token: channel.__dict__ for channel in channels}

    async def upsert_channel(self, channel_data: dict):
        async with self.async_session() as session:
            async with session.begin():
                stmt = insert(TgChannels).values(channel_data).on_conflict_do_update(
                    index_elements=['token'],
                    set_={k: v for k, v in channel_data.items() if k != 'token'}
                )
                await session.execute(stmt)
            await session.commit()

    async def update_channel_fields(self, token: str, fields: dict):
        async with self.async_session() as session:
            async with session.begin():
                query = select(TgChannels).where(TgChannels.token == token)
                result = await session.execute(query)
                channel = result.scalar_one_or_none()
                if channel:
                    for key, value in fields.items():
                        setattr(channel, key, value)
                    session.add(channel)
            await session.commit()


    async def get_averaging_signals_telegram_ids(self) -> list:
        async with self.async_session() as session:
            async with session.begin():
                # Выполняем запрос с фильтрацией по channel_type
                query = select(TgChannels.telegram_id).filter(TgChannels.channel_type == 'averaging_signals')
                result = await session.execute(query)
                telegram_ids = result.scalars().all()

                return telegram_ids


async def main():
    db_tg_channels = TgChannelsOperations(DATABASE_URL)
    await db_tg_channels.create_table()

    main_channel = {
        'token': str(os.getenv('channel')),
        'name': 'main_signal_channel',
    }

    averaging_channel = {
        'token': str(os.getenv('averaging_channel')),
        'name': 'main_averaging_channel',
        'channel_type': 'averaging_signals',
    }

    await db_tg_channels.upsert_channel(main_channel)
    await db_tg_channels.upsert_channel(averaging_channel)


if __name__ == '__main__':
    asyncio.run(main())

