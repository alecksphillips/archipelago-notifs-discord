import json
import os
from collections import namedtuple
from pathlib import Path

from loguru import logger
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

async def add_notification(user, itemName, playerName):
    userID = user.id
    username = user.name

    for notification in current_notifications:
        if (notification.itemName == itemName and notification.playerName == playerName):
            if userID in notification.userIDs:
                return "You are already signed up for this notification!"
            notification.userIDs.append(userID)
            notification.usernames.append(username)
            save_notifs_to_file()
            return "Notification added!"

    # new notification
    current_notifications.append(Notification([userID], [username], itemName, playerName))
    save_notifs_to_file()
    return "Notification added!"

async def remove_notification(user, itemName, playerName, uid=-1, uname=""):

    # allow for direct discord.py user object or specify uid/uname manually
    userID, username = (user.id, user.name) if user else (uid, uname)

    notifIndex = None
    for i, notification in enumerate(current_notifications):
        if (notification.itemName == itemName and notification.playerName == playerName):
            notifIndex = i
            break

    if (notifIndex is None):
        msg = "This notification does not exist!"
    else:
        notification = current_notifications[notifIndex]

        if userID not in notification.userIDs:
            msg = f"Cannot remove: {username} is not signed up for this notification!"
            
        # remove the entire notification object or just remove that user (if they are not the only one subscribed)
        if len(notification.usernames) == 1:
            current_notifications.pop(notifIndex)
        else:
            notification.userIDs.remove(userID)
            notification.usernames.remove(username)

        msg = "Notification removed!"
        logger.info(f"{msg}")

    save_notifs_to_file()
    return msg

async def list_notifications():
    logger.debug("running list command")

    # list all active notifications
    if (len(current_notifications) == 0):
        return 'There are no active notifications!'
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
        return notifsListStr

async def go_to_burger_king(playerName, channel):
    msg = ""
    if (playerName in current_burger_king_patrons):
        msg = f"{playerName} is already at Burger King!"
    else:
        current_burger_king_patrons.append(playerName)
        msg = f"{playerName} walks to Burger King..."

    save_patrons_to_bk()
    return msg

async def leave_burger_king(playerName, channel):
    msg = ""
    if (playerName in current_burger_king_patrons):
        current_burger_king_patrons.remove(playerName)
        msg = f"{playerName} walks back home from Burger King"
    else:
        msg = f"{playerName} isn't at Burger King!'"
    save_patrons_to_bk()
    return msg

async def list_burger_king_patrons(channel):
    logger.debug("running list BK command")
    msg = ""
    # list all burger king patrons
    if (len(current_burger_king_patrons) == 0):
        msg = ':crab: Burger King is empty! :crab:'
    else:
        bkListStr = "```"
        for patron in current_burger_king_patrons:
            msg = np.random.choice(burger_king_messages, 1, p=burger_king_message_probs)
            bkListStr += f"\n* {patron} {msg[0]} "
        bkListStr += "```"
        msg = bkListStr
    return msg
