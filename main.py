import os
import discord
from discord import app_commands
from keep_alive import keep_alive  # Flask keep-alive server

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

ALLOWED_ROLE_NAME = "Admin"

# ID of the channel where you want to announce the rank assignment
ANNOUNCE_CHANNEL_ID = 123456789012345678  # <-- replace with your Discord channel ID


@client.event
async def on_ready():
    await tree.sync()
    print(f'Logged in as {client.user}')


def has_allowed_role(interaction: discord.Interaction):
    return any(role.name == ALLOWED_ROLE_NAME for role in interaction.user.roles)


@tree.command(
    name="givetier",
    description="Assign a tier role to a player",
)
@app_commands.describe(
    player="The member to give the role to",
    tier="The name of the tier role to assign",
    region="The region of the player"
)
async def givetier(interaction: discord.Interaction, player: discord.Member, tier: str, region: str):
    if not has_allowed_role(interaction):
        await interaction.response.send_message(
            "❌ You don't have permission to use this command.", ephemeral=True
        )
        return

    role = discord.utils.get(interaction.guild.roles, name=tier)
    if role is None:
        await interaction.response.send_message(f"Role '{tier}' not found.", ephemeral=True)
        return

    try:
        await player.add_roles(role)
        await interaction.response.send_message(f"✅ Assigned role '{tier}' to {player.mention}.")

        # Send announcement message in the specific channel
        channel = client.get_channel(ANNOUNCE_CHANNEL_ID)
        if channel:
            announcement = (
                f"**Tester:** {interaction.user.mention}\n"
                f"**Username:** {player.mention}\n"
                f"**Region:** {region}\n"
                f"**Rank earned:** {role.name}"
            )
            await channel.send(announcement)
        else:
            print(f"Announcement channel with ID {ANNOUNCE_CHANNEL_ID} not found.")

    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I don't have permission to add that role.", ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)


keep_alive()

token = os.getenv("TOKEN")
if not token:
    raise Exception("No token found. Please set your bot token as an environment variable named 'TOKEN'.")

client.run(token)
