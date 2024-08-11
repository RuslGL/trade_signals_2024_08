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


BaseUsers = declarative_base()


class Users(BaseUsers):
    """
    Represents a users with its settings.
    """
    __tablename__ = 'users'

    telegram_id = Column(BigInteger, primary_key=True, nullable=False)
    username = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False)
    subscription = Column(BigInteger, nullable=True)
    stop_trading = Column(Boolean, default=True)
    created = Column(DateTime, server_default=func.now())  # Automatically set to current timestamp

    # api
    main_api_key = Column(String, nullable=True)
    main_secret_key = Column(String, nullable=True)

    demo_api_key = Column(String, nullable=True)
    demo_secret_key = Column(String, nullable=True)

    # trade
    trade_type = Column(String, nullable='real') # real/demo

    min_trade = Column(Float, nullable=True)
    max_trade = Column(Float, nullable=True)

    spot = Column(Boolean, default=True) # if false trade linear
    # futures = Column(Boolean, default=False)

    tp = Column(Float, nullable=True)
    sl = Column(Float, nullable=True)
    averaging = Column(Boolean, default=False)

    leverage = Column(Float, nullable=True)
    max_leverage = Column(Float, nullable=True)

    risk_tolerance = Column(BigInteger, nullable=True) # stop trade if below

    orders_type = Column(String, nullable=True)
    limit_order_slip = Column(Float, nullable=True)

    max_positions = Column(Integer, nullable=True)


class UsersOperations:
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
        if not await self.table_exists(Users.__tablename__):
            async with self.engine.begin() as conn:
                await conn.run_sync(BaseUsers.metadata.create_all)
            print(f"Table '{Users.__tablename__}' created successfully.")
        else:
            print(f"Table '{Users.__tablename__}' already exists, skipping creation.")


    async def create_table(self):
        if not await self.table_exists(Users.__tablename__):
            async with self.engine.begin() as conn:
                await conn.run_sync(BaseUsers.metadata.create_all)
            print(f"Table '{Users.__tablename__}' created successfully.")
        else:
            print(f"Table '{Users.__tablename__}' already exists, skipping creation.")

    async def get_user_data(self, telegram_id: int) -> dict:
        async with self.async_session() as session:
            async with session.begin():
                query = select(Users).where(Users.telegram_id == telegram_id)
                result = await session.execute(query)
                user = result.scalar_one_or_none()
                return user.__dict__ if user else {}

    async def get_all_users_data(self) -> dict:
        async with self.async_session() as session:
            async with session.begin():
                query = select(Users)
                result = await session.execute(query)
                users = result.scalars().all()
                return {user.telegram_id: user.__dict__ for user in users}

    async def upsert_user(self, user_data: dict):
        async with self.async_session() as session:
            async with session.begin():
                stmt = insert(Users).values(user_data).on_conflict_do_update(
                    index_elements=['telegram_id'],
                    set_=user_data
                )
                await session.execute(stmt)
            await session.commit()

    async def update_user_fields(self, telegram_id: int, fields: dict):
        async with self.async_session() as session:
            async with session.begin():
                query = select(Users).where(Users.telegram_id == telegram_id)
                result = await session.execute(query)
                user = result.scalar_one_or_none()
                if user:
                    for key, value in fields.items():
                        setattr(user, key, value)
                    session.add(user)
            await session.commit()

    async def get_active_users(self) -> List[Dict[str, Optional[str]]]:
        async with self.async_session() as session:
            async with session.begin():
                # Текущая дата и время
                current_time = func.now()

                # Запрос для получения всех пользователей с подпиской больше текущего времени
                query = select(Users.telegram_id, Users.username).where(
                    func.to_timestamp(Users.subscription) > current_time)
                result = await session.execute(query)
                active_users = result.fetchall()

                # Преобразование результатов в список словарей
                return [{'telegram_id': user.telegram_id, 'username': user.username or 'N/A'} for user in active_users]

    async def get_inactive_users(self) -> List[Dict[str, Optional[str]]]:
        async with self.async_session() as session:
            async with session.begin():
                # Текущая дата и время
                current_time = func.now()

                # Запрос для получения всех пользователей с подпиской меньше или равной текущему времени
                query = select(Users.telegram_id, Users.username).where(
                    func.to_timestamp(Users.subscription) <= current_time)
                result = await session.execute(query)
                inactive_users = result.fetchall()

                # Преобразование результатов в список словарей с учетом отсутствующих значений
                return [{'telegram_id': user.telegram_id, 'username': user.username or 'N/A'} for user in
                        inactive_users]

if __name__ == '__main__':
    async def main():
        db_users = UsersOperations(DATABASE_URL)
        await db_users.create_table()



        users_data = [
            {
                'telegram_id': 1,
                'is_admin': True,
                'subscription': 1712265600,  # Example timestamp
                'stop_trading': True,

            },
            {
                'telegram_id': 2,
                'subscription': 1712265600,
                'stop_trading': False,
            },
            {
                'telegram_id': 3,
                'subscription': 1712265600,
                'stop_trading': True,
            },
            {
                'telegram_id': 4,
                'subscription': 1712265600,
                'stop_trading': False,
            },
            {
                'telegram_id': 5,
                'subscription': 1712265600,
                'stop_trading': True,
            }
        ]

        #for user_data in users_data:
        #    await db_users.upsert_user(user_data)


        # admin_id = int(os.getenv('owner_id'))

        res = await db_users.get_active_users()
        print(res)

    asyncio.run(main())
