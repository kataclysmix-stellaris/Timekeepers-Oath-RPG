import json
import random
import os
import copy

''' ----------------------------
WORLD DATA
----------------------------'''

BASE_ROOMS = {
    "forest": {
        "description": "You are in a dark forest. Paths lead north and east.",
        "options": {"north": "town", "east": "river"}
    },
    "town": {
        "description": "An abandoned town square. A broken clock tower looms overhead.",
        "options": {"north": "dark_alley", "south": "forest", "east": "library"}
    },
    "dark_alley": {
        "description": "The alley feels wrong. Shadows cling to the walls.",
        "boss": {
            "name": "Nyctophobia",
            "hp": 25,
            "attack": 6,
            "fear": "darkness",
            "watch_piece": "Minute Hand Fragment"
        },
        "options": {"south": "town"}
    },
    "river": {
        "description": "A quiet river. You see something shining nearby.",
        "item": "Broken Clock",
        "options": {"west": "forest"}
    },
    "library": {
        "description": "Dusty shelves. Books whisper when you walk past.",
        "boss": {
            "name": "Chronophobia",
            "hp": 30,
            "attack": 5,
            "fear": "time",
            "watch_piece": "Hour Gear"
        },
        "options": {"west": "town", "north": "basement"}
    },
    "basement": {
        "description": "It smells like damp stone. Something breathes below.",
        "boss": {
            "name": "Claustrophobia",
            "hp": 35,
            "attack": 7,
            "fear": "tight spaces",
            "watch_piece": "Balance Spring"
        },
        "options": {"south": "library"}
    }
}

# ----------------------------
# PLAYER SETUP
# ----------------------------

def new_player():
    return {
        "name": input("Enter your character's name: "),
        "hp": 30,
        "max_hp": 30,
        "attack": 6,
        "inventory": []
    }

# ----------------------------
# GAME STATE
# ----------------------------

game_state = {
    "hour": 0,
    "resets": 0,
    "base_loop_length": 24,
    "current_loop_length": 24,
    "watch_pieces": [],
    "last_loop_cache": {}
}

def advance_time(state, player, room):
    state["hour"] += 1

    if state["hour"] >= state["current_loop_length"]:
        collapse_loop(state, player, room)
        return True

    return False

def between_space(player, state):
    print("\nYou stand in a place without walls.")
    print("A woman sits beside a warm pyre growing in a hearth.")
    print("She looks at you the way someone looks at a child who fell too hard.\n")

    player["hp"] = player["max_hp"]

    while True:
        print('"You have returned, Timekeeper. How goes the journey?"')
        print("1. I need to be stronger.")
        print("2. I need to survive longer.")
        print("3. I need more time.")
        print("4. I need to leave.")

        choice = input("> ")

        if choice == "1":
            player["attack"] += 3
            print('"Then I will steady your hands."')
            print('"Do not worry. The shadows are only the fears of others."')
            break
        elif choice == "2":
            player["max_hp"] += 10
            print('"Then I will hold you together a little better."')
            print('"Exercise more caution, the body needs time to heal."')
            break
        elif choice == "3":
            state["current_loop_length"] += 2
            print('"I can delay the collapse… but only slightly."')
            print('"Be careful this time, please."')
            break
        elif choice == "4":
            print('"I will be waiting for you to come back."')
            break
        else:
            print('"That is not what you truly need."')

def collapse_loop(state, player, room):
    print("\nReality seems to unravel.")
    print("The loop resets once more.\n")
    
    state["resets"] += 1
    state["current_loop_length"] = int(state["base_loop_length"] * 0.85)
    
    state["last_loop_cache"] = {
        "room": room,
        "inventory": player["inventory"].copy(),
        "watch_pieces": state["watch_pieces"].copy()
    }

    between_space(player, state)

    player["inventory"] = []
    state["watch_pieces"] = []
    state["hour"] = 0
    
    print("You wake up in town with one heck of a headache and your stuff gone.")

    return "town"

# ----------------------------
# SAVE / LOAD
# ----------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_PATH = os.path.join(BASE_DIR, "savegame.json")

def save_game(player, current_room, state, loop_rooms):
    try:
        with open(SAVE_PATH, "w") as f:
            json.dump({
                "player": player,
                "current_room": current_room,
                "state": state,
                "rooms": loop_rooms
            }, f)
        print("Game saved.\n")

    except PermissionError:
        print("Save failed: Permission denied.")

def load_game():
    if os.path.exists("savegame.json"):
        with open("savegame.json", "r") as f:
            data = json.load(f)
        print("Game loaded.\n")
        return data["player"], data["current_room"], data["state"], data["rooms"]
    return None, None, None, None

# ----------------------------
# COMBAT SYSTEM
# ----------------------------

def combat(player, boss, state, room):
    print(f"\nYou face {boss['name']} — embodiment of {boss['fear']}.\n")

    while boss["hp"] > 0 and player["hp"] > 0:
        print(f"Time: {state['hour']}:00")
        print(f"Timekeeper HP: {player['hp']}")
        print(f"{boss['name']} HP: {boss['hp']}")
        action = input("[A]ttack or [R]ewind? ").lower()

        if action == "a":
            damage = random.randint(1, player["attack"])
            boss["hp"] -= damage
            print(f"You deal {damage} damage!")

        elif action == "r":
            if "Broken Clock" in player["inventory"]:
                heal = 10
                player["hp"] = min(player["hp"] + heal, player["max_hp"])
                state["hour"] -= 2
                print("You used the Broken Clock! Time went back an hour!")
            else:
                print("You don't have anything to rewind!")

        else:
            print("You freeze up in fear.")
            continue

        # Night buff for darkness fear
        if boss["fear"] == "darkness" and (state["hour"] >= 20 or state["hour"] < 6):
            enemy_damage = random.randint(4, boss["attack"] + 3)
        else:
            enemy_damage = random.randint(1, boss["attack"])

        if boss["hp"] > 0:
            player["hp"] -= enemy_damage
            print(f"{boss['name']} hits you for {enemy_damage}!")

        advance_time(state, player, room)
        print()

    if player["hp"] <= 0:
        print("You fall as the clock tower tolls...")
        return False
    else:
        print(f"You defeated {boss['name']}!")
        del room["boss"]
        state["watch_pieces"].append(boss["watch_piece"])
        print("You obtained:", boss["watch_piece"])
        return True

# ----------------------------
# GAME LOOP
# ----------------------------

def game():
    print("1) New Game")
    print("2) Load Game")
    choice = input("> ")

    if choice == "2":
        player, current_room, state, rooms = load_game()
        if not player:
            player = new_player()
        elif not state:
            state = game_state
        elif not current_room:
            current_room = "river"
        elif not rooms:
            rooms = copy.deepcopy(BASE_ROOMS)
    else:
        player = new_player()
        state = game_state
        current_room = "river"
        rooms = copy.deepcopy(BASE_ROOMS)

    while True:
        room = rooms[current_room]
        print(room["description"])
        print(f"Current Time: {state['hour']}:00")
        print("Watch Pieces:", state["watch_pieces"])

        if "item" in room:
            if room["item"] == "Broken Clock" and state["last_loop_cache"]:
                print("You find a broken clock.")
                print("It feels familiar.")

                recovered = state["last_loop_cache"]

                player["inventory"].extend(recovered["inventory"])
                state["watch_pieces"].extend(recovered["watch_pieces"])

                print("You reclaim what was lost.")

                state["last_loop_cache"] = None

            else:
                print(f"You found a {room['item']}!")
                player["inventory"].append(room["item"])

            del room["item"]

        if "boss" in room:
            boss = room["boss"].copy()
            survived = combat(player, boss, state, current_room)
            if not survived:
                current_room = collapse_loop(state, player, current_room)
        
        print("Options:", ", ".join(room["options"].keys()))
        print("[S]ave [I]nspect [Q]uit")

        command = input("> ").lower()

        if command == "s":
            save_game(player, current_room, state, rooms)
        elif command == "q":
            print("Goodbye.")
            break
        elif command == "i":
            print(room["description"])
            print(f"Current Time: {state['hour']}:00")
            print("Watch Pieces:", state["watch_pieces"])
        elif command in room["options"]:
            current_room = room["options"][command]
            advance_time(state, player, room)
        else:
            print("You can't do that right now.")

# ----------------------------

if __name__ == "__main__":
    game()