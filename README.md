# 5D-Chess-League-Bot
  
## About
This is a discord elo bot for the 5D Chess League. The bot uses a sqlite database to store player info.  

## Installation Requirements 
Make sure to have the discord python module installed in your enviroment  
```pip install discord```

## Usage
To run the bot you can execute the following command  
```python3 bot.py```

## Bot Commands
### User Commands
$register: Registers the user into the system and adds their discord user id to the database  
$rep <w/l/d> @opponent: Reports a match result (Opponent must report the opposite result to confirm the match)  
$cancel <w/l/d> @opponent: Cancels the last pending match  
$leaderboard <index> <role>: Shows the leaderboard (If index is specified it shows the player info of that rank, If role is specified it filters the leaderboard to only show people with that role)  
$stats: Shows your stats (Elo, wins, losses, draws, win rate)  
$help: Lists all the commands and what they do

### Admin Commands
$update_rolesL Updates roles for all registered players based on their elo and the elo cutoffs
