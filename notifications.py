# This module stores important data and functions associated with
# the "notifications" feature. This feature allows users to subscribe
# to notifications on specific items and then receive pings when
# said item is obtained by another player.

import json
import os
import shlex
from collections import namedtuple
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

DATA_DIR = Path(os.getenv("DATA_DIR"))

filename = DATA_DIR / "saved_notifs.json"
bkfilename = DATA_DIR / "patron_list.json"
current_notifications = []
current_burger_king_patrons = []

Notification = namedtuple('Notification', ['userIDs', 'usernames', 'itemName', "playerName"])

burger_king_messages = [
    "is waiting to order",
    "is waiting for their food",
    "is filling their drink",
    "is eating a burger",
    "is eating fries",
    "is sipping their drink",
    "is in the bathroom",
    "is sleeping on a table",
    "is sleeping in a booth",
    "is sleeping on the floor",
    "got burger king foot lettuce", # rare
    "got an onion ring in their fries", # rare
    "got a fry in their onion rings", # rare
    "is complaining to the manager", # rare
    "is staring wistfully out the window", # rare
    "is staring wistfully at a rat", # epic
    "is sipping on promethazine (they can't put down the cup)", # epic
    "is looking out the window at somebody coming in\n(doo-doo-doo-doo, doo-do-dooo-doo doo-doo-doo-doo-do-doo-doo)", # epic
    "is checking the clopen sign", # epic
    "thinks this might be a burger king for rats" # epic
]

# p_common = 0.7, p_rare = 0.2, p_epic = 0.1
burger_king_message_probs = [0.07, 0.07, 0.07, 0.07, 0.07, 0.07, 0.07, 0.07, 0.07, 0.07, 0.04, 0.04, 0.04, 0.04, 0.04, 0.02, 0.02, 0.02, 0.02, 0.02]

def load_notifs_from_file():
    current_notifications.clear()

    if(os.path.isfile(filename)):
        with open(filename, 'r') as file:
            for entry in json.load(file):
                current_notifications.append(Notification(*entry))

def load_patrons_from_bk():
    global current_burger_king_patrons
    if(os.path.isfile(bkfilename)):
        with open(bkfilename, 'r') as file:
            current_burger_king_patrons = json.load(file)
    else:
        current_burger_king_patrons = []

def save_notifs_to_file():
    with open(filename, 'w+') as file:
        json.dump(current_notifications, file)

def save_patrons_to_bk():
    with open(bkfilename, 'w+') as file:
        json.dump(current_burger_king_patrons, file)

async def add_notification(user, itemName, playerName, channel):
    userID = user.id
    username = user.name

    existingNotifIndex = -1
    for i, notification in enumerate(current_notifications):
        if (notification.itemName == itemName and notification.playerName == playerName):
            existingNotifIndex = i
            break

    if existingNotifIndex != -1:
        existingNotif = current_notifications[existingNotifIndex]

        if userID in existingNotif.userIDs:
            await channel.send("You are already signed up for this notification!")
            return

        existingNotif.userIDs.append(userID)
        existingNotif.usernames.append(username)

        await channel.send("Notification added!")
    else:
        current_notifications.append(Notification([userID], [username], itemName, playerName))
        await channel.send("Notification added!")

    save_notifs_to_file()

async def remove_notification(user, itemName, playerName, channel=None, uid=-1, uname=""):

    # allow for direct discord.py user object or specify uid/uname manually
    if user:
        userID = user.id
        username = user.name
    else:
        userID = uid
        username = uname

    notifIndex = -1
    for index, notification in enumerate(current_notifications):
        if (notification.itemName == itemName and notification.playerName == playerName):
            notifIndex = index
            break

    if (notifIndex == -1):
        msg = "This notification does not exist!"
        if channel:
            await channel.send(msg)
        else:
            utc_now = datetime.now(UTC)
            utc_timestamp_string = utc_now.strftime("%Y-%m-%d %H:%M:%S UTC")
            print(f"[{utc_timestamp_string}] {msg}")
    else:
        notifObj = current_notifications[notifIndex]

        if userID not in notifObj.userIDs:
            msg = f"Cannot remove: {username} is not signed up for this notification!"
            if channel:
                await channel.send(msg)
            else:
                utc_now = datetime.now(UTC)
                utc_timestamp_string = utc_now.strftime("%Y-%m-%d %H:%M:%S UTC")
                print(f"[{utc_timestamp_string}] {msg}")
            return

        # remove the entire notification object or just remove that user (if they are not the only one subscribed)
        if len(notifObj.usernames) == 1:
            current_notifications.pop(notifIndex)
        else:
            notifObj.userIDs.remove(userID)
            notifObj.usernames.remove(username)

        msg = "Notification removed!"
        if channel:
            await channel.send(msg)
        else:
            utc_now = datetime.now(UTC)
            utc_timestamp_string = utc_now.strftime("%Y-%m-%d %H:%M:%S UTC")
            print(f"[{utc_timestamp_string}] {msg}")
    save_notifs_to_file()

async def list_notifications(channel):
    print("running list command")

    # list all active notifications
    if (len(current_notifications) == 0):
        await channel.send('There are no active notifications!')
    else:
        notifsListStr = "Active notifications:\n```"
        for notification in current_notifications:
            itemName = notification.itemName if notification.itemName != "" else "ANY"
            notifsListStr += f"\n* {itemName} ==> {notification.playerName} (notifies "

            for i in range(len(notification.usernames)):
                if i != 0:
                    notifsListStr += ", "

                notifsListStr += f"{notification.usernames[i]}"
            notifsListStr += ")"
        notifsListStr += "```"
        await channel.send(notifsListStr)

async def go_to_burger_king(playerName, channel):
    if (playerName in current_burger_king_patrons):
        await channel.send(f"{playerName} is already at Burger King!")
    else:
        current_burger_king_patrons.append(playerName)
        await channel.send(f"{playerName} walks to Burger King..." )

    save_patrons_to_bk()

async def leave_burger_king(playerName, channel):
    if (playerName in current_burger_king_patrons):
        current_burger_king_patrons.remove(playerName)
        await channel.send(f"{playerName} walks back home from Burger King")
    else:
        await channel.send(f"{playerName} isn't at Burger King!'" )
    save_patrons_to_bk()

async def list_burger_king_patrons(channel):
    print("running list BK command")

    # list all burger king patrons
    if (len(current_burger_king_patrons) == 0):
        await channel.send(':crab: Burger King is empty! :crab:')
    else:
        bkListStr = "```"
        for patron in current_burger_king_patrons:
            msg = np.random.choice(burger_king_messages, 1, p=burger_king_message_probs)
            bkListStr += f"\n* {patron} {msg[0]} "
        bkListStr += "```"
        await channel.send(bkListStr)

async def parse_usr_msg(message):
    args = shlex.split(message.content[1:])
    argsLen = len(args)
    print(args)

    if (argsLen > 0 and args[0].lower() == "notify"):
        if (argsLen == 1):
            await send_usage_help_msg(message.channel)
            return

        match args[1].lower():
            case "add":
                # create a new notification (if it does not already exist)

                if (argsLen not in [3, 4]):
                    await send_usage_help_msg(message.channel)
                    return

                user = message.author
                playerName = args[2].lower().strip()
                itemName = args[3].lower().strip() if argsLen == 4 else ""

                await add_notification(user,itemName,playerName,message.channel)

            case "remove":
                # remove an existing notification (if a matching one exists)
                if (argsLen not in [3, 4]):
                    await send_usage_help_msg(message.channel)
                    return

                playerName = args[2].lower().strip()
                itemName = args[3].lower().strip() if argsLen == 4 else ""

                await remove_notification(message.author, itemName, playerName, message.channel)

            case "list":
                await list_notifications(message.channel)
            case "gotobk":
                if (argsLen != 3):
                    await send_usage_help_msg(message.channel)
                    return

                playerName = args[2].lower().strip()

                await go_to_burger_king(playerName, message.channel)

            case "leavebk":
                if (argsLen != 3):
                    await send_usage_help_msg(message.channel)
                    return

                playerName = args[2].lower().strip()

                await leave_burger_king(playerName, message.channel)
            case "listbk":
                await list_burger_king_patrons(message.channel)
                
            case _:
                await send_usage_help_msg(message.channel)

async def send_usage_help_msg(channel):
    await channel.send(
        'Unrecognized command. Usage:\n' +
        '!notify add <PlayerName> [ItemName]\n' +
        '!notify remove <PlayerName> [ItemName]\n' +
        '!notify list\n' +
        '!notify gotobk <PlayerName>\n' +
        '!notify leavebk <PlayerName>\n' +
        '!notify listbk'
    )
