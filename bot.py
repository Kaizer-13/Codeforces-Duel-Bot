# bot.py

import discord
from discord.ext import commands, tasks
import requests
import json
import os
import asyncio
import random
import string
from datetime import datetime, timedelta, UTC
from dotenv import load_dotenv
# --- CONFIGURATION ---
load_dotenv()
BOT_TOKEN = os.getenv('DISCORD_TOKEN')
# The command prefix
COMMAND_PREFIX = '!'

# --- BOT SETUP ---
# Define the intents your bot needs to function
intents = discord.Intents.default()
intents.members = True  # Required to see server members
intents.message_content = True  # Required to read message content

# Create the bot instance
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)

# --- GLOBAL STATE MANAGEMENT ---
# This dictionary will hold the duel state for each server separately.
# The key will be the server_id.
duel_state = {}

# --- DATA PERSISTENCE ---
# Functions to load and save user data from the users.json file
DATA_DIR = os.getenv('RAILWAY_VOLUME_MOUNT_PATH', './') 
USERS_FILE = os.path.join(DATA_DIR, 'users.json')
def load_users():
    """Loads user data from users.json."""
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_users(users_data):
    """Saves user data to users.json."""
    with open(USERS_FILE, 'w') as f:
        json.dump(users_data, f, indent=4)

def calculate_points(rating):
    """Calculates points awarded based on problem rating.
    
    The formula gives 5 base points, plus 1 bonus point for every 100 rating
    points above 800.
    """
    base_points = 5
    bonus_points = (rating - 800) // 100
    return base_points + bonus_points

# --- BOT EVENTS ---
@bot.event
async def on_ready():
    """Event that runs when the bot has successfully connected to Discord."""
    print(f'Logged in as {bot.user.name}')
    print(f'Bot ID: {bot.user.id}')
    print('Bot is ready and online.')
    print('------')

# --- HELP, USER REGISTRATION & PROFILE ---
@bot.command(name='help', help='Shows this help message.')
async def help(ctx):
    """Displays a formatted help message for all commands."""
    embed = discord.Embed(
        title="🤖 Codeforces Duel Bot Help",
        description="Here are all the available commands and their formats:",
        color=discord.Color.purple()
    )

    embed.add_field(
        name="`!register <handle>`",
        value="Register yourself with your Codeforces handle on this server.",
        inline=False
    )
    embed.add_field(
        name="`!updatehandle <new_handle>`",
        value="Change your registered handle on this server (requires re-verification).",
        inline=False
    )
    embed.add_field(
        name="`!challenge @user <rating>`",
        value="Challenge another user to a duel. Higher ratings award more points.",
        inline=False
    )
    embed.add_field(
        name="`!solved`",
        value="Use this during a duel to claim victory and earn points based on the problem's rating.",
        inline=False
    )
    embed.add_field(
        name="`!profile [@user]`",
        value="View your own or another user's profile and points on this server.",
        inline=False
    )
    embed.add_field(
        name="`!leaderboard`",
        value="See this server's top-ranked duelists.",
        inline=False
    )
    embed.add_field(
        name="`!help`",
        value="Shows this help message.",
        inline=False
    )

    embed.set_footer(text="Let the duels begin! Higher rating = higher reward!")
    await ctx.send(embed=embed)

@bot.command(name='register', help='Register your Codeforces handle. Usage: !register <YourCodeforcesHandle>')
async def register(ctx, codeforces_handle: str):
    """Registers a user by verifying their Codeforces account for the current server."""
    codeforces_handle = codeforces_handle.replace('\\_', '_')
    all_data = load_users()
    server_id = str(ctx.guild.id)
    discord_id = str(ctx.author.id)

    # Get or create the dictionary for this specific server
    server_users = all_data.get(server_id, {})

    if discord_id in server_users:
        await ctx.send("You are already registered on this server!")
        return

    # Check if the Codeforces handle is valid by calling the API
    try:
        response = requests.get(f"https://codeforces.com/api/user.info?handles={codeforces_handle}")
        data = response.json()
        if data['status'] != 'OK':
            await ctx.send(f"Could not find a Codeforces user with the handle `{codeforces_handle}`.")
            return
    except Exception as e:
        await ctx.send("An error occurred while contacting the Codeforces API.")
        print(f"Codeforces API error: {e}")
        return

    # Generate a unique verification token
    token = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

    try:
        # DM the user with instructions
        verification_message = (
            f"To verify your Codeforces account `{codeforces_handle}`, please temporarily change your **First Name** on Codeforces to:\n"
            f"**`{token}`**\n\n"
            f"You can change your name here: https://codeforces.com/settings/social\n"
            f"Once you've done that, come back here and click the ✅ reaction within 5 minutes."
        )
        dm_message = await ctx.author.send(verification_message)
        await dm_message.add_reaction('✅')
        await ctx.send(f"I've sent you a DM with instructions to verify your account, {ctx.author.mention}.")
    except discord.Forbidden:
        await ctx.send(f"{ctx.author.mention}, I can't send you a DM. Please enable DMs from server members in your privacy settings.")
        return

    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) == '✅' and reaction.message.id == dm_message.id

    try:
        # Wait for the user to react
        await bot.wait_for('reaction_add', timeout=300.0, check=check)

        # Acknowledge reaction and wait for API to update
        await ctx.author.send("✅ Got it! Checking for the update on Codeforces in 30 seconds...")
        await asyncio.sleep(30)

        # After the delay, verify the change on Codeforces
        response = requests.get(f"https://codeforces.com/api/user.info?handles={codeforces_handle}")
        data = response.json()
        if data['status'] == 'OK' and data['result'][0].get('firstName') == token:
            # Add user to the server-specific dictionary
            server_users[discord_id] = {"codeforces_handle": codeforces_handle, "points": 0}
            all_data[server_id] = server_users
            save_users(all_data)
            await ctx.author.send(
                f"✅ Verification successful! You are now registered as `{codeforces_handle}` on **{ctx.guild.name}**.\n"
                f"You can now change your name back on Codeforces."
            )
        else:
            await ctx.author.send("Verification failed. The first name on your Codeforces profile did not match the token. Please try again.")

    except asyncio.TimeoutError:
        await ctx.author.send("Verification timed out. Please run the `!register` command again.")

@bot.command(name='updatehandle', help='Update your Codeforces handle. Requires re-verification.')
async def updatehandle(ctx, new_codeforces_handle: str):
    """Updates an existing user's Codeforces handle after re-verification for the current server."""
    new_codeforces_handle = new_codeforces_handle.replace('\\_', '_')
    all_data = load_users()
    server_id = str(ctx.guild.id)
    discord_id = str(ctx.author.id)
    server_users = all_data.get(server_id, {})

    if discord_id not in server_users:
        await ctx.send("You are not registered on this server. Please use `!register` to create an account.")
        return

    # MODIFIED: Check the duel state for this specific server
    if duel_state.get(server_id, {}).get("active", False):
        await ctx.send("You cannot change your handle while a duel or challenge is in progress on this server.")
        return

    for user_id, data in server_users.items():
        if data['codeforces_handle'].lower() == new_codeforces_handle.lower() and user_id != discord_id:
            await ctx.send(f"The handle `{new_codeforces_handle}` is already registered by another user on this server.")
            return

    if server_users[discord_id]['codeforces_handle'].lower() == new_codeforces_handle.lower():
        await ctx.send("This is already your registered handle.")
        return

    # --- Re-verification Process (same as before) ---
    try:
        response = requests.get(f"https://codeforces.com/api/user.info?handles={new_codeforces_handle}")
        data = response.json()
        if data['status'] != 'OK':
            await ctx.send(f"Could not find a Codeforces user with the handle `{new_codeforces_handle}`.")
            return
    except Exception as e:
        await ctx.send("An error occurred while contacting the Codeforces API.")
        print(f"Codeforces API error: {e}")
        return

    token = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

    try:
        verification_message = (
            f"To verify your new handle `{new_codeforces_handle}`, please temporarily change your **First Name** on Codeforces to:\n"
            f"**`{token}`**\n\n"
            f"You can change your name here: https://codeforces.com/settings/social\n"
            f"Once done, click the ✅ reaction on this message within 5 minutes."
        )
        dm_message = await ctx.author.send(verification_message)
        await dm_message.add_reaction('✅')
        await ctx.send(f"I've sent you a DM with instructions to verify your new handle, {ctx.author.mention}.")
    except discord.Forbidden:
        await ctx.send(f"{ctx.author.mention}, I can't send you a DM. Please enable DMs from server members.")
        return

    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) == '✅' and reaction.message.id == dm_message.id

    try:
        await bot.wait_for('reaction_add', timeout=300.0, check=check)

        # Acknowledge reaction and wait for API to update
        await ctx.author.send("✅ Got it! Checking for the update on Codeforces in 30 seconds to allow for API caching...")
        await asyncio.sleep(30)

        response = requests.get(f"https://codeforces.com/api/user.info?handles={new_codeforces_handle}")
        data = response.json()

        if data['status'] == 'OK' and data['result'][0].get('firstName') == token:
            server_users[discord_id]['codeforces_handle'] = new_codeforces_handle
            all_data[server_id] = server_users
            save_users(all_data)
            await ctx.author.send(
                f"✅ Verification successful! Your Codeforces handle has been updated to `{new_codeforces_handle}` on **{ctx.guild.name}**.\n"
                f"You can now change your name back on Codeforces."
            )
        else:
            await ctx.author.send("Verification failed. The first name on your Codeforces profile did not match the token. Please try again.")

    except asyncio.TimeoutError:
        await ctx.author.send("Verification timed out. Please run the `!updatehandle` command again.")

@bot.command(name='profile', help='Shows your or another user\'s profile.')
async def profile(ctx, member: discord.Member = None):
    """Displays the profile of the mentioned user or the command author for the current server."""
    target_user = member or ctx.author
    all_data = load_users()
    server_id = str(ctx.guild.id)
    discord_id = str(target_user.id)
    server_users = all_data.get(server_id, {})

    if discord_id not in server_users:
        await ctx.send(f"{target_user.display_name} is not registered on this server.")
        return

    user_data = server_users[discord_id]
    embed = discord.Embed(
        title=f"{target_user.display_name}'s Profile on {ctx.guild.name}",
        color=discord.Color.blue()
    )
    embed.add_field(name="Codeforces Handle", value=f"[{user_data['codeforces_handle']}](https://codeforces.com/profile/{user_data['codeforces_handle']})", inline=False)
    embed.add_field(name="Points", value=user_data['points'], inline=False)
    await ctx.send(embed=embed)

@bot.command(name='leaderboard', help='Shows the server leaderboard.')
async def leaderboard(ctx):
    """Displays the top 10 users by points for the current server."""
    all_data = load_users()
    server_id = str(ctx.guild.id)
    server_users = all_data.get(server_id, {})

    if not server_users:
        await ctx.send("No users are registered on this server yet.")
        return

    sorted_users = sorted(server_users.items(), key=lambda item: item[1]['points'], reverse=True)
    embed = discord.Embed(title=f"Leaderboard for {ctx.guild.name}", color=discord.Color.gold())
    description = ""
    for i, (discord_id, data) in enumerate(sorted_users[:10]):
        try:
            user = await bot.fetch_user(int(discord_id))
            description += f"**{i+1}. {user.display_name}** - {data['points']} points ({data['codeforces_handle']})\n"
        except discord.NotFound:
            description += f"**{i+1}. Unknown User** - {data['points']} points ({data['codeforces_handle']})\n"
    embed.description = description
    await ctx.send(embed=embed)

# --- DUELING SYSTEM COMMANDS ---
@bot.command(name='challenge', help='Challenge another user to a duel. Usage: !challenge @<User> <Rating>')
async def challenge(ctx, opponent: discord.Member, rating: int):
    """Initiates a duel challenge against another user on the same server."""
    global duel_state
    all_data = load_users()
    server_id = str(ctx.guild.id)
    challenger_id = str(ctx.author.id)
    opponent_id = str(opponent.id)
    server_users = all_data.get(server_id, {})

    if duel_state.get(server_id, {}).get("active", False):
        await ctx.send("A challenge or duel is already in progress on this server. Please wait.")
        return

    if challenger_id not in server_users or opponent_id not in server_users:
        await ctx.send("Both you and your opponent must be registered on this server to duel.")
        return
    if ctx.author == opponent:
        await ctx.send("You cannot challenge yourself.")
        return
    if opponent.bot:
        await ctx.send("You cannot challenge a bot.")
        return
    if not (800 <= rating <= 3500 and rating % 100 == 0):
        await ctx.send("Please choose a valid rating (800-3500, in increments of 100).")
        return

    # MODIFIED: Store the rating in the server's duel state
    duel_state[server_id] = {
        "active": True,
        "challenger": ctx.author,
        "opponent": opponent,
        "rating": rating,  # Store the rating for later
        "problem": None,
        "problem_url": None,
        "start_time": None
    }

    challenge_message = await ctx.send(
        f"⚔️ {opponent.mention}, you have been challenged by {ctx.author.mention} to a duel at rating **{rating}**!\n"
        f"React with ✅ to accept or ❌ to decline within 5 minutes."
    )
    await challenge_message.add_reaction('✅')
    await challenge_message.add_reaction('❌')

    def check(reaction, user):
        return user == opponent and str(reaction.emoji) in ['✅', '❌'] and reaction.message.id == challenge_message.id

    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=300.0, check=check)
        if str(reaction.emoji) == '❌':
            await ctx.send(f"{opponent.mention} has declined the challenge.")
            del duel_state[server_id]
            return

        await ctx.send(f"{opponent.mention} has accepted! Finding a suitable problem...")
        challenger_handle = server_users[challenger_id]['codeforces_handle']
        opponent_handle = server_users[opponent_id]['codeforces_handle']

        try:
            async def get_cf_api(url):
                response = requests.get(url)
                response.raise_for_status()
                data = response.json()
                if data.get('status') != 'OK':
                    raise Exception(f"Codeforces API Error: {data.get('comment', 'No comment provided')}")
                return data

            ch_data = await get_cf_api(f"https://codeforces.com/api/user.status?handle={challenger_handle}")
            op_data = await get_cf_api(f"https://codeforces.com/api/user.status?handle={opponent_handle}")
            problems_data = await get_cf_api("https://codeforces.com/api/problemset.problems")

            ch_solved = {f"{p['problem']['contestId']}{p['problem']['index']}" for p in ch_data['result'] if p.get('verdict') == 'OK' and 'contestId' in p.get('problem', {})}
            op_solved = {f"{p['problem']['contestId']}{p['problem']['index']}" for p in op_data['result'] if p.get('verdict') == 'OK' and 'contestId' in p.get('problem', {})}
            potential_problems = [p for p in problems_data['result']['problems'] if p.get('rating') == rating and 'contestId' in p and 'index' in p and f"{p.get('contestId')}{p.get('index')}" not in ch_solved and f"{p.get('contestId')}{p.get('index')}" not in op_solved]

        except Exception as e:
            await ctx.send(f"An error occurred while fetching data from Codeforces. The duel is cancelled. Please try again later.\n`Error: {e}`")
            del duel_state[server_id]
            return

        if not potential_problems:
            await ctx.send(f"Could not find a suitable unsolved problem at rating {rating}. The challenge has been cancelled.")
            del duel_state[server_id]
            return

        problem = random.choice(potential_problems)
        problem_url = f"https://codeforces.com/problemset/problem/{problem['contestId']}/{problem['index']}"
        
        duel_state[server_id].update({"problem": problem, "problem_url": problem_url, "start_time": datetime.now(UTC)})
        
        await ctx.send(
            f"**Duel Start!**\n"
            f"**Problem:** {problem['name']} (Rating: {rating})\n"
            f"**Link:** {problem_url}\n\n"
            f"{duel_state[server_id]['challenger'].mention} vs {duel_state[server_id]['opponent'].mention}: The first to solve it in **15 minutes** wins points based on rating! Type `!solved` when you have an accepted solution."
        )
        bot.loop.create_task(duel_timeout_task(ctx, duel_state[server_id]['start_time'], server_id))
    except asyncio.TimeoutError:
        await ctx.send(f"The duel challenge for {opponent.mention} expired.")
        del duel_state[server_id]

@bot.command(name='solved', help='Claim victory in the current duel.')
async def solved(ctx):
    """Allows a duel participant to claim victory after solving the problem."""
    global duel_state
    all_data = load_users()
    server_id = str(ctx.guild.id)
    winner_id = str(ctx.author.id)
    server_users = all_data.get(server_id, {})

    current_server_duel = duel_state.get(server_id, {})
    if not current_server_duel.get("active") or current_server_duel.get("problem") is None:
        await ctx.send("There is no duel in progress on this server.")
        return
    if ctx.author != current_server_duel['challenger'] and ctx.author != current_server_duel['opponent']:
        await ctx.send("You are not a participant in the current duel.")
        return

    if winner_id not in server_users:
        await ctx.send("Error: Could not find your user data for this server.")
        return

    winner_handle = server_users[winner_id]['codeforces_handle']
    problem_info = current_server_duel['problem']
    duel_rating = current_server_duel['rating'] # MODIFIED: Get the rating

    await ctx.send(f"Checking {ctx.author.mention}'s recent submissions for a correct solution...")

    try:
        response = requests.get(f"https://codeforces.com/api/user.status?handle={winner_handle}&from=1&count=10")
        response.raise_for_status()
        data = response.json()
        if data.get('status') != 'OK':
            raise Exception(f"Codeforces API Error: {data.get('comment', 'Failed to fetch status')}")

        submissions = data['result']
        for sub in submissions:
            if (sub['problem']['contestId'] == problem_info['contestId'] and sub['problem']['index'] == problem_info['index'] and sub['verdict'] == 'OK'):
                if datetime.fromtimestamp(sub['creationTimeSeconds'], UTC) > current_server_duel['start_time']:
                    # MODIFIED: Calculate weighted points and update user score
                    points_awarded = calculate_points(duel_rating)
                    server_users[winner_id]['points'] += points_awarded
                    all_data[server_id] = server_users
                    save_users(all_data)
                    
                    # MODIFIED: Update win message
                    await ctx.send(
                        f"🎉 **Winner!** {ctx.author.mention} has solved the problem and won the duel!\n"
                        f"**{points_awarded} points** awarded for a {duel_rating}-rated problem. Their total is now **{server_users[winner_id]['points']}**."
                    )
                    del duel_state[server_id]
                    return

        await ctx.send("I couldn't find a recent, correct submission from you for the duel problem. Keep trying!")
    except Exception as e:
        await ctx.send("An error occurred while checking submissions.")
        print(f"Error during !solved: {e}")

async def duel_timeout_task(ctx, original_start_time, server_id):
    """A background task that waits 15 minutes and ends the duel if it's still active."""
    await asyncio.sleep(900)  # Wait for 15 minutes

    # MODIFIED: Check the duel state for the specific server
    current_server_duel = duel_state.get(server_id, {})
    if current_server_duel.get("active") and current_server_duel.get("start_time") == original_start_time:
        await ctx.send(
            f"**Time's up!** The duel between {current_server_duel['challenger'].mention} and "
            f"{current_server_duel['opponent'].mention} has ended in a **draw**. No points awarded."
        )
        # MODIFIED: Clear the server's duel state
        del duel_state[server_id]

# --- RUN THE BOT ---
if __name__ == "__main__":
    if BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        print("ERROR: Please replace 'YOUR_BOT_TOKEN_HERE' with your actual bot token in bot.py")
    else:
        bot.run(BOT_TOKEN)