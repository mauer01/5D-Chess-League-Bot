from collections import Counter
import unittest
from logic import (
    calculate_match_stats,
    calculate_sb,
    get_role_ranges,
    group_players,
    update_elo,
)
from testdata import playerlist, groupsfromtestdata


class TestLogic(unittest.TestCase):

    def test_update_elo(self):
        playerAElo = 1400
        playerBElo = 1400
        [*newEloWin] = update_elo(playerAElo, playerBElo)
        self.assertListEqual(newEloWin, [1412.5, 1387.5])
        [*newEloDraw] = update_elo(playerAElo, playerBElo, True)
        self.assertListEqual(newEloDraw, [1400, 1400])

    def test_get_role_ranges(self):
        self.assertListEqual(
            get_role_ranges(),
            [
                {"name": "Pro League", "min": 1550, "max": 9999},
                {"name": "Advanced League", "min": 1410, "max": 1549},
                {"name": "Entry League", "min": 0, "max": 1409},
            ],
        )

    def test_group_players(self):
        players = playerlist()
        structplayerdict = [[player.getId(), player.getElo()] for player in players]
        group = group_players(structplayerdict, get_role_ranges())
        self.assertCountEqual(group, groupsfromtestdata)
        for league in group:
            self.assertCountEqual(groupsfromtestdata[league], group[league])

    def test_calculate_match_stats(self):
        player1statsafter1match = {"wins": 1, "losses": 0, "draws": 1, "elo": 1411.6}
        player2statsafter1match = {"wins": 0, "losses": 1, "draws": 1, "elo": 1388.4}
        statsafter1match = [player1statsafter1match, player2statsafter1match]
        match1_game1 = 1.0
        match1_game2 = 0.5
        player1elo = 1400
        player2elo = 1400
        [*stats] = calculate_match_stats(
            match1_game1, match1_game2, player1elo, player2elo
        )
        for i in [0, 1]:
            for stat in stats[i]:
                self.assertAlmostEqual(statsafter1match[i][stat], stats[i][stat], 1)

    def test_calculate_sb(self):
        with self.assertRaises(AttributeError):
            calculate_sb("")
