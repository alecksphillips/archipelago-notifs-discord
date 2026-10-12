import os
from datetime import UTC, datetime

import discord
from discord.ext import tasks
from dotenv import load_dotenv

# custom module imports
from archipelago_site import (
    check_for_new_archipelago_actions,
    get_recent_archipelago_actions,
)
from notifications import (
    current_burger_king_patrons,
    current_notifications,
    load_notifs_from_file,
    load_patrons_from_bk,
    parse_usr_msg,
    remove_notification,
    save_notifs_to_file,
)

# globals
recorded_actions = {}
updates_channel = None

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# fires off notifications messages for the values in "for_values" to the updates channel.
# If allow_unregistered is False, then mute any notifications that don't ping a specific user.
async def fire_notif_msgs(for_values, allow_unregistered=True):
    for update in for_values:

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

                msg_content = f"# ARCHIPELAGO UPDATE!\n{pinglist}\n***{update['Finder']}*** has found ***{update['Item']}*** for ***{update['Receiver']}***!"

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
            msg_content = f"***{update['Finder']}*** found ***\"{update['Item']}\"*** for ***{update['Receiver']}!!!***"
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

    # log the time of the routine

    # Get the current UTC datetime object
    utc_now = datetime.now(UTC)

    # Format the datetime object into a string
    # Example format: "2025-10-31 18:43:00 UTC"
    utc_timestamp_string = utc_now.strftime("%Y-%m-%d %H:%M:%S UTC")

    print(f"[{utc_timestamp_string}] performed scraping routine")

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

    archipelago_updates.start()

@client.event
async def on_message(message):
    global updates_channel

    if message.content.startswith("!") and updates_channel and message.channel == updates_channel:
        await parse_usr_msg(message)

    if client.user.mentioned_in(message):
        if not updates_channel:
            updates_channel = message.channel

            # attempts to fire off any important notifications that may have been missed since last time

            utc_now = datetime.now(UTC)
            utc_timestamp_string = utc_now.strftime("%Y-%m-%d %H:%M:%S UTC")
            print(f"[{utc_timestamp_string}] firing off latent notifs!!")

            await fire_notif_msgs(for_values=recorded_actions.values(), allow_unregistered=False)

        updates_channel = message.channel
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


