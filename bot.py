import discord
from discord.ext import commands, tasks
import sqlite3
import math
import csv
import os
import asyncio
from datetime import datetime, timedelta


# Configuration loader
def load_config():
    config = {}
    try:
        with open('config.csv', mode='r') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                config[row['setting']] = row['value']

        if 'token' not in config or not config['token']:
            raise ValueError("Bot token not found in config.csv")
        if 'channel_id' not in config or not config['channel_id']:
            raise ValueError("Channel ID not found in config.csv")

        return config
    except FileNotFoundError:
        raise FileNotFoundError("config.csv file not found")
    except Exception as e:
        raise Exception(f"Error reading config.csv: {str(e)}")


# Load configuration
try:
    config = load_config()
    BOT_TOKEN = config['token']
    ALLOWED_CHANNEL_ID = int(config['channel_id'])
except Exception as e:
    print(f"Configuration error: {e}")
    exit(1)

# Constants
K_FACTOR = 25
INITIAL_ELO = 1380
ROLES_CONFIG_FILE = 'elo_roles.csv'

# Initialize bot
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='$', intents=intents, help_command=None)


# Database functions
def init_db():
    conn = sqlite3.connect('elo_bot.db')
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS players
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
                     0
                 )''')

    c.execute('''CREATE TABLE IF NOT EXISTS pending_reps
                 (
                     id
                     INTEGER
                     PRIMARY
                     KEY
                     AUTOINCREMENT,
                     reporter_id
                     INTEGER,
                     opponent_id
                     INTEGER,
                     reporter_result
                     TEXT,
                     timestamp
                     DATETIME
                     DEFAULT
                     CURRENT_TIMESTAMP
                 )''')

    conn.commit()
    conn.close()


init_db()


# ELO calculations
def get_expected_score(a, b):
    return 1 / (1 + math.pow(10, (b - a) / 400))


def update_elo(winner_elo, loser_elo, draw=False):
    if draw:
        expected_winner = get_expected_score(winner_elo, loser_elo)
        expected_loser = get_expected_score(loser_elo, winner_elo)
        new_winner_elo = winner_elo + K_FACTOR * (0.5 - expected_winner)
        new_loser_elo = loser_elo + K_FACTOR * (0.5 - expected_loser)
        return new_winner_elo, new_loser_elo
    else:
        expected = get_expected_score(winner_elo, loser_elo)
        new_winner_elo = winner_elo + K_FACTOR * (1 - expected)
        new_loser_elo = loser_elo + K_FACTOR * (0 - (1 - expected))
        return new_winner_elo, new_loser_elo


# Player management
def get_player_data(player_id):
    conn = sqlite3.connect('elo_bot.db')
    c = conn.cursor()
    c.execute("SELECT * FROM players WHERE id=?", (player_id,))
    player = c.fetchone()
    conn.close()
    return player


def update_player_stats(player_id, elo, wins=0, losses=0, draws=0):
    conn = sqlite3.connect('elo_bot.db')
    c = conn.cursor()
    c.execute('''UPDATE players
                 SET elo=?,
                     wins=wins + ?,
                     losses=losses + ?,
                     draws=draws + ?
                 WHERE id = ?''',
              (elo, wins, losses, draws, player_id))
    conn.commit()
    conn.close()


def add_pending_rep(reporter_id, opponent_id, reporter_result):
    conn = sqlite3.connect('elo_bot.db')
    c = conn.cursor()
    c.execute('''INSERT INTO pending_reps (reporter_id, opponent_id, reporter_result)
                 VALUES (?, ?, ?)''',
              (reporter_id, opponent_id, reporter_result))
    conn.commit()
    conn.close()


def get_pending_rep(reporter_id, opponent_id):
    conn = sqlite3.connect('elo_bot.db')
    c = conn.cursor()
    cutoff_time = datetime.now() - timedelta(minutes=30)
    cutoff_str = cutoff_time.strftime('%Y-%m-%d %H:%M:%S')
    c.execute('''SELECT *
                 FROM pending_reps
                 WHERE reporter_id = ?
                   AND opponent_id = ?
                   AND timestamp >= ?
                 ORDER BY timestamp DESC LIMIT 1''',
              (reporter_id, opponent_id, cutoff_str))
    rep = c.fetchone()
    conn.close()
    return rep


def delete_pending_rep(rep_id):
    conn = sqlite3.connect('elo_bot.db')
    c = conn.cursor()
    c.execute("DELETE FROM pending_reps WHERE id=?", (rep_id,))
    conn.commit()
    conn.close()


# Background tasks
async def clean_old_pending_matches():
    while True:
        try:
            conn = sqlite3.connect('elo_bot.db')
            c = conn.cursor()
            cutoff_time = datetime.now() - timedelta(minutes=30)
            cutoff_str = cutoff_time.strftime('%Y-%m-%d %H:%M:%S')
            c.execute("DELETE FROM pending_reps WHERE timestamp < ?", (cutoff_str,))
            deleted_count = c.rowcount
            conn.commit()
            if deleted_count > 0:
                print(f"Cleaned up {deleted_count} old pending matches")
            conn.close()
        except Exception as e:
            print(f"Error cleaning pending matches: {e}")
        await asyncio.sleep(1800)  # 30 minutes


# Channel check
def check_channel(ctx):
    if ctx.channel.id != ALLOWED_CHANNEL_ID:
        allowed_channel = bot.get_channel(ALLOWED_CHANNEL_ID)
        channel_name = f"#{allowed_channel.name}" if allowed_channel else f"channel with ID {ALLOWED_CHANNEL_ID}"
        return False, f"This command can only be used in {channel_name}!"
    return True, None


# Commands
@bot.command(name='register')
async def register_player(ctx):
    allowed, error_msg = check_channel(ctx)
    if not allowed:
        await ctx.send(error_msg)
        return

    player_id = ctx.author.id
    if get_player_data(player_id):
        await ctx.send(f"{ctx.author.mention}, you're already registered!")
        return

    conn = sqlite3.connect('elo_bot.db')
    c = conn.cursor()
    c.execute("INSERT INTO players (id, elo) VALUES (?, ?)", (player_id, INITIAL_ELO))
    conn.commit()
    conn.close()

    await ctx.send(f"🎉 {ctx.author.mention} has been registered with an initial ELO of {INITIAL_ELO}!")


@bot.command(name='rep')
async def report_match(ctx, result: str, opponent: discord.Member):
    allowed, error_msg = check_channel(ctx)
    if not allowed:
        await ctx.send(error_msg)
        return

    # Check registration
    reporter_data = get_player_data(ctx.author.id)
    if not reporter_data:
        await ctx.send(f"You need to register first with `$register`!")
        return

    opponent_data = get_player_data(opponent.id)
    if not opponent_data:
        await ctx.send(f"{opponent.mention} needs to register with `$register` first!")
        return

    # Process result
    result = result.lower()
    if result not in ['w', 'l', 'd']:
        await ctx.send("Invalid result. Use 'w' for win, 'l' for loss, or 'd' for draw.")
        return

    if ctx.author.id == opponent.id:
        await ctx.send("You can't report a match with yourself!")
        return

    pending_rep = get_pending_rep(opponent.id, ctx.author.id)

    if pending_rep:
        pending_result = pending_rep[3]
        valid_confirmation = (
                (result == 'w' and pending_result == 'l') or
                (result == 'l' and pending_result == 'w') or
                (result == 'd' and pending_result == 'd')
        )

        if valid_confirmation:
            reporter_elo = reporter_data[1]
            opponent_elo = opponent_data[1]

            if result == 'w':
                new_reporter_elo, new_opponent_elo = update_elo(reporter_elo, opponent_elo)
                update_player_stats(ctx.author.id, new_reporter_elo, wins=1)
                update_player_stats(opponent.id, new_opponent_elo, losses=1)
            elif result == 'l':
                new_opponent_elo, new_reporter_elo = update_elo(opponent_elo, reporter_elo)
                update_player_stats(ctx.author.id, new_reporter_elo, losses=1)
                update_player_stats(opponent.id, new_opponent_elo, wins=1)
            else:
                new_reporter_elo, new_opponent_elo = update_elo(reporter_elo, opponent_elo, draw=True)
                update_player_stats(ctx.author.id, new_reporter_elo, draws=1)
                update_player_stats(opponent.id, new_opponent_elo, draws=1)

            delete_pending_rep(pending_rep[0])
            await ctx.send(f"Match confirmed! {ctx.author.mention} vs {opponent.mention}")
        else:
            await ctx.send("Results don't match! Make sure you're reporting the opposite result.")
    else:
        add_pending_rep(ctx.author.id, opponent.id, result)
        await ctx.send(
            f"Match reported! {opponent.mention} please confirm by typing:\n"
            f"`$rep {'l' if result == 'w' else 'w' if result == 'l' else 'd'} @{ctx.author.name}`"
        )


@bot.command(name='cancel')
async def cancel_pending_match(ctx, result: str, opponent: discord.Member):
    """Cancel your last pending match with the specified opponent"""
    allowed, error_msg = check_channel(ctx)
    if not allowed:
        await ctx.send(error_msg)
        return

    result = result.lower()
    if result not in ['w', 'l', 'd']:
        await ctx.send("Invalid result. Use 'w' for win, 'l' for loss, or 'd' for draw.")
        return

    if ctx.author.id == opponent.id:
        await ctx.send("You can't cancel a match with yourself!")
        return

    pending_rep = get_pending_rep(ctx.author.id, opponent.id)

    if not pending_rep:
        await ctx.send(f"No pending match found against {opponent.mention} to cancel!")
        return

    if pending_rep[3].lower() != result:
        await ctx.send(f"Result doesn't match your pending match against {opponent.mention}!")
        return

    delete_pending_rep(pending_rep[0])
    await ctx.send(f"✅ Successfully canceled your pending match against {opponent.mention}!")


@bot.command(name='stats')
async def show_stats(ctx, player: discord.Member = None):
    allowed, error_msg = check_channel(ctx)
    if not allowed:
        await ctx.send(error_msg)
        return

    target = player or ctx.author
    data = get_player_data(target.id)

    if not data:
        if target == ctx.author:
            await ctx.send(f"You're not registered! Use `$register` to join the ELO system.")
        else:
            await ctx.send(f"{target.name} isn't registered with the ELO system.")
        return

    embed = discord.Embed(title=f"Stats for {target.name}", color=0x00ff00)
    embed.add_field(name="ELO", value=f"{data[1]:.0f}")
    embed.add_field(name="Wins", value=data[2])
    embed.add_field(name="Losses", value=data[3])
    embed.add_field(name="Draws", value=data[4])

    total_games = data[2] + data[3] + data[4]
    embed.add_field(name="Total Games", value=total_games)

    if data[2] + data[3] > 0:
        win_rate = (data[2] / total_games) * 100
        embed.add_field(name="Win Rate", value=f"{win_rate:.1f}%")

    await ctx.send(embed=embed)


@bot.command(name='leaderboard')
async def show_leaderboard(ctx, *args):
    allowed, error_msg = check_channel(ctx)
    if not allowed:
        await ctx.send(error_msg)
        return

    # Default values
    limit = 10
    role_name = None

    # Parse arguments
    for arg in args:
        if arg.isdigit():
            limit = min(max(1, int(arg)), 25)
        else:
            if role_name is None:
                role_name = arg
            else:
                role_name += " " + arg

    conn = sqlite3.connect('elo_bot.db')
    c = conn.cursor()

    # Base query
    query = "SELECT id, elo, wins, losses, draws FROM players"
    params = ()

    # Role filtering
    role = None
    if role_name:
        role = discord.utils.find(lambda r: r.name.lower() == role_name.lower(), ctx.guild.roles)
        if not role:
            await ctx.send(f"Role '{role_name}' not found!")
            conn.close()
            return

        member_ids = [str(m.id) for m in role.members]
        if not member_ids:
            await ctx.send(f"No players found with the '{role.name}' role!")
            conn.close()
            return

        query += " WHERE id IN (" + ",".join(["?"] * len(member_ids)) + ")"
        params = tuple(member_ids)

    # Get total player count
    c.execute(
        "SELECT COUNT(*) FROM players" + (" WHERE id IN (" + ",".join(["?"] * len(member_ids)) + ")" if role else ""),
        params if role else ())
    total_players = c.fetchone()[0]

    # Get user data and rank if registered
    user_data = get_player_data(ctx.author.id)
    user_rank = None
    user_surrounding = []

    if user_data:
        # Get user's exact rank
        rank_query = "SELECT COUNT(*) FROM players WHERE elo > ?"
        if role:
            rank_query += " AND id IN (" + ",".join(["?"] * len(member_ids)) + ")"

        c.execute(rank_query, (user_data[1],) + (params if role else ()))
        user_rank = c.fetchone()[0] + 1

        # Get surrounding ranks if not in top limit
        if user_rank > limit:
            # Get top players
            c.execute(query + " ORDER BY elo DESC LIMIT ?", params + (limit,))
            top_players = c.fetchall()

            # Get user's surrounding ranks (rank-1, rank, rank+1)
            offset = max(0, user_rank - 2)
            c.execute(query + " ORDER BY elo DESC LIMIT 3 OFFSET ?", params + (offset,))
            user_surrounding = c.fetchall()
        else:
            # If user is in top limit, just get top players
            c.execute(query + " ORDER BY elo DESC LIMIT ?", params + (limit,))
            top_players = c.fetchall()
    else:
        # If user not registered, just get top players
        c.execute(query + " ORDER BY elo DESC LIMIT ?", params + (limit,))
        top_players = c.fetchall()

    conn.close()

    if not top_players and not user_surrounding:
        msg = "No players found"
        if role:
            msg += f" with the '{role.name}' role"
        msg += "! Use `$register` to join."
        await ctx.send(msg)
        return

    # Create embed
    title = f"🏆 Top {limit} Leaderboard"
    if role:
        title += f" ({role.name})"
    title += " 🏆"

    embed = discord.Embed(title=title, color=role.color if role else 0xffd700)

    # Add top players
    displayed_ranks = set()
    for i, (player_id, elo, wins, losses, draws) in enumerate(top_players, 1):
        try:
            member = await ctx.guild.fetch_member(player_id)
            name = member.display_name
            if role and role in member.roles:
                name = f"{name} {str(role)}"
        except:
            name = f"Unknown Player ({player_id})"

        games = wins + losses + draws
        if games > 0:
            win_rate = (wins / (wins + losses)) * 100 if (wins + losses) > 0 else 0
            stats = f"**{elo:.0f} ELO** | {wins}W {losses}L {draws}D ({win_rate:.1f}%)"
        else:
            stats = f"**{elo:.0f} ELO** | No games played"

        embed.add_field(name=f"{i}. {name}", value=stats, inline=False)
        displayed_ranks.add(i)

    # Add surrounding ranks if user not in top limit
    if user_surrounding:
        embed.add_field(name="\n...", value="...", inline=False)

        for i, (player_id, elo, wins, losses, draws) in enumerate(user_surrounding, user_rank - 1):
            if i in displayed_ranks:
                continue

            try:
                member = await ctx.guild.fetch_member(player_id)
                name = member.display_name
                highlight = "**>>>** " if player_id == ctx.author.id else ""

                if role and role in member.roles:
                    name = f"{name} {str(role)}"
            except:
                name = f"Unknown Player ({player_id})"
                highlight = ""

            games = wins + losses + draws
            if games > 0:
                win_rate = (wins / (wins + losses)) * 100 if (wins + losses) > 0 else 0
                stats = f"**{elo:.0f} ELO** | {wins}W {losses}L {draws}D ({win_rate:.1f}%)"
            else:
                stats = f"**{elo:.0f} ELO** | No games played"

            embed.add_field(name=f"{highlight}{i}. {name}", value=stats, inline=False)

    # Add user stats if registered
    if user_data:
        user_games = user_data[2] + user_data[3] + user_data[4]
        if user_games > 0:
            win_rate = (user_data[2] / (user_data[2] + user_data[3])) * 100 if (user_data[2] + user_data[3]) > 0 else 0
            user_stats = f"**{user_data[1]:.0f} ELO** | {user_data[2]}W {user_data[3]}L {user_data[4]}D ({win_rate:.1f}%)"
        else:
            user_stats = f"**{user_data[1]:.0f} ELO** | No games played"

        if user_rank:
            embed.add_field(name=f"\nYour Rank: #{user_rank} of {total_players}", value=user_stats, inline=False)
    elif not role or (role and ctx.author.id in [m.id for m in role.members]):
        embed.add_field(name="\nYou're not registered!", value="Use `$register` to join the leaderboard", inline=False)

    await ctx.send(embed=embed)

@bot.command(name='help')
async def show_help(ctx):
    """Show all available commands and how to use them"""
    allowed, error_msg = check_channel(ctx)
    if not allowed:
        await ctx.send(error_msg)
        return

    embed = discord.Embed(
        title="🏆 ELO Bot Help 🏆",
        description="Here are all the available commands:",
        color=0x00ff00
    )

    # Basic commands
    embed.add_field(
        name="🔹 Registration",
        value="`$register` - Register yourself in the ELO system",
        inline=False
    )

    # Match reporting
    embed.add_field(
        name="🔹 Match Reporting",
        value=(
            "`$rep [w/l/d] @opponent` - Report a match result\n"
            "  • `w` for win, `l` for loss, `d` for draw\n"
            "  • Example: `$rep w @Player2`\n"
            "`$cancel [w/l/d] @opponent` - Cancel a pending match report",
        ),
        inline=False
    )

    # Stats commands
    embed.add_field(
        name="🔹 Statistics",
        value=(
            "`$stats` - Show your stats\n"
            "`$stats @player` - Show another player's stats\n"
            "`$leaderboard` - Show top 10 players\n"
            "`$leaderboard [number]` - Show top X players (max 25)\n"
            "`$leaderboard [role name]` - Show leaderboard for a specific role\n"
            "`$leaderboard [number] [role name]` - Combined options"
        ),
        inline=False
    )

    # Admin commands
    if ctx.author.guild_permissions.manage_roles:
        embed.add_field(
            name="🔹 Admin Commands",
            value=(
                "`$update_roles` - Update all players' roles based on ELO\n"
                "  • Requires a properly configured 'elo_roles.csv' file"
            ),
            inline=False
        )

    # Additional info
    embed.add_field(
        name="ℹ️ How It Works",
        value=(
            "1. Both players must `$register` first\n"
            "2. One player reports the match with `$rep`\n"
            "3. The other player confirms by reporting the opposite result\n"
            "4. ELO is updated automatically after confirmation"
        ),
        inline=False
    )

    embed.set_footer(text=f"Bot is restricted to #{bot.get_channel(ALLOWED_CHANNEL_ID).name}")

    await ctx.send(embed=embed)

@bot.command(name='update_roles')
@commands.has_permissions(manage_roles=True)
async def update_player_roles(ctx):
    allowed, error_msg = check_channel(ctx)
    if not allowed:
        await ctx.send(error_msg)
        return

    try:
        # Check if file exists
        if not os.path.exists(ROLES_CONFIG_FILE):
            raise FileNotFoundError(f"'{ROLES_CONFIG_FILE}' not found in bot directory")

        # Load and validate role configuration
        role_ranges = []
        with open(ROLES_CONFIG_FILE, mode='r') as csvfile:
            reader = csv.DictReader(csvfile)
            if not reader.fieldnames or 'role' not in reader.fieldnames or 'min elo' not in reader.fieldnames or 'max elo' not in reader.fieldnames:
                raise ValueError("CSV file must have headers: 'role', 'min elo', 'max elo'")

            for row in reader:
                if not row.get('role') or not row.get('min elo') or not row.get('max elo'):
                    continue

                try:
                    role_ranges.append({
                        'name': row['role'].strip(),
                        'min': int(row['min elo']),
                        'max': int(row['max elo'])
                    })
                except ValueError:
                    raise ValueError(f"Invalid ELO values in row: {row}")

        if not role_ranges:
            raise ValueError("No valid role ranges found in the configuration file")

        # Sort by min ELO (highest first)
        role_ranges.sort(key=lambda x: x['min'], reverse=True)

        # Get all registered players
        conn = sqlite3.connect('elo_bot.db')
        c = conn.cursor()
        c.execute("SELECT id, elo FROM players")
        players = c.fetchall()
        conn.close()

        if not players:
            await ctx.send("No registered players found!")
            return

        # Process each player
        updated_count = 0
        progress_msg = await ctx.send("Updating roles... 0%")

        for i, (player_id, elo) in enumerate(players):
            try:
                member = await ctx.guild.fetch_member(player_id)
                if not member:
                    continue

                # Find appropriate role
                new_role = None
                for role_range in role_ranges:
                    if role_range['min'] <= elo <= role_range['max']:
                        new_role = discord.utils.get(ctx.guild.roles, name=role_range['name'])
                        if not new_role:
                            await ctx.send(f"⚠️ Role '{role_range['name']}' not found on server!")
                            continue
                        break

                if not new_role:
                    continue

                # Remove all existing league roles
                roles_to_remove = []
                for role_range in role_ranges:
                    existing_role = discord.utils.get(member.roles, name=role_range['name'])
                    if existing_role:
                        roles_to_remove.append(existing_role)

                if roles_to_remove:
                    await member.remove_roles(*roles_to_remove)

                # Add new role
                await member.add_roles(new_role)
                updated_count += 1

                # Update progress every 10% or every 5 players (whichever is larger)
                if (i + 1) % max(5, len(players) // 10) == 0:
                    progress = int((i + 1) / len(players) * 100)
                    await progress_msg.edit(content=f"Updating roles... {progress}%")

            except discord.Forbidden:
                await ctx.send("❌ Bot doesn't have permission to manage roles!")
                return
            except discord.HTTPException as e:
                print(f"HTTP Error updating {player_id}: {e}")
            except Exception as e:
                print(f"Error updating {player_id}: {e}")

        await progress_msg.delete()
        await ctx.send(f"✅ Successfully updated roles for {updated_count}/{len(players)} players!")

    except FileNotFoundError as e:
        await ctx.send(f"❌ {e}\nPlease create a '{ROLES_CONFIG_FILE}' file with columns: 'role', 'min elo', 'max elo'")
    except ValueError as e:
        await ctx.send(f"❌ Invalid configuration: {e}")
    except Exception as e:
        await ctx.send(f"❌ Unexpected error: {e}")


# Events
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    print(f'Commands restricted to channel ID: {ALLOWED_CHANNEL_ID}')
    print('------')
    bot.loop.create_task(clean_old_pending_matches())


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.CheckFailure):
        return
    print(f"Error in command {ctx.command}: {error}")


@bot.event
async def on_message(message):
    if message.content.startswith(bot.command_prefix):
        allowed, _ = check_channel(message)
        if allowed:
            await bot.process_commands(message)


# Run the bot
try:
    bot.run(BOT_TOKEN)
except discord.LoginError:
    print("Invalid bot token in config.csv. Please check your token.")
except Exception as e:
    print(f"Error starting bot: {e}")