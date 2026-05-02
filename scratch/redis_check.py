import asyncio
import redis.asyncio as redis

async def check():
    try:
        r = redis.from_url("redis://localhost:6379/0", socket_timeout=2)
        await r.ping()
        print("Connected to Redis!")
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(check())
