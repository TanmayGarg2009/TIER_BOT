import os
import discord
import json
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from keep_alive import keep_alive

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

ALLOWED_ROLE_NAME = "Admin"
ANNOUNCE_CHANNEL_ID = 1346137032933642351
DATA_FILE = "tier_data.json"

TIERS = ["LT5", "LT4", "LT3", "LT2", "LT1", "HT5", "HT4", "HT3", "HT2", "HT1"]

TIER_CHOICES = [app_commands.Choice(name=t, value=t) for t in TIERS]
REGION_CHOICES = [
    app_commands.Choice(name="AS", value="AS"),
    app_commands.Choice(name="NA", value="NA"),
    app_commands.Choice(name="EU", value="EU"),
]

def has_allowed_role(interaction: discord.Interaction):
    return any(role.name == ALLOWED_ROLE_NAME for role in interaction.user.roles)

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("⚠️ tier_data.json is empty or invalid, reinitializing...")
            return {}
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

async def create_tier_roles_if_missing(guild: discord.Guild):
    existing_roles = [role.name for role in guild.roles]
    for tier in TIERS:
        if tier not in existing_roles:
            await guild.create_role(name=tier)
            print(f"Created missing role: {tier}")

@bot.event
async def on_ready():
    for guild in bot.guilds:
        await create_tier_roles_if_missing(guild)
    await tree.sync()
    print(f"Logged in as {bot.user}")

@tree.command(name="givetier", description="Assign a tier role to a player")
@app_commands.describe(
    player="The member to give the role to",
    username="Minecraft or game username",
    tier="The tier role to assign",
    region="Select the region"
)
@app_commands.choices(tier=TIER_CHOICES, region=REGION_CHOICES)
async def givetier(
    interaction: discord.Interaction,
    player: discord.Member,
    username: str,
    tier: app_commands.Choice[str],
    region: app_commands.Choice[str]
):
    if not has_allowed_role(interaction):
        await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
        return

    role = discord.utils.get(interaction.guild.roles, name=tier.value)
    if not role:
        await interaction.response.send_message(f"Role '{tier.value}' not found.", ephemeral=True)
        return

    try:
        await player.add_roles(role)
        date_now = datetime.now().strftime("%d/%m/%Y")

        data = load_data()
        data[str(player.id)] = {
            "username": username,
            "tier": tier.value,
            "date": date_now
        }
        save_data(data)

        await interaction.response.send_message(f"✅ Assigned role '{tier.value}' to {player.mention}.", ephemeral=True)

        channel = bot.get_channel(ANNOUNCE_CHANNEL_ID)
        if channel:
            embed = discord.Embed(title="Tier Role Assigned", color=discord.Color.green())
            embed.add_field(name="Tester", value=interaction.user.mention, inline=False)
            embed.add_field(name="Username", value=username, inline=False)
            embed.add_field(name="Region", value=region.value, inline=False)
            embed.add_field(name="Rank Earned", value=tier.value, inline=False)
            await channel.send(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"Error: {e}", ephemeral=True)

@tree.command(name="removetier", description="Remove a tier role from a player")
@app_commands.describe(player="The member to remove the role from", tier="Tier role to remove")
@app_commands.choices(tier=TIER_CHOICES)
async def removetier(interaction: discord.Interaction, player: discord.Member, tier: app_commands.Choice[str]):
    if not has_allowed_role(interaction):
        await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
        return

    role = discord.utils.get(interaction.guild.roles, name=tier.value)
    if not role:
        await interaction.response.send_message(f"Role '{tier.value}' not found.", ephemeral=True)
        return

    if role not in player.roles:
        await interaction.response.send_message(f"{player.mention} does not have the role.", ephemeral=True)
        return

    try:
        await player.remove_roles(role)
        await interaction.response.send_message(f"✅ Removed role '{tier.value}' from {player.mention}.", ephemeral=True)

        # Update database
        data = load_data()
        if str(player.id) in data and data[str(player.id)]["tier"] == tier.value:
            del data[str(player.id)]
            save_data(data)

        channel = bot.get_channel(ANNOUNCE_CHANNEL_ID)
        if channel:
            embed = discord.Embed(title="Tier Role Removed", color=discord.Color.red())
            embed.add_field(name="Tester", value=interaction.user.mention, inline=False)
            embed.add_field(name="Username", value=player.mention, inline=False)
            embed.add_field(name="Rank Removed", value=tier.value, inline=False)
            await channel.send(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"Error: {e}", ephemeral=True)

@tree.command(name="tier", description="Check someone's tier and assignment date")
@app_commands.describe(player="The player to check")
async def tier(interaction: discord.Interaction, player: discord.Member):
    data = load_data()
    record = data.get(str(player.id))
    if not record:
        await interaction.response.send_message("No tier assigned to this player.", ephemeral=True)
        return

    embed = discord.Embed(title="Tier Info", color=discord.Color.blue())
    embed.add_field(name="Username", value=record["username"], inline=False)
    embed.add_field(name="Discord", value=player.mention, inline=False)
    embed.add_field(name="Current Tier", value=record["tier"], inline=False)
    embed.add_field(name="Assigned Date", value=record["date"], inline=False)
    await interaction.response.send_message(embed=embed)

@tree.command(name="database", description="List all tiered players")
async def database(interaction: discord.Interaction):
    data = load_data()
    if not data:
        await interaction.response.send_message("No data in the database.")
        return

    embed = discord.Embed(title="Tier Database", color=discord.Color.purple())
    for user_id, info in data.items():
        member = interaction.guild.get_member(int(user_id))
        name = member.display_name if member else f"User ID {user_id}"
        embed.add_field(
            name=name,
            value=f"Username: {info['username']}\nTier: {info['tier']}\nDate: {info['date']}",
            inline=False
        )
    await interaction.response.send_message(embed=embed)

# Start keep_alive and bot
keep_alive()
token = os.getenv("TOKEN")
if not token:
    raise Exception("No token found. Please set your bot token as an environment variable named 'TOKEN'.")
bot.run(token)
