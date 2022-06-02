import asyncio
import discord
import re
import os
import logging
import requests
from re import search
from replit import db
from fuzzywuzzy import fuzz

### SETUP ###
logging.basicConfig(filename='console.log', level=logging.INFO)
client = discord.Client()
discord_token = os.environ['discord_bot_token']
db["active_question"] = None
if not db["players"]:
    db["players"] = {}


class Jeopardy:
    async def get_question(guild, message, channel):

        if db["active_question"]:
            embed = discord.Embed(title="{}          {}".format(
                db["question"]["type_line"], db["question"]["color_identity_emoji"]),
                                  description=db["question"]["oracle_text"])
            embed.set_footer(text=db["question"]["set_name"])
            await channel.send(content="For {} points:".format(
                db["question"]["edhrec_rank"]),
                               embed=embed)

        if not db["active_question"]:
            scryfall_api = "https://api.scryfall.com/cards/random?" + db[
                "query"]
            card = requests.get(scryfall_api).json()
            attempt = 0
            while "edhrec_rank" not in card:
                logging.info(
                    "No edhrec rank or double sided card: {}. Trying again...".
                    format(card["name"]))
                card = requests.get(scryfall_api).json()
                attempt = attempt + 1
                if attempt > 10:
                    result = "Couldn't find a card. Try changing Scryfall search"
                    return result
            # For debugging purposes.
            #logging.info(card["name"])
            db["question"] = card
            db["question"]["guild"] = guild.id
            db["question"]["message"] = message
            db["question"]["color_identity_emoji"] = ""
            db["active_question"] = True

            if db["question"]["name"] or db["question"]["name"].split(
            )[0] in db["question"]["oracle_text"]:
                for r in (db["question"]["name"],
                          db["question"]["name"].split()[0][:-1]):
                    db["question"]["oracle_text"] = db["question"][
                        "oracle_text"].replace(r, "...")

            for mana in db["question"]["color_identity"]:
                logging.info(mana)
                for emoji in guild.emojis:
                    if (search(mana, str(emoji))):
                        db["question"]["color_identity_emoji"] = db["question"]["color_identity_emoji"] + "<:{}:{}> ".format(emoji.name, emoji.id)
                        logging.info("Final color identity: {}".format(db["question"]["color_identity_emoji"]))

            embed = discord.Embed(title="{}          {}".format(
                db["question"]["type_line"], db["question"]["color_identity_emoji"]),
                                  description=db["question"]["oracle_text"])
            embed.set_footer(text=db["question"]["set_name"])
            await channel.send(content="For {} points:".format(
                db["question"]["edhrec_rank"]),
                               embed=embed)

            client.loop.create_task(
                Timers.question_timer(guild.id, channel, db["question"]["id"]))
            client.loop.create_task(
                Timers.hint_timers(guild.id, channel, db["question"]["id"]))

    async def check_answer(guild, message, channel, user):
        if not db["active_question"]:
            logging.info("No active question")
            answer = False
        else:
            logging.info("Found active question")

            message = re.sub(
                r"^(what|whats|where|wheres|who|whos)(\s)(is|are)",
                '',
                message,
                flags=re.IGNORECASE)
            check_full = fuzz.ratio(message, db["question"]["name"])
            check_name = fuzz.ratio(message, db["question"]["name"].split()[0])
            score = db["question"]["edhrec_rank"]

            if user.display_name in db["players"] and db["question"][
                    "id"] == db["players"][user.display_name]["last_question"]:
                answer = "You have already tried to answer this question, {}!".format(
                    user.display_name)

            elif check_full > 60 or check_name > 50:
                db["players"][user.display_name]["score"] = Bot.update_score(
                    guild, user, score, db["question"]["id"])
                answer = "That is correct, {}! Your score is now {}.".format(
                    user.display_name,
                    db["players"][user.display_name]["score"])
                embed = discord.Embed()
                embed.set_image(url=db["question"]["image_uris"]["large"])
                embed.add_field(name=db["question"]["name"],
                                value="${}".format(
                                    db["question"]["prices"]["usd"]),
                                inline=True)
                await channel.send(content=answer, embed=embed)
                db["active_question"] = False

            else:
                score = score * -1
                user_score = Bot.update_score(guild, user, score,
                                              db["question"]["id"])
                answer = "That is incorrect, {}! Your score is now {}.".format(
                    user.display_name, user_score)
                await channel.send(content=answer)


class Bot:
    def admin_tools(guild, user, channel, action, message):
        if not user.guild_permissions.administrator:
            update = "Sorry, only admin can reset the Jeopardy score.\nUse !jmtg to request a question.\nUse 🏅 to check the leaderboard."
        else:
            if action == "reset":
                db["players"] = {}
                update = "Scores have been reset!\nUse !jmtg to request a question."
            elif action == "set_query":
                db["query"] = message[6:]
                update = "Scryfall query is now: " + db["query"]

        return update

    def get_leaderboard(guild, message):
        place = 0
        medals = ["🥇", "🥈", "🥉"]
        #try:
        leaderboard = "Let's take a look at the leaderboard:\n"
        leaders = dict(
            sorted(db["players"].items(), key=lambda player: player[0]))
        for leader in leaders:
            leaderboard = leaderboard + "{} {} with a score of {}\n".format(
                medals[place], db["players"][leader]["name"],
                db["players"][leader]["score"])
            place = place + 1
        #except:
        #  leaderboard = "There is currently no leaderboard."
        return leaderboard

    def update_score(guild, user, score, question):
        logging.info("Checking for user...")

        if not user.display_name in db["players"]:
            logging.info("No user found, adding...")
            player = {
                'name': user.display_name,
                'guild': guild,
                'score': score,
                'last_question': db["question"]["id"]
            }
            db["players"][user.display_name] = player
        else:
            logging.info("User found, updating score...")
            db["players"][user.display_name]["score"] = score + db["players"][
                user.display_name]["score"]
            db["players"][
                user.display_name]["last_question"] = db["question"]["id"]

        return db["players"][user.display_name]["score"]


class Timers:
    async def question_timer(guild, channel, question_id):

        logging.info("Starting question timer...")
        await asyncio.sleep(30)
        logging.info("Time is up for question")

        if not db["active_question"] or question_id != db["question"]["id"]:
            logging.info("Question was answered: {}".format(
                db["question"]["name"]))
        else:
            logging.info("sending answer")
            db["active_question"] = False
            embed = discord.Embed()
            embed.set_image(url=db["question"]["image_uris"]["large"])
            embed.add_field(name=db["question"]["name"],
                            value="${}".format(
                                db["question"]["prices"]["usd"]),
                            inline=True)
            await channel.send(content="Time is up! The answer is...",
                               embed=embed)

    async def hint_timers(guild, channel, question_id):

        logging.info("Starting hint timer...")
        await asyncio.sleep(15)

        if not db["active_question"] or question_id != db["question"]["id"]:
            logging.info("Question was answered: {} {}".format(
                question_id, db["question"]["id"]))
        else:
            logging.info("sending hint")
            await channel.send(
                "*Here's a hint. The name starts with {}*".format(
                    str(db["question"]["name"])[0]))


@client.event
async def on_ready():
    logging.info('We have logged in as {0.user}'.format(client))


@client.event
async def on_message(message):

    channel = message.channel
    question_format = re.match("^(what|whats|where|wheres|who|whos)(\s)",
                               message.content, re.IGNORECASE)

    if message.author == client.user:
        return

    if message.content.startswith('!jmtg'):
        await Jeopardy.get_question(message.guild, message.id, channel)

    if message.content.startswith('!jldr'):
        result = Bot.get_leaderboard(message.guild.id, channel)

        await channel.send(result)

    if message.content.startswith('!jrst'):
        action = "reset"
        result = Bot.admin_tools(message.guild.id, message.author, channel,
                                 action, message.content)

        await channel.send(result)

    if message.content.startswith('!jset'):
        action = "set_query"
        result = Bot.admin_tools(message.guild.id, message.author, channel,
                                 action, message.content)

        await channel.send(result)

    if question_format:
        await Jeopardy.check_answer(message.guild.id, message.content, channel,
                                    message.author)


client.run(discord_token)