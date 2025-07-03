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
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# --- GLOBAL STATE MANAGEMENT ---
# This dictionary holds the state of any ongoing duel or challenge
duel_state = {
    "active": False,
    "challenger": None,
    "opponent": None,
    "challenge_message": None,
    "problem": None,
    "problem_url": None,
    "start_time": None
}

# --- DATA PERSISTENCE ---
# Functions to load and save user data from the users.json file
def load_users():
    """Loads user data from users.json."""
    if not os.path.exists('users.json'):
        return {}
    try:
        with open('users.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_users(users_data):
    """Saves user data to users.json."""
    with open('users.json', 'w') as f:
        json.dump(users_data, f, indent=4)

# --- BOT EVENTS ---
@bot.event
async def on_ready():
    """Event that runs when the bot has successfully connected to Discord."""
    print(f'Logged in as {bot.user.name}')
    print(f'Bot ID: {bot.user.id}')
    print('Bot is ready and online.')
    print('------')

# --- USER REGISTRATION & PROFILE ---
@bot.command(name='register', help='Register your Codeforces handle. Usage: !register <YourCodeforcesHandle>')
async def register(ctx, codeforces_handle: str):
    """Registers a user by verifying their Codeforces account."""

    # Clean the handle to remove any Discord escape characters
    codeforces_handle = codeforces_handle.replace('\\_', '_')

    users = load_users()
    discord_id = str(ctx.author.id)

    if discord_id in users:
        await ctx.send("You are already registered!")
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

        # After reaction, verify the change on Codeforces
        response = requests.get(f"https://codeforces.com/api/user.info?handles={codeforces_handle}")
        data = response.json()

        if data['status'] == 'OK' and data['result'][0].get('firstName') == token:
            users[discord_id] = {"codeforces_handle": codeforces_handle, "points": 0}
            save_users(users)
            await ctx.author.send(
                f"✅ Verification successful! You are now registered as `{codeforces_handle}`.\n"
                f"You can now change your name back on Codeforces."
            )
        else:
            await ctx.author.send("Verification failed. The first name on your Codeforces profile did not match the token.")

    except asyncio.TimeoutError:
        await ctx.author.send("Verification timed out. Please run the `!register` command again.")

@bot.command(name='updatehandle', help='Update your Codeforces handle. Requires re-verification.')
async def updatehandle(ctx, new_codeforces_handle: str):
    """Updates an existing user's Codeforces handle after re-verification."""

    # Clean the handle to remove any Discord escape characters
    new_codeforces_handle = new_codeforces_handle.replace('\\_', '_')

    users = load_users()
    discord_id = str(ctx.author.id)

    # --- Initial Checks ---
    if discord_id not in users:
        await ctx.send("You are not registered yet. Please use `!register` to create an account.")
        return

    if duel_state["active"]:
        await ctx.send("You cannot change your handle while a duel or challenge is in progress.")
        return

    # Check if the new handle is already registered by another user
    for user_id, data in users.items():
        if data['codeforces_handle'].lower() == new_codeforces_handle.lower() and user_id != discord_id:
            await ctx.send(f"The handle `{new_codeforces_handle}` is already registered by another user.")
            return

    if users[discord_id]['codeforces_handle'].lower() == new_codeforces_handle.lower():
        await ctx.send("This is already your registered handle.")
        return

    # --- Re-verification Process (similar to !register) ---
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

        response = requests.get(f"https://codeforces.com/api/user.info?handles={new_codeforces_handle}")
        data = response.json()

        if data['status'] == 'OK' and data['result'][0].get('firstName') == token:
            # Update the handle in the database
            users[discord_id]['codeforces_handle'] = new_codeforces_handle
            save_users(users)
            await ctx.author.send(
                f"✅ Verification successful! Your Codeforces handle has been updated to `{new_codeforces_handle}`.\n"
                f"You can now change your name back on Codeforces."
            )
        else:
            await ctx.author.send("Verification failed. The first name on your Codeforces profile did not match the token.")

    except asyncio.TimeoutError:
        await ctx.author.send("Verification timed out. Please run the `!updatehandle` command again.")

@bot.command(name='profile', help='Shows your or another user\'s profile.')
async def profile(ctx, member: discord.Member = None):
    """Displays the profile of the mentioned user or the command author."""
    target_user = member or ctx.author
    users = load_users()
    discord_id = str(target_user.id)

    if discord_id not in users:
        await ctx.send(f"{target_user.display_name} is not registered.")
        return

    user_data = users[discord_id]
    embed = discord.Embed(
        title=f"{target_user.display_name}'s Profile",
        color=discord.Color.blue()
    )
    embed.add_field(name="Codeforces Handle", value=f"[{user_data['codeforces_handle']}](https://codeforces.com/profile/{user_data['codeforces_handle']})", inline=False)
    embed.add_field(name="Points", value=user_data['points'], inline=False)
    await ctx.send(embed=embed)

@bot.command(name='leaderboard', help='Shows the server leaderboard.')
async def leaderboard(ctx):
    """Displays the top 10 users by points."""
    users = load_users()
    if not users:
        await ctx.send("No users are registered yet.")
        return

    # Sort users by points in descending order
    sorted_users = sorted(users.items(), key=lambda item: item[1]['points'], reverse=True)

    embed = discord.Embed(title="Leaderboard", color=discord.Color.gold())
    description = ""
    for i, (discord_id, data) in enumerate(sorted_users[:10]):
        try:
            user = await bot.fetch_user(int(discord_id))
            description += f"**{i+1}. {user.display_name}** - {data['points']} points ({data['codeforces_handle']})\n"
        except discord.NotFound:
            # User might have left the server
             description += f"**{i+1}. Unknown User** - {data['points']} points ({data['codeforces_handle']})\n"

    embed.description = description
    await ctx.send(embed=embed)

# --- DUELING SYSTEM COMMANDS ---
@bot.command(name='challenge', help='Challenge another user to a duel. Usage: !challenge @<User> <Rating>')
async def challenge(ctx, opponent: discord.Member, rating: int):
    """Initiates a duel challenge against another user."""
    global duel_state
    users = load_users()
    challenger_id = str(ctx.author.id)
    opponent_id = str(opponent.id)

    # --- Validation checks (same as before) ---
    if duel_state["active"]:
        await ctx.send("A challenge or duel is already in progress. Please wait.")
        return
    if challenger_id not in users or opponent_id not in users:
        await ctx.send("Both you and your opponent must be registered to duel.")
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

    # --- Set duel to pending state ---
    duel_state.update({
        "active": True,
        "challenger": ctx.author,
        "opponent": opponent
    })

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
            duel_state.update({"active": False, "challenger": None, "opponent": None})
            return

        # --- If accepted, proceed ---
        await ctx.send(f"{opponent.mention} has accepted! Finding a suitable problem...")

        challenger_handle = users[challenger_id]['codeforces_handle']
        opponent_handle = users[opponent_id]['codeforces_handle']

        # --- MORE ROBUST API CALLS ---
        try:
            # Helper function to make and check API calls
            async def get_cf_api(url):
                response = requests.get(url)
                response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
                data = response.json()
                if data.get('status') != 'OK':
                    raise Exception(f"Codeforces API Error: {data.get('comment', 'No comment provided')}")
                return data

            # Fetch solved problems for both users
            ch_data = await get_cf_api(f"https://codeforces.com/api/user.status?handle={challenger_handle}")
            op_data = await get_cf_api(f"https://codeforces.com/api/user.status?handle={opponent_handle}")
            problems_data = await get_cf_api("https://codeforces.com/api/problemset.problems")

            # --- SAFER DATA PROCESSING ---
            # Safely create sets of solved problems, skipping any malformed entries
            ch_solved = {
                f"{p['problem']['contestId']}{p['problem']['index']}"
                for p in ch_data['result']
                if p.get('verdict') == 'OK' and 'contestId' in p.get('problem', {})
            }
            op_solved = {
                f"{p['problem']['contestId']}{p['problem']['index']}"
                for p in op_data['result']
                if p.get('verdict') == 'OK' and 'contestId' in p.get('problem', {})
            }

            # Safely filter for potential duel problems
            potential_problems = [
                p for p in problems_data['result']['problems']
                if p.get('rating') == rating and 'contestId' in p and 'index' in p and
                f"{p.get('contestId')}{p.get('index')}" not in ch_solved and
                f"{p.get('contestId')}{p.get('index')}" not in op_solved
            ]
            # --- END OF SAFER DATA PROCESSING ---

        except Exception as e:
            await ctx.send(f"An error occurred while fetching data from Codeforces. The duel is cancelled. Please try again later.\n`Error: {e}`")
            duel_state.update({"active": False, "challenger": None, "opponent": None})
            return
        # --- END OF ROBUST API CALLS ---

        if not potential_problems:
            await ctx.send(f"Could not find a suitable unsolved problem at rating {rating}. The challenge has been cancelled.")
            duel_state.update({"active": False, "challenger": None, "opponent": None})
            return

        # --- Start the duel ---
        problem = random.choice(potential_problems)
        problem_url = f"https://codeforces.com/problemset/problem/{problem['contestId']}/{problem['index']}"
        duel_state.update({
            "problem": problem,
            "problem_url": problem_url,
            "start_time": datetime.now(UTC)
        })

        await ctx.send(
            f"**Duel Start!**\n"
            f"**Problem:** {problem['name']} (Rating: {rating})\n"
            f"**Link:** {problem_url}\n\n"
            f"{duel_state['challenger'].mention} vs {duel_state['opponent'].mention}: The first to solve it in **15 minutes** wins 10 points! Type `!solved` when you have an accepted solution."
        )

        bot.loop.create_task(duel_timeout_task(ctx, duel_state['start_time']))

    except asyncio.TimeoutError:
        await ctx.send(f"The duel challenge for {opponent.mention} expired.")
        duel_state.update({"active": False, "challenger": None, "opponent": None})


@bot.command(name='solved', help='Claim victory in the current duel.')
async def solved(ctx):
    """Allows a user to claim they have solved the duel problem."""
    global duel_state
    users = load_users()
    winner_id = str(ctx.author.id)

    # Validation
    if not duel_state["active"] or duel_state["problem"] is None:
        await ctx.send("There is no duel in progress.")
        return
    if ctx.author != duel_state['challenger'] and ctx.author != duel_state['opponent']:
        await ctx.send("You are not a participant in the current duel.")
        return

    winner_handle = users[winner_id]['codeforces_handle']
    problem_info = duel_state['problem']

    await ctx.send(f"Checking {ctx.author.mention}'s recent submissions for a correct solution...")

    try:
        # Check the user's last 10 submissions on Codeforces
        response = requests.get(f"https://codeforces.com/api/user.status?handle={winner_handle}&from=1&count=10")
        submissions = response.json()['result']

        for sub in submissions:
            # Check if submission matches problem and is correct
            if (sub['problem']['contestId'] == problem_info['contestId'] and
                sub['problem']['index'] == problem_info['index'] and
                sub['verdict'] == 'OK'):

                # Check if the submission was made after the duel started
                if datetime.fromtimestamp(sub['creationTimeSeconds'], UTC) > duel_state['start_time']:
                    users[winner_id]['points'] += 10
                    save_users(users)

                    await ctx.send(
                        f"🎉 **Winner!** {ctx.author.mention} has solved the problem and won the duel!\n"
                        f"10 points awarded. Their total is now **{users[winner_id]['points']}**."
                    )

                    # End the duel
                    duel_state.update({"active": False, "challenger": None, "opponent": None, "problem": None})
                    return

        await ctx.send("I couldn't find a recent, correct submission from you for the duel problem. Keep trying!")

    except Exception as e:
        await ctx.send("An error occurred while checking submissions.")
        print(f"Error during !solved: {e}")

# ADD THIS NEW FUNCTION
async def duel_timeout_task(ctx, original_start_time):
    """A background task that waits 15 minutes and ends the duel if it's still active."""
    await asyncio.sleep(900)  # Wait for 15 minutes

    # After waiting, check if the duel is the SAME one that started this task
    if duel_state["active"] and duel_state["start_time"] == original_start_time:
        await ctx.send(
            f"**Time's up!** The duel between {duel_state['challenger'].mention} and "
            f"{duel_state['opponent'].mention} has ended in a **draw**. No points awarded."
        )
        # Reset the duel state
        duel_state.update({"active": False, "challenger": None, "opponent": None, "problem": None, "start_time": None})

# --- RUN THE BOT ---
if __name__ == "__main__":
    if BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        print("ERROR: Please replace 'YOUR_BOT_TOKEN_HERE' with your actual bot token in bot.py")
    else:
        bot.run(BOT_TOKEN)