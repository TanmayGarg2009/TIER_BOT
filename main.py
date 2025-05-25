import discord
from discord import app_commands
from discord.ext import commands
import json
from datetime import datetime
import os
from keep_alive import keep_alive

# Bot setup
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Constants
VALID_TIERS = ['HT1', 'LT1', 'HT2', 'LT2', 'HT3', 'LT3', 'HT4', 'LT4', 'HT5', 'LT5']
VALID_REGIONS = ['AS', 'NA', 'EU']
CHANNEL_ID = 1346137032933642351
SERVER_ID = 1346134488547332217

# JSON file handling
def load_data():
    try:
        with open('tier_data.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_data(data):
    with open('tier_data.json', 'w') as f:
        json.dump(data, f, indent=4)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    # Create empty JSON file if it doesn't exist
    if not os.path.exists('tier_data.json'):
        save_data({})
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.tree.command(name="givetier", description="Assign a tier to a player")
async def givetier(interaction: discord.Interaction, 
                   member: discord.Member,
                   tier: str,
                   region: str,
                   username: str):
    
    # Validate inputs
    if tier not in VALID_TIERS:
        await interaction.response.send_message("Invalid tier! Use one of: " + ", ".join(VALID_TIERS), ephemeral=True)
        return
    
    if region not in VALID_REGIONS:
        await interaction.response.send_message("Invalid region! Use one of: " + ", ".join(VALID_REGIONS), ephemeral=True)
        return

    # Get the role
    role = discord.utils.get(interaction.guild.roles, name=tier)
    if not role:
        # Create the role if it doesn't exist
        role = await interaction.guild.create_role(name=tier)

    # Add role to member
    try:
        await member.add_roles(role)
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to assign roles!", ephemeral=True)
        return

    # Update JSON data
    data = load_data()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    data[str(member.id)] = {
        "discord_name": str(member),
        "username": username,
        "tier": tier,
        "region": region,
        "last_updated": current_time
    }
    
    save_data(data)

    # Create embed
    embed = discord.Embed(
        title="Tier Assigned",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Username", value=username, inline=False)
    embed.add_field(name="Discord", value=str(member), inline=False)
    embed.add_field(name="Tier", value=tier, inline=False)
    embed.add_field(name="Region", value=region, inline=False)
    embed.add_field(name="Date", value=current_time, inline=False)

    # Send to the specific channel
    channel = interaction.guild.get_channel(CHANNEL_ID)
    if channel:
        await channel.send(embed=embed)
    await interaction.response.send_message("Tier assigned successfully!", ephemeral=True)

@bot.tree.command(name="removetier", description="Remove a tier from a player")
async def removetier(interaction: discord.Interaction, 
                    member: discord.Member,
                    tier: str):
    
    if tier not in VALID_TIERS:
        await interaction.response.send_message("Invalid tier!", ephemeral=True)
        return

    # Get the role
    role = discord.utils.get(interaction.guild.roles, name=tier)
    if role:
        try:
            await member.remove_roles(role)
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to remove roles!", ephemeral=True)
            return

    # Get player info from JSON
    data = load_data()
    player_data = data.get(str(member.id))
    
    if player_data:
        username = player_data['username']
        region = player_data['region']
        
        # Remove from JSON
        del data[str(member.id)]
        save_data(data)

        # Create embed
        embed = discord.Embed(
            title="Tier Removed",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Username", value=username, inline=False)
        embed.add_field(name="Discord", value=str(member), inline=False)
        embed.add_field(name="Tier", value=tier, inline=False)
        embed.add_field(name="Region", value=region, inline=False)
        embed.add_field(name="Date", value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), inline=False)

        # Send to the specific channel
        channel = interaction.guild.get_channel(CHANNEL_ID)
        if channel:
            await channel.send(embed=embed)
        
    await interaction.response.send_message("Tier removed successfully!", ephemeral=True)

@bot.tree.command(name="database", description="Show all players with tiers")
async def database(interaction: discord.Interaction):
    # Update database based on current roles
    await update_database_from_server(interaction.guild)
    
    # Fetch data from JSON
    data = load_data()

    if not data:
        await interaction.response.send_message("No players found in database!", ephemeral=True)
        return

    # Create embed
    embed = discord.Embed(
        title="Player Database",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )

    # Sort and format the data
    sorted_players = sorted(data.items(), key=lambda x: x[1]['tier'])
    formatted_data = ""
    
    for _, player_info in sorted_players:
        formatted_data += f"{player_info['discord_name']} - {player_info['region']} - {player_info['tier']}\n"

    # Split into chunks if too long
    chunks = [formatted_data[i:i+1024] for i in range(0, len(formatted_data), 1024)]
    for i, chunk in enumerate(chunks):
        embed.add_field(name=f"Players {i+1}" if i > 0 else "Players", 
                       value=chunk or "No players", 
                       inline=False)

    await interaction.response.send_message(embed=embed)

async def update_database_from_server(guild):
    data = load_data()
    updated_data = {}
    
    for member in guild.members:
        for role in member.roles:
            if role.name in VALID_TIERS:
                if str(member.id) in data:
                    updated_data[str(member.id)] = data[str(member.id)]
                    updated_data[str(member.id)]['tier'] = role.name
                else:
                    updated_data[str(member.id)] = {
                        "discord_name": str(member),
                        "username": str(member.name),
                        "tier": role.name,
                        "region": "N/A",
                        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                break
    
    save_data(updated_data)

# Keep the bot alive
keep_alive()

# Run the bot
bot.run(os.environ['TOKEN'])