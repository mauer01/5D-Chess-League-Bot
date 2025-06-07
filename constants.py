ROLES_CONFIG_FILE = "elo_roles.csv"
SQLITEFILE = "elo_bot.db"
DATABASE_STRUCTURE = {
    "pairings": [
        "id",
        "player1_id",
        "player2_id",
        "result1",
        "result2",
        "season_number",
        "group_name",
    ],
    "pending_reps": [
        "id",
        "pairing_id",
        "reporter_id",
        "result",
        "game_number",
        "timestamp",
    ],
    "players": ["id", "elo", "wins", "losses", "draws", "signed_up"],
    "seasons": ["season_number", "active"],
    "match_history": [
        "match",
        "whiteplayer",
        "blackplayer",
        "colorwon",
        "season",
        "league",
    ],
    "elo_history": ["id", "player_id", "elo_change", "timestamp"],
}
