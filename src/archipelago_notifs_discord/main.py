from notifications import add_notification
import os
from pathlib import Path
import json

import discord
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv 
from loguru import logger

# custom module imports
from archipelago_site import (
    check_for_new_archipelago_actions,
    get_recent_archipelago_actions,
)
from notifications import (
    current_burger_king_patrons,
    current_notifications,
    list_burger_king_patrons,
    go_to_burger_king,
    leave_burger_king,
    list_notifications,
    load_notifs_from_file,
    load_patrons_from_bk,
    remove_notification,
    save_notifs_to_file,
)


LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | "
    "<level>{message}</level>"
)

DATA_DIR = Path(os.getenv("DATA_DIR", "./data/"))
CH_FILENAME = DATA_DIR / "channel.json"

# globals
recorded_actions = {}
updates_channel = None

intents = discord.Intents.default()
intents.message_content = True


class ArchieClient(discord.Client):
    async def setup_hook(self):
        tree.add_command(notify)
        guild_id = os.environ.get("GUILD_ID")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            tree.copy_global_to(guild=guild)
            await tree.sync(guild=guild)
        else:
            await tree.sync()


client = ArchieClient(intents=intents)
tree = app_commands.CommandTree(client)
notify = app_commands.Group(
    name = "notify",
    description = "Archipelago server notifications"
)

@notify.command(
    name = "add",
    description = "Request a ping when an item is found for a specified player slot name"
)
@app_commands.describe(
    player="Receiving player slot name",
    item="Item name (leave blank to receive a ping for any item sent to that slot)"
)
async def notify_add(
    interaction: discord.Interaction,
    player: str,
    item: str = ""
):
    msg = await add_notification(interaction.user, item.lower().strip(), player.lower().strip())
    await interaction.response.send_message(msg)

@notify.command(
    name = "remove",
    description = "Remove notification for a specified player slot name (and item)"
)
@app_commands.describe(
    player="Receiving player slot name to remove notification for",
    item="Item name (leave blank if removing an any item ping)"
)
async def notify_remove(
    interaction: discord.Interaction,
    player: str,
    item: str = ""
):
    msg = await remove_notification(interaction.user, item.lower().strip(), player.lower().strip())
    await interaction.response.send_message(msg)

@notify.command(name="list", description="List active notifications")
async def notify_list(interaction: discord.Interaction):
    await interaction.response.send_message(await list_notifications())


@notify.command(name="gotobk", description="Send a player to Burger King")
async def notify_gotobk(interaction: discord.Interaction, player: str):
    await interaction.response.send_message(await go_to_burger_king(player.lower().strip()))


@notify.command(name="leavebk", description="Send a player home from Burger King")
async def notify_leavebk(interaction: discord.Interaction, player: str):
    await interaction.response.send_message(await leave_burger_king(player.lower().strip()))


@notify.command(name="listbk", description="See who's at Burger King")
async def notify_listbk(interaction: discord.Interaction):
    await interaction.response.send_message(await list_burger_king_patrons())


def save_channel_to_file():
    with open(CH_FILENAME, 'w+') as file:
        json.dump({"updates_channel": updates_channel.id}, file)

def get_channel_id_from_file():
    if(os.path.isfile(CH_FILENAME)):
        with open(CH_FILENAME, 'r') as file:
            ch_dict = json.load(file)
        updates_channel_id = ch_dict["updates_channel"]
        return updates_channel_id
        

@client.event
async def on_ready():
    global updates_channel

    logger.info(f'Logged in as {client.user}')

    if updates_channel is None:
        channel_id = get_channel_id_from_file()
        if channel_id:
            channel = client.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await client.fetch_channel(channel_id)
                except (discord.NotFound, discord.Forbidden):
                    logger.error(f"Couldn't connect to previous channel with id: {channel_id}")
                    channel = None
            if channel:
                updates_channel = channel
                logger.info(f"Connected to channel #{channel.name}")

    if not archipelago_updates.is_running():
        archipelago_updates.start()


# fires off notifications messages for the values in "for_values" to the updates channel.
# If allow_unregistered is False, then mute any notifications that don't ping a specific user.
async def fire_notif_msgs(for_values, allow_unregistered=True):
    for update in for_values:

        msg_content = f"***{update['Finder']}*** found ***\"{update['Item']}\"*** for ***{update['Receiver']}\n({update['Location']})!!!***"

        # check for any matching notifications
        existingNotif = None
        for notification in current_notifications:
            if(
                (notification.itemName == update['Item'].lower() or notification.itemName == "")
                and notification.playerName == update['Receiver'].lower()
            ):
                existingNotif = notification

                # grab a list of every ping
                pinglist = ""
                for i in range(len(notification.usernames)):
                    if notification.itemName != "":
                        await remove_notification(None, notification.itemName, notification.playerName, uname=notification.usernames[i], uid=notification.userIDs[i])

                    if i != 0:
                        pinglist += ", "

                    pinglist += f"<@{notification.userIDs[i]}>"

                msg_content = f"# ARCHIPELAGO UPDATE!\n{pinglist}\n{msg_content}"

                print(f'sending notifcation update:\n{msg_content}\npinging: {notification.usernames!s}')

                await updates_channel.send(msg_content)

                # if an important item has been found, the receiver can become a burger king leaver
                if update['Receiver'] in current_burger_king_patrons:
                    current_burger_king_patrons.remove(update['Receiver'])

                break

        if existingNotif and existingNotif.itemName != "":
            try:
                current_notifications.remove(existingNotif)
            except ValueError as e:
                print(f"existingNotif, {existingNotif} not in list", e)

            save_notifs_to_file()

        elif allow_unregistered:
            # nobody signed up for pings, so give the message normally (if instructed)
            print(f'sending this update:\n{msg_content}\n')
            await updates_channel.send(msg_content)

@tasks.loop(seconds=20.0)
async def archipelago_updates():
    global recorded_actions

    # if an updates channel has not been specified, skip over the routine for now.
    # This allows updates that were added before the channel was specified to stack up
    # and not be missed.
    if not updates_channel:
        return

    # scrape the data from the webpage in the most recent visit. Then, compare it against the data
    # from the last visit to see what was newly added
    updated_actions = get_recent_archipelago_actions()
    if updated_actions is not None:
        newly_added = check_for_new_archipelago_actions(recorded_actions, updated_actions)

        await fire_notif_msgs(newly_added.values())

        recorded_actions = updated_actions

    logger.debug("Performed scraping routine")

@client.event
async def on_message(message):
    global updates_channel

    if client.user.mentioned_in(message):
        if not updates_channel:
            updates_channel = message.channel

            # attempts to fire off any important notifications that may have been missed since last time
            logger.debug("Firing off latent notifs!!")

            await fire_notif_msgs(for_values=recorded_actions.values(), allow_unregistered=False)

        updates_channel = message.channel
        save_channel_to_file()
        await message.channel.send('Archipelago updates will now occur in this channel!')


# Main function initializes .env vars and global variables, then initializes the bot
# with the appropriate intents.
def main():
    global recorded_actions

    try:
        load_dotenv()

        recorded_actions = get_recent_archipelago_actions()

        load_notifs_from_file()
        load_patrons_from_bk()
    except Exception as e:
        print("something went wrong: ", e)
        while(True):
            pass

    client.run(os.environ['BOT_TOKEN'])


if __name__ == "__main__":
    main()


