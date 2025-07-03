# Codeforces Duel Bot ⚔️

A Discord bot that brings the thrill of competitive programming duels right to your server\! Challenge your friends, solve random Codeforces problems, and climb the leaderboard to prove your skills.

This bot allows users to register with their Codeforces handle, challenge each other to timed 1-v-1 duels on problems of a specific rating, and earn points for being the first to find the correct solution. It's designed to be a fun and engaging way to practice problem-solving and foster a competitive spirit within a community.

## Key Features ✨

  * **Verified Registration:** Securely link a Discord account to a Codeforces handle through a unique verification process.
  * **1-v-1 Dueling:** Challenge another registered user to a duel.
  * **Rated Problem Selection:** Choose a Codeforces problem rating (800-3500), and the bot will find a random, unsolved problem for both participants.
  * **Timed Showdown:** A 15-minute time limit keeps the pressure on. The first to solve the problem wins\!
  * **Points & Leaderboard:** Earn points for every victory and see how you stack up against others with the `!leaderboard` command.
  * **Flexible & Secure:** Ready for remote hosting with `.env` support for secret keys.

## Bot Commands

| Command                             | Description                                                                 |
| ----------------------------------- | --------------------------------------------------------------------------- |
| `!register <handle>`                | Register or re-verify with your Codeforces handle.                          |
| `!updatehandle <new_handle>`        | Change your registered Codeforces handle (requires re-verification).        |
| `!challenge @user <rating>`         | Challenge another registered user to a duel at a specific problem rating.   |
| `!solved`                           | Claim victory during a duel after getting an "Accepted" verdict.            |
| `!profile [@user]`                  | View your own or another user's profile, including points and CF handle.    |
| `!leaderboard`                      | Display the server's top duelists by points.                                |

## Getting Started

### Prerequisites

  * Python 3.8+
  * A Discord Bot Token
  * A Git client

### Installation & Setup

1.  **Clone the repository:**

    ```bash
    git clone <your-repo-url>
    cd DiscordDuelBot
    ```

2.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure your environment:**

      * Create a `.env` file in the root directory.
      * Add your Discord token to the `.env` file:
        ```env
        DISCORD_TOKEN=YourActualBotTokenGoesHere
        ```

4.  **Run the bot:**

    ```bash
    python bot.py
    ```

Ready for a challenge? Add the bot to your server and let the duels begin\!
