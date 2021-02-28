#!/usr/bin/python3
from datetime import datetime
from json.decoder import JSONDecodeError
from dotenv import load_dotenv
from discord.ext import tasks, commands
import os
import srcomapi
import srcomapi.datatypes as dt
from prettytable import PrettyTable
from typing import List, Dict
from groovybotsetup import conn, QUERIES

api = srcomapi.SpeedrunCom()
api.debug = 0
game = api.search(dt.Game, {"name": "Beetle Adventure Racing"})[0]

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
MODE = os.getenv("MODE")
bot = commands.Bot("!")

if MODE == "PROD":
    print("Running in production mode")
    GROOVYBOT_CHANNEL_IDS = [760197170686328842, 797386043024343090]
else:
    print("Running in test mode")
    GROOVYBOT_CHANNEL_IDS = [797386043024343090]


@bot.event
async def on_ready():
    print(f"{bot.user.name} has connected to Discord!")


@bot.command()
async def ilranking(ctx, username: str, shortform: str):
    if ctx.channel.id not in GROOVYBOT_CHANNEL_IDS:
        return

    track_and_category = track_category_converter(shortform.strip().lower())
    if not track_and_category:
        await ctx.send(
            enclose_in_code_block(
                "Invalid category - please use track initials like cc or MMm100"
            )
        )
        return

    track = track_and_category["track"]
    category = track_and_category["category"]

    c = conn.cursor()
    run = c.execute(
        QUERIES.get_one_run_for_ilranking,
        [category, track, username.strip().lower()],
    ).fetchone()

    message = (
        f"{run['level']} - {run['category']} in {run['time']} by {run['name']}, {make_ordinal(run['place'])} place"
        if run
        else "No run matching that username"
    )
    await ctx.send(enclose_in_code_block(message))


@bot.command()
async def longeststanding(ctx):
    if ctx.channel.id not in GROOVYBOT_CHANNEL_IDS:
        return

    now = datetime.now().strftime("%Y-%m-%d")

    c = conn.cursor()
    wr_runs = sorted(
        [
            {**run, "age": days_between(now, run["date"])}
            for run in c.execute(QUERIES.get_wr_runs).fetchall()
        ],
        key=lambda i: i["age"],
        reverse=True,
    )

    def string_gen():
        for run in wr_runs:
            age = run["age"]
            s = age != 1
            yield f"{run['level']} - {run['category']} in {run['time']} by {run['name']}, {age} day{'s' if s else ''} old"

    message_to_send = "\n".join(["Longest standing WR runs:\n", *string_gen()])
    await ctx.send(enclose_in_code_block(message_to_send))


@bot.command()
async def pointrankings(ctx):
    if ctx.channel.id not in GROOVYBOT_CHANNEL_IDS:
        return

    c = conn.cursor()
    table = c.execute(QUERIES.get_point_rankings).fetchone()["data"]

    await ctx.send(enclose_in_code_block(table))


@tasks.loop(minutes=20.0)
async def point_rankings_task():
    print("Check Leaderboards @ " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    channel = bot.get_channel(id=GROOVYBOT_CHANNEL_IDS[0])

    bar_runs = get_all_runs()

    # list of only important data about each run
    runs_dict = get_current_runs_dict(bar_runs)

    player_scores = get_player_scores(runs_dict)

    new_runs_string = get_new_runs_string(runs_dict)

    message_to_send = []

    if new_runs_string:
        print("New run(s)")
        message_to_send.append(enclose_in_code_block(new_runs_string))
        save_runs(runs_dict)
    else:
        print("No new runs")

    c = conn.cursor()
    if player_scores != {
        row["name"]: row["score"]
        for row in c.execute("SELECT * FROM scores").fetchall()
    }:
        table = get_table(player_scores)
        print("Point Rankings Update")
        message_to_send.append(
            enclose_in_code_block(f"Point Rankings Update!\n{table}")
        )
        save_scores(player_scores)

        c.execute(QUERIES.replace_point_rankings, [table])
        conn.commit()

    else:
        if new_runs_string:
            message_to_send.append(enclose_in_code_block("But rankings are unchanged"))
        print("Rankings unchanged")

    if message_to_send:
        message_to_send = "".join(message_to_send)
        await channel.send(message_to_send)

    print("Sleeping")


def save_runs(runs_dict):
    c = conn.cursor()
    c.execute(QUERIES.delete_all_runs)

    for run in runs_dict:
        c.execute(
            QUERIES.insert_run,
            run,
        )
    conn.commit()


def save_scores(player_scores: Dict):
    c = conn.cursor()
    c.execute(QUERIES.delete_all_scores)

    for name, score in player_scores.items():
        c.execute(
            QUERIES.insert_score,
            [name, score],
        )
    conn.commit()


@point_rankings_task.before_loop
async def before_point_rankings():
    await bot.wait_until_ready()


def track_category_converter(shortform: str) -> Dict:
    if shortform.endswith("100"):
        category = "100 Points"
    else:
        category = "Time Attack"

    if shortform.startswith("cc"):
        track = "Coventry Cove"
    elif shortform.startswith("mmm"):
        track = "Mount Mayhem"
    elif shortform.startswith("ii"):
        track = "Inferno Isle"
    elif shortform.startswith("ss"):
        track = "Sunset Sands"
    elif shortform.startswith("mms"):
        track = "Metro Madness"
    elif shortform.startswith("ww"):
        track = "Wicked Woods"
    else:
        return {}

    return {"category": category, "track": track}


def calc_score(placing: int) -> int:
    if placing == 1:
        return 100
    if placing == 2:
        return 97
    return max(0, 98 - placing)


def make_ordinal(n: int) -> str:
    n = int(n)
    suffix = ["th", "st", "nd", "rd", "th"][min(n % 10, 4)]
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    return str(n) + suffix


def seconds_to_minutes(time: float) -> str:
    timestr = str(time)

    minutes = 0
    if "." in timestr:
        seconds, hundredths = timestr.split(".")
    else:
        seconds = timestr
        hundredths = "00"
    seconds = int(seconds)
    while seconds >= 60:
        minutes += 1
        seconds -= 60
    hundredths = "{:<02s}".format(hundredths)
    seconds = "{:>02n}".format(seconds)
    return f"{minutes}:{seconds}.{hundredths}"


def enclose_in_code_block(string: str) -> str:
    return f"```\n{string}\n```"


def get_all_runs() -> Dict:
    return {
        category.name: {
            level.name: dt.Leaderboard(
                api,
                data=api.get(
                    f"leaderboards/{game.id}/level/{level.id}/{category.id}?embed=variables"
                ),
            )
            for level in game.levels
        }
        for category in game.categories
        if category.type == "per-level"
    }


def get_current_runs_dict(bar_runs: Dict):
    def run_gen():
        for category in bar_runs:
            for level in bar_runs[category]:
                leaderboard = bar_runs[category][level]
                for run in leaderboard.runs:
                    yield {
                        "category": category,
                        "level": level,
                        "name": str(run["run"].players).split('"')[1],
                        "time": seconds_to_minutes(run["run"].times["ingame_t"]),
                        "place": run["place"],
                        "date": run["run"].date,
                    }

    return list(run_gen())


def get_player_scores(runs_list: List[Dict]) -> Dict[str, int]:
    players = set(run["name"] for run in runs_list)
    return {
        player: sum(
            calc_score(run["place"]) for run in runs_list if run["name"] == player
        )
        for player in players
    }


def get_new_runs_string(runs_list: List[Dict]) -> str:
    c = conn.cursor()
    return "\n".join(
        (
            f"New run! {run['level']} - {run['category']} in {run['time']} by {run['name']}, {make_ordinal(run['place'])} place"
            for run in runs_list
            if not c.execute(QUERIES.get_one_run_for_new_runs, run).fetchall()
        )
    )


def get_table(player_scores: Dict) -> str:
    ranking = sorted(player_scores, key=player_scores.get, reverse=True)

    t = PrettyTable(["Pos", "Score", "Name"])
    t.align["Pos"] = "r"
    t.align["Score"] = "r"
    t.align["Name"] = "l"

    prev_score = 0
    prev_pos = 0
    for pos, name in enumerate(ranking, 1):
        if pos > 1 and prev_score == player_scores[name]:
            t.add_row([make_ordinal(prev_pos), player_scores[name], name])
        else:
            t.add_row([make_ordinal(pos), player_scores[name], name])
            prev_pos = pos
            prev_score = player_scores[name]

    return str(t)


def days_between(d1: str, d2: str) -> int:
    dt1 = datetime.strptime(d1, "%Y-%m-%d")
    dt2 = datetime.strptime(d2, "%Y-%m-%d")
    return abs((dt2 - dt1).days)


point_rankings_task.add_exception_type(JSONDecodeError)
point_rankings_task.start()

bot.run(TOKEN)
