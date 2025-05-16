import os
import discord
from discord import app_commands
from keep_alive import keep_alive  # Assuming this starts a Flask server to keep the bot alive

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Change this to the role allowed to use the command
ALLOWED_ROLE_NAME = "Admin"


@client.event
async def on_ready():
    await tree.sync()  # Sync slash commands with Discord
    print(f'Logged in as {client.user}')


def has_allowed_role(interaction: discord.Interaction):
    # Check if the user has the allowed role
    return any(role.name == ALLOWED_ROLE_NAME for role in interaction.user.roles)


@tree.command(
    name="givetier",
    description="Assign a tier role to a player",
)
@app_commands.describe(player="The member to give the role to", tier="The name of the tier role to assign")
async def givetier(interaction: discord.Interaction, player: discord.Member, tier: str):
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
