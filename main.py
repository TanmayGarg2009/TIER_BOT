import os
import json
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
from keep_alive import keep_alive
from datetime import datetime

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.guild_messages = True
intents.guild_reactions = True
intents.guild_typing = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

TIERS = ["LT5", "LT4", "LT3", "LT2", "LT1", "HT5", "HT4", "HT3", "HT2", "HT1"]
TIER_CHOICES = [app_commands.Choice(name=t, value=t) for t in TIERS]
REGION_CHOICES = [
    app_commands.Choice(name="AS", value="AS"),
    app_commands.Choice(name="NA", value="NA"),
    app_commands.Choice(name="EU", value="EU")
]

DATA_FILE = "tier_data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

tier_data = load_data()

def get_highest_tier(roles):
    for tier in reversed(TIERS):  # HT1 > ... > LT5
        if any(role.name == tier for role in roles):
            return tier
    return None

async def update_tier_data(member: discord.Member):
    highest = get_highest_tier(member.roles)
    if highest:
        tier_data[str(member.id)] = {
            "discord_name": member.display_name,
            "username": tier_data.get(str(member.id), {}).get("username", "unknown"),
            "tier": highest,
            "region": tier_data.get(str(member.id), {}).get("region", "unknown"),
            "date": datetime.now().strftime("%d/%m/%Y")
        }
    else:
        if str(member.id) in tier_data:
            del tier_data[str(member.id)]
    save_data(tier_data)

@bot.event
async def on_ready():
    await tree.sync()
    print(f"Bot is ready. Logged in as {bot.user}")

@bot.event
async def on_member_update(before, after):
    await update_tier_data(after)

@tree.command(name="givetier", description="Assign a tier role to a player")
@app_commands.describe(player="The member to give the role to", username="In-game username", tier="Tier", region="Region")
@app_commands.choices(tier=TIER_CHOICES, region=REGION_CHOICES)
async def givetier(interaction: discord.Interaction, player: discord.Member, username: str, tier: app_commands.Choice[str], region: app_commands.Choice[str]):
    role = discord.utils.get(interaction.guild.roles, name=tier.value)
    if not role:
        await interaction.response.send_message("Role not found.", ephemeral=True)
        return

    await player.add_roles(role)
    tier_data[str(player.id)] = {
        "discord_name": player.display_name,
        "username": username,
        "tier": tier.value,
        "region": region.value,
        "date": datetime.now().strftime("%d/%m/%Y")
    }
    save_data(tier_data)
    await interaction.response.send_message(f"✅ Assigned {tier.value} to {player.mention}", ephemeral=True)

@tree.command(name="removetier", description="Remove a tier role from a player")
@app_commands.describe(player="The member to remove the role from", tier="Tier")
@app_commands.choices(tier=TIER_CHOICES)
async def removetier(interaction: discord.Interaction, player: discord.Member, tier: app_commands.Choice[str]):
    role = discord.utils.get(interaction.guild.roles, name=tier.value)
    if not role:
        await interaction.response.send_message("Role not found.", ephemeral=True)
        return

    await player.remove_roles(role)
    await update_tier_data(player)
    await interaction.response.send_message(f"✅ Removed {tier.value} from {player.mention}", ephemeral=True)

@tree.command(name="tier", description="Check a user's tier info")
@app_commands.describe(player="The member to check")
async def tier(interaction: discord.Interaction, player: discord.Member):
    await update_tier_data(player)
    data = tier_data.get(str(player.id))
    if data:
        await interaction.response.send_message(
            f"{data['discord_name']} {data['username']} {data['tier']} {data['region']} {data['date']}"
        )
    else:
        await interaction.response.send_message("No tier data found.")

@tree.command(name="database", description="View full tier database")
async def database(interaction: discord.Interaction):
    # Refresh all users
    for member in interaction.guild.members:
        await update_tier_data(member)

    if not tier_data:
        await interaction.response.send_message("No tier data found.")
        return

    msg = "**Tier Database:**\n"
    for user_id, data in tier_data.items():
        msg += f"{data['discord_name']} {data['username']} {data['tier']}\n"

    # Split long messages
    for chunk in [msg[i:i+1900] for i in range(0, len(msg), 1900)]:
        await interaction.channel.send(chunk)

# Ticket view
class TicketButtons(View):
    def __init__(self):
        super().__init__(timeout=None)

        self.add_item(Button(label="Support", style=discord.ButtonStyle.blurple, custom_id="ticket_support"))
        self.add_item(Button(label="Whitelist", style=discord.ButtonStyle.green, custom_id="ticket_whitelist"))
        self.add_item(Button(label="Purge", style=discord.ButtonStyle.red, custom_id="ticket_purge"))

        # High Test only for LT3+
        high_test = Button(label="High Test", style=discord.ButtonStyle.gray, custom_id="ticket_hightest")
        self.add_item(high_test)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        high_test_button = next((btn for btn in self.children if btn.custom_id == "ticket_hightest"), None)
        if high_test_button:
            lt3_index = TIERS.index("LT3")
            user_tiers = [role.name for role in interaction.user.roles if role.name in TIERS]
            user_highest = max((TIERS.index(t) for t in user_tiers), default=-1)
            if user_highest >= lt3_index:
                high_test_button.disabled = False
            else:
                high_test_button.disabled = True
        return True

@tree.command(name="setup_ticket", description="Setup the ticket system in this channel")
async def setup_ticket(interaction: discord.Interaction):
    view = TicketButtons()
    await interaction.channel.send("🎟 **Select a ticket category:**", view=view)
    await interaction.response.send_message("✅ Ticket system setup in this channel!", ephemeral=True)

keep_alive()
token = os.getenv("TOKEN")
bot.run(token)
