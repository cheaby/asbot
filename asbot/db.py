
from aiosqlite import connect

from datetime import datetime, timedelta


_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id integer PRIMARY key,
    exp DATETIME,
    f BOOL)
"""


_APPLY_SUB = """
INSERT OR REPLACE INTO users (id, exp, f) VALUES (?, ?, ?)
"""

_DISC_SUB = """
DELETE from users WHERE id = ?
"""

_GET_EXP_SUB = """
SELECT * FROM users WHERE f != 1 AND CURRENT_DATE > exp
"""

_GET_INFO_SUB = """
SELECT * FROM users WHERE id = ?
"""


class Users:

    def __init__(self, dbpath):
        self._db = dbpath

    async def create(self):
        async with connect(self._db) as _db:
            await _db.execute(_CREATE_TABLE)
            await _db.commit()

    async def apply_subscription(self, user_id: int, days: int, is_infinity: bool) -> None:
        """Apply subscription.

        Apply subscription, if user has no subscription, but
        if he has, update it.

        :param int user_id: Unique ID of user
        :param int days: lifetime of the subscription
        :param int is_infinity: applied for infinity subscription, it will never expire
        """
        _exp_date = datetime.now() + timedelta(days=days)

        async with connect(self._db) as _db:
            await _db.execute(_APPLY_SUB, (user_id, _exp_date, is_infinity))
            await _db.commit()

    async def discard_subscription(self, user_id: int) -> None:
        """Discard subscription

        :param int user_id: Unique ID of user
        """
        async with connect(self._db) as _db:
            await _db.execute(_DISC_SUB, (user_id, ))
            await _db.commit()

    async def get_expiried(self) -> tuple:
        """Get expiried subscriptions

        :return: sequence of rows with values (user_id, expdate)
        """
        async with connect(self._db) as _db:
            async with _db.execute(_GET_EXP_SUB) as _c:
                return await _c.fetchall()

    async def get_sub(self, user_id: int) -> tuple:
        """Get info about subscription

        :return: row with (user_id, expdate) values
        """
        async with connect(self._db) as _db:
            async with _db.execute(_GET_INFO_SUB, (user_id, )) as _c:
                return await _c.fetchone()
