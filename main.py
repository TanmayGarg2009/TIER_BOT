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
TIERS = ["LT5", "LT4", "LT3", "LT2", "LT1", "HT5", "HT4", "HT3", "HT2", "HT1"]
TIER_CHOICES = [app_commands.Choice(name=t, value=t) for t in TIERS]
REGION_CHOICES = [app_commands.Choice(name=r, value=r) for r in ["AS", "NA", "EU"]]

DATA_FILE = "tier_data.json"

# ---------------------- DATA HANDLING ----------------------

def load_data():
    if not os.path.exists(DATA_FILE) or os.stat(DATA_FILE).st_size == 0:
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_highest_tier(roles):
    tier_order = {name: i for i, name in enumerate(TIERS)}
    return max((role.name for role in roles if role.name in TIERS), key=lambda r: tier_order[r], default=None)

tier_data = load_data()

# ---------------------- ROLE SETUP ----------------------

async def create_tier_roles(guild):
    existing = [r.name for r in guild.roles]
    for tier in TIERS:
        if tier not in existing:
            await guild.create_role(name=tier)
            print(f"Created role: {tier}")

@bot.event
async def on_ready():
    for guild in bot.guilds:
        await create_tier_roles(guild)
    await tree.sync()
    update_highest_roles.start()
    print(f"Bot ready as {bot.user}")

def has_admin(interaction):
    return any(r.name == ALLOWED_ROLE_NAME for r in interaction.user.roles)

# ---------------------- AUTO UPDATE LOOP ----------------------

@tasks.loop(minutes=10)
async def update_highest_roles():
    for guild in bot.guilds:
        for member in guild.members:
            highest = get_highest_tier(member.roles)
            if highest:
                tier_data[str(member.id)] = {
                    "discord_name": str(member),
                    "username": tier_data.get(str(member.id), {}).get("username", "Unknown"),
                    "tier": highest,
                    "region": tier_data.get(str(member.id), {}).get("region", "N/A"),
                    "date": tier_data.get(str(member.id), {}).get("date", datetime.now().strftime("%d/%m/%Y"))
                }
    save_data(tier_data)

# ---------------------- COMMANDS ----------------------

@tree.command(name="givetier", description="Assign a tier role")
@app_commands.describe(player="User", tier="Tier to assign", username="Their in-game username", region="Region")
@app_commands.choices(tier=TIER_CHOICES, region=REGION_CHOICES)
async def givetier(interaction: discord.Interaction, player: discord.Member, tier: app_commands.Choice[str], username: str, region: app_commands.Choice[str]):
    if not has_admin(interaction):
        return await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)

    role = discord.utils.get(interaction.guild.roles, name=tier.value)
    if not role:
        return await interaction.response.send_message("❌ Role not found.", ephemeral=True)

    await player.add_roles(role)

    # Update database
    highest = get_highest_tier(player.roles)
    tier_data[str(player.id)] = {
        "discord_name": str(player),
        "username": username,
        "tier": highest,
        "region": region.value,
        "date": datetime.now().strftime("%d/%m/%Y")
    }
    save_data(tier_data)

    await interaction.response.send_message(f"✅ Assigned {tier.value} to {player.mention}.", ephemeral=True)

    # Public announcement
    channel = bot.get_channel(ANNOUNCE_CHANNEL_ID)
    if channel:
        embed = discord.Embed(title="Tier Role Assigned", color=discord.Color.green())
        embed.add_field(name="Discord", value=interaction.user.mention, inline=False)
        embed.add_field(name="Username", value=username, inline=False)
        embed.add_field(name="Region", value=region.value, inline=False)
        embed.add_field(name="Tier", value=tier.value, inline=False)
        await channel.send(embed=embed)

@tree.command(name="removetier", description="Remove a tier role")
@app_commands.describe(player="User", tier="Tier to remove")
@app_commands.choices(tier=TIER_CHOICES)
async def removetier(interaction: discord.Interaction, player: discord.Member, tier: app_commands.Choice[str]):
    if not has_admin(interaction):
        return await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)

    role = discord.utils.get(interaction.guild.roles, name=tier.value)
    if not role or role not in player.roles:
        return await interaction.response.send_message("❌ User doesn't have this role.", ephemeral=True)

    await player.remove_roles(role)

    highest = get_highest_tier(player.roles)
    if highest:
        tier_data[str(player.id)]["tier"] = highest
    else:
        tier_data.pop(str(player.id), None)
    save_data(tier_data)

    await interaction.response.send_message(f"✅ Removed {tier.value} from {player.mention}.", ephemeral=True)

    channel = bot.get_channel(ANNOUNCE_CHANNEL_ID)
    if channel:
        embed = discord.Embed(title="Tier Role Removed", color=discord.Color.red())
        embed.add_field(name="Removed From", value=player.mention, inline=False)
        embed.add_field(name="Tier", value=tier.value, inline=False)
        await channel.send(embed=embed)

@tree.command(name="tier", description="Check a user's tier")
@app_commands.describe(player="User to check")
async def tier(interaction: discord.Interaction, player: discord.Member):
    user_data = tier_data.get(str(player.id))
    if not user_data:
        return await interaction.response.send_message("❌ No tier assigned to this user.", ephemeral=True)

    msg = f"**{user_data['discord_name']}** {user_data['username']} {user_data['tier']} {user_data['region']} {user_data['date']}"
    await interaction.response.send_message(msg)

@tree.command(name="database", description="See all users with tiers")
async def database(interaction: discord.Interaction):
    await interaction.response.defer()

    # Update roles before showing
    for member in interaction.guild.members:
        highest = get_highest_tier(member.roles)
        if highest:
            if str(member.id) not in tier_data:
                tier_data[str(member.id)] = {
                    "discord_name": str(member),
                    "username": "Unknown",
                    "tier": highest,
                    "region": "N/A",
                    "date": datetime.now().strftime("%d/%m/%Y")
                }
            else:
                tier_data[str(member.id)]["tier"] = highest
    save_data(tier_data)

    entries = [f"{v['discord_name']} {v['username']} {v['tier']}" for v in tier_data.values()]
    if not entries:
        return await interaction.followup.send("No users have been assigned tiers.")

    chunks = ["```" + "\n".join(entries[i:i+20]) + "```" for i in range(0, len(entries), 20)]
    for chunk in chunks:
        await interaction.followup.send(chunk)

# ---------------------- STARTUP ----------------------

keep_alive()
token = os.getenv("TOKEN")
if not token:
    raise Exception("Please set TOKEN as env variable.")
bot.run(token)
