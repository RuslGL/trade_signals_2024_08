import os
import asyncio
from dotenv import load_dotenv
from sqlalchemy import Column, String
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.future import select
from sqlalchemy import Column, String, DateTime, func, text


# Загрузка переменных окружения из .env файла
load_dotenv()

# Получение URL базы данных из переменной окружения
DATABASE_URL = os.getenv('database_url')

BaseChannels = declarative_base()

class TgChannels(BaseChannels):
    """
    Represents averaging tg channels only.
    """
    __tablename__ = 'tg_channels'

    telegram_id = Column(String, primary_key=True, nullable=False)

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

    async def upsert_channel(self, channel_data: dict):
        async with self.async_session() as session:
            async with session.begin():
                # Если словарь для обновления пустой, ничего не делаем
                update_dict = {k: v for k, v in channel_data.items() if k != 'telegram_id'}
                if update_dict:  # Проверяем, не пустой ли словарь для обновления
                    stmt = insert(TgChannels).values(channel_data).on_conflict_do_update(
                        index_elements=['telegram_id'],
                        set_=update_dict
                    )
                    await session.execute(stmt)
                else:
                    # Если нет данных для обновления, просто вставляем
                    stmt = insert(TgChannels).values(channel_data)
                    await session.execute(stmt)
            await session.commit()

    async def delete_channel(self, telegram_id: str):
        async with self.async_session() as session:
            async with session.begin():
                query = select(TgChannels).where(TgChannels.telegram_id == telegram_id)
                result = await session.execute(query)
                channel = result.scalar_one_or_none()
                if channel:
                    await session.delete(channel)
            await session.commit()

    async def get_all_channels(self) -> list:
        async with self.async_session() as session:
            async with session.begin():
                query = select(TgChannels.telegram_id)
                result = await session.execute(query)
                telegram_ids = result.scalars().all()
                return telegram_ids

async def main():
    db_tg_channels = TgChannelsOperations(DATABASE_URL)
    await db_tg_channels.create_table()

    # Вставка и удаление объектов
    channel_to_upsert = {
        'telegram_id': str(os.getenv('averaging_channel')),
    }

    await db_tg_channels.upsert_channel(channel_to_upsert)
    # await db_tg_channels.delete_channel(str(os.getenv('averaging_channel')))

    # Получение списка всех каналов
    channels = await db_tg_channels.get_all_channels()
    print(channels)

if __name__ == '__main__':
    asyncio.run(main())





# import os
# import asyncio
# from dotenv import load_dotenv
# from sqlalchemy import Column, String, DateTime, func, text
# from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
# from sqlalchemy.orm import declarative_base, sessionmaker
# from sqlalchemy.dialects.postgresql import insert
# from sqlalchemy.future import select
#
# # Загрузка переменных окружения из .env файла
# load_dotenv()
#
# # Получение URL базы данных из переменной окружения
# DATABASE_URL = os.getenv('database_url')
#
# BaseChannels = declarative_base()
#
# class TgChannels(BaseChannels):
#     """
#     Represents tg channels with its settings.
#     """
#     __tablename__ = 'tg_channels'
#
#     telegram_id = Column(String, primary_key=True, nullable=False)
#     name = Column(String, nullable=True)
#     channel_type = Column(String, default='regular') # averaging_signals also available
#     created = Column(DateTime, server_default=func.now())  # Automatically set to current timestamp
#
# class TgChannelsOperations:
#     def __init__(self, database_url: str):
#         self.engine = create_async_engine(database_url, echo=False)
#         self.async_session = sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
#
#     async def table_exists(self, table_name: str) -> bool:
#         async with self.engine.connect() as conn:
#             result = await conn.scalar(
#                 text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = :table_name)"),
#                 {"table_name": table_name}
#             )
#             return result
#
#     async def create_table(self):
#         if not await self.table_exists(TgChannels.__tablename__):
#             async with self.engine.begin() as conn:
#                 await conn.run_sync(BaseChannels.metadata.create_all)
#             print(f"Table '{TgChannels.__tablename__}' created successfully.")
#         else:
#             print(f"Table '{TgChannels.__tablename__}' already exists, skipping creation.")
#
#     async def get_channel_data(self, telegram_id: str) -> dict:
#         async with self.async_session() as session:
#             async with session.begin():
#                 query = select(TgChannels).where(TgChannels.telegram_id == telegram_id)
#                 result = await session.execute(query)
#                 channel = result.scalar_one_or_none()
#                 return channel.__dict__ if channel else {}
#
#     async def get_all_channels_data(self) -> dict:
#         async with self.async_session() as session:
#             async with session.begin():
#                 query = select(TgChannels)
#                 result = await session.execute(query)
#                 channels = result.scalars().all()
#                 return {channel.telegram_id: channel.__dict__ for channel in channels}
#
#     async def upsert_channel(self, channel_data: dict):
#         async with self.async_session() as session:
#             async with session.begin():
#                 stmt = insert(TgChannels).values(channel_data).on_conflict_do_update(
#                     index_elements=['telegram_id'],
#                     set_={k: v for k, v in channel_data.items() if k != 'telegram_id'}
#                 )
#                 await session.execute(stmt)
#             await session.commit()
#
#     async def update_channel_fields(self, telegram_id: str, fields: dict):
#         async with self.async_session() as session:
#             async with session.begin():
#                 query = select(TgChannels).where(TgChannels.telegram_id == telegram_id)
#                 result = await session.execute(query)
#                 channel = result.scalar_one_or_none()
#                 if channel:
#                     for key, value in fields.items():
#                         setattr(channel, key, value)
#                     session.add(channel)
#             await session.commit()
#
#     async def get_averaging_signals_telegram_ids(self) -> list:
#         async with self.async_session() as session:
#             async with session.begin():
#                 query = select(TgChannels.telegram_id).filter(TgChannels.channel_type == 'averaging_signals')
#                 result = await session.execute(query)
#                 telegram_ids = result.scalars().all()
#                 return telegram_ids
#
#     async def get_channels_by_type(self) -> tuple:
#         async with self.async_session() as session:
#             async with session.begin():
#                 # Запрос для каналов с типом 'averaging_signals'
#                 query_averaging = select(TgChannels).where(TgChannels.channel_type == 'averaging')
#                 result_averaging = await session.execute(query_averaging)
#                 averaging_channels = result_averaging.scalars().all()
#                 averaging_channels_settings = [channel.__dict__ for channel in averaging_channels]
#
#                 # Запрос для всех остальных каналов
#                 query_others = select(TgChannels).where(TgChannels.channel_type != 'averaging')
#                 result_others = await session.execute(query_others)
#                 other_channels = result_others.scalars().all()
#                 other_channels_settings = [channel.__dict__ for channel in other_channels]
#
#                 # Возвращаем кортеж из двух списков настроек
#                 return averaging_channels_settings, other_channels_settings
#
# async def main():
#     db_tg_channels = TgChannelsOperations(DATABASE_URL)
#     await db_tg_channels.create_table()
#
#     main_channel = {
#         'telegram_id': str(os.getenv('channel')),
#         'name': 'main_signal_channel',
#     }
#
#     averaging_channel = {
#         'telegram_id': str(os.getenv('averaging_channel')),
#         'name': 'main_averaging_channel',
#         'channel_type': 'averaging',
#     }
#
#     await db_tg_channels.upsert_channel(main_channel)
#     await db_tg_channels.upsert_channel(averaging_channel)
#     res = await db_tg_channels.get_channels_by_type()
#     print(res)
#
# if __name__ == '__main__':
#     asyncio.run(main())
