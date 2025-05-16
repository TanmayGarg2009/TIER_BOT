import os
import discord
from discord import app_commands
from keep_alive import keep_alive

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Change these as needed
ALLOWED_ROLE_NAME = "Admin"  # Role allowed to use the command


@client.event
async def on_ready():
    await tree.sync()  # Sync commands with Discord
    print(f'Logged in as {client.user}')


def has_allowed_role(interaction: discord.Interaction):
    return any(role.name == ALLOWED_ROLE_NAME
               for role in interaction.user.roles)


@tree.command(
    name="givetier",
    description="Assign a tier role to a player",
)
@app_commands.describe(player="The member to give the role to",
                       tier="The name of the tier role to assign")
async def givetier(interaction: discord.Interaction, player: discord.Member,
                   tier: str):
    # Permission check
    if not has_allowed_role(interaction):
        await interaction.response.send_message(
            "❌ You don't have permission to use this command.", ephemeral=True)
        return

    # Find the role by name
    role = discord.utils.get(interaction.guild.roles, name=tier)
    if role is None:
        await interaction.response.send_message(f"Role '{tier}' not found.",
                                                ephemeral=True)
        return

    try:
        await player.add_roles(role)
        await interaction.response.send_message(
            f"✅ Assigned role '{tier}' to {player.mention}.")
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I don't have permission to add that role.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}",
                                                ephemeral=True)


keep_alive()

token = os.getenv("TOKEN")
if not token:
    raise Exception("No token found. Add it as a Secret in Replit.")

client.run(token)
