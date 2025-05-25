import asyncio
from datetime import datetime, timedelta
import sqlite3


def init_db():
    conn = sqlite3.connect("elo_bot.db")
    c = conn.cursor()

    c.execute(
        """CREATE TABLE IF NOT EXISTS players
                 (
                     id
                     INTEGER
                     PRIMARY
                     KEY,
                     elo
                     INTEGER
                     DEFAULT
                     1380,
                     wins
                     INTEGER
                     DEFAULT
                     0,
                     losses
                     INTEGER
                     DEFAULT
                     0,
                     draws
                     INTEGER
                     DEFAULT
                     0,
                     signed_up
                     INTEGER
                     DEFAULT
                     0
                 )"""
    )

    c.execute(
        """CREATE TABLE IF NOT EXISTS pending_reps
                 (
                     id
                     INTEGER
                     PRIMARY
                     KEY
                     AUTOINCREMENT,
                     pairing_id
                     INTEGER,
                     reporter_id
                     INTEGER,
                     result
                     TEXT,
                     game_number
                     INTEGER,
                     timestamp
                     DATETIME
                     DEFAULT
                     CURRENT_TIMESTAMP
                 )"""
    )

    c.execute(
        """CREATE TABLE IF NOT EXISTS seasons
                 (
                     season_number
                     INTEGER
                     PRIMARY
                     KEY,
                     active
                     INTEGER
                     DEFAULT
                     0
                 )"""
    )

    c.execute(
        """CREATE TABLE IF NOT EXISTS pairings
    (
        id
        INTEGER
        PRIMARY
        KEY
        AUTOINCREMENT,
        player1_id
        INTEGER,
        player2_id
        INTEGER,
        result1
        REAL
        DEFAULT
        NULL,
        result2
        REAL
        DEFAULT
        NULL,
        season_number
        INTEGER,
        group_name
        TEXT,
        FOREIGN
        KEY
                 (
        player1_id
                 ) REFERENCES players
                 (
                     id
                 ),
        FOREIGN KEY
                 (
                     player2_id
                 ) REFERENCES players
                 (
                     id
                 )
        )"""
    )

    c.execute(
        """INSERT
    OR IGNORE INTO seasons (season_number, active) VALUES (1, 0)"""
    )

    c.execute("PRAGMA table_info(pairings)")
    columns = [col[1] for col in c.fetchall()]

    if "result1" not in columns:
        c.execute("ALTER TABLE pairings ADD COLUMN result1 REAL DEFAULT NULL")
    if "result2" not in columns:
        c.execute("ALTER TABLE pairings ADD COLUMN result2 REAL DEFAULT NULL")
    if "season_number" not in columns:
        c.execute("ALTER TABLE pairings ADD COLUMN season_number INTEGER")
    if "group_name" not in columns:
        c.execute("ALTER TABLE pairings ADD COLUMN group_name TEXT")

    if "signed_up" not in [
        col[1] for col in c.execute("PRAGMA table_info(players)").fetchall()
    ]:
        c.execute("ALTER TABLE players ADD COLUMN signed_up INTEGER DEFAULT 0")

    conn.commit()
    conn.close()


def delete_pending_rep(rep_id):
    conn = sqlite3.connect("elo_bot.db")
    c = conn.cursor()
    c.execute("DELETE FROM pending_reps WHERE id=?", (rep_id,))
    conn.commit()
    conn.close()


def update_player_stats(player_id, elo, wins=0, losses=0, draws=0):
    conn = sqlite3.connect("elo_bot.db")
    c = conn.cursor()
    c.execute(
        """UPDATE players
                 SET elo=?,
                     wins=wins + ?,
                     losses=losses + ?,
                     draws=draws + ?
                 WHERE id = ?""",
        (elo, wins, losses, draws, player_id),
    )
    conn.commit()
    conn.close()


def get_player_data(player_id):
    conn = sqlite3.connect("elo_bot.db")
    c = conn.cursor()
    c.execute("SELECT * FROM players WHERE id=?", (player_id,))
    player = c.fetchone()
    conn.close()
    return player


async def clean_old_pending_matches():
    while True:
        try:
            conn = sqlite3.connect("elo_bot.db")
            c = conn.cursor()
            cutoff_time = datetime.now() - timedelta(minutes=30)
            cutoff_str = cutoff_time.strftime("%Y-%m-%d %H:%M:%S")
            c.execute("DELETE FROM pending_reps WHERE timestamp < ?", (cutoff_str,))
            deleted_count = c.rowcount
            conn.commit()
            if deleted_count > 0:
                print(f"Cleaned up {deleted_count} old pending matches")
            conn.close()
        except Exception as e:
            print(f"Error cleaning pending matches: {e}")
        await asyncio.sleep(1800)
