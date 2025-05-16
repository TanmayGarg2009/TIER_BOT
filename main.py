import os
import discord
from discord import app_commands
from discord.ext import commands
from keep_alive import keep_alive  # Your Flask server to keep the bot alive

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

ALLOWED_ROLE_NAME = "Admin"
ANNOUNCE_CHANNEL_ID = 1346137032933642351

# Tier choices for the command dropdown
TIERS = [
    "LT5", "LT4", "LT3", "LT2", "LT1",
    "HT5", "HT4", "HT3", "HT2", "HT1"
]

# Prepare choices for app_commands (dropdowns)
TIER_CHOICES = [app_commands.Choice(name=t, value=t) for t in TIERS]
REGION_CHOICES = [
    app_commands.Choice(name="AS", value="AS"),
    app_commands.Choice(name="NA", value="NA"),
    app_commands.Choice(name="EU", value="EU"),
]

async def create_tier_roles_if_missing(guild: discord.Guild):
    existing_roles = [role.name for role in guild.roles]
    for tier in TIERS:
        if tier not in existing_roles:
            await guild.create_role(name=tier)
            print(f"Created missing role: {tier}")

def has_allowed_role(interaction: discord.Interaction):
    return any(role.name == ALLOWED_ROLE_NAME for role in interaction.user.roles)

@bot.event
async def on_ready():
    for guild in bot.guilds:
        await create_tier_roles_if_missing(guild)
    await tree.sync()
    print(f"Logged in as {bot.user}")

@tree.command(name="givetier", description="Assign a tier role to a player")
@app_commands.describe(
    player="The member to give the role to",
    tier="The tier role to assign",
    region="Select the region"
)
@app_commands.choices(tier=TIER_CHOICES, region=REGION_CHOICES)
async def givetier(
    interaction: discord.Interaction,
    player: discord.Member,
    tier: app_commands.Choice[str],
    region: app_commands.Choice[str]
):
    if not has_allowed_role(interaction):
        await interaction.response.send_message(
            "❌ You don't have permission to use this command.", ephemeral=True
        )
        return

    role = discord.utils.get(interaction.guild.roles, name=tier.value)
    if role is None:
        await interaction.response.send_message(f"Role '{tier.value}' not found.", ephemeral=True)
        return

    try:
        await player.add_roles(role)
        await interaction.response.send_message(
            f"✅ Assigned role '{tier.value}' to {player.mention}.", ephemeral=True
        )
        channel = bot.get_channel(ANNOUNCE_CHANNEL_ID)
        if channel:
            embed = discord.Embed(title="Tier Role Assigned", color=discord.Color.green())
            embed.add_field(name="Tester", value=interaction.user.mention, inline=False)
            embed.add_field(name="Username", value=player.mention, inline=False)
            embed.add_field(name="Region", value=region.value, inline=False)
            embed.add_field(name="Rank Earned", value=tier.value, inline=False)
            await channel.send(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I don't have permission to add that role.", ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

@tree.command(name="removetier", description="Remove a tier role from a player")
@app_commands.describe(
    player="The member to remove the role from",
    tier="The tier role to remove",
)
@app_commands.choices(tier=TIER_CHOICES)
async def removetier(
    interaction: discord.Interaction,
    player: discord.Member,
    tier: app_commands.Choice[str]
):
    if not has_allowed_role(interaction):
        await interaction.response.send_message(
            "❌ You don't have permission to use this command.", ephemeral=True
        )
        return

    role = discord.utils.get(interaction.guild.roles, name=tier.value)
    if role is None:
        await interaction.response.send_message(f"Role '{tier.value}' not found.", ephemeral=True)
        return

    if role not in player.roles:
        await interaction.response.send_message(
            f"{player.mention} does not have the role '{tier.value}'.", ephemeral=True
        )
        return

    try:
        await player.remove_roles(role)
        await interaction.response.send_message(
            f"✅ Removed role '{tier.value}' from {player.mention}.", ephemeral=True
        )
        channel = bot.get_channel(ANNOUNCE_CHANNEL_ID)
        if channel:
            embed = discord.Embed(title="Tier Role Removed", color=discord.Color.red())
            embed.add_field(name="Tester", value=interaction.user.mention, inline=False)
            embed.add_field(name="Username", value=player.mention, inline=False)
            embed.add_field(name="Rank Removed", value=tier.value, inline=False)
            await channel.send(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I don't have permission to remove that role.", ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

keep_alive()

token = os.getenv("TOKEN")
if not token:
    raise Exception("No token found. Please set your bot token as an environment variable named 'TOKEN'.")

bot.run(token)
