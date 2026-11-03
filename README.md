# The Last Demigod

A top-down survival game made with pygame. Lightning strikes your cell door, and you
fight your way up out of the Underworld through three levels, picking up gifts from
the gods along the way, until you face Hera herself.

## How to run

```
pip install -r requirements.txt
python last_demigod.py
```

## Controls

- **W/S** or **Up/Down** arrows — move the highlight in menus
- **WASD** or **Arrow keys** — move the player in-game
- Attacks are automatic — you don't need to aim or press anything to attack
- **1 / 2 / 3** — pick a gift when you level up
- **P** or **ESC** — pause
- **M** — mute/unmute sound (works anywhere, and is remembered next time)
- **ENTER** — confirm on menus, continue after a cutscene/level
- **F1** — (debug only) show collision walls, off unless `DEBUG = True` in the code

## What's in the game

- **Main menu**: Start, Controls, Settings, Quit
- **Character select**: play as Leon or Elena
- **Prologue**: escape a Tartarus prison cell by defeating 2 skeleton guards
- **Level 1 — Tartar**: boss Kampe, who swings in a wide circle around herself
- **Level 2 — River Styx**: boss Cerberus, who lunges and breathes fireballs
- **Level 3 — Gates of the Underworld**: final boss Hera, who throws peacock
  feathers, summons shadows, and unleashes a wave of divine energy
- Charon ferries and fully heals you between levels, with a line of advice
- 3 regular enemy types (skeletons, fast/fragile shadows, zigzagging flying harpies)
  that mix in more as levels and fights get harder
- Every boss stands still and takes extra damage for a couple of seconds after its
  big attack — that's the window to punish it
- 7 gifts from the gods, each upgradeable 5 times; once everything is maxed, leveling
  up heals you instead of doing nothing
- Pause menu (Resume / Restart level / Main menu / Quit), and win/death screens with
  run stats (level reached, time survived, enemies defeated, gifts taken) and
  Retry level / Main menu options
- Hit feedback: floating damage numbers, a white flash and screen shake when you get hit
- Settings screen: music volume, sound volume, fullscreen — saved to `save.json`
  along with your best run (furthest level reached, longest survival time)

## Story

The last child of Zeus wakes up in a Tartarus prison cell. Lightning breaks the door,
and the escape begins: fight through the prison, survive Tartarus and Kampe, cross
the River Styx and beat Cerberus, then face Hera herself at the Gates of the
Underworld.

## Assets

The game runs with simple colored shapes and silence for anything missing from
`assets/`, so it never crashes if art/sound isn't there. Still missing:

**Images** (`assets/`)
- `title_screen.png` — main menu background
- `styx_arena.png` — Level 2 background. There's already a styx_arena.png in the
  repo and it's untouched; I looked for a better fit (Vampire Survivors stage art
  and free dark top-down dungeon packs) but didn't find anything both top-down and
  16:9 that matched the painted style of the existing backgrounds closely enough to
  be worth swapping in — happy to try again with a specific picture if you have one.
- `gates_arena.png` — Level 3 background. Same story as styx_arena.png - not found.
- Once either exists, add wall rects for it to `STYX_WALLS`/`GATES_WALLS` near the
  top of `last_demigod.py`, the same way `TARTARUS_WALLS` was done — turn on `F1`
  with `DEBUG = True` to line them up against the picture.
- `tartarus_arena.png`, `prison.png` — already in the repo, untouched

**Sounds** (`assets/sounds/`)
- `lightning.wav`, `hit.wav`, `enemy_death.wav`, `xp_pickup.wav`, `level_up.wav`,
  `gate_open.wav`, `boss_spawn.wav`, `win.wav`, `lose.wav` — sound effects
- `music_prison.ogg`, `music_level1.ogg`, `music_level2.ogg`, `music_level3.ogg` —
  background music per scene

Leon, Elena, the enemies, and the bosses all use real sprite animations now. Zeus'
lightning, Poseidon's trident, Ares' sword, Apollo's arrows, Athena's shield, Hermes'
sandals, and Ambrosia all show real Vampire Survivors weapon/item icons too, both on
the gift cards and in play (projectiles and the orbiting sword rotate to face the
direction they're moving). There's no in-game health-potion pickup to attach the
Floor Chicken icon to, so that one's downloaded but unused.

## Third-party assets (private use only)

This is a private study project and is not shared or published, so the following
assets - which belong to other people - were used as reference/placeholder art and
are **not cleared for any public or commercial release** of this project:

- **Character, enemy, and boss sprites** are from *Vampire Survivors* (poncle), sourced
  from the community wiki at vampire.survivors.wiki (spriters-resource.com blocked
  automated downloads, so this was the fallback). None of these are actually named
  "Leon," "Kampe," etc. in Vampire Survivors - they're reskinned stand-ins:
  - Leon = **Antonio Belpaese**, Elena = **Imelda Belpaese**
  - skeleton = **Skeleton**, harpy = **Bat (Pipeestrello)**
  - shadow = **Spiritoso** / **Spiritosa** (ghost sprites, picked at random per spawn)
  - Kampe = **Bat Dragon**, Cerberus = **Giant Werewolf**, Hera = **Queen Medusa**
  - Charon = **The Reaper**
  - Zeus' Lightning = **Lightning Ring**, Poseidon's Trident = **Santa Javelin**,
    Ares' Sword = **Night Sword**, Apollo's Arrows = **Knife**, Athena's Shield =
    **Laurel**, Hermes' Sandals = **Wings**, Ambrosia = **Hollow Heart**
  - the XP orb = the game's own **Experience Gem** sprite
  - Raw downloads are in `assets/vs/`; `_extract_frames.py` is the one-off script
    that sliced them into the numbered frames the game actually loads.
- **Font**: `Pixelify Sans` (`assets/fonts/`), which is a separate, freely-licensed
  (SIL Open Font License) pixel font from Google Fonts chosen to *look* like Vampire
  Survivors' UI style - it is not Vampire Survivors' actual font, which was not
  sourced or used here.

## Credits

Built as a learning project with Claude's help, based on the game's one-page design
document.
