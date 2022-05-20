import asyncio
import discord
import re
import os
import requests
from re import search
from replit import db
from unidecode import unidecode
from fuzzywuzzy import fuzz

### SETUP ###
client = discord.Client()
discord_token = os.environ['discord_bot_token']
db["active_question"] = None
if not db["players"]:
  db["players"] = {}

class Jeopardy:
    def get_question(guild, message, channel):
        result = "Could not find question. Perhaps something is wrong?"
    
        if not db["active_question"]:   
          scryfall_api = "https://api.scryfall.com/cards/random?" + db["query"]
          card = requests.get(scryfall_api).json()
          attempt = 0
          while "edhrec_rank" not in card:
            print("No edhrec rank or double sided card: {}. Trying again...".format(card["name"]))
            card = requests.get(scryfall_api).json()
            attempt = attempt + 1
            if attempt > 10:
              result = "Couldn't find a card. Try changing Scryfall search"
              return result
          # For debugging purposes.
          print(card["name"])
          db["question"] = card
          db["question"]["guild"] = guild.id
          db["question"]["message"] = message
          db["active_question"] = True
          
          if db["question"]["name"] or db["question"]["name"].split()[0] in db["question"]["oracle_text"]:
            for r in (db["question"]["name"],db["question"]["name"].split()[0][:-1]):
              db["question"]["oracle_text"] = db["question"]["oracle_text"].replace(r, "...")
              
          for mana in db["question"]["color_identity"]:
            color_identity = ""
            for emoji in guild.emojis:
              if (search(mana,str(emoji))):
                color_identity = color_identity + "<:{}:{}> ".format(emoji.name,emoji.id)

          embed=discord.Embed(title="{}          {}".format(db["question"]["edhrec_rank"],color_identity), description=db["question"]["oracle_text"])
          embed.set_author(name="For {} points:".format(db["question"]["edhrec_rank"]))
          await channel.send(embed=embed)
          result = "For {} points:\n> Set Name: {}\n> Colors: {}\n> Type Line: {}\n```{}```".format(db["question"]["edhrec_rank"],db["question"]["set_name"],color_identity,db["question"]["type_line"],db["question"]["oracle_text"])
          client.loop.create_task(Timers.question_timer(guild.id,channel,db["question"]["id"]))
          client.loop.create_task(Timers.hint_timer(guild.id,channel,db["question"]["id"]))

        if db["active_question"]:
            result = "For {} points:\n> Set Name: {}\n> Colors: {}\n> Type Line: {}\n```{}```".format(db["question"]["edhrec_rank"],db["question"]["set_name"],color_identity,db["question"]["type_line"],db["question"]["oracle_text"])
        return result

    async def check_answer(guild, message, channel, user):
        if not db["active_question"]:
            print("No active question")
            answer = False
        else:
            print("Found active question")
    
            message = re.sub(r"^(what|whats|where|wheres|who|whos)(\s)(is|are)", '', message, flags=re.IGNORECASE)
            print("Answer pre-decoding: {}".format(db["question"]["name"]))
            decoded = unidecode(db["question"]["name"])
            print("Answer post-decoding: {}".format(decoded))
            check_full = fuzz.ratio(message,decoded)
            check_name = fuzz.ratio(message,decoded.split()[0])
            score = db["question"]["edhrec_rank"]
    
            if user.display_name in db["players"] and db["question"]["id"] == db["players"][user.display_name]["last_question"]:
                answer = "You have already tried to answer this question, {}!".format(user.display_name)
    
            elif check_full > 60 or check_name > 70:
                db["players"][user.display_name]["score"] = Bot.update_score(guild, user, score, db["question"]["id"])
                answer = "That is correct, {}! Your score is now {}.".format(user.display_name,db["players"][user.display_name]["score"])
                embed=discord.Embed()
                embed.set_image(url=db["question"]["image_uris"]["large"])
                embed.add_field(name=db["question"]["name"], value="${}".format(db["question"]["prices"]["usd"]), inline=True)
                await channel.send(content=answer, embed=embed)
                db["active_question"] = False

            else:
                score = score * -1
                user_score = Bot.update_score(guild, user, score, db["question"]["id"])
                answer = "That is incorrect, {}! Your score is now {}.".format(user.display_name,user_score)
                await channel.send(content=answer)

class Bot:
  def admin_tools(guild,user,channel,action,message):
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
    medals = ["🥇","🥈","🥉"]
    try:
      leaderboard = "Let's take a look at the leaderboard:\n"
      for leader in db["players"]:
        leaderboard = leaderboard + "{} {} with a score of {}\n".format(medals[place],db["players"][leader]["name"],db["players"][leader]["score"])
        place = place + 1
    except:
      leaderboard = "There is currently no leaderboard."
    return leaderboard

  def update_score(guild, user, score, question):
    print("Checking for user...")

    if not user.display_name in db["players"]:
        print("No user found, adding...")
        player = {
        'name': user.display_name,
        'guild': guild,
        'score': score,
        'last_question': db["question"]["id"]
        }
        db["players"][user.display_name] = player
    else:
        print("User found, updating score...")
        db["players"][user.display_name]["score"] = score + db["players"][user.display_name]["score"]
        db["players"][user.display_name]["last_question"] = db["question"]["id"]

    print("Done.")

    return db["players"][user.display_name]["score"]


class Timers:
    async def question_timer(guild, channel, question_id):
    
        print("Starting question timer...")
        await asyncio.sleep(30)
        print("Time is up for question")
    
        if not db["active_question"] or question_id != db["question"]["id"]:
            print("Question was answered: {}".format(db["question"]["name"]))
        else:
            print("sending answer")
            db["active_question"] = False
            embed=discord.Embed()
            embed.set_image(url=db["question"]["image_uris"]["large"])
            embed.add_field(name=db["question"]["name"], value="${}".format(db["question"]["prices"]["usd"]), inline=True)
            await channel.send(content="Time is up! The answer is...", embed=embed)

    async def hint_timer(guild, channel, question_id):
    
        print("Starting hint timer...")
        await asyncio.sleep(15)
        print("Time is up for question")
    
        if not db["active_question"] or question_id != db["question"]["id"]:
            print("Question was answered: {} {}".format(question_id,db["question"]["id"]))
        else:
            print("sending hint")
            await channel.send("*Here's a hint. The name starts with {}*".format(str(db["question"]["name"])[0]))

@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))


@client.event
async def on_message(message):

    channel = message.channel
    question_format = re.match("^(what|whats|where|wheres|who|whos)(\s)",message.content,re.IGNORECASE)

    if message.author == client.user:
        return

    if message.content.startswith('!jmtg'):
        result = Jeopardy.get_question(message.guild,message.id,channel)

        await channel.send(result)

    if message.content.startswith('!jldr'):
        result = Bot.get_leaderboard(message.guild.id,channel)

        await channel.send(result)

    if message.content.startswith('!jrst'):
        action = "reset"
        result = Bot.admin_tools(message.guild.id,message.author,channel,action,message.content)

        await channel.send(result)

    if message.content.startswith('!jset'):
        action = "set_query"
        result = Bot.admin_tools(message.guild.id,message.author,channel,action,message.content)

        await channel.send(result)

    if message.content.startswith('!emoji'):
        print("checking emoji")
        for emoji in message.guild.emojis:
            
            print(emoji.name, emoji.id)
        await channel.send("<:{}:{}>".format(emoji.name,emoji.id))

    if question_format:
        print("found an answer!")
        await Jeopardy.check_answer(message.guild.id,message.content,channel,message.author)

client.run(discord_token)