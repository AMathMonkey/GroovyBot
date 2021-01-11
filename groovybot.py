from datetime import datetime
from json.decoder import JSONDecodeError
from dotenv import load_dotenv
from discord.ext import tasks, commands
import os
import srcomapi
import srcomapi.datatypes as dt
import json
from prettytable import PrettyTable

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
async def ilranking(ctx, username: str, category: str):
    if ctx.channel.id in GROOVYBOT_CHANNEL_IDS:
        username = username.strip().lower()
        track_and_category = track_category_converter(category.strip().lower())
        if not track_and_category:
            await ctx.send(
                enclose_in_code_block(
                    "Invalid category - please use track initials like cc or MMm100"
                )
            )
            return

        track = track_and_category["track"]
        category = track_and_category["category"]

        runs_mini = json.load(open("runs.json", "r"))
        for run in runs_mini.values():
            if (
                run["category"] == category
                and run["level"] == track
                and run["name"].lower() == username
            ):
                message = f"{run['level']} - {run['category'].title()} in {run['time']} by {run['name']}, {make_ordinal(run['place'])} place\n"
                await ctx.send(enclose_in_code_block(message))
                return
        await ctx.send(enclose_in_code_block("No run matching that username"))


@bot.command()
async def longeststanding(ctx):
    if ctx.channel.id in GROOVYBOT_CHANNEL_IDS:
        message_to_send = ["Longest standing WR runs:\n\n"]
        now = datetime.now().strftime("%Y-%m-%d")
        runs_mini = json.load(open("runs.json", "r"))

        wr_runs = [run for run in runs_mini.values() if run["place"] == 1]
        for run in wr_runs:
            run["age"] = days_between(now, run["date"])

        wr_runs.sort(key=lambda i: i["age"], reverse=True)
        for run in wr_runs:
            age = run["age"]
            s = age != 1
            message_to_send.append(
                f"{run['level']} - {run['category'].title()} in {run['time']} by {run['name']}, {age} day{'s' if s else ''} old\n"
            )

        message_to_send = "".join(message_to_send)
        await ctx.send(enclose_in_code_block(message_to_send))


@tasks.loop(minutes=20.0)
async def point_rankings_task():
    print("Check Leaderboards @ " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    channel = bot.get_channel(id=GROOVYBOT_CHANNEL_IDS[0])

    bar_runs = get_all_runs()

    # list of only important data about each run
    runs_mini = get_runs_mini(bar_runs)
    # load a json object as a dict of all runs
    old_runs_mini = json.load(open("runs.json"))

    player_scores = get_player_scores(runs_mini)
    table = get_table(player_scores)
    new_runs_string = get_new_runs_string(runs_mini, old_runs_mini)

    message_to_send = []

    if new_runs_string:
        print("New run(s)")
        message_to_send.append(enclose_in_code_block(new_runs_string))

        json.dump(runs_mini, open("runs.json", "w"), indent=2)
    else:
        print("No new runs")

    with open("rankings.txt", "r+") as rankings:
        if table != rankings.read():
            print("Point Rankings Update")
            message_to_send.append(
                enclose_in_code_block("Point Rankings Update!\n" + table)
            )
            rankings.seek(0)
            rankings.truncate()
            rankings.write(table)
        else:
            if new_runs_string != None:
                message_to_send.append(
                    enclose_in_code_block("But rankings are unchanged")
                )
            print("No update")

        if message_to_send:
            message_to_send = "".join(message_to_send)
            await channel.send(message_to_send)

    print("Sleeping")


@point_rankings_task.before_loop
async def before_point_rankings():
    await bot.wait_until_ready()


def track_category_converter(shortform: str):
    if shortform.endswith("100"):
        category = "100 points"
    else:
        category = "Best track time"

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
        return None

    return {"category": category, "track": track}


def calc_score(placing):
    if placing == 1:
        return 100
    if placing == 2:
        return 97
    return max(0, 98 - placing)


def make_ordinal(n):
    n = int(n)
    suffix = ["th", "st", "nd", "rd", "th"][min(n % 10, 4)]
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    return str(n) + suffix


def time_string(time):
    minutes = 0
    if "." in time:
        seconds, hundredths = time.split(".")
    else:
        seconds = time
        hundredths = "00"
    seconds = int(seconds)
    while seconds >= 60:
        minutes += 1
        seconds -= 60
    hundredths = "{:<02s}".format(hundredths)
    seconds = "{:>02n}".format(seconds)
    return f"{minutes}:{seconds}.{hundredths}"


def enclose_in_code_block(string):
    return "```\n" + string + "\n```"


def get_all_runs():
    bar_runs = {}
    for category in game.categories:
        if category.type == "per-level":
            if not category.name in bar_runs:
                bar_runs[category.name] = {}
            for level in game.levels:
                bar_runs[category.name][level.name] = dt.Leaderboard(
                    api,
                    data=api.get(
                        f"leaderboards/{game.id}/level/{level.id}/{category.id}?embed=variables"
                    ),
                )
    return bar_runs


def get_runs_mini(bar_runs):
    runs_mini = {}
    for category in bar_runs:
        for level in bar_runs[category]:
            leaderboard = bar_runs[category][level]
            for run in leaderboard.runs:
                name = str(run["run"].players).split('"')[1]
                time = str(run["run"].times["ingame_t"])
                place = run["place"]
                date = run["run"].date

                id_string = category + level + name + time
                runs_mini[id_string] = {
                    "category": category,
                    "level": level,
                    "name": name,
                    "time": time_string(time),
                    "place": place,
                    "date": date,
                }
    return runs_mini


def get_player_scores(runs_mini):
    player_scores = {}
    for run in runs_mini:
        run = runs_mini[run]
        name = run["name"]
        place = run["place"]
        if not name in player_scores:
            player_scores[name] = 0
        player_scores[name] += calc_score(place)
    return player_scores


def get_new_runs_string(runs_mini, old_runs_mini):
    new_runs_string = []

    for run in runs_mini:  # just looks at the keys of this dict, which are run IDs
        # if this ID isn't in the set of old IDs, run is new
        if not run in old_runs_mini:

            # temporarily convert run from an ID string to the actual run with that ID to simplify next line
            run = runs_mini[run]
            new_runs_string.append(
                f"New run! {run['level']} - {run['category'].title()} in {run['time']} by {run['name']}, {make_ordinal(run['place'])} place\n"
            )

    if not new_runs_string:
        return None

    return "".join(new_runs_string)


def get_table(player_scores):
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


def days_between(d1, d2):
    d1 = datetime.strptime(d1, "%Y-%m-%d")
    d2 = datetime.strptime(d2, "%Y-%m-%d")
    return abs((d2 - d1).days)


point_rankings_task.start()

bot.run(TOKEN)