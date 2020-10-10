from datetime import datetime
from json.decoder import JSONDecodeError
from dotenv import load_dotenv
import asyncio
import discord
import os
import srcomapi
import srcomapi.datatypes as dt
import json
from prettytable import PrettyTable

api = srcomapi.SpeedrunCom()
api.debug = 0
game = api.search(srcomapi.datatypes.Game, {
                  "name": "Beetle Adventure Racing"})[0]

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
client = discord.Client()


@client.event
async def on_ready():
    print(f'{client.user.name} has connected to Discord!')
    channel = client.get_channel(id=760197170686328842)
    client.loop.create_task(my_background_task())


def calc_score(placing):
    if placing == 1:
        return 100
    if placing == 2:
        return 97
    return max(0, 98 - placing)


def make_ordinal(n):
    n = int(n)
    suffix = ['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]
    if 11 <= (n % 100) <= 13:
        suffix = 'th'
    return str(n) + suffix


def time_string(time):
    minutes = 0
    if '.' in time:
        seconds, hundredths = time.split('.')
    else:
        seconds = time
        hundredths = '00'
    seconds = int(seconds)
    while seconds >= 60:
        minutes += 1
        seconds -= 60
    hundredths = '{:<02s}'.format(hundredths)
    seconds = '{:>02n}'.format(seconds)
    return f"{minutes}:{seconds}.{hundredths}"

# def check_new_runs():
#     print(dt.Run(api, data=api.get("runs?game=" + game.id)))
#     + "&status=verified&orderby=verify-date&direction=desc")))


def enclose_in_code_block(string):
    return '```\n' + string + '\n```'


def parse_leaderboards():
    bar_runs = {}
    runs_mini = {}  # list of only important data about each run to be scraped and saved
    # load a json list and convert to a set
    old_runs_mini = set(json.load(open('runs.json', 'r')))

    for category in game.categories:
        if category.type == 'per-level':
            if not category.name in bar_runs:
                bar_runs[category.name] = {}
            for level in game.levels:
                bar_runs[category.name][level.name] = dt.Leaderboard(api, data=api.get(
                    f"leaderboards/{game.id}/level/{level.id}/{category.id}?embed=variables"))

    player_scores = {}
    for category in bar_runs:
        for level in bar_runs[category]:
            leaderboard = bar_runs[category][level]
            for run in leaderboard.runs:
                name = str(run["run"].players).split('"')[1]
                time = str(run["run"].times['ingame_t'])
                place = run['place']
                if not name in player_scores:
                    player_scores[name] = 0
                player_scores[name] += calc_score(place)

                id_string = category+level+name+time
                runs_mini[id_string] = {'category': category, 'level': level,
                                        'name': name, 'time': time_string(time), 'place': place}

    ranking = sorted(player_scores, key=player_scores.get, reverse=True)
    new_runs_string = ''

    for run in runs_mini:  # just looks at the keys of this dict, which are run IDs
        if not run in old_runs_mini:  # if this ID isn't in the set of old IDs, run is new

            # temporarily convert run from an ID string to the actual run with that ID to simplify next line
            run = runs_mini[run]
            new_runs_string += f"New run! {run['level']} - {run['category'].title()} in {run['time']} by {run['name']}, {make_ordinal(run['place'])} place\n"

    t = PrettyTable(['Pos', 'Score', 'Name'])
    t.align['Pos'] = 'r'
    t.align['Score'] = 'r'
    t.align['Name'] = 'l'

    prev_score = 0
    prev_pos = 0
    for pos, name in enumerate(ranking, 1):
        if(pos > 1 and prev_score == player_scores[name]):
            t.add_row([make_ordinal(prev_pos), player_scores[name], name])
        else:
            t.add_row([make_ordinal(pos), player_scores[name], name])
            prev_pos = pos
            prev_score = player_scores[name]

    if len(new_runs_string) > 0:
        json.dump(list(runs_mini.keys()), open('runs.json', 'w'), indent=2)

    if new_runs_string == '':
        new_runs_string = None

    return {'new_runs': new_runs_string,
            'table': str(t)}


async def my_background_task():

    await client.wait_until_ready()
    channel = client.get_channel(id=760197170686328842)
    while True:
        print("Check Leaderboards @ " +
              datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        try:
            parsed_result = parse_leaderboards()
            new_runs = parsed_result['new_runs']
            table = parsed_result['table']

            message_to_send = ''

            if new_runs != None:
                print("New run(s)")
                message_to_send += enclose_in_code_block(new_runs)
            else:
                print("No new runs")

            rankings = open("rankings.txt", "r+")

            if table != rankings.read():
                print("Point Rankings Update")
                message_to_send += enclose_in_code_block(
                    'Point Rankings Update!\n' + table)
                rankings.seek(0)
                rankings.truncate()
                rankings.write(table)
            else:
                if new_runs != None:
                    message_to_send += enclose_in_code_block(
                        'But rankings are unchanged')
                print("No Update")

            if len(message_to_send) > 0:
                # print(message_to_send)
                await channel.send(message_to_send)
            rankings.close()
            print('sleeping')
        except JSONDecodeError as e:
            print('Unexpected API issue')
            print(e)
        await asyncio.sleep(1200)  # task runs every 1200 seconds

client.run(TOKEN)
