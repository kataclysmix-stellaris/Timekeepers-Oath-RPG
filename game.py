import json
import random
import os
import copy
import time
import re
import sys

''' ----------------------------
WORLD DATA
----------------------------'''

BASE_ROOMS = {
    "forest": {
        "description": "You are in a dark forest. Paths lead north and east.",
        "options": {"north": "town", "east": "river", "west": "orchard"}
    },
    "town": {
        "description": "An abandoned town square. A broken clock tower looms overhead.",
        "options": {"north": "dark_alley", "south": "forest", "east": "library", "west": "shop"}
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
        "options": {"west": "forest", "south": "old_dock"}
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
    },
    "shop": {
        "description": "The town's abandoned general store is frozen in time. Dusty shelves line the walls, and Anthrophobia waits behind the counter.",
        "shopkeeper": "Anthrophobia",
        "options": {"east": "town", "north": "workshop"}
    },
    "orchard": {
        "description": "An overgrown orchard crowds the edge of the forest. Pale fruit hangs from the branches, and webs stretch between the trees.",
        "encounter": {"name": "Arachnophobia", "fear": "spiders", "hp": 10, "attack": 3, "wisps": 1},
        "options": {"east": "forest"}
    },
    "old_dock": {
        "description": "Rotting boards stretch over the river. Something churns beneath the dark water, just out of sight.",
        "encounter": {"name": "Aquaphobia", "fear": "deep water", "hp": 12, "attack": 4, "wisps": 2},
        "options": {"north": "river"}
    },
    "workshop": {
        "description": "A narrow workshop sits behind the shop. Dust and grime coat the benches as a pale shape stirs in the corners.",
        "encounter": {"name": "Mysophobia", "fear": "germs and contamination", "hp": 9, "attack": 3, "wisps": 1},
        "options": {"south": "shop"}
    }
}

REQUIRED_WATCH_PIECES = {
    "Minute Hand Fragment",
    "Hour Gear",
    "Balance Spring"
}

'''----------------------------
PLAYER SETUP
----------------------------'''

BLOCKED_NAME_WORDS = {
    "asshole", "bastard", "bitch", "bullshit", "cunt", "damn", "dick",
    "fag", "faggot", "fuck", "motherfucker", "nigger", "nigga", "piss",
    "shit", "slut", "whore"
}


def is_appropriate_name(name):
    words = re.findall(r"[a-z0-9]+", name.casefold())
    return not any(word in BLOCKED_NAME_WORDS for word in words)


def new_player():
    while True:
        name = input("Enter your character's name: ").strip()
        if not name:
            print("Please enter a name.")
        elif not is_appropriate_name(name):
            print("That's not a proper name for someone. Try again.")
        else:
            break
    return {
        "name": name,
        "hp": 30,
        "max_hp": 30,
        "attack": 6,
        "attack_bonus": 0,
        "inventory": [],
        "wisps": 0
    }

'''----------------------------
GAME STATE
----------------------------'''

game_state = {
    "hour": 0,
    "resets": 0,
    "base_loop_length": 24,
    "current_loop_length": 24,
    "watch_pieces": [],
    "last_loop_cache": None,
    "instability": 0
}

def advance_time(state, player, room, rooms=None):
    state["hour"] += 1

    if state["hour"] >= state["current_loop_length"]:
        return collapse_loop(state, player, room, rooms)

    return None

def get_intensity(state):
    return min(0.2 + state["instability"] * 0.15, 0.9)

def get_break_chance(state):
    return min(0.1 + state["instability"] * 0.1, 0.8)

def break_text(text, break_chance=0.3):
    result = ""

    for word in text.split():
        if random.random() < break_chance and len(word) > 2:
            split_point = random.randint(1, len(word) - 1)

            part1 = word[:split_point]
            part2 = word[split_point:]

            # Add a stutter or break
            broken = f"{part1}— {part1}{part2}"
            result += broken + " "
        else:
            result += word + " "

    return result.strip()

def panic_text(text, intensity=0.5):
    result = ""

    for char in text:
        if char.isalpha() and random.random() < intensity:
            result += char.upper()
        else:
            result += char.lower()

    return result

def panic_words(text, intensity=0.5):
    words = text.split()

    result = []
    for word in words:
        if random.random() < intensity:
            result.append(word.upper())
        else:
            result.append(word.lower())

    return " ".join(result)

def panic_break_text(text, state):
    attempts = get_intensity(state)

    intensity = min(0.2 + attempts * 0.2, 0.9)
    break_chance = min(0.2 + attempts * 0.2, 0.8)

    broken = break_text(text, break_chance)
    return panic_text(broken, intensity)

def cut_text(text, cut_chance=0.2):
    if random.random() < cut_chance:
        cut_point = random.randint(1, len(text))
        return text[:cut_point] + "—"
    return text

def full_panic_line(text, state):
    intensity = get_intensity(state)
    break_chance = get_break_chance(state)

    text = break_text(text, break_chance)
    text = cut_text(text, 0.2)
    text = panic_text(text, intensity)

    return text

def alone_pause(state):
    print(panic_text("I'm alone.", get_intensity(state)))
    
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
            clear_screen()
            player["attack"] += 3
            print('"Then I will steady your hands."')
            print('"Do not worry. The shadows are only the fears of others."')
            break
        elif choice == "2":
            clear_screen()
            player["max_hp"] += 10
            state["instability"] -= 2
            print('"Then I will hold you together a little better."')
            print('"Exercise more caution, the body needs time to heal."')
            break
        elif choice == "3":
            clear_screen()
            state["current_loop_length"] += 2
            state["instability"] -= 10
            print('"I can delay the collapse… but only slightly."')
            print('"Be careful this time, please."')
            break
        elif choice == "4":
            clear_screen()
            print('"I will be waiting for you to come back."')
            break
        else:
            clear_screen()
            print('"That is not what you truly need."')
            
# Error Handling
def load_file(file_name, state="OK", glitch=False):
    print(f"\nLoading '{file_name}'...")
    time.sleep(0.2)

    # Optional glitch behavior
    if glitch:
        glitch_text(file_name)
        return False

    print(f"Status: {state}")
    time.sleep(0.2)
    return True

def file_error(file_name, error_type="not_found"):
    time.sleep(0.2)

    print("\nTraceback (most recent call last):")
    time.sleep(0.2)

    print(f'  File "runtime_loader.py", line 86')
    time.sleep(0.2)

    if error_type == "not_found":
        print(f"FileNotFoundError: '{file_name}'")

    elif error_type == "corrupt":
        print(f"Error: '{file_name}' is corrupted")

    elif error_type == "conflict":
        print(f"Error: duplicate entity detected for '{file_name}'")

    time.sleep(0.2)

def glitch_text(text):
    corrupted = ""

    for char in text:
        if random.random() < 0.2:
            corrupted += random.choice(["?", "#", "%"])
        else:
            corrupted += char

    print(f"Loading '{corrupted}'...")
    time.sleep(0.2)

    print("Status: ???")
    time.sleep(0.2)

def collapse_loop(state, player, room, rooms=None):
    clear_screen()
    print("Reality seems to unravel.")
    time.sleep(0.2)
    print("The loop resets once more.")
    time.sleep(0.2)
    clear_screen()
    
    state["resets"] += 1
    state["instability"] += 2
    state["current_loop_length"] = max(1, int(state["base_loop_length"] * 0.85))
    player["attack_bonus"] = 0
    
    state["last_loop_cache"] = {
        "room": next((name for name, data in rooms.items() if data is room), "town") if rooms else "town",
        "inventory": player["inventory"].copy(),
        "watch_pieces": state["watch_pieces"].copy()
    }

    for room_name, base_room in BASE_ROOMS.items():
        if "boss" in base_room and base_room["boss"]["watch_piece"] in state["watch_pieces"]:
            if rooms and room_name in rooms:
                rooms[room_name].pop("boss", None)

    if not REQUIRED_WATCH_PIECES.issubset(state["watch_pieces"]):
        between_space(player, state)

        player["inventory"] = []
        state["hour"] = 0
        return "town"
    else:
        autophobia(player, state)
        return "town"

"""----------------------------
SAVE / LOAD
----------------------------"""

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_PATH = os.path.join(BASE_DIR, "savegame.json")

def save_game(player, current_room, state, loop_rooms):
    try:
        with open(SAVE_PATH, "w", encoding="utf-8") as f:
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
    if not os.path.exists(SAVE_PATH):
        print("No save file found. Starting a new game.\n")
        return None
    try:
        with open(SAVE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        player, state = data["player"], data["state"]
        current_room, saved_rooms = data["current_room"], data["rooms"]
        if not isinstance(saved_rooms, dict):
            raise ValueError("Saved room map is invalid")
        rooms = copy.deepcopy(BASE_ROOMS)
        for room_name, saved_room in saved_rooms.items():
            if room_name not in rooms or not isinstance(saved_room, dict):
                continue
            for key, value in saved_room.items():
                if key == "options" and isinstance(value, dict):
                    rooms[room_name]["options"].update(value)
                else:
                    rooms[room_name][key] = value
            for transient_key in ("boss", "item"):
                if transient_key not in saved_room:
                    rooms[room_name].pop(transient_key, None)
        current_room = data["current_room"]
        if not isinstance(player, dict) or not isinstance(state, dict) or current_room not in rooms:
            raise ValueError("Save data is incomplete")
        for key, value in copy.deepcopy(game_state).items():
            state.setdefault(key, value)
        player.setdefault("inventory", [])
        player.setdefault("wisps", 0)
        player.setdefault("max_hp", 30)
        player.setdefault("hp", player["max_hp"])
        player.setdefault("attack", 6)
        player.setdefault("attack_bonus", 0)
        player.setdefault("name", "Chronos")
        if (not isinstance(player["name"], str) or not player["name"].strip()
                or not is_appropriate_name(player["name"])):
            if isinstance(player["name"], str) and player["name"].strip() and not is_appropriate_name(player["name"]):
                print("That's not my name. I don't want to be called that. I'll choose a new name instead.")
            player["name"] = "Chronos"
        print("Game loaded.\n")
        return player, current_room, state, rooms
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        print(f"Could not load save ({error}). Starting a new game.\n")
        return None
        
def clear_screen():
    if not sys.stdout.isatty():
        print("\n" * 2, end="")
        return

    # ANSI clear-screen and move-cursor-to-home sequences are supported by
    # Windows Terminal, modern PowerShell, and common Unix terminals.
    print("\033[2J\033[H", end="", flush=True)

'''----------------------------
COMBAT SYSTEM
----------------------------'''

def combat(player, boss, state, room, rooms):
    print(f"\nYou face {boss['name']} — embodiment of {boss['fear']}.\n")

    while boss["hp"] > 0 and player["hp"] > 0:
        print(f"Time: {state['hour']}:00(Loop {state['resets']})")
        print(f"Timekeeper HP: {player['hp']} out of {player['max_hp']}")
        print(f"{boss['name']} HP: {boss['hp']}")
        action = input("[A]ttack, [R]ewind, [P]otion, or [I]nventory? ").strip().lower()

        if action == "a":
            damage = random.randint(1, player["attack"] + player.get("attack_bonus", 0))
            boss["hp"] -= damage
            print(f"You deal {damage} damage!")
            if boss["hp"] <= 0:
                print(f"You defeated {boss['name']}!")
                state["watch_pieces"].append(boss["watch_piece"])
                print("You obtained:", boss["watch_piece"])
                room.pop("boss", None)
                return "victory"

        elif action == "i":
            print("Inventory:", ", ".join(player["inventory"]) or "empty")
            continue
        elif action == "p":
            if not use_healing_tonic(player):
                continue
        elif action == "r":
            if "Broken Clock" in player["inventory"]:
                heal = 10
                player["hp"] = min(player["hp"] + heal, player["max_hp"])
                rewind = 1 + len(state["watch_pieces"])
                state["hour"] = max(0, state["hour"] - rewind)
                print(f"You used the Runtime Clock! Time went back by {rewind} hours!")
            else:
                print("You don't have anything to rewind!")

        else:
            print("You freeze up in fear.")
            continue

        #Night buff for darkness fear
        if boss["fear"] == "darkness" and (state["hour"] >= 20 or state["hour"] < 6):
            enemy_damage = random.randint(4, boss["attack"] + 3)
        else:
            enemy_damage = random.randint(1, boss["attack"])

        if boss["hp"] > 0:
            player["hp"] = max(0, player["hp"] - enemy_damage)
            print(f"{boss['name']} hits you for {enemy_damage}!")

        if player["hp"] <= 0:
            print("You fall as the clock tower tolls...")
            collapse_loop(state, player, room, rooms)
            return "reset"

        if advance_time(state, player, room, rooms) is not None:
            return "reset"
        print()

    return "reset"


def minor_combat(player, enemy_data, state, rooms):
    enemy = enemy_data.copy()
    print(f"\nA Wisp of {enemy['name']} gathers in your path, embodying the fear of {enemy['fear']}.")

    while enemy["hp"] > 0 and player["hp"] > 0:
        print(f"Time: {state['hour']}:00 (Loop {state['resets']})")
        print(f"Timekeeper HP: {player['hp']} out of {player['max_hp']}")
        print(f"Wisps: {player.get('wisps', 0)}")
        print(f"{enemy['name']} HP: {enemy['hp']}")
        action = input("[A]ttack, [G]uard, or [P]otion? ").strip().lower()
        if action not in {"a", "g", "p"}:
            print("Choose attack, guard, or potion.")
            continue

        if action == "a":
            damage = random.randint(1, player["attack"] + player.get("attack_bonus", 0))
            enemy["hp"] -= damage
            print(f"You deal {damage} damage!")
            if enemy["hp"] <= 0:
                reward = enemy.get("wisps", 1)
                player["wisps"] = player.get("wisps", 0) + reward
                print(f"You dispersed the {enemy['name']} and gathered {reward} Wisps.")
                return "victory"
        elif action == "p":
            if not use_healing_tonic(player):
                continue

        damage = random.randint(1, enemy["attack"])
        if action == "g":
            damage = max(0, damage - 3)
            print("You brace for the attack.")
        player["hp"] = max(0, player["hp"] - damage)
        print(f"{enemy['name']} hits you for {damage}!")

        if player["hp"] <= 0:
            print("You fall as the clock tower tolls...")
            collapse_loop(state, player, None, rooms)
            return "reset"
        if advance_time(state, player, None, rooms) is not None:
            return "reset"

    return "reset"


def use_healing_tonic(player):
    if "Healing Tonic" not in player["inventory"]:
        print("You don't have a Healing Tonic.")
        return False
    if player["hp"] >= player["max_hp"]:
        print("You're already at full HP.")
        return False
    player["inventory"].remove("Healing Tonic")
    player["hp"] = min(player["max_hp"], player["hp"] + 12)
    print("You drink a Healing Tonic and recover 12 HP.")
    return True


def anthrophobia_shop(player):
    while True:
        print(f"\nAnthrophobia: \"Wisps carry a little courage. Would you like to trade? You have {player.get('wisps', 0)}.\"")
        print("1) Courage charm — 4 Wisps: +2 attack until the next loop reset")
        print("2) Healing Tonic — 2 Wisps: restore up to 12 HP once in combat")
        print("0) Leave the counter")
        choice = input("> ").strip()

        if choice == "0":
            return
        if choice == "1":
            if player.get("wisps", 0) < 4:
                print("You don't have enough Wisps.")
                continue
            player["wisps"] -= 4
            player["attack_bonus"] = player.get("attack_bonus", 0) + 2
            print("Anthrophobia ties a small charm around your wrist. Your attack is stronger until the loop resets.")
        elif choice == "2":
            if player.get("wisps", 0) < 2:
                print("You don't have enough Wisps.")
                continue
            player["wisps"] -= 2
            player["inventory"].append("Healing Tonic")
            print("Anthrophobia places a Healing Tonic in your hands.")
        else:
            print("Anthrophobia waits patiently while you decide.")

def autophobia(player, state):
    print("...you...no, I find myself in the empty space again.")
    clear_screen()
    time.sleep(0.2)
    print("...but Creator's not there.")
    clear_screen()
    alone_pause(state)
    clear_screen()
    print("...")
    time.sleep(0.2)
    if state["resets"] >= 10:
        clear_screen()
        print("Why do you keep having me go to her?")
        time.sleep(0.2)
    clear_screen()
    print("I don't understand...")
    time.sleep(0.2)
    clear_screen()
    print(f"'What's the matter, {player['name']}?'")
    time.sleep(0.2)
    print("The figure looks just like me, but twisted by fear and despair.")
    time.sleep(0.2)
    self_fight(player, state)
    
def self_fight(player, state):

    shadow = {
        "name": "Monophobia",
    }
    accept_attempts = 0
    threshold = 5
    acceptance = False
    trust_break = False
    while player["hp"] > 0:
        print(f"Time: ??:?? (Dark Hour; Loop {(state['resets'] - 1)})")
        print(f"Timekeeper HP: {player['hp']} out of {player['max_hp']}")
        print(f"{shadow['name']} HP: {player['max_hp']}")
        action = input(f"[A]ttack or [C]onfront? ").lower()

        if action == "a":
            damage = random.randint(1, player["attack"])
            player["hp"] = max(0, player["hp"] - damage)
            print(f"I deal {damage} damage! But it feels like I'm hurting myself.")
            state["instability"] += damage // 2
            if accept_attempts > 0:
                accept_attempts = 0 # reset acceptance attempts if Player attacks
                threshold += 1 # increase threshold for acceptance after each attack
                if threshold >= 16:
                    threshold = 16 # cap threshold to prevent it from becoming impossible
                if acceptance:
                    time.sleep(0.2)
                    print("'So that was a lie, then. You don't want to accept me.'")
                    acceptance = False
                    trust_break = True
                    time.sleep(0.2)
                    clear_screen()
                elif not trust_break:
                    time.sleep(0.2)
                    print("'What are you doing?'")
                    time.sleep(0.2)
                    clear_screen()
                elif trust_break:
                    time.sleep(0.2)
                    print("I expected the shadow to be upset, but it just looks...worried for some reason.")
                    time.sleep(0.2)
                    print("'...'")
                    time.sleep(0.2)
                    clear_screen()
            continue
        elif action == "c":
            clear_screen()
            print("I take a deep breath and try to accept my fears.")
            player["hp"] = min(player["hp"] + 5, player["max_hp"])
            state["instability"] = max(0, state["instability"] - 8)
            accept_attempts += 1
            if acceptance:
                time.sleep(0.2)
                print("I hold out my hand to the shadow, and it hesitantly takes it.")
                time.sleep(0.2)
                print("It becomes a part of me. I feel whole for the first time.")
                break
            if accept_attempts >= threshold and not acceptance:
                time.sleep(0.2)
                print("The shadow looks at you with a mix of surprise and relief.")
                time.sleep(0.2)
                print("'You... you actually want to accept me?'")
                acceptance = True
            elif trust_break and accept_attempts < threshold:
                print("'You said you wanted to accept me, but you keep hurting yourself.'")
                time.sleep(0.2)
                print("'I don't know if I can trust you.'")
                trust_break = False
            elif accept_attempts < threshold:
                if accept_attempts == 1:
                    time.sleep(0.2)
                    print("I feel a slight improvement in my mental state.")
                    time.sleep(0.2)
                    print("'That's a start, I guess.'")
                if accept_attempts == 2:
                    time.sleep(0.2)
                    print("I feel more at peace, but the shadow looks uncertain.")
                    time.sleep(0.2)
                    print("'...are you sure about this?'")
                if accept_attempts == 3:
                    time.sleep(0.2)
                    print("I feel a significant improvement in my mental state.")
                    time.sleep(0.2)
                    print("'Why are you doing this to yourself?'")
                if accept_attempts == 4:
                    time.sleep(0.2)
                    print("I feel a profound improvement in my mental state.")
                    time.sleep(0.2)
                    print("'...what's wrong with you?'")
                if accept_attempts >= 5:
                    if accept_attempts == 5:
                        time.sleep(0.2)
                        print("The shadow seems to shrink and weaken.")
                        time.sleep(0.2)
                        print("'I...I don't understand. Why aren't you afraid of me?'")
                    if accept_attempts == 6:
                        time.sleep(0.2)
                        print("The shadow looks genuinely confused and a little scared.")
                        time.sleep(0.2)
                        print("'...you don't want to fight me? You want to accept me?'")
                    if accept_attempts == 7:
                        time.sleep(0.2)
                        print("The shadow seems to be on the verge of breaking down.")
                        time.sleep(0.2)
                        print("'I don't know how to deal with this.'")
                    if accept_attempts >= 8:
                        time.sleep(0.2)
                        print("The shadow looks like it's about to collapse.")
                        time.sleep(0.2)
                        if accept_attempts == 10:
                            print("'...I don't want to be alone anymore.'")
                        elif accept_attempts == 12:
                            print("'I just want to be accepted.'")
                        elif accept_attempts == 14:
                            print("'Please...just accept me.'")
                        else:
                            print("'...'")
                time.sleep(0.2)
        elif action == "r":
            clear_screen()
            print("The clock doesn't work here. No matter how much I want to go back, I can't.")
            time.sleep(0.2)
            if accept_attempts == 0:
                print("'Time doesn't flow the same way here. Nice try, though.'")
            elif accept_attempts < threshold:
                print("'You keep trying to heal yourself by rewinding time, but you have to face me eventually.'")
                threshold += 1 # increase threshold for acceptance after each rewind attempt
            elif accept_attempts == threshold:
                print("'I thought maybe you'd give up and accept me by now.'")
                trust_break = True
                acceptance = False
                threshold += 1
                accept_attempts = 0
            continue
        else:
            print("I hesitate, paralyzed by self-doubt.")
            time.sleep(0.2)
            continue
        
        time.sleep(0.2)
        clear_screen()
        if player["hp"] <= 0:
            creator_encouragement(player, state)
    
    if acceptance:
        time.sleep(0.2)
        clear_screen()
        ending(player, state)
        
def creator_encouragement(player, state):
    file_error("Timekeeper.chr", "conflict")
    time.sleep(0.2)
    clear_screen()
    file_error("Creator.chr", "not_found")
    time.sleep(0.2)
    clear_screen()
    file_error("savegame.json", "corrupt")
    time.sleep(0.2)
    clear_screen()
    print('\n"Try again, Timekeeper."')
    time.sleep(0.2)
    print('"...but be a little nicer to yourself this time."')
    time.sleep(0.2)
    print('"I know you can do it."')
    time.sleep(0.2)
    print('"They\'re just as scared of you as you are of them."')
    time.sleep(0.2)
    print('"Baby steps, okay?"')
    player["hp"] = player["max_hp"]
    self_fight(player, state)
    
def ending(player, state):
    print("I wake up in a cozy house, sunlight streaming through the windows.")
    time.sleep(0.2)
    clear_screen()
    print("Creator is there, smiling warmly as I sit up. The clock on the wall ticks softly, but it doesn't feel ominous anymore.")
    time.sleep(0.2)
    clear_screen()
    print(f'"Welcome back, {player["name"]}. And Mono, too, I suppose."')
    time.sleep(0.2)
    clear_screen()
    print('I look at the wall. A shadow hangs out there, attached to both the wall and my body, but it looks more like a mischievous figure than a threat.')
    time.sleep(0.2)
    print('"You both gave me quite a scare, but I\'m glad you\'re here."')
    time.sleep(0.2)
    print(f'"I quite like your new name, by the way. {player["name"]}. It suits you."')
    time.sleep(0.2)
    print('"I hope you\'ll stay with me for a while. But if you go to explore again, just remember that I\'ll be here when you get back."')
    time.sleep(0.2)
    clear_screen()
    print("I go to the window and look out at the world.")
    time.sleep(0.2)
    print("It looks...well, complete.")
    time.sleep(0.2)
    print("With people walking around, birds flying, and the sun shining.")
    time.sleep(0.2)
    print("It feels like a place I can belong.")
    time.sleep(0.2)
    print("I turn back to Creator, who is still smiling at me.")
    time.sleep(0.2)
    print("I feel a sense of excitement wash over me.")
    time.sleep(0.2)
    clear_screen()
    print('"Well, what are you waiting for? I made this world for you. Go out and enjoy it!"')
    time.sleep(0.2)
    clear_screen()
    print("I step outside.")
    time.sleep(0.2)
    print("The world is bright and full of life.")
    time.sleep(0.2)
    print("I feel like I can finally breathe.")
    time.sleep(0.2)
    print("Monophobia is there too, but it seems content to just follow me around, no longer a source of fear.")
    clear_screen()
    print("I walk down the street, taking in the sights and sounds of the world.")
    time.sleep(0.2)
    print("I see people laughing, talking, and going about their lives.")
    time.sleep(0.2)
    print("And I see a young girl sitting on a bench, looking lost.")
    time.sleep(0.2)
    clear_screen()
    print("I remember being lost, too. I walk over to her and sit down.")
    time.sleep(0.2)
    clear_screen()
    print('"Hey there, kiddo. You look like you could use a friend."')
    time.sleep(0.2)
    clear_screen()
    print("The girl looks up at me. She looks scared, but also hopeful.")
    time.sleep(0.2)
    print("Her own shadow curls around her feet, like a protective pet.")
    time.sleep(0.2)
    print("It reminds me of Monophobia, but it seems to be comforting her rather than threatening her.")
    time.sleep(0.2)
    print("I reach out and take her hand, offering her a smile.")
    time.sleep(0.2)
    clear_screen()
    print('"It\'s okay. I know how you feel. But you\'re not alone anymore."')
    time.sleep(0.2)
    clear_screen()
    print("She hesitates, but decides to trust me.")
    time.sleep(0.2)
    print("I decide to take her under my wing, just like Creator did for me.")
    time.sleep(0.2)
    clear_screen()
    print("Together, we explore the world, making new friends and having adventures.")
    time.sleep(0.2)
    print("Monophobia tags along, but it seems to be more of a companion than a source of fear now.")
    time.sleep(0.2)
    clear_screen()
    print("...I guess I can say that I have a happy ending after all.")
    time.sleep(0.2)
    print("Thanks...whoever you are, for helping me get here.")
    return

'''----------------------------
GAME LOOP
----------------------------'''

def game():
    print("\nTHE TIMEKEEPER'S OATH")
    print("A terminal story about fear, time, and making peace with yourself.\n")
    print("1) New Game")
    print("2) Load Game")
    print("3) Quit")
    choice = input("> ").strip()

    if choice == "2":
        loaded = load_game()
        if loaded:
            player, current_room, state, rooms = loaded
        else:
            player = new_player()
            state = copy.deepcopy(game_state)
            current_room = "town"
            rooms = copy.deepcopy(BASE_ROOMS)
    elif choice == "3":
        print("Goodbye, Timekeeper.")
        return
    else:
        player = new_player()
        state = copy.deepcopy(game_state)
        current_room = "town"
        rooms = copy.deepcopy(BASE_ROOMS)

    while True:
        clear_screen()
        room = rooms[current_room]
        print(room["description"])
        print(f"Current Time: {state['hour']}:00 (Loop {state['resets']})")
        print("Watch Pieces:", ", ".join(state["watch_pieces"]) or "none")
        print(f"Wisps: {player.get('wisps', 0)}")
        print("Inventory:", ", ".join(player["inventory"]) or "empty")
        
        if state["last_loop_cache"]:
            drop_room = state["last_loop_cache"]["room"]
            rooms.setdefault(drop_room, copy.deepcopy(BASE_ROOMS[drop_room]))["item"] = "Broken Clock"

        if "item" in room:
            if room["item"] == "Broken Clock" and state["last_loop_cache"]:
                print("You find a broken clock.")
                print("It feels familiar.")
                recovered = state["last_loop_cache"]
                player["inventory"].extend(item for item in recovered["inventory"] if item not in player["inventory"])
                state["watch_pieces"] = list(dict.fromkeys(state["watch_pieces"] + recovered["watch_pieces"]))
                print("You reclaim what was lost.")
                state["last_loop_cache"] = None

            else:
                print(f"You found a {room['item']}!")
                if room["item"] not in player["inventory"]:
                    player["inventory"].append(room["item"])

            del room["item"]

        if "boss" in room:
            boss = room["boss"].copy()
            result = combat(player, boss, state, room, rooms)
            if result == "reset":
                current_room = "town"
                continue

        if "shopkeeper" in room:
            print(f"{room['shopkeeper']} watches you from behind the counter.")
            print('"Welcome. Take your time looking around. I am not going anywhere."')
        
        print("Options:", ", ".join(room["options"].keys()))
        print("[N/S/E/W] Move  [T]alk  [S]ave  [I]nventory  [H]elp  [Q]uit")

        command = input("> ").lower()

        if command == "s":
            clear_screen()
            save_game(player, current_room, state, rooms)
        elif command == "q":
            confirm = input("Save before quitting? [Y/n] ").strip().lower()
            if confirm != "n":
                save_game(player, current_room, state, rooms)
            print("Goodbye, Timekeeper.")
            return
        elif command == "i":
            print("Inventory:", ", ".join(player["inventory"]) or "empty")
        elif command == "t" and "shopkeeper" in room:
            print(f'{room["shopkeeper"]}: "It has been a long time since anyone visited this shop."')
            anthrophobia_shop(player)
        elif command == "h":
            print("Explore by entering a listed direction. Each move advances time.")
            print("Defeat the three fears to assemble the watch. Save often.")
            print("In combat, attack or rewind with the Broken Clock to heal and recover time.")
        elif command in room["options"]:
            clear_screen()
            current_room = room["options"][command]
            collapse_to = advance_time(state, player, room, rooms)
            if collapse_to:
                current_room = collapse_to
                continue
            encounter = rooms[current_room].get("encounter")
            if encounter:
                result = minor_combat(player, encounter, state, rooms)
                if result == "reset":
                    current_room = "town"
                    continue
        else:
            print("You can't do that right now.")

'''----------------------------'''

if __name__ == "__main__":
    game()
