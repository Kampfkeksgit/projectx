"""In-memory Discord rate-limit cache to pace per-channel sends.

discord.py already retries on HTTP 429, but bursty bulk operations still pile up
against Discord's per-channel message route (~5 messages / 5 s) and spam 429
warnings. The classic trigger here: the server-backup restore creates dozens of
channels/roles, and the logs cog posts one embed per event → ~100 messages slam
the same log channel within seconds.

This limiter caches the recent send timestamps per channel and *proactively*
waits before sending, so we stay under the limit instead of being throttled
after the fact. Pure in-memory, no dependency, safe across cogs.

Usage:
    from utils.ratelimit import safe_send
    await safe_send(channel, embed=embed)
"""

import asyncio
import time
from collections import defaultdict, deque


class ChannelRateLimiter:
    """Sliding-window limiter keyed by channel id.

    Allows at most `max_calls` acquisitions per `period` seconds per key; callers
    beyond that await until a slot frees up. A per-key lock serializes waiters so
    sends to the same channel stay ordered and drain at a steady rate.
    """

    def __init__(self, max_calls=5, period=5.0):
        self.max_calls = max(1, int(max_calls))
        self.period = float(period)
        self._hits = defaultdict(deque)      # key -> deque[monotonic timestamps]
        self._locks = defaultdict(asyncio.Lock)

    async def acquire(self, key):
        """Block until a call for `key` stays within the configured limit."""
        async with self._locks[key]:
            while True:
                now = time.monotonic()
                hits = self._hits[key]
                while hits and now - hits[0] >= self.period:
                    hits.popleft()
                if len(hits) < self.max_calls:
                    hits.append(now)
                    return
                # oldest hit decides how long until a slot frees up
                wait = self.period - (now - hits[0])
                if wait > 0:
                    await asyncio.sleep(wait)


# Shared singleton — Discord's per-channel message create limit is ~5 / 5 s.
channel_limiter = ChannelRateLimiter(max_calls=5, period=5.0)


async def safe_send(channel, **kwargs):
    """`channel.send(**kwargs)` paced through the per-channel rate-limit cache.

    Returns the sent message. Raises whatever `channel.send` raises (callers keep
    their own try/except for Forbidden/HTTPException).
    """
    await channel_limiter.acquire(channel.id)
    return await channel.send(**kwargs)
