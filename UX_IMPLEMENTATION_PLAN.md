# Timekeeper's Oath RPG: UX Implementation Plan (Draft)

**Status:** Draft; first implementation pass added
**Scope:** Implement the UX ideas agreed during brainstorming; preserve the game's terminal format and existing story.

## Implementation snapshot

The first implementation pass is in `game.py`. It adds the player-facing combat, map, journal, settings, reset, and save flows described below. Character carryover covers attack/max-HP upgrades (HP is restored to full at a reset); Inventory carryover includes carried items such as the Broken Clock; world progress stays persistent. The reset review appears on timer expiry, while defeat skips that review and follows the existing immediate reset path. Settings default to brief pauses, screen clearing on, and sound on. Checkpoints currently update on boss victories. This pass has not been run through gameplay or test verification yet.

## One-line goal

Help players make informed combat and exploration choices, recover their place in the story, and control pacing and save behavior without losing the game's unsettling atmosphere.

## Current project shape

- The game is a single-file Python terminal game in `game.py`.
- `BASE_ROOMS` contains room descriptions, exits, bosses, items, and encounters. The main `game()` loop prints status and handles exploration commands.
- Boss and minor combat have separate loops (`combat()` and `minor_combat()`). Bosses currently have no Guard action; minor encounters reduce damage by 3 when Guard is chosen.
- `advance_time()` invokes `collapse_loop()` when the timer expires. Defeat also calls `collapse_loop()`, so the reset cause is not currently distinguished.
- Manual saves currently serialize player, state, room, and room data to one `savegame.json`. There is no checkpoint or settings file. Existing saves need to remain loadable.
- Story presentation uses many fixed `time.sleep(0.2)` calls, and `clear_screen()` is called throughout the game.

These details suggest implementing shared data and display helpers before adding each player-facing feature. Keep the first pass inside the current Python project; extract modules only if the work makes `game.py` hard to maintain.

## Agreed UX direction

### Combat

- Show a compact tactical status with player and enemy HP, loop time, and the exact incoming damage range.
- Report actual damage dealt after an attack.
- Explain basic action effects in the prompt. A dedicated `[?]` command explains special mechanics such as Rewind and enemy-specific rules.
- Make Guard available in boss and minor encounters, using a consistent effect (the existing minor encounter reduction of 3 is the starting point).
- Explain unavailable or invalid actions, then continue combat normally so the enemy still acts. Inspection commands such as Inventory and `?` should remain non-turn actions.
- Keep Rewind's explanatory text in the game's narrative voice.

### Navigation and map

- List exits by direction, destination name, and short spoiler-light hint.
- Add `[M] Map`: display a compact grid and a legend for room names and the player's current location.
- Reveal rooms as explored, display exits that lead to unmapped areas, and do not reveal undiscovered points of interest.
- Preserve discovered rooms across loop resets and saves.

### Journal and recap

- Add optional `[J] Journal`; also offer the recap after a reset and when loading a save.
- Include a short in-world reflection, current objectives, recent loop events, lasting milestones, and unresolved leads.
- Keep completed leads visible and mark them complete.

### Save and quit

- Replace the ambiguous quit prompt with **Save and quit**, **Quit without saving**, and **Cancel**.
- Keep manual saves separate from automatic checkpoints. If both are available and differ, let the player choose which to load.
- Keep the most recent checkpoint when quitting without saving.
- Create checkpoints at major milestones such as boss victories and story chapters.

### Loop carryover

- At timer expiry, show a review where the player chooses whether **Character** and **Inventory** carry over; explain the contents of each category and retain a custom choice for future timer resets.
- World progress always persists.
- Do not show the review after defeat-driven resets; those continue immediately.

### Accessibility and pacing

- Add settings accessible from both the title menu and during play.
- Include text pacing, screen clearing, and sound controls.
- Store settings separately from game progress so they persist across new games.

### Instability as a gameplay system

- Treat instability as a two-sided gameplay dial rather than only a source of unsettling text effects. High instability can create volatile opportunities alongside greater danger; low or negative instability can reward control and safe exploration.
- In exploration, let stability affect hazards and navigation: stable zones may quiet environmental threats or make paths easier to read, while unstable routes can expose shortcuts or hidden opportunities at a cost.
- In combat, let enemy behavior respond to instability. Chaos-oriented enemies may become more dangerous at high instability, while predictable enemies may lose abilities or become easier to read when the world is stable.
- Connect instability to abilities, giving players meaningful choices between defensive or precise actions at low instability and riskier, stronger effects at high instability.
- Let NPCs and the environment react to the current state, reinforcing the player's effect on the world.
- Balance both ends with benefits and drawbacks. Low instability should not be universally optimal: it may suppress unsettling clues or close unstable shortcuts, while high instability should offer useful opportunities as well as risks.
- Keep the implementation incremental: begin with one exploration effect and one combat effect at each end of the scale, then expand after play feedback.

## MVP and later work

### MVP

1. Centralize combat status/action descriptions and implement the agreed combat prompt behavior.
2. Add room hints, visited-room tracking, persistent map display, and exploration command.
3. Add journal data and a readable optional recap, with reset/load offers.
4. Separate manual save and checkpoint files, implement milestone checkpointing, explicit quit choices, and load selection.
5. Separate timer expiry from defeat reset and implement the carryover review for Character and Inventory.
6. Add persistent settings for text pacing, screen clearing, and sound, accessible at title and in-game.
7. Add compatibility defaults for older `savegame.json` files and validate loaded values.
8. In a later gameplay pass, connect instability to one exploration effect and one combat effect at both low and high values; preserve readable feedback and balance trade-offs.

### Later

- Expand hint content or add optional room/POI markers after discovery, if play feedback shows the simple map is insufficient.
- Add richer per-enemy combat rules only if the game gains distinct enemy patterns.
- Split `game.py` into modules after the behavior is stable, rather than combining a broad restructure with the UX changes.

## Suggested design and data changes

- **Room data:** Add a short `hint` for destinations. Keep map layout coordinates in a separate static mapping; this lets exploration state change without changing geography.
- **Progress state:** Add a versioned `visited_rooms` collection and journal facts/events. Record events at the moment they happen (room discovery, item discovery, boss victory, lead completion, loop reset) rather than trying to reconstruct them from the current room state.
- **Map rendering:** Render only visited rooms and their known connections. Use an unknown marker for exits from explored rooms whose destination has not been visited. Always show the current-room marker and a legend. The map must not expose boss/item data before discovery.
- **Combat:** Use small pure helpers for incoming damage ranges and action descriptions so the displayed range matches actual combat rules. Share Guard's reduction value between both combat loops. Treat `?`, Inventory, and invalid input as inspection/selection behavior according to the agreed turn rule; unavailable actions should consume a turn and allow the enemy response.
- **Journal:** Derive current objectives and lead completion from explicit progression facts (such as watch pieces and defeated bosses). Store a bounded recent-event list plus durable milestones; do not store generated prose as the source of truth.
- **Persistence:** Add save schema versioning and separate paths for manual save, checkpoint, and settings. Write saves atomically via a temporary file and replace to reduce corruption risk. Keep old manual saves readable by filling absent fields with defaults.
- **Loop reset:** Pass a reset reason (`timer` or `defeat`) explicitly. The timer path shows and applies the saved carryover selection; the defeat path bypasses the review. Ensure world progress and map discovery persist in either path.
- **Settings:** Store settings in a small independent JSON file. Route existing pauses, screen clearing, and sound calls through preference-aware helpers so settings apply consistently.
- **Instability:** Centralize thresholds and effects so low, neutral, and high instability have explicit gameplay meanings. Clamp probability values used for text effects at zero; negative values should mean reduced or absent instability effects, never negative probability. Surface the active gameplay consequences in concise player-facing feedback, and ensure any exploration or combat effects remain consistent with the same instability state.

## Task board

Estimates are rough engineering time, not calendar commitments. Tasks are ordered to get persistence and shared behavior in place before building dependent UI.

| # | Task | Priority | Estimate | Depends on | Done when |
|---|---|---:|---:|---|---|
| 1 | Define save schema, defaults, and legacy-save migration | P0 | 2–4 hours | — | Existing saves load with defaults for new fields; malformed optional fields fail gracefully. |
| 2 | Add settings storage and preference-aware presentation helpers | P0 | 3–5 hours | 1 | Settings persist across new games and can control pauses, clearing, and sound. |
| 3 | Add title and in-game settings menus | P0 | 2–4 hours | 2 | Players can open, change, and leave settings from both contexts without advancing game time. |
| 4 | Improve combat panels, action details, and shared Guard behavior | P0 | 3–5 hours | — | Both combat types show accurate incoming ranges; damage rolls are reported; Guard consistently reduces damage by 3; `?` works; invalid/unavailable actions trigger the stated enemy response. |
| 5 | Add room hints and visited-room tracking | P0 | 2–4 hours | 1 | Exits show direction, destination, and spoiler-light hint; discovery is recorded in saved progress. |
| 6 | Render the persistent, gradually revealed map | P0 | 3–6 hours | 5 | `[M]` shows a compact grid, names, current location, visited areas, and unknown exits without leaking undiscovered points of interest. |
| 7 | Record progression events and render the journal | P1 | 4–7 hours | 1 | `[J]` shows in-world recap, objectives, recent events, milestones, unresolved leads, and completed leads. |
| 8 | Offer journal recap after load and timer reset | P1 | 1–3 hours | 7, 10 | Offers appear at both moments and can be skipped; defeat reset does not incorrectly present a timer recap. |
| 9 | Separate manual saves and checkpoint persistence; add load selection | P1 | 4–7 hours | 1 | Manual and checkpoint files remain independent; when both differ, load offers both; old manual save remains available. |
| 10 | Refactor reset flow to distinguish timer expiry from defeat | P1 | 3–5 hours | 1 | Timer and defeat paths are explicit; defeat remains immediate; timer expiry is the only path to carryover review. |
| 11 | Add configurable Character/Inventory carryover review | P1 | 3–6 hours | 10 | Timer reset explains categories, applies remembered choices, and always retains world progress; defeat bypasses the review. |
| 12 | Create checkpoints at boss victories and story milestones | P1 | 2–4 hours | 9 | Checkpoint updates at defined milestone hooks and remains available after quit without saving. |
| 13 | Add explicit Save and Quit / Quit without saving / Cancel flow | P1 | 1–2 hours | 9 | Each choice is unambiguous; cancel returns to play; quit without saving retains the checkpoint and leaves manual save untouched. |
| 14 | Integrate and review the complete UX flow | P1 | 2–4 hours | 2–13 | Title, exploration, combat, timer reset, defeat, load, and quit paths use consistent prompts and persistence. |

## Risks and open questions

1. **Character carryover contents:** Confirm whether current HP carries over, resets to full, or is restored according to a separate rule. The current interstitial heals the player, while attack upgrades persist.
2. **Inventory carryover contents:** Confirm whether key items (for example, the Broken Clock) are included in the player-controlled Inventory category, or whether key items always persist. Watch pieces are world progress and always persist.
3. **Legacy save semantics:** The current save contains an in-progress run. Migration should preserve its current meaning rather than silently applying new reset rules.
4. **Checkpoint milestone list:** Boss victories are clear; identify which story events count as chapters before wiring every checkpoint hook.
5. **Map rendering constraints:** A fixed grid needs manually assigned coordinates. Confirm the intended terminal width and whether Unicode box drawing is acceptable; an ASCII fallback is safer across terminals.
6. **Combat timing wording:** The current rules include non-turn Inventory/invalid boss input, while minor invalid input is free and missing/full-health Potion is also free. The agreed direction says invalid/unavailable choices allow an enemy turn; inspection commands remain free. Confirm whether failed Potion use should also consume a turn.
7. **Carryover UX:** A saved custom setup is described, but it is not yet clear whether the review should appear every timer reset for confirmation or can be skipped after the player has saved a setup. The current plan keeps the review at each timer reset, as agreed.

## Recommended implementation order

Start with the schema and reset-path separation because map, journal, checkpoint, and carryover behavior all depend on reliable progression state. In parallel, the combat prompt and settings helpers can be implemented as isolated changes. Then add map and journal views, followed by checkpoint/load/quit flows and the timer-reset review. Integrate at the end, paying particular attention to the existing ways combat and exploration can trigger a reset.

## Definition of done

- Existing saves remain usable, and new fields have safe defaults.
- All new review and inspection commands are non-time-advancing unless explicitly specified as a combat turn.
- Timer resets and defeat resets follow their distinct agreed behaviors.
- Map, journal, manual save, checkpoint, and settings data persist in their intended scopes.
- Every menu shows valid choices, handles invalid input without accidental destructive behavior, and returns to the expected game state.
