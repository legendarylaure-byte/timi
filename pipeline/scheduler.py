from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import os
from datetime import datetime

scheduler = BlockingScheduler()

def schedule_daily_generation():
    shorts_per_day = int(os.getenv("SCHEDULE_SHORTS_PER_DAY", 2))
    long_per_day = int(os.getenv("SCHEDULE_LONG_PER_DAY", 2))

    topics = {
        "shorts": [
            "ABC Song with Fun Animations",
            "Counting 1 to 10 with Animals",
            "Learn Colors with Magic",
            "Shapes Adventure Song",
            "Animal Sounds Farm Tour",
            "Days of the Week Dance",
            "Good Manners Song",
            "Weather Song",
        ],
        "long": [
            "The Brave Little Star - Bedtime Story",
            "Ganesha and the Lost Sweet - Myth Story",
            "Why the Sky is Blue - Science for Kids",
            "The Tortoise and the Hare - Fable",
            "Lakshmi Blesses the Village - Myth Story",
            "The Rainbow Fish - Bedtime Story",
            "Hanuman's Great Strength - Myth Story",
            "The Thirsty Crow - Fable",
        ],
    }

    categories = {
        "shorts": ["Self-Learning", "Self-Learning", "Self-Learning", "Self-Learning"],
        "long": ["Bedtime Stories", "Mythology Stories", "Science for Kids", "Animated Fables"],
    }

    print(f"[{datetime.now()}] Daily generation: {shorts_per_day} shorts, {long_per_day} long videos")
    return topics, categories, shorts_per_day, long_per_day

scheduler.add_job(schedule_daily_generation, CronTrigger(hour=6, minute=0, timezone="UTC"))
scheduler.add_job(schedule_daily_generation, CronTrigger(hour=18, minute=0, timezone="UTC"))
