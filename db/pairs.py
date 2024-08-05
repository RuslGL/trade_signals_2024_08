import os
import asyncio
from dotenv import load_dotenv
from sqlalchemy import Column, String, Boolean, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.dialects.postgresql import insert
from typing import List, Dict, Optional

# Загрузка переменных окружения из .env файла
load_dotenv()

# Получение URL базы данных из переменной окружения
DATABASE_URL = os.getenv('database_url')


BaseSpot = declarative_base()
BaseLinear = declarative_base()

# ####### SPOT ########
#     ############
#        #####


class SpotPairs(BaseSpot):
    """
    Represents a spot pairs with its settings.
    """
    __tablename__ = 'spot_pairs'

    name = Column(String, primary_key=True, nullable=False)
    short_name = Column(String, primary_key=True, nullable=False)
    if_trading = Column(Boolean, nullable=False, server_default='false')  # true only if bot trades it currently

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
                await conn.run_sync(BaseSpot.metadata.create_all)
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
                        set_={
                            'margin_trading': pair.get('margin_trading'),
                            'base_precision': pair.get('base_precision'),
                            'quote_precision': pair.get('quote_precision'),
                            'min_order_qty': pair.get('min_order_qty'),
                            'max_order_qty': pair.get('max_order_qty'),
                            'tick_size': pair.get('tick_size')
                        }
                    )
                    await session.execute(stmt)
            await session.commit()

    async def update_if_trading(self, short_names: List[str], if_trading: bool):
        async with self.async_session() as session:
            async with session.begin():
                await session.execute(
                    text(
                        "UPDATE spot_pairs SET if_trading = :if_trading WHERE short_name = ANY(:short_names)"
                    ),
                    {"if_trading": if_trading, "short_names": short_names}
                )
            await session.commit()

    async def get_spot_pairs_data(self, short_names: List[str]) -> Dict[str, Dict[str, Optional[str]]]:
        async with self.async_session() as session:
            result = await session.execute(
                text(
                    "SELECT * FROM spot_pairs WHERE short_name = ANY(:short_names)"
                ),
                {"short_names": short_names}
            )
            rows = result.mappings().all()

            data = {}
            for row in rows:
                short_name = row['short_name']
                data[short_name] = {
                    'name': row['name'],
                    'short_name': row['short_name'],
                    'if_trading': row['if_trading'],
                    'margin_trading': row['margin_trading'],
                    'base_precision': row['base_precision'],
                    'quote_precision': row['quote_precision'],
                    'min_order_qty': row['min_order_qty'],
                    'max_order_qty': row['max_order_qty'],
                    'tick_size': row['tick_size']
                }
            return data

    async def get_all_spot_pairs_data(self):
        async with self.async_session() as session:
            result = await session.execute(
                text(
                    "SELECT * FROM spot_pairs"
                )
            )
            rows = result.mappings().all()

            data = {}
            for row in rows:
                short_name = row['short_name']
                data[short_name] = {
                    'name': row['name'],
                    'short_name': row['short_name'],
                    'if_trading': row['if_trading'],
                    'margin_trading': row['margin_trading'],
                    'base_precision': row['base_precision'],
                    'quote_precision': row['quote_precision'],
                    'min_order_qty': row['min_order_qty'],
                    'max_order_qty': row['max_order_qty'],
                    'tick_size': row['tick_size']
                }
            return data

# ####### LINEAR ########
#     ############
#        #####

class LinearPairs(BaseLinear):
    """
    Represents a linear pairs with its settings.
    """
    __tablename__ = 'linear_pairs'

    name = Column(String, primary_key=True, nullable=False)
    short_name = Column(String, primary_key=True, nullable=False)
    if_trading = Column(Boolean, nullable=False, server_default='false')  # true only if bot trades it currently

    min_leverage = Column(String, nullable=True)
    max_leverage = Column(String, nullable=True)
    leverage_step = Column(String, nullable=True)
    unified_margin_trade = Column(Boolean, nullable=True)
    min_price = Column(String, nullable=True)
    max_price = Column(String, nullable=True)
    price_tick_size = Column(String, nullable=True)
    max_order_qty = Column(String, nullable=True)
    min_order_qty = Column(String, nullable=True)
    qty_step = Column(String, nullable=True)


class LinearPairsOperations:
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
        if not await self.table_exists(LinearPairs.__tablename__):
            async with self.engine.begin() as conn:
                await conn.run_sync(BaseLinear.metadata.create_all)
            print(f"Table '{LinearPairs.__tablename__}' created successfully.")
        else:
            print(f"Table '{LinearPairs.__tablename__}' already exists, skipping creation.")

    async def insert_linear_pairs(self, pairs: List[Dict[str, Optional[str]]]):
        async with self.async_session() as session:
            async with session.begin():
                for pair in pairs:
                    stmt = insert(LinearPairs).values(
                        name=pair['name'],
                        short_name=pair['short_name'],
                        min_leverage=pair.get('min_leverage'),
                        max_leverage=pair.get('max_leverage'),
                        leverage_step=pair.get('leverage_step'),
                        unified_margin_trade=pair.get('unified_margin_trade'),
                        min_price=pair.get('min_price'),
                        max_price=pair.get('max_price'),
                        price_tick_size=pair.get('price_tick_size'),
                        max_order_qty=pair.get('max_order_qty'),
                        min_order_qty=pair.get('min_order_qty'),
                        qty_step=pair.get('qty_step')
                    ).on_conflict_do_update(
                        index_elements=['name', 'short_name'],
                        set_={
                            'min_leverage': pair.get('min_leverage'),
                            'max_leverage': pair.get('max_leverage'),
                            'leverage_step': pair.get('leverage_step'),
                            'unified_margin_trade': pair.get('unified_margin_trade'),
                            'min_price': pair.get('min_price'),
                            'max_price': pair.get('max_price'),
                            'price_tick_size': pair.get('price_tick_size'),
                            'max_order_qty': pair.get('max_order_qty'),
                            'min_order_qty': pair.get('min_order_qty'),
                            'qty_step': pair.get('qty_step')
                        }
                    )
                    await session.execute(stmt)
            await session.commit()

    async def update_if_trading(self, short_names: List[str], if_trading: bool):
        async with self.async_session() as session:
            async with session.begin():
                await session.execute(
                    text(
                        "UPDATE linear_pairs SET if_trading = :if_trading WHERE short_name = ANY(:short_names)"
                    ),
                    {"if_trading": if_trading, "short_names": short_names}
                )
            await session.commit()

    async def get_linear_pairs_data(self, short_names: List[str]) -> Dict[str, Dict[str, Optional[str]]]:
        async with self.async_session() as session:
            result = await session.execute(
                text(
                    "SELECT * FROM linear_pairs WHERE short_name = ANY(:short_names)"
                ),
                {"short_names": short_names}
            )
            rows = result.mappings().all()

            data = {}
            for row in rows:
                short_name = row['short_name']
                data[short_name] = {
                    'name': row['name'],
                    'short_name': row['short_name'],
                    'if_trading': row['if_trading'],
                    'min_leverage': row['min_leverage'],
                    'max_leverage': row['max_leverage'],
                    'leverage_step': row['leverage_step'],
                    'unified_margin_trade': row['unified_margin_trade'],
                    'min_price': row['min_price'],
                    'max_price': row['max_price'],
                    'price_tick_size': row['price_tick_size'],
                    'max_order_qty': row['max_order_qty'],
                    'min_order_qty': row['min_order_qty'],
                    'qty_step': row['qty_step']
                }
            return data

    async def get_all_linear_pairs_data(self) -> Dict[str, Dict[str, Optional[str]]]:
        async with self.async_session() as session:
            result = await session.execute(
                text("SELECT * FROM linear_pairs")
            )
            rows = result.mappings().all()

            data = {}
            for row in rows:
                short_name = row['short_name']
                data[short_name] = {
                    'name': row['name'],
                    'short_name': row['short_name'],
                    'if_trading': row['if_trading'],
                    'min_leverage': row['min_leverage'],
                    'max_leverage': row['max_leverage'],
                    'leverage_step': row['leverage_step'],
                    'unified_margin_trade': row['unified_margin_trade'],
                    'min_price': row['min_price'],
                    'max_price': row['max_price'],
                    'price_tick_size': row['price_tick_size'],
                    'max_order_qty': row['max_order_qty'],
                    'min_order_qty': row['min_order_qty'],
                    'qty_step': row['qty_step']
                }

        return data


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
            # Добавьте другие пары здесь
        ]

        await db_spot_pairs.insert_spot_pairs(spot_symbols)

        db_linear_pairs = LinearPairsOperations(DATABASE_URL)
        await db_linear_pairs.create_table()

    asyncio.run(main())

