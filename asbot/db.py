
from datetime import datetime, timedelta
from aiosqlite import connect


_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id integer PRIMARY key,
    exp DATETIME,
    f BOOL,
    spent INTEGER DEFAULT 0)
"""


_REGISTER_USER = """
INSERT OR IGNORE INTO users (id) VALUES (?)
"""

_APPLY_SUB = """
UPDATE users SET exp = ?, f = ?, spent = spent + ? WHERE id = ?
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

_GET_SPENT = """
SELECT * FROM users WHERE id = ?
"""


class UserModel:
    user_id: int
    expdate: str
    is_infinity: bool
    spent: int

    def __init__(self, data):
        self.user_id = data[0]
        self.expdate = data[1]
        self.is_infinity = data[2]
        self.spent = data[3]


class Users:

    def __init__(self, dbpath):
        self._db = dbpath

    async def create(self):
        async with connect(self._db) as _db:
            await _db.execute(_CREATE_TABLE)
            await _db.commit()

    async def register_user(self, user_id: int):
        async with connect(self._db) as _db:
            await _db.execute(_REGISTER_USER, (user_id, ))
            await _db.commit()

    async def apply_subscription(self, user_id: int, days: int, is_infinity: bool, amount: int) -> None:
        """Apply subscription.

        Apply subscription, if user has no subscription, but
        if he has, update it.

        :param int user_id: Unique ID of user
        :param int days: lifetime of the subscription
        :param int is_infinity: applied for infinity subscription, it will never expire
        :param int amount: cost of the subscription
        """
        _exp_date = datetime.now() + timedelta(days=days)

        async with connect(self._db) as _db:
            await _db.execute(_APPLY_SUB, (_exp_date, is_infinity, amount, user_id))
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

    async def get_user_data(self, user_id: int) -> UserModel:
        """Get info about subscription

        :return: row with (user_id, expdate, f, spent) values
        """
        async with connect(self._db) as _db:
            async with _db.execute(_GET_INFO_SUB, (user_id, )) as _c:
                return UserModel(await _c.fetchone())
