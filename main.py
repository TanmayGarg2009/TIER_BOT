import os
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import json
from keep_alive import keep_alive  # Flask pinger

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.presences = False

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

# Load/Save Data
def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({}, f)
    with open(DATA_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

tier_data = load_data()

# Create roles on startup
async def create_tier_roles_if_missing(guild):
    existing = [r.name for r in guild.roles]
    for tier in TIERS:
        if tier not in existing:
            await guild.create_role(name=tier)

def get_highest_tier(roles):
    tier_ranks = {tier: i for i, tier in enumerate(TIERS)}
    tier_roles = [r.name for r in roles if r.name in tier_ranks]
    if not tier_roles:
        return None
    return max(tier_roles, key=lambda r: tier_ranks[r])

@bot.event
async def on_ready():
    for guild in bot.guilds:
        await create_tier_roles_if_missing(guild)
    await tree.sync()
    print(f"✅ Logged in as {bot.user}")

@tree.command(name="givetier", description="Assign a tier role")
@app_commands.describe(
    player="The member to give the role to",
    username="Their game username",
    tier="Tier role to assign",
    region="Region"
)
@app_commands.choices(tier=TIER_CHOICES, region=REGION_CHOICES)
async def givetier(interaction, player: discord.Member, username: str,
                   tier: app_commands.Choice[str], region: app_commands.Choice[str]):
    if not any(r.name == ALLOWED_ROLE_NAME for r in interaction.user.roles):
        return await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)

    role = discord.utils.get(interaction.guild.roles, name=tier.value)
    if not role:
        return await interaction.response.send_message("Role not found.", ephemeral=True)

    await player.add_roles(role)
    tier_data[str(player.id)] = {
        "username": username,
        "discord_name": str(player),
        "tier": tier.value,
        "region": region.value,
        "assigned": datetime.utcnow().strftime("%d/%m/%Y")
    }
    save_data(tier_data)

    await interaction.response.send_message(
        f"✅ Assigned role '{tier.value}' to {player.mention}.", ephemeral=True
    )

    embed = discord.Embed(title="Tier Assigned", color=discord.Color.green())
    embed.add_field(name="Tester", value=interaction.user.mention, inline=False)
    embed.add_field(name="Username", value=username, inline=False)
    embed.add_field(name="Region", value=region.value, inline=False)
    embed.add_field(name="Rank Earned", value=tier.value, inline=False)

    channel = bot.get_channel(ANNOUNCE_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed)

@tree.command(name="removetier", description="Remove a tier role")
@app_commands.describe(
    player="The member to remove the role from",
    tier="Tier role to remove"
)
@app_commands.choices(tier=TIER_CHOICES)
async def removetier(interaction, player: discord.Member, tier: app_commands.Choice[str]):
    if not any(r.name == ALLOWED_ROLE_NAME for r in interaction.user.roles):
        return await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)

    role = discord.utils.get(interaction.guild.roles, name=tier.value)
    if not role or role not in player.roles:
        return await interaction.response.send_message("Player doesn't have that role.", ephemeral=True)

    await player.remove_roles(role)

    # Update database after role removal
    remaining = get_highest_tier(player.roles)
    if remaining:
        tier_data[str(player.id)]["tier"] = remaining
    else:
        tier_data.pop(str(player.id), None)
    save_data(tier_data)

    await interaction.response.send_message(
        f"✅ Removed role '{tier.value}' from {player.mention}.", ephemeral=True
    )

    embed = discord.Embed(title="Tier Role Removed", color=discord.Color.red())
    embed.add_field(name="Tester", value=interaction.user.mention, inline=False)
    embed.add_field(name="Username", value=str(player), inline=False)
    embed.add_field(name="Rank Removed", value=tier.value, inline=False)

    channel = bot.get_channel(ANNOUNCE_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed)

@tree.command(name="tier", description="Check a user's highest tier")
@app_commands.describe(player="The member to check")
async def tier(interaction, player: discord.Member):
    member_id = str(player.id)
    # Update before showing
    highest = get_highest_tier(player.roles)
    if highest:
        if member_id in tier_data:
            tier_data[member_id]["tier"] = highest
        else:
            tier_data[member_id] = {
                "username": str(player),
                "discord_name": str(player),
                "tier": highest,
                "assigned": datetime.utcnow().strftime("%d/%m/%Y")
            }
        save_data(tier_data)
        data = tier_data[member_id]
        await interaction.response.send_message(
            f"{data['discord_name']} username {data.get('username', 'unknown')} "
            f"{data['tier']} assigned date - {data['assigned']}"
        )
    else:
        await interaction.response.send_message(f"{player.mention} has no tier assigned.")

@tree.command(name="database", description="List all users and their highest tier")
async def database(interaction: discord.Interaction):
    updated = 0
    for member in interaction.guild.members:
        highest = get_highest_tier(member.roles)
        if highest:
            tier_data[str(member.id)] = {
                "username": tier_data.get(str(member.id), {}).get("username", "unknown"),
                "discord_name": str(member),
                "tier": highest,
                "assigned": tier_data.get(str(member.id), {}).get("assigned", datetime.utcnow().strftime("%d/%m/%Y"))
            }
            updated += 1
    save_data(tier_data)

    lines = []
    for data in tier_data.values():
        lines.append(
            f"{data['discord_name']} username {data.get('username', 'unknown')} "
            f"{data['tier']} assigned date - {data['assigned']}"
        )

    chunks = [lines[i:i+10] for i in range(0, len(lines), 10)]
    for chunk in chunks:
        await interaction.followup.send("\n".join(chunk), ephemeral=True)

@bot.event
async def on_member_update(before, after):
    before_roles = set(r.name for r in before.roles if r.name in TIERS)
    after_roles = set(r.name for r in after.roles if r.name in TIERS)

    if before_roles != after_roles:
        highest = get_highest_tier(after.roles)
        member_id = str(after.id)

        if highest:
            tier_data[member_id] = tier_data.get(member_id, {})
            tier_data[member_id]["tier"] = highest
            tier_data[member_id]["discord_name"] = str(after)
            if "assigned" not in tier_data[member_id]:
                tier_data[member_id]["assigned"] = datetime.utcnow().strftime("%d/%m/%Y")
        else:
            tier_data.pop(member_id, None)

        save_data(tier_data)

# Flask pinger to keep bot alive on replit
keep_alive()

token = os.getenv("TOKEN")
if not token:
    raise Exception("No token found in environment variable 'TOKEN'.")
bot.run(token)
