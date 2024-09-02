import os
import uuid
import asyncio
from dotenv import load_dotenv
from typing import List
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import Column, String, DateTime, func, delete, select, BigInteger, Boolean, text
from datetime import datetime, timedelta, timezone


import logging


logging.getLogger('sqlalchemy').setLevel(logging.WARNING)

# Загрузка переменных окружения из .env файла
load_dotenv()

# Получение URL базы данных из переменной окружения
DATABASE_URL = os.getenv('database_url')

Base = declarative_base()

class Alerts(Base):
    """
    Represents alerts to users
    """
    __tablename__ = 'alerts'

    alert_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    telegram_id = Column(BigInteger, nullable=False)
    type = Column(String, nullable=False)
    created = Column(DateTime(timezone=True), server_default=func.now())
    notified = Column(Boolean, default=False)

class AlertsOperations:
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
        if not await self.table_exists(Alerts.__tablename__):
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            print(f"Table '{Alerts.__tablename__}' created successfully.")
        else:
            print(f"Table '{Alerts.__tablename__}' already exists, skipping creation.")

    async def delete_old_alerts(self):
        # Вычисляем дату 24 часа назад
        twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)

        async with self.async_session() as session:
            async with session.begin():
                # Удаляем записи старше 24 часов
                await session.execute(
                    delete(Alerts).where(Alerts.created < twenty_four_hours_ago)
                )
            await session.commit()

    async def upsert_alerts(self, alert_data):
        async with self.async_session() as session:
            async with session.begin():
                # Проверка наличия существующей записи по telegram_id и type
                result = await session.execute(
                    select(Alerts).where(
                        Alerts.telegram_id == alert_data['telegram_id'],
                        Alerts.type == alert_data['type']
                    )
                )
                alert = result.scalars().first()

                if alert:
                    # Обновление существующей записи на основе полей из словаря
                    for key, value in alert_data.items():
                        if key != 'created':  # Не изменяем поле created
                            setattr(alert, key, value)
                else:
                    # Вставка новой записи, если она не существует
                    new_alert = Alerts(**alert_data)
                    session.add(new_alert)

            await session.commit()




    async def get_unnotified_alerts(self):
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(Alerts).where(Alerts.notified == False)
                )
                alerts = result.scalars().all()

                # Преобразование списка объектов в список словарей
                return [
                    {
                        'alert_id': alert.alert_id,
                        'type': alert.type,
                        'telegram_id': alert.telegram_id,
                        'notified': alert.notified,
                    }
                    for alert in alerts
                ]

# Пример использования
if __name__ == '__main__':
    async def main():
        alerts_ops = AlertsOperations(DATABASE_URL)

        # Создание таблицы
        await alerts_ops.create_table()

        # Вставка/обновление алертов
        await alerts_ops.upsert_alerts(['BTCUSD', 'ETHUSD'], telegram_id=123456789)

        # Получение всех ненотифицированных алертов
        unnotified_alerts = await alerts_ops.get_unnotified_alerts()
        print("Unnotified Alerts:", unnotified_alerts)

        # Удаление старых алертов
        await alerts_ops.delete_old_alerts()

    asyncio.run(main())