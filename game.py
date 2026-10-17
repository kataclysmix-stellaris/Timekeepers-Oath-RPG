import json
import random
import os
import copy
import time
import re
import sys
import tempfile

try:
    import winsound
except ImportError:
    winsound = None

''' ----------------------------
WORLD DATA
----------------------------'''

BASE_ROOMS = {
    "forest": {
        "description": "You are in a dark forest. Paths lead north and east.",
        "hint": "A quiet clearing with paths deeper into the woods.",
        "options": {"north": "town", "east": "river", "west": "orchard"}
    },
    "town": {
        "description": "An abandoned town square. A broken clock tower looms overhead.",
        "hint": "The clock tower stands at the center of the abandoned town.",
        "options": {"north": "dark_alley", "south": "forest", "east": "library", "west": "shop"}
    },
    "dark_alley": {
        "description": "The alley feels wrong. Shadows cling to the walls.",
        "hint": "A narrow alley where the shadows seem unusually deep.",
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
        "hint": "A glint near the bank catches the light.",
        "item": "Broken Clock",
        "options": {"west": "forest", "south": "old_dock"}
    },
    "library": {
        "description": "Dusty shelves. Books whisper when you walk past.",
        "hint": "A silent library whose books seem to whisper.",
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
        "hint": "Damp steps descend into a close, dark space.",
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
        "hint": "An old general store with someone waiting inside.",
        "shopkeeper": "Anthrophobia",
        "options": {"east": "town", "north": "workshop"}
    },
    "orchard": {
        "description": "An overgrown orchard crowds the edge of the forest. Pale fruit hangs from the branches, and webs stretch between the trees.",
        "hint": "Pale fruit hangs among the overgrown trees.",
        "encounter": {"name": "Arachnophobia", "fear": "spiders", "hp": 10, "attack": 3, "wisps": 1},
        "options": {"east": "forest"}
    },
    "old_dock": {
        "description": "Rotting boards stretch over the river. Something churns beneath the dark water, just out of sight.",
        "hint": "Rotting boards reach out over dark water.",
        "encounter": {"name": "Aquaphobia", "fear": "deep water", "hp": 12, "attack": 4, "wisps": 2},
        "options": {"north": "river"}
    },
    "workshop": {
        "description": "A narrow workshop sits behind the shop. Dust and grime coat the benches as a pale shape stirs in the corners.",
        "hint": "Dusty workbenches fill a cramped room.",
        "encounter": {"name": "Mysophobia", "fear": "germs and contamination", "hp": 9, "attack": 3, "wisps": 1},
        "options": {"south": "shop"}
    }
}

REQUIRED_WATCH_PIECES = {
    "Minute Hand Fragment",
    "Hour Gear",
    "Balance Spring"
}

SAVE_SCHEMA_VERSION = 2
GUARD_REDUCTION = 3
MAX_RECENT_EVENTS = 12
SETTINGS_DEFAULTS = {
    "text_pacing": "brief",
    "clear_screen": True,
    "sound": True,
}
SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
CHECKPOINT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "checkpoint.json")
MAP_COORDS = {
    "workshop": (0, 0), "shop": (1, 0), "dark_alley": (0, 1),
    "town": (1, 1), "forest": (2, 1), "orchard": (3, 1),
    "basement": (0, 2), "library": (1, 2), "river": (2, 2), "old_dock": (3, 2),
}
ROOM_CODES = {
    "workshop": "WK", "shop": "SH", "basement": "BS", "dark_alley": "AL",
    "town": "TW", "library": "LB", "forest": "FO", "orchard": "OR",
    "river": "RV", "old_dock": "DK",
}
SETTINGS = copy.deepcopy(SETTINGS_DEFAULTS)

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
    "instability": 0,
    "cat_trust": False,
    "cat_last_heal_reset": -1,
    "visited_rooms": [],
    "recent_events": [],
    "milestones": [],
    "leads": {},
    "carryover": {"character": True, "inventory": False}
}


def record_event(state, event, milestone=False):
    state.setdefault("recent_events", []).append(event)
    state["recent_events"] = state["recent_events"][-MAX_RECENT_EVENTS:]
    if milestone and event not in state.setdefault("milestones", []):
        state["milestones"].append(event)


def story_pause(seconds=0.2):
    pacing = SETTINGS.get("text_pacing", "brief")
    multiplier = {"off": 0.0, "brief": 0.35, "normal": 1.0}.get(pacing, 0.35)
    if multiplier:
        time.sleep(seconds * multiplier)


def load_settings():
    global SETTINGS
    SETTINGS = copy.deepcopy(SETTINGS_DEFAULTS)
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as file:
            stored = json.load(file)
        if isinstance(stored, dict):
            if stored.get("text_pacing") in {"off", "brief", "normal"}:
                SETTINGS["text_pacing"] = stored["text_pacing"]
            if isinstance(stored.get("clear_screen"), bool):
                SETTINGS["clear_screen"] = stored["clear_screen"]
            if isinstance(stored.get("sound"), bool):
                SETTINGS["sound"] = stored["sound"]
    except (OSError, json.JSONDecodeError):
        pass


def save_settings():
    try:
        _atomic_json_write(SETTINGS_PATH, SETTINGS)
        return True
    except OSError as error:
        print(f"Settings could not be saved: {error}")
        return False


def settings_menu():
    while True:
        print("\nSettings")
        print(f"1) Text pacing: {SETTINGS['text_pacing']}")
        print(f"2) Clear screen between scenes: {'on' if SETTINGS['clear_screen'] else 'off'}")
        print(f"3) Sound effects: {'on' if SETTINGS['sound'] else 'off'}")
        print("0) Return")
        choice = input("> ").strip().lower()
        if choice == "0":
            return
        if choice == "1":
            print("Text pacing: [O]ff, [B]rief pauses, [N]ormal pauses")
            pacing = input("> ").strip().lower()
            SETTINGS["text_pacing"] = {"o": "off", "b": "brief", "n": "normal"}.get(pacing, SETTINGS["text_pacing"])
        elif choice == "2":
            SETTINGS["clear_screen"] = not SETTINGS["clear_screen"]
        elif choice == "3":
            SETTINGS["sound"] = not SETTINGS["sound"]
        else:
            print("Choose one of the listed settings.")
            continue
        save_settings()

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

def dialogue(speaker, line):
    print(f'{speaker}: "{line}"')


def play_sound(file_name):
    if winsound is None or not SETTINGS.get("sound", True):
        return

    sound_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds", file_name)
    if os.path.exists(sound_path):
        winsound.PlaySound(
            sound_path,
            winsound.SND_FILENAME | winsound.SND_ASYNC
        )
    
def between_space(player, state):
    print("\nYou stand in a place without walls.")
    print("A woman sits beside a warm pyre growing in a hearth.")
    print("She looks at you the way someone looks at a child who fell too hard.\n")

    player["hp"] = player["max_hp"]

    while True:
        dialogue("Creator", "You have returned, Timekeeper. How goes the journey?")
        print("1. I need to be stronger.")
        print("2. I need to survive longer.")
        print("3. I need more time.")
        print("4. I need to leave.")

        choice = input("> ")

        if choice == "1":
            clear_screen()
            player["attack"] += 3
            dialogue("Creator", "Then I will steady your hands.")
            dialogue("Creator", "Do not worry. The shadows are only the fears of others.")
            break
        elif choice == "2":
            clear_screen()
            player["max_hp"] += 10
            state["instability"] -= 2
            dialogue("Creator", "Then I will hold you together a little better.")
            dialogue("Creator", "Exercise more caution, the body needs time to heal.")
            break
        elif choice == "3":
            clear_screen()
            state["current_loop_length"] += 2
            state["instability"] -= 10
            print('"I can delay the collapse… but only slightly."')
            dialogue("Creator", "Be careful this time, please.")
            break
        elif choice == "4":
            clear_screen()
            dialogue("Creator", "I will be waiting for you to come back.")
            break
        else:
            clear_screen()
            dialogue("Creator", "That is not what you truly need.")
            
# Error Handling
def load_file(file_name, state="OK", glitch=False):
    print(f"\nLoading '{file_name}'...")
    story_pause(0.2)

    # Optional glitch behavior
    if glitch:
        glitch_text(file_name)
        return False

    print(f"Status: {state}")
    story_pause(0.2)
    return True

def file_error(file_name, error_type="not_found"):
    story_pause(0.2)

    print("\nTraceback (most recent call last):")
    story_pause(0.2)

    print(f'  File "runtime_loader.py", line 86')
    story_pause(0.2)

    if error_type == "not_found":
        print(f"FileNotFoundError: '{file_name}'")

    elif error_type == "corrupt":
        print(f"Error: '{file_name}' is corrupted")

    elif error_type == "conflict":
        print(f"Error: duplicate entity detected for '{file_name}'")

    story_pause(0.2)

def glitch_text(text):
    corrupted = ""

    for char in text:
        if random.random() < 0.2:
            corrupted += random.choice(["?", "#", "%"])
        else:
            corrupted += char

    print(f"Loading '{corrupted}'...")
    story_pause(0.2)

    print("Status: ???")
    story_pause(0.2)

def collapse_loop(state, player, room, rooms=None, reset_reason="timer"):
    clear_screen()
    print("Reality seems to unravel.")
    story_pause(0.2)
    print("The loop resets once more.")
    story_pause(0.2)
    clear_screen()
    
    state["resets"] += 1
    state["instability"] += 2
    state["current_loop_length"] = max(1, int(state["base_loop_length"] * 0.85))
    player["attack_bonus"] = 0
    if state.pop("cat_fed", False):
        state["cat_trust"] = True
    
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
        if reset_reason == "timer":
            review_carryover(player, state)
        else:
            player["inventory"] = []
        state["hour"] = 0
        record_event(state, f"Loop {state['resets']} began in the town.")
        offer_journal(state, player)
        return "town"
    else:
        autophobia(player, state)
        return "town"


def review_carryover(player, state):
    choices = state.setdefault("carryover", {"character": True, "inventory": False})
    print("\nAs the loop turns, choose what you carry with you.")
    print("Character: attack and health upgrades; current HP is restored to full.")
    print("Inventory: carried items, including the Broken Clock. Watch pieces and world progress always persist.")
    while True:
        print(f"1) Character upgrades: {'carry over' if choices.get('character', True) else 'reset'}")
        print(f"2) Inventory: {'carry over' if choices.get('inventory', False) else 'reset'}")
        print("3) Keep this setup and continue")
        choice = input("> ").strip()
        if choice == "1":
            choices["character"] = not choices.get("character", True)
        elif choice == "2":
            choices["inventory"] = not choices.get("inventory", False)
        elif choice == "3":
            break
        else:
            print("Choose 1, 2, or 3.")
    if not choices["character"]:
        player["attack"] = 6
        player["max_hp"] = 30
        player["attack_bonus"] = 0
    player["hp"] = player["max_hp"]
    if not choices["inventory"]:
        player["inventory"] = []

"""----------------------------
SAVE / LOAD
----------------------------"""

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_PATH = os.path.join(BASE_DIR, "savegame.json")

def _atomic_json_write(path, data):
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=directory, delete=False) as file:
            temporary_path = file.name
            json.dump(data, file, ensure_ascii=False, indent=2)
        os.replace(temporary_path, path)
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.remove(temporary_path)


def save_game(player, current_room, state, loop_rooms, destination="manual", quiet=False):
    path = CHECKPOINT_PATH if destination == "checkpoint" else SAVE_PATH
    payload = {
        "schema_version": SAVE_SCHEMA_VERSION,
        "player": player,
        "current_room": current_room,
        "state": state,
        "rooms": loop_rooms,
    }
    try:
        _atomic_json_write(path, payload)
        if not quiet:
            print("Checkpoint saved.\n" if destination == "checkpoint" else "Game saved.\n")
        return True
    except (OSError, TypeError, ValueError) as error:
        print(f"Save failed: {error}")
        return False


def load_game(source="manual", announce=True):
    path = CHECKPOINT_PATH if source == "checkpoint" else SAVE_PATH
    if not os.path.exists(path):
        if announce:
            print("No checkpoint found.\n" if source == "checkpoint" else "No save file found.\n")
        return None
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise ValueError("Save data must be an object")
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
        if not isinstance(player["inventory"], list):
            player["inventory"] = []
        for key in ("visited_rooms", "recent_events", "milestones"):
            if not isinstance(state.get(key), list):
                state[key] = []
        if not isinstance(state.get("leads"), dict):
            state["leads"] = {}
        if not isinstance(state.get("carryover"), dict):
            state["carryover"] = copy.deepcopy(game_state["carryover"])
        else:
            for key, default in game_state["carryover"].items():
                state["carryover"].setdefault(key, default)
        if (not isinstance(player["name"], str) or not player["name"].strip()
                or not is_appropriate_name(player["name"])):
            if isinstance(player["name"], str) and player["name"].strip() and not is_appropriate_name(player["name"]):
                print("That's not my name. I don't want to be called that. I'll choose a new name instead.")
            player["name"] = "Chronos"
        if announce:
            print("Checkpoint loaded.\n" if source == "checkpoint" else "Game loaded.\n")
        return player, current_room, state, rooms
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        if announce:
            print(f"Could not load {source} ({error}).\n")
        return None
        
def clear_screen():
    if not SETTINGS.get("clear_screen", True):
        print("\n")
        return
    if not sys.stdout.isatty():
        print("\n" * 2, end="")
        return

    # ANSI clear-screen and move-cursor-to-home sequences are supported by
    # Windows Terminal, modern PowerShell, and common Unix terminals.
    print("\033[2J\033[H", end="", flush=True)

'''----------------------------
COMBAT SYSTEM
----------------------------'''

def incoming_damage_range(enemy, state, guard=False, boss=False):
    if boss and enemy.get("fear") == "darkness" and (state["hour"] >= 20 or state["hour"] < 6):
        low, high = 4, enemy["attack"] + 3
    else:
        low, high = 1, enemy["attack"]
    if guard:
        low, high = max(0, low - GUARD_REDUCTION), max(0, high - GUARD_REDUCTION)
    return low, high


def show_action_details(player, enemy, state, boss=False):
    attack_max = player["attack"] + player.get("attack_bonus", 0)
    print(f"Attack: 1–{attack_max} damage; the enemy retaliates unless defeated.")
    print(f"Guard: reduce the next hit by {GUARD_REDUCTION}; time advances and the enemy still attacks.")
    print("Potion: restore up to 12 HP; the enemy still attacks.")
    if boss:
        rewind = 1 + len(state.get("watch_pieces", []))
        print(f"Rewind: the Runtime Clock heals 10 HP and rewinds up to {rewind} hour(s).")
        if enemy.get("fear") == "darkness":
            print("Nyctophobia strikes harder at night (20:00–05:00).")


def combat(player, boss, state, room, rooms):
    print(f"\nYou face {boss['name']} — embodiment of {boss['fear']}.\n")
    while boss["hp"] > 0 and player["hp"] > 0:
        low, high = incoming_damage_range(boss, state, boss=True)
        remaining = max(0, state["current_loop_length"] - state["hour"])
        print(f"Time {state['hour']}:00 | Loop {state['resets']} | {remaining} hours remain")
        print(f"You: {player['hp']}/{player['max_hp']} HP | {boss['name']}: {boss['hp']} HP")
        print(f"Incoming damage: {low}–{high}")
        action = input("[A]ttack, [G]uard (−3), [R]ewind, [P]otion, [I]nventory, [?] Details: ").strip().lower()
        if action in {"i", "?"}:
            if action == "i":
                print("Inventory:", ", ".join(player["inventory"]) or "empty")
            else:
                show_action_details(player, boss, state, boss=True)
            continue

        guarding = action == "g"
        if action == "a":
            damage = random.randint(1, player["attack"] + player.get("attack_bonus", 0))
            boss["hp"] -= damage
            print(f"You deal {damage} damage.")
            play_sound("hit.wav")
            if boss["hp"] <= 0:
                print(f"You defeated {boss['name']}!")
                if boss["watch_piece"] not in state["watch_pieces"]:
                    state["watch_pieces"].append(boss["watch_piece"])
                print("You obtained:", boss["watch_piece"])
                room.pop("boss", None)
                complete_lead(state, f"boss:{boss['name']}")
                record_event(state, f"Defeated {boss['name']} and recovered the {boss['watch_piece']}.", milestone=True)
                room_name = next((name for name, data in rooms.items() if data is room), "town")
                save_game(player, room_name, state, rooms, destination="checkpoint", quiet=True)
                print("A milestone checkpoint was recorded.")
                return "victory"
        elif action == "g":
            print("You brace for the attack.")
        elif action == "p":
            if not use_healing_tonic(player):
                print("The tonic cannot help right now; the enemy presses its attack.")
        elif action == "r":
            if "Broken Clock" in player["inventory"]:
                heal = min(10, player["max_hp"] - player["hp"])
                player["hp"] += heal
                rewind = 1 + len(state["watch_pieces"])
                state["hour"] = max(0, state["hour"] - rewind)
                print(f"The Runtime Clock's hands turn backward by {rewind} hour(s); you recover {heal} HP.")
            else:
                print("The clock's face is empty; nothing answers your attempt to rewind.")
        else:
            print("You freeze up in fear. The enemy takes advantage of the hesitation.")

        if boss["hp"] > 0:
            low, high = incoming_damage_range(boss, state, guard=guarding, boss=True)
            enemy_damage = random.randint(low, high)
            player["hp"] = max(0, player["hp"] - enemy_damage)
            print(f"{boss['name']} hits you for {enemy_damage} damage.")
            play_sound("damage.wav")
        if player["hp"] <= 0:
            print("You fall as the clock tower tolls...")
            collapse_loop(state, player, room, rooms, reset_reason="defeat")
            return "reset"
        if advance_time(state, player, room, rooms) is not None:
            return "reset"
        print()
    return "reset"


def minor_combat(player, enemy_data, state, rooms):
    enemy = enemy_data.copy()
    print(f"\nA Wisp of {enemy['name']} gathers in your path, embodying the fear of {enemy['fear']}.")
    while enemy["hp"] > 0 and player["hp"] > 0:
        low, high = incoming_damage_range(enemy, state)
        remaining = max(0, state["current_loop_length"] - state["hour"])
        print(f"Time {state['hour']}:00 | Loop {state['resets']} | {remaining} hours remain")
        print(f"You: {player['hp']}/{player['max_hp']} HP | Wisps: {player.get('wisps', 0)} | {enemy['name']}: {enemy['hp']} HP")
        print(f"Incoming damage: {low}–{high}")
        action = input("[A]ttack, [G]uard (−3), [P]otion, [I]nventory, [?] Details: ").strip().lower()
        if action in {"i", "?"}:
            if action == "i":
                print("Inventory:", ", ".join(player["inventory"]) or "empty")
            else:
                show_action_details(player, enemy, state)
            continue

        guarding = action == "g"
        if action == "a":
            damage = random.randint(1, player["attack"] + player.get("attack_bonus", 0))
            enemy["hp"] -= damage
            print(f"You deal {damage} damage.")
            play_sound("hit.wav")
            if enemy["hp"] <= 0:
                reward = enemy.get("wisps", 1)
                player["wisps"] = player.get("wisps", 0) + reward
                print(f"You dispersed the {enemy['name']} and gathered {reward} Wisps.")
                if enemy["name"] == "Aquaphobia" and not state.get("fish_found", False):
                    player["inventory"].append("River Fish")
                    state["fish_found"] = True
                    print("Something silver-flashing lands on the dock: a River Fish.")
                complete_lead(state, f"encounter:{enemy['name']}")
                record_event(state, f"Dispersed {enemy['name']}.")
                for room in rooms.values():
                    if room.get("encounter", {}).get("name") == enemy["name"]:
                        room.pop("encounter", None)
                return "victory"
        elif action == "g":
            print("You brace for the attack.")
        elif action == "p":
            if not use_healing_tonic(player):
                print("The tonic cannot help right now; the enemy presses its attack.")
        else:
            print("You hesitate. The wisp attacks while you recover.")

        low, high = incoming_damage_range(enemy, state, guard=guarding)
        damage = random.randint(low, high)
        player["hp"] = max(0, player["hp"] - damage)
        print(f"{enemy['name']} hits you for {damage} damage.")
        if damage > 0:
            play_sound("damage.wav")
        if player["hp"] <= 0:
            print("You fall as the clock tower tolls...")
            collapse_loop(state, player, None, rooms, reset_reason="defeat")
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


def town_cat(player, state):
    if state.get("cat_trust", False):
        print("A black cat sits beneath the clock tower, watching you with bright, patient eyes.")
    else:
        print("A black cat stares at you from the town square, then edges just out of reach.")

    while True:
        print("1) Pet the cat")
        if "River Fish" in player["inventory"] and not state.get("cat_trust", False):
            print("2) Offer it the River Fish")
        print("T) Talk to the cat")
        print("0) Leave")
        choice = input("> ").strip()

        if choice == "0":
            return
        if choice.lower() == "t":
            print("The cat has no idea what you're saying but decides to respond regardless.")
            print("Meow.")
            play_sound("meow.wav")
        elif choice == "1":
            if state.get("cat_trust", False):
                print("The cat leans into your hand and purrs. You feel a little steadier.")
                if state.get("cat_last_heal_reset", -1) != state.get("resets", 0):
                    healing = min(10, player["max_hp"] - player["hp"])
                    player["hp"] += healing
                    state["cat_last_heal_reset"] = state.get("resets", 0)
                    if healing:
                        print(f"The cat's company restores {healing} HP.")
                    else:
                        print("You are already at full health.")
                else:
                    print("The cat has already helped you this loop.")
            else:
                print("It watches your hand, then slips beneath a nearby bench.")
        elif choice == "2" and "River Fish" in player["inventory"] and not state.get("cat_trust", False):
            player["inventory"].remove("River Fish")
            state["cat_fed"] = True
            print("The cat takes the fish and vanishes between the unfinished buildings.")
            print("It won't return until the world turns over again.")
        else:
            print("The cat flicks its tail, still watching you.")

def autophobia(player, state):
    print("...you...no, I find myself in the empty space again.")
    clear_screen()
    story_pause(0.2)
    print("...but Creator's not there.")
    clear_screen()
    alone_pause(state)
    clear_screen()
    print("...")
    story_pause(0.2)
    if state["resets"] >= 10:
        clear_screen()
        print("Why do you keep having me go to her?")
        story_pause(0.2)
    clear_screen()
    print("I don't understand...")
    story_pause(0.2)
    clear_screen()
    print(f"Monophobia: 'What's the matter, {player['name']}?'")
    story_pause(0.2)
    print("The figure looks just like me, but twisted by fear and despair.")
    story_pause(0.2)
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
                    story_pause(0.2)
                    dialogue("Monophobia", "So that was a lie, then. You don't want to accept me.")
                    acceptance = False
                    trust_break = True
                    story_pause(0.2)
                    clear_screen()
                elif not trust_break:
                    story_pause(0.2)
                    dialogue("Monophobia", "What are you doing?")
                    story_pause(0.2)
                    clear_screen()
                elif trust_break:
                    story_pause(0.2)
                    print("I expected the shadow to be upset, but it just looks...worried for some reason.")
                    story_pause(0.2)
                    dialogue("Monophobia", "...")
                    story_pause(0.2)
                    clear_screen()
            continue
        elif action == "c":
            clear_screen()
            print("I take a deep breath and try to accept my fears.")
            player["hp"] = min(player["hp"] + 5, player["max_hp"])
            state["instability"] = max(0, state["instability"] - 8)
            accept_attempts += 1
            if acceptance:
                story_pause(0.2)
                print("I hold out my hand to the shadow, and it hesitantly takes it.")
                story_pause(0.2)
                print("It becomes a part of me. I feel whole for the first time.")
                break
            if accept_attempts >= threshold and not acceptance:
                story_pause(0.2)
                print("The shadow looks at you with a mix of surprise and relief.")
                story_pause(0.2)
                dialogue("Monophobia", "You... you actually want to accept me?")
                acceptance = True
            elif trust_break and accept_attempts < threshold:
                dialogue("Monophobia", "You said you wanted to accept me, but you keep hurting yourself.")
                story_pause(0.2)
                dialogue("Monophobia", "I don't know if I can trust you.")
                trust_break = False
            elif accept_attempts < threshold:
                if accept_attempts == 1:
                    story_pause(0.2)
                    print("I feel a slight improvement in my mental state.")
                    story_pause(0.2)
                    dialogue("Monophobia", "That's a start, I guess.")
                if accept_attempts == 2:
                    story_pause(0.2)
                    print("I feel more at peace, but the shadow looks uncertain.")
                    story_pause(0.2)
                    dialogue("Monophobia", "...are you sure about this?")
                if accept_attempts == 3:
                    story_pause(0.2)
                    print("I feel a significant improvement in my mental state.")
                    story_pause(0.2)
                    dialogue("Monophobia", "Why are you doing this to yourself?")
                if accept_attempts == 4:
                    story_pause(0.2)
                    print("I feel a profound improvement in my mental state.")
                    story_pause(0.2)
                    dialogue("Monophobia", "...what's wrong with you?")
                if accept_attempts >= 5:
                    if accept_attempts == 5:
                        story_pause(0.2)
                        print("The shadow seems to shrink and weaken.")
                        story_pause(0.2)
                        dialogue("Monophobia", "I...I don't understand. Why aren't you afraid of me?")
                    if accept_attempts == 6:
                        story_pause(0.2)
                        print("The shadow looks genuinely confused and a little scared.")
                        story_pause(0.2)
                        dialogue("Monophobia", "...you don't want to fight me? You want to accept me?")
                    if accept_attempts == 7:
                        story_pause(0.2)
                        print("The shadow seems to be on the verge of breaking down.")
                        story_pause(0.2)
                        dialogue("Monophobia", "I don't know how to deal with this.")
                    if accept_attempts >= 8:
                        story_pause(0.2)
                        print("The shadow looks like it's about to collapse.")
                        story_pause(0.2)
                        if accept_attempts == 10:
                            dialogue("Monophobia", "...I don't want to be alone anymore.")
                        elif accept_attempts == 12:
                            dialogue("Monophobia", "I just want to be accepted.")
                        elif accept_attempts == 14:
                            dialogue("Monophobia", "Please...just accept me.")
                        else:
                            dialogue("Monophobia", "...")
                story_pause(0.2)
        elif action == "r":
            clear_screen()
            print("The clock doesn't work here. No matter how much I want to go back, I can't.")
            story_pause(0.2)
            if accept_attempts == 0:
                dialogue("Monophobia", "Time doesn't flow the same way here. Nice try, though.")
            elif accept_attempts < threshold:
                dialogue("Monophobia", "You keep trying to heal yourself by rewinding time, but you have to face me eventually.")
                threshold += 1 # increase threshold for acceptance after each rewind attempt
            elif accept_attempts == threshold:
                dialogue("Monophobia", "I thought maybe you'd give up and accept me by now.")
                trust_break = True
                acceptance = False
                threshold += 1
                accept_attempts = 0
            continue
        else:
            print("I hesitate, paralyzed by self-doubt.")
            story_pause(0.2)
            continue
        
        story_pause(0.2)
        clear_screen()
        if player["hp"] <= 0:
            creator_encouragement(player, state)
    
    if acceptance:
        story_pause(0.2)
        clear_screen()
        ending(player, state)
        
def creator_encouragement(player, state):
    file_error(f"Timekeeper_{player['name']}.chr", "conflict")
    story_pause(0.2)
    clear_screen()
    file_error("Creator_Klysm.chr", "not_found")
    story_pause(0.2)
    clear_screen()
    file_error("savegame.json", "corrupt")
    story_pause(0.2)
    clear_screen()
    dialogue("Creator", "Try again, Timekeeper.")
    story_pause(0.2)
    dialogue("Creator", "...but be a little nicer to yourself this time.")
    story_pause(0.2)
    dialogue("Creator", "I know you can do it.")
    story_pause(0.2)
    dialogue("Creator", "They're just as scared of you as you are of them.")
    story_pause(0.2)
    dialogue("Creator", "Baby steps, okay?")
    player["hp"] = player["max_hp"]
    self_fight(player, state)
    
def ending(player, state):
    print("I wake up in a cozy house, sunlight streaming through the windows.")
    story_pause(0.2)
    clear_screen()
    print("Creator is there, smiling warmly as I sit up. The clock on the wall ticks softly, but it doesn't feel ominous anymore.")
    story_pause(0.2)
    clear_screen()
    dialogue("Creator", f"Welcome back, {player['name']}. And Mono, too, I suppose.")
    story_pause(0.2)
    clear_screen()
    print('I look at the wall. A shadow hangs out there, attached to both the wall and my body, but it looks more like a mischievous figure than a threat.')
    story_pause(0.2)
    dialogue("Creator", "You both gave me quite a scare, but I'm glad you're here.")
    story_pause(0.2)
    dialogue("Creator", f"I quite like your new name, by the way. {player['name']}. It suits you.")
    story_pause(0.2)
    dialogue("Creator", "I hope you'll stay with me for a while. But if you go to explore again, just remember that I'll be here when you get back.")
    story_pause(0.2)
    clear_screen()
    print("I go to the window and look out at the world.")
    story_pause(0.2)
    print("It looks...well, complete.")
    story_pause(0.2)
    print("With people walking around, birds flying, and the sun shining.")
    story_pause(0.2)
    print("It feels like a place I can belong.")
    story_pause(0.2)
    print("I turn back to Creator, who is still smiling at me.")
    story_pause(0.2)
    print("I feel a sense of excitement wash over me.")
    story_pause(0.2)
    clear_screen()
    dialogue("Creator", "Well, what are you waiting for? I made this world for you. Go out and enjoy it!")
    story_pause(0.2)
    clear_screen()
    print("I step outside.")
    story_pause(0.2)
    print("The world is bright and full of life.")
    story_pause(0.2)
    print("I feel like I can finally breathe.")
    story_pause(0.2)
    print("Monophobia is there too, but it seems content to just follow me around, no longer a source of fear.")
    clear_screen()
    print("I walk down the street, taking in the sights and sounds of the world.")
    story_pause(0.2)
    print("I see people laughing, talking, and going about their lives.")
    story_pause(0.2)
    print("And I see a young girl sitting on a bench, looking lost.")
    story_pause(0.2)
    clear_screen()
    print("I remember being lost, too. I walk over to her and sit down.")
    story_pause(0.2)
    clear_screen()
    dialogue(f"Timekeeper {player['name']}", "Hey there, kiddo. You look like you could use a friend.")
    story_pause(0.2)
    clear_screen()
    print("The girl looks up at me. She looks scared, but also hopeful.")
    story_pause(0.2)
    print("Her own shadow curls around her feet, like a protective pet.")
    story_pause(0.2)
    print("It reminds me of Monophobia, but it seems to be comforting her rather than threatening her.")
    story_pause(0.2)
    print("I reach out and take her hand, offering her a smile.")
    story_pause(0.2)
    clear_screen()
    dialogue(f"Timekeeper {player['name']}", "It's okay. I know how you feel. But you're not alone anymore.")
    story_pause(0.2)
    clear_screen()
    print("She hesitates, but decides to trust me.")
    story_pause(0.2)
    print("I decide to take her under my wing, just like Creator did for me.")
    story_pause(0.2)
    clear_screen()
    print("Together, we explore the world, making new friends and having adventures.")
    story_pause(0.2)
    print("Monophobia tags along, but it seems to be more of a companion than a source of fear now.")
    story_pause(0.2)
    clear_screen()
    print("...I guess I can say that I have a happy ending after all.")
    story_pause(0.2)
    print("Thanks...whoever you are, for helping me get here.")
    return

def complete_lead(state, key):
    leads = state.setdefault("leads", {})
    lead = leads.get(key)
    if isinstance(lead, dict):
        lead["complete"] = True
    elif key in leads:
        leads[key] = {"text": str(key).replace(":", " — "), "complete": True}


def register_room_discovery(state, room_name, room):
    visited = state.setdefault("visited_rooms", [])
    first_visit = room_name not in visited
    if first_visit:
        visited.append(room_name)
        record_event(state, f"Discovered {room_name.replace('_', ' ')}.")
    leads = state.setdefault("leads", {})
    if "boss" in room:
        boss = room["boss"]
        key = f"boss:{boss['name']}"
        leads.setdefault(key, {"text": f"A presence waits in {room_name.replace('_', ' ')}.", "complete": False})
    if "encounter" in room:
        enemy = room["encounter"]
        key = f"encounter:{enemy['name']}"
        leads.setdefault(key, {"text": f"A wisp embodying {enemy['fear']} haunts {room_name.replace('_', ' ')}.", "complete": False})


def print_exits(room, rooms):
    print("Routes:")
    for direction, destination in room["options"].items():
        target = rooms[destination]
        print(f"  {direction.title()}: {destination.replace('_', ' ')} — {target.get('hint', 'A path leads onward.')}")


def render_map(state, current_room):
    visited = set(state.get("visited_rooms", []))
    visited.add(current_room)
    rows = max(row for row, _ in MAP_COORDS.values()) + 1
    cols = max(col for _, col in MAP_COORDS.values()) + 1
    height, width = rows * 2 - 1, cols * 8 + 1
    canvas = [[" " for _ in range(width)] for _ in range(height)]

    def center(room_name):
        row, col = MAP_COORDS[room_name]
        return row * 2, col * 8 + 4

    for source in visited:
        if source not in BASE_ROOMS:
            continue
        sr, sc = center(source)
        for destination in BASE_ROOMS[source]["options"].values():
            if destination not in MAP_COORDS:
                continue
            dr, dc = center(destination)
            if destination in visited:
                if sr == dr:
                    for x in range(min(sc, dc) + 3, max(sc, dc) - 2):
                        canvas[sr][x] = "-"
                elif sc == dc:
                    for y in range(min(sr, dr) + 1, max(sr, dr)):
                        canvas[y][sc] = "|"
            else:
                marker = "[??]"
                start = max(0, dc - 2)
                for offset, char in enumerate(marker):
                    if start + offset < width:
                        canvas[dr][start + offset] = char
                if sr == dr:
                    for x in range(min(sc, dc) + 3, max(sc, dc) - 2):
                        if canvas[sr][x] == " ":
                            canvas[sr][x] = "-"
                elif sc == dc:
                    for y in range(min(sr, dr) + 1, max(sr, dr)):
                        canvas[y][sc] = "|"

    for room_name in visited:
        if room_name not in MAP_COORDS:
            continue
        row, col = center(room_name)
        token = f">{ROOM_CODES[room_name]}<" if room_name == current_room else f"[{ROOM_CODES[room_name]}]"
        start = max(0, col - len(token) // 2)
        for offset, char in enumerate(token):
            if start + offset < width:
                canvas[row][start + offset] = char

    print("\nMap (north is up):")
    for line in canvas:
        print("".join(line).rstrip())
    print("Legend: [??] unmapped exit; >XX< current room")
    for room_name in sorted(visited, key=lambda name: MAP_COORDS.get(name, (99, 99))):
        if room_name in ROOM_CODES:
            print(f"  {ROOM_CODES[room_name]}: {room_name.replace('_', ' ')}")


def show_journal(state, player):
    print("\nJournal")
    resets = state.get("resets", 0)
    print(f'"I have crossed this world {resets + 1} time(s). The clock keeps asking me to begin again."')
    missing = sorted(REQUIRED_WATCH_PIECES - set(state.get("watch_pieces", [])))
    print("\nCurrent objectives:")
    if missing:
        print("  Recover the remaining pieces of the watch:")
        for piece in missing:
            print(f"    - {piece}")
    else:
        print("  The watch is whole. Face what waits beyond the loop.")
    print("\nRecent events:")
    for event in state.get("recent_events", [])[-5:] or ["No events recorded yet."]:
        print(f"  - {event}")
    print("\nMilestones:")
    for event in state.get("milestones", []) or ["No milestones recorded yet."]:
        print(f"  - {event}")
    print("\nLeads:")
    leads = state.get("leads", {})
    if not leads:
        print("  No leads recorded yet.")
    for lead in leads.values():
        if isinstance(lead, dict):
            text = lead.get("text", "Unrecorded lead")
            complete = lead.get("complete", False)
        else:
            text, complete = str(lead), bool(lead)
        print(f"  [{'Complete' if complete else 'Open'}] {text}")


def offer_journal(state, player):
    choice = input("The journey feels distant. Open the journal? [J/Enter] ").strip().lower()
    if choice in {"j", "y", "yes"}:
        show_journal(state, player)


def save_files_differ():
    try:
        with open(SAVE_PATH, "r", encoding="utf-8") as manual_file:
            manual = json.load(manual_file)
        with open(CHECKPOINT_PATH, "r", encoding="utf-8") as checkpoint_file:
            checkpoint = json.load(checkpoint_file)
        return manual != checkpoint
    except (OSError, json.JSONDecodeError):
        return True


def choose_loaded_game():
    manual_exists, checkpoint_exists = os.path.exists(SAVE_PATH), os.path.exists(CHECKPOINT_PATH)
    if manual_exists and checkpoint_exists and save_files_differ():
        while True:
            choice = input("Load [M]anual save or [C]heckpoint? ").strip().lower()
            if choice in {"m", "c"}:
                return load_game("manual" if choice == "m" else "checkpoint")
            print("Choose M or C.")
    if checkpoint_exists and not manual_exists:
        return load_game("checkpoint")
    if manual_exists:
        return load_game("manual")
    if checkpoint_exists:
        return load_game("checkpoint")
    print("No save or checkpoint found. Starting a new game.\n")
    return None


'''----------------------------
GAME LOOP
----------------------------'''

def game():
    load_settings()
    print("\nTHE TIMEKEEPER'S OATH")
    print("A terminal story about fear, time, and making peace with yourself.\n")
    loaded = None
    while True:
        print("1) New Game")
        print("2) Load Game")
        print("3) Settings")
        print("4) Quit")
        choice = input("> ").strip().lower()
        if choice == "1":
            player = new_player()
            state = copy.deepcopy(game_state)
            current_room = "town"
            rooms = copy.deepcopy(BASE_ROOMS)
            break
        if choice == "2":
            loaded = choose_loaded_game()
            if loaded:
                player, current_room, state, rooms = loaded
                offer_journal(state, player)
                break
            print("No usable game was loaded. Choose another menu option.")
        elif choice == "3":
            settings_menu()
        elif choice == "4":
            print("Goodbye, Timekeeper.")
            return
        else:
            print("Choose 1, 2, 3, or 4.")

    state.setdefault("visited_rooms", [])
    register_room_discovery(state, current_room, rooms[current_room])

    while True:
        clear_screen()
        room = rooms[current_room]
        register_room_discovery(state, current_room, room)
        print(room["description"])
        print(f"Current Time: {state['hour']}:00 (Loop {state['resets']})")
        print(f"Time remaining: {max(0, state['current_loop_length'] - state['hour'])} hours")
        print("Watch Pieces:", ", ".join(state["watch_pieces"]) or "none")
        print(f"Wisps: {player.get('wisps', 0)}")
        print("Inventory:", ", ".join(player["inventory"]) or "empty")

        if state.get("last_loop_cache"):
            drop_room = state["last_loop_cache"].get("room", "town")
            if drop_room in rooms:
                rooms[drop_room]["item"] = "Broken Clock"

        if "item" in room:
            item = room["item"]
            if item == "Broken Clock" and state.get("last_loop_cache"):
                recovered = state["last_loop_cache"]
                player["inventory"].extend(item for item in recovered.get("inventory", []) if item not in player["inventory"])
                state["watch_pieces"] = list(dict.fromkeys(state["watch_pieces"] + recovered.get("watch_pieces", [])))
                print("You find a broken clock. It feels familiar. You reclaim what was lost.")
                state["last_loop_cache"] = None
                record_event(state, "Recovered what the previous loop left behind.")
            else:
                print(f"You found a {item}!")
                if item not in player["inventory"]:
                    player["inventory"].append(item)
                    record_event(state, f"Found {item} in {current_room.replace('_', ' ')}.")
            del room["item"]

        if "boss" in room:
            result = combat(player, room["boss"].copy(), state, room, rooms)
            if result == "reset":
                current_room = "town"
                continue

        if "shopkeeper" in room:
            print(f"{room['shopkeeper']} watches you from behind the counter.")
            dialogue(room["shopkeeper"], "Welcome. Take your time looking around. I am not going anywhere.")

        print_exits(room, rooms)
        print("[N/S/E/W] Move  [T]alk  [C]at  [S]ave  [I]nventory  [M]ap  [J]ournal  [O]ptions  [H]elp  [Q]uit")
        command = input("> ").strip().lower()

        if command == "s":
            save_game(player, current_room, state, rooms)
        elif command == "q":
            while True:
                print("1) Save and quit  2) Quit without saving  0) Cancel")
                choice = input("> ").strip()
                if choice == "1":
                    save_game(player, current_room, state, rooms)
                    print("Goodbye, Timekeeper.")
                    return
                if choice == "2":
                    if os.path.exists(CHECKPOINT_PATH):
                        print("Goodbye, Timekeeper. Your last checkpoint remains available.")
                    else:
                        print("Goodbye, Timekeeper. No save was made.")
                    return
                if choice == "0":
                    break
                print("Choose 1, 2, or 0.")
        elif command == "i":
            print("Inventory:", ", ".join(player["inventory"]) or "empty")
        elif command == "m":
            render_map(state, current_room)
        elif command == "j":
            show_journal(state, player)
        elif command == "o":
            settings_menu()
        elif command == "t" and "shopkeeper" in room:
            dialogue(room["shopkeeper"], "It has been a long time since anyone visited this shop.")
            anthrophobia_shop(player)
        elif command == "t" and current_room == "town":
            print("The cat has no idea what you're saying, but decides to respond regardless.")
            print("Cat: Mrow.")
            play_sound("meow.wav")
        elif command == "t":
            print("Why are you talking to yourself?")
        elif command == "c":
            if current_room == "town":
                town_cat(player, state)
            else:
                print("What cat. There is no cat.")
        elif command == "h":
            print("Choose a listed direction to travel; each move advances time.")
            print("Defeat the three fears to assemble the watch. Use [M]ap and [J]ournal to review progress.")
            print("Combat lists incoming damage. Use [?] there for action details; Guard reduces one hit by 3.")
            print("Settings are available with [O]ptions. In town, press [C] to interact with the black cat.")
        elif command in room["options"]:
            destination = room["options"][command]
            current_room = destination
            collapse_to = advance_time(state, player, room, rooms)
            if collapse_to:
                current_room = collapse_to
                continue
            target = rooms[current_room]
            register_room_discovery(state, current_room, target)
            encounter = target.get("encounter")
            if encounter:
                result = minor_combat(player, encounter, state, rooms)
                if result == "reset":
                    current_room = "town"
                    continue
        else:
            print("That choice isn't available here. Choose a listed direction or command.")


if __name__ == "__main__":
    game()
