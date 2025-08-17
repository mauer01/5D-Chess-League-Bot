import sqlite3, os
import unittest
import database_initialiser
from database import (
    register_new_player,
    setCurrentDBFile,
    update_player_stats,
)


class TestDatabase(unittest.TestCase):
    db_path = ":memory:"

    @classmethod
    def setUpClass(cls):
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)
        database_initialiser.init_db(cls.db_path, False)
        setCurrentDBFile(cls.db_path)

    def test_register_new_player(self):
        testplayerid = 1234213213
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        register_new_player(testplayerid)
        with self.assertRaises(sqlite3.IntegrityError):
            register_new_player(testplayerid)
        result = c.execute(
            "SELECT 1 FROM players where id = ? and elo = 1380 and wins = 0 and losses = 0 and draws = 0 and signed_up = 0 and seasons_missed = 0;",
            (testplayerid,),
        ).fetchone()
        self.assertEqual(result[0], 1)
        update_player_stats(testplayerid, 1300)
        result = c.execute(
            "SELECT 1 FROM players where id = ? and elo = 1300 and wins = 0 and losses = 0 and draws = 0 and signed_up = 0 and seasons_missed = 0;",
            (testplayerid,),
        ).fetchone()
        result2 = c.execute(
            "SELECT 1 FROM players where id = ? and elo = 1300 and wins = 0 and losses = 0 and draws = 0 and signed_up = 0 and seasons_missed = 0;",
            (testplayerid,),
        ).fetchone()

        self.assertNotEqual(result, result2)
