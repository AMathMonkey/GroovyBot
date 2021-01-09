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
game = api.search(srcomapi.datatypes.Game, {"name": "Beetle Adventure Racing"})[0]

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
bot = commands.Bot("!")


@bot.event
async def on_ready():
    print(f"{bot.user.name} has connected to Discord!")


@tasks.loop(minutes=20.0)
async def point_rankings_task():
    print("Check Leaderboards @ " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    channel = bot.get_channel(id=760197170686328842)

    bar_runs = get_all_runs()

    # list of only important data about each run
    runs_mini = get_runs_mini(bar_runs)
    # load a json list and convert to a set
    old_runs_mini = set(json.load(open("runs.json", "r")))

    player_scores = get_player_scores(runs_mini)
    table = get_table(player_scores)
    new_runs_string = get_new_runs_string(runs_mini, old_runs_mini)

    message_to_send = []

    if new_runs_string:
        print("New run(s)")
        message_to_send.append(enclose_in_code_block(new_runs_string))
        json.dump(list(runs_mini.keys()), open("runs.json", "w"), indent=2)
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
            # print(message_to_send)
            await channel.send(message_to_send)

    print("Sleeping")


@point_rankings_task.before_loop
async def before_point_rankings():
    await bot.wait_until_ready()


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

                id_string = category + level + name + time
                runs_mini[id_string] = {
                    "category": category,
                    "level": level,
                    "name": name,
                    "time": time_string(time),
                    "place": place,
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

point_rankings_task.add_exception_type(JSONDecodeError)
point_rankings_task.start()

bot.run(TOKEN)