import os
import discord
from discord import app_commands
from discord.ext import commands, tasks
import json
from datetime import datetime
from keep_alive import keep_alive

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

ALLOWED_ROLE_NAME = "Admin"
ANNOUNCE_CHANNEL_ID = 1346137032933642351
TIER_FILE = "tier_data.json"

TIERS = ["LT5", "LT4", "LT3", "LT2", "LT1", "HT5", "HT4", "HT3", "HT2", "HT1"]
TIER_CHOICES = [app_commands.Choice(name=t, value=t) for t in TIERS]
REGION_CHOICES = [
    app_commands.Choice(name="AS", value="AS"),
    app_commands.Choice(name="NA", value="NA"),
    app_commands.Choice(name="EU", value="EU"),
]
TIER_INDEX = {t: i for i, t in enumerate(TIERS)}

def load_data():
    if os.path.exists(TIER_FILE):
        with open(TIER_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(TIER_FILE, "w") as f:
        json.dump(data, f, indent=2)

tier_data = load_data()

def has_allowed_role(interaction):
    return any(role.name == ALLOWED_ROLE_NAME for role in interaction.user.roles)

async def create_tier_roles_if_missing(guild):
    existing = [r.name for r in guild.roles]
    for tier in TIERS:
        if tier not in existing:
            await guild.create_role(name=tier)

def get_highest_tier(roles):
    tier_roles = [r.name for r in roles if r.name in TIER_INDEX]
    if not tier_roles:
        return None
    return max(tier_roles, key=lambda r: TIER_INDEX[r])

@bot.event
async def on_ready():
    for guild in bot.guilds:
        await create_tier_roles_if_missing(guild)
    await tree.sync()
    update_all_users.start()
    print(f"✅ Logged in as {bot.user}")

@tree.command(name="givetier", description="Assign a tier role to a player")
@app_commands.describe(player="The member to give the role to",
                       tier="Tier role to assign",
                       region="Region",
                       username="Their username")
@app_commands.choices(tier=TIER_CHOICES, region=REGION_CHOICES)
async def givetier(interaction: discord.Interaction,
                   player: discord.Member,
                   tier: app_commands.Choice[str],
                   region: app_commands.Choice[str],
                   username: str):
    if not has_allowed_role(interaction):
        await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
        return

    role = discord.utils.get(interaction.guild.roles, name=tier.value)
    if not role:
        await interaction.response.send_message(f"❌ Role {tier.value} not found.", ephemeral=True)
        return

    await player.add_roles(role)
    now = datetime.now().strftime("%d/%m/%Y")
    highest = get_highest_tier(player.roles)
    tier_data[str(player.id)] = {
        "discord": player.name,
        "username": username,
        "highest_tier": highest,
        "assign_date": now
    }
    save_data(tier_data)

    await interaction.response.send_message(f"✅ Assigned role '{tier.value}' to {player.mention}.", ephemeral=True)

    embed = discord.Embed(title="Tier Role Assigned", color=discord.Color.green())
    embed.add_field(name="Tester", value=interaction.user.mention, inline=False)
    embed.add_field(name="Username", value=username, inline=False)
    embed.add_field(name="Region", value=region.value, inline=False)
    embed.add_field(name="Rank Earned", value=tier.value, inline=False)

    channel = bot.get_channel(ANNOUNCE_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed)

@tree.command(name="removetier", description="Remove a tier role")
@app_commands.describe(player="The member to remove the role from",
                       tier="Tier role to remove")
@app_commands.choices(tier=TIER_CHOICES)
async def removetier(interaction: discord.Interaction,
                     player: discord.Member,
                     tier: app_commands.Choice[str]):
    if not has_allowed_role(interaction):
        await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
        return

    role = discord.utils.get(interaction.guild.roles, name=tier.value)
    if not role or role not in player.roles:
        await interaction.response.send_message(f"{player.mention} doesn't have {tier.value}.", ephemeral=True)
        return

    await player.remove_roles(role)
    now = datetime.now().strftime("%d/%m/%Y")
    highest = get_highest_tier(player.roles)
    tier_data[str(player.id)] = {
        "discord": player.name,
        "username": tier_data.get(str(player.id), {}).get("username", "Unknown"),
        "highest_tier": highest if highest else "None",
        "assign_date": now
    }
    save_data(tier_data)

    await interaction.response.send_message(f"✅ Removed {tier.value} from {player.mention}.", ephemeral=True)

    embed = discord.Embed(title="Tier Role Removed", color=discord.Color.red())
    embed.add_field(name="Tester", value=interaction.user.mention, inline=False)
    embed.add_field(name="Username", value=tier_data[str(player.id)]["username"], inline=False)
    embed.add_field(name="Rank Removed", value=tier.value, inline=False)

    channel = bot.get_channel(ANNOUNCE_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed)

@tree.command(name="tier", description="Check a member's tier info")
@app_commands.describe(player="The member to check")
async def tier(interaction: discord.Interaction, player: discord.Member):
    await update_user(player)
    data = tier_data.get(str(player.id))
    if not data:
        await interaction.response.send_message("❌ No tier data found.", ephemeral=True)
        return
    await interaction.response.send_message(
        f"{data['discord']} ({data['username']}) has tier **{data['highest_tier']}**\nAssigned on - {data['assign_date']}",
        ephemeral=True
    )

@tree.command(name="database", description="Show all users with tier data")
async def database(interaction: discord.Interaction):
    await update_all_users_now()
    lines = []
    for uid, data in tier_data.items():
        lines.append(f"**{data['discord']}** ({data['username']}) - `{data['highest_tier']}` on {data['assign_date']}")
    message = "\n".join(lines) if lines else "No tier data found."
    await interaction.response.send_message(message[:2000], ephemeral=False)

async def update_user(member):
    highest = get_highest_tier(member.roles)
    current = tier_data.get(str(member.id), {}).get("highest_tier")
    if highest and (current != highest):
        tier_data[str(member.id)] = {
            "discord": member.name,
            "username": tier_data.get(str(member.id), {}).get("username", "Unknown"),
            "highest_tier": highest,
            "assign_date": datetime.now().strftime("%d/%m/%Y")
        }
        save_data(tier_data)

@tasks.loop(minutes=10)
async def update_all_users():
    for guild in bot.guilds:
        for member in guild.members:
            if any(role.name in TIERS for role in member.roles):
                await update_user(member)

async def update_all_users_now():
    for guild in bot.guilds:
        for member in guild.members:
            if any(role.name in TIERS for role in member.roles):
                await update_user(member)

keep_alive()
token = os.getenv("TOKEN")
if not token:
    raise Exception("Bot token not found in env variable 'TOKEN'")
bot.run(token)
