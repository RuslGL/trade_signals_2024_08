import os
import asyncio
from dotenv import load_dotenv
from sqlalchemy import Column, String, create_engine, text, Boolean
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from typing import List, Dict, Optional

from sqlalchemy.dialects.postgresql import insert

# Загрузка переменных окружения из .env файла
load_dotenv()

# Получение URL базы данных из переменной окружения
DATABASE_URL = str(os.getenv('database_url'))

Base = declarative_base()

class SpotPairs(Base):
    """
    Represents a spot pairs with its settings.
    """
    __tablename__ = 'spot_pairs'

    name = Column(String, primary_key=True, nullable=False)
    short_name = Column(String, primary_key=True, nullable=False)
    # if_trading = Column(Boolean, nullable=False, server_default='false') # true only if bot trades it currently

    margin_trading = Column(String, nullable=True)  # none, both, utaOnly, normalSpotOnly
    base_precision = Column(String, nullable=True)  # precision of base coin
    quote_precision = Column(String, nullable=True)  # precision of quote coin
    min_order_qty = Column(String, nullable=True)  # minimum order in base coin
    max_order_qty = Column(String, nullable=True)  # maximum order in base coin
    tick_size = Column(String, nullable=True)  # step to change price

class SpotPairsOperations:
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
        if not await self.table_exists(SpotPairs.__tablename__):
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            print(f"Table '{SpotPairs.__tablename__}' created successfully.")
        else:
            print(f"Table '{SpotPairs.__tablename__}' already exists, skipping creation.")



    async def insert_spot_pairs(self, pairs: List[Dict[str, Optional[str]]]):
        async with self.async_session() as session:
            async with session.begin():
                for pair in pairs:
                    stmt = insert(SpotPairs).values(
                        name=pair['name'],
                        short_name=pair['short_name'],
                        margin_trading=pair.get('margin_trading'),
                        base_precision=pair.get('base_precision'),
                        quote_precision=pair.get('quote_precision'),
                        min_order_qty=pair.get('min_order_qty'),
                        max_order_qty=pair.get('max_order_qty'),
                        tick_size=pair.get('tick_size')
                    ).on_conflict_do_update(
                        index_elements=['name', 'short_name'],
                        set_=pair
                    )
                    await session.execute(stmt)
            await session.commit()

if __name__ == '__main__':


    async def main():
        db_spot_pairs = SpotPairsOperations(DATABASE_URL)
        await db_spot_pairs.create_table()

        spot_symbols = [
            {
                'name': 'BTCUSDT',
                'short_name': 'BTC',
                'base_precision': '8',
                'quote_precision': '8',
                'min_order_qty': '0.001',
                'max_order_qty': '1000',
                'tick_size': '0.01'
            },

        ]

        await db_spot_pairs.insert_spot_pairs(spot_symbols)

    asyncio.run(main())
