import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.mongodb import MongoDBJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.triggers.cron import CronTrigger
from motor.motor_asyncio import AsyncIOMotorClient
from db import get_mongo_db
from typing import Callable, Dict, Any
import uuid
import logging
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from apscheduler.schedulers.asyncio import AsyncIOScheduler 
from pymongo import MongoClient
import asyncio

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGO_URI)
db = client.crewai_scheduler

mongo_db = get_mongo_db()

logger = logging.getLogger(__name__)

class SchedulerManager:
    def __init__(self):
        self.sync_client = MongoClient(MONGO_URI)
        self.async_client = AsyncIOMotorClient(MONGO_URI)
        self.async_db = self.async_client.crewai_scheduler
        self.scheduler = AsyncIOScheduler(
            jobstores={
                'default': MongoDBJobStore(
                    database='crewai_scheduler',
                    collection='apscheduler_jobs',
                    client=self.sync_client
                ),
            },
            executors={
                'default': AsyncIOExecutor()
            },
            timezone="UTC"
        )

    async def init_scheduler(self):
        try:
            await self._create_indexes()
            self.scheduler.start()
            logger.info("Scheduler initialized with MongoDB backend")
        except Exception as e:
            logger.error(f"Failed to initialize scheduler: {e}")
            raise

    async def _create_indexes(self):
        try:
            await self.async_db.jobs.create_index("job_id", unique=True)
            await self.async_db.jobs.create_index("status")
            await self.async_db.jobs.create_index("next_run")
            logger.info("Created MongoDB indexes")
        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")
            raise

    def _get_trigger(self, schedule: Dict[str, Any]):
        try:
            frequency = schedule.get("frequency", "Daily").lower()
            time = schedule.get("time", "00:00")
            hour, minute = map(int, time.split(":"))

            if frequency == "daily":
                return CronTrigger(hour=hour, minute=minute)
            elif frequency == "weekly":
                return CronTrigger(day_of_week="mon", hour=hour, minute=minute)
            elif frequency == "monthly":
                return CronTrigger(day=1, hour=hour, minute=minute)
            else:
                raise ValueError(f"Unsupported frequency: {frequency}")
        except Exception as e:
            logger.error(f"Error creating trigger: {e}")
            raise

    async def schedule_job(
        self,
        job_func: Callable,
        schedule: Dict[str, Any],
        args: tuple = (),
        kwargs: dict = None,
        metadata: Dict[str, Any] = None,
        job_id: str = None,
        replace_existing: bool = True
    ) -> str:
        try:
            kwargs = kwargs or {}
            metadata = metadata or {}
            job_id = job_id or f"{metadata.get('job_prefix', 'job')}_{uuid.uuid4().hex[:8]}"
            trigger = self._get_trigger(schedule)

            job = self.scheduler.add_job(
                job_func,
                trigger=trigger,
                id=job_id,
                args=args,
                kwargs=kwargs,
                executor='default',
                replace_existing=replace_existing,
                max_instances=3,
            )

            await self.async_db.jobs.insert_one({
                "job_id": job_id,
                "func_name": job_func.__name__,
                "metadata": metadata,
                "schedule": schedule,
                "type": "cron",
                "status": "active",
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None
            })

            logger.info(f"Scheduled job {job_id} ({job_func.__name__})")
            return job_id
        except Exception as e:
            logger.error(f"Failed to schedule job {job_id}: {e}")
            raise

    def get_scheduler(self):
        return self.scheduler

    async def shutdown_scheduler(self):
        try:
            await asyncio.to_thread(self.scheduler.shutdown)
            logger.info("Scheduler shut down successfully")
        except Exception as e:
            logger.error(f"Error shutting down scheduler: {e}")
            raise

scheduler_manager = SchedulerManager()