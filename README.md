# The Last Demigod

A top-down survival game made with pygame. Lightning strikes your cell door, and you
fight your way up out of the Underworld through three levels, picking up gifts from
the gods along the way.

## How to run

```
pip install -r requirements.txt
python last_demigod.py
```

## Controls

- **WASD** or **Arrow keys** — move
- Attacks are automatic — you don't need to aim or press anything to attack
- **1 / 2 / 3** — pick a gift when you level up
- **P** or **ESC** — pause
- **M** — mute/unmute sound
- **ENTER** — confirm on menus, continue after a cutscene/level
- **F1** — (debug only) show collision walls, off unless `DEBUG = True` in the code

## Story

The last child of Zeus wakes up in a Tartarus prison cell. Lightning breaks the door,
and the escape begins: fight through the prison, survive Tartarus and Kampe, cross
the River Styx and beat Cerberus, then face Hera herself at the Gates of the
Underworld.

## Assets

The game runs with simple colored shapes for anything missing from `assets/`, so it
never crashes if art/sound isn't there yet. Drop in files with these exact names to
replace the placeholders:

**Images** (`assets/`)
- `title_screen.png` — main menu background
- `leon.png`, `elena.png` — playable character sprites
- `skeleton.png`, `shadow.png`, `harpy.png` — regular enemies
- `kampe.png`, `cerberus.png`, `hera.png` — bosses
- `charon.png` — the ferryman NPC
- `tartarus_arena.png`, `styx_arena.png`, `gates_arena.png` — level backgrounds (the
  first already exists)
- `prison.png` — prologue background (already exists)

**Sounds** (`assets/sounds/`)
- `lightning.wav`, `hit.wav`, `enemy_death.wav`, `xp_pickup.wav`, `level_up.wav`,
  `gate_open.wav`, `boss_spawn.wav`, `win.wav`, `lose.wav` — sound effects
- `music_prison.ogg`, `music_level1.ogg`, `music_level2.ogg`, `music_level3.ogg` —
  background music per scene

## Credits

Built as a learning project with Claude's help, based on the game's one-page design
document.
