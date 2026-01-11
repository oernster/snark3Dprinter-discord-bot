import discord
import random
import asyncio
import json

# Replace with your own token (ugh)
TOKEN = 'YOUR_DISCORD_BOT_TOKEN_HERE'

# Intents because bots aren't allowed to have fun without permission
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Load quotes from external JSON file like a responsible adult
def load_quotes():
    try:
        with open('quotes.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("quotes.json is missing. Congrats.")
        return {"snark": [], "it_crowd": []}
    except json.JSONDecodeError:
        print("quotes.json is invalid JSON. Impressive.")
        return {"snark": [], "it_crowd": []}

quotes = load_quotes()

@client.event
async def on_ready():
    print(f'Logged in as {client.user}, who is definitely judging you.')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.lower().startswith('!printquote'):
        if random.random() < 0.75:
            quote = random.choice(quotes.get("snark", ["Your JSON is empty. Shame."]))
        else:
            quote = random.choice(quotes.get("it_crowd", ["Where are the quotes, Roy?"]))
        await message.channel.send(quote)

if __name__ == '__main__':
    client.run(TOKEN)
