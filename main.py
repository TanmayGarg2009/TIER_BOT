import os
import discord
from discord import app_commands
from keep_alive import keep_alive  # Your Flask keep-alive server

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

ALLOWED_ROLE_NAME = "Admin"  # Role allowed to use the command
ANNOUNCE_CHANNEL_ID = 1346137032933642351  # <--- Put your announce channel ID here (int)

# Region choices for the command
REGION_CHOICES = [
    app_commands.Choice(name="AS", value="AS"),
    app_commands.Choice(name="NA", value="NA"),
    app_commands.Choice(name="EU", value="EU"),
]

# Roles to create automatically
ROLES_TO_CREATE = [
    "LT5", "LT4", "LT3", "LT2", "LT1",
    "HT5", "HT4", "HT3", "HT2", "HT1"
]


@client.event
async def on_ready():
    print(f"Logged in as {client.user}")

    # Create missing roles if bot has manage_roles permission
    guild = client.guilds[0]  # Assuming bot is on 1 server only or use your logic to pick a guild
    existing_roles = [role.name for role in guild.roles]

    for role_name in ROLES_TO_CREATE:
        if role_name not in existing_roles:
            try:
                await guild.create_role(name=role_name)
                print(f"Created missing role: {role_name}")
            except discord.Forbidden:
                print(f"Missing permissions to create role: {role_name}")
            except Exception as e:
                print(f"Failed to create role {role_name}: {e}")

    await tree.sync()  # Sync slash commands


def has_allowed_role(interaction: discord.Interaction):
    return any(role.name == ALLOWED_ROLE_NAME for role in interaction.user.roles)


@tree.command(
    name="givetier",
    description="Assign a tier role to a player",
)
@app_commands.describe(
    player="The member to give the role to",
    tier="The name of the tier role to assign",
    region="The region of the player",
)
@app_commands.choices(region=REGION_CHOICES)
async def givetier(
    interaction: discord.Interaction,
    player: discord.Member,
    tier: str,
    region: app_commands.Choice[str],
):
    if not has_allowed_role(interaction):
        await interaction.response.send_message(
            "❌ You don't have permission to use this command.", ephemeral=True
        )
        return

    role = discord.utils.get(interaction.guild.roles, name=tier)
    if role is None:
        await interaction.response.send_message(
            f"Role '{tier}' not found.", ephemeral=True
        )
        return

    try:
        await player.add_roles(role)

        # Ephemeral confirmation to command user
        await interaction.response.send_message(
            f"✅ Assigned role '{tier}' to {player.mention}.", ephemeral=True
        )

        # Public announcement in announce channel
        channel = client.get_channel(ANNOUNCE_CHANNEL_ID)
        if channel:
            announcement = (
                f"**Tester:** {interaction.user.mention}\n"
                f"**Username:** {player.mention}\n"
                f"**Region:** {region.name}\n"
                f"**Rank earned:** {role.name}"
            )
            await channel.send(announcement)
        else:
            print(f"Announcement channel with ID {ANNOUNCE_CHANNEL_ID} not found.")

    except discord.Forbidden:
        await interaction.followup.send(
            "❌ I don't have permission to add that role.", ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)


keep_alive()

token = os.getenv("TOKEN")
if not token:
    raise Exception("No token found. Please set your bot token as an environment variable named 'TOKEN'.")

client.run(token)
