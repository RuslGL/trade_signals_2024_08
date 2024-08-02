import asyncio
import os

from dotenv import load_dotenv

from db.pairs import SpotPairsOperations, LinearPairsOperations
from api.market import process_spot_linear_settings

load_dotenv()

DATABASE_URL = str(os.getenv('database_url'))


async def params_download():
    db_spot_pairs = SpotPairsOperations(DATABASE_URL)
    db_linear_pairs = LinearPairsOperations(DATABASE_URL)

    tasks = [
        asyncio.create_task(process_spot_linear_settings()),
        asyncio.create_task(db_spot_pairs.create_table()),
        asyncio.create_task(db_linear_pairs.create_table())
    ]

    tasks_res = await asyncio.gather(*tasks)

    tasks = [
        asyncio.create_task(db_spot_pairs.insert_spot_pairs(tasks_res[0][0])),
        asyncio.create_task(db_linear_pairs.insert_linear_pairs(tasks_res[0][1])),
    ]
    await asyncio.gather(*tasks)


async def main():
    await params_download()

asyncio.run(main())
