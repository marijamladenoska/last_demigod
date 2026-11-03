# The Last Demigod
# Top-down survival game: WASD / arrows to move, attacks are automatic.
# 1/2/3 = choose a gift on level-up, P/ESC = pause, R = restart, ENTER = next level.
# Shapes are placeholders for the Kenney sprites.

import json
import math
import os
import random
import sys

import pygame

WIDTH, HEIGHT = 1152, 648  # 16:9, same shape as the background pictures
FPS = 60
MAX_ENEMIES_ALIVE = 25  # caps the swarm so spawns can't snowball past this
ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "save.json")
DEBUG = False  # True shows collision walls with F1

# Every picture the game can use. If a file isn't in assets/, the game falls back
# to plain shapes/colors instead of crashing. "bg" pictures are stretched to fill
# the window; "sprite" pictures keep their own size and transparency.
BACKGROUND_FILES = [
    "title_screen.png", "prison.png", "tartarus_arena.png",
    "styx_arena.png", "gates_arena.png",
]
SPRITE_FILES = [
    "leon.png", "elena.png", "skeleton.png", "shadow.png", "harpy.png",
    "kampe.png", "cerberus.png", "hera.png", "charon.png",
]

# Sound effects and music both live in assets/sounds/, and both are optional -
# the game just plays silently if a file is missing.
SOUND_DIR = os.path.join(ASSET_DIR, "sounds")
SOUND_NAMES = ["lightning", "hit", "enemy_death", "xp_pickup", "level_up",
               "gate_open", "boss_spawn", "win", "lose"]
MUSIC_FILES = {
    -1: "music_prison.ogg",   # -1 is the prison prologue (level_index -1)
    0: "music_level1.ogg",
    1: "music_level2.ogg",
    2: "music_level3.ogg",
}

# Background pictures are 1672 x 941. Wall positions below are written in
# picture pixels and scaled to the window, so they stay correct at any size.
IMG_W, IMG_H = 1672, 941
SX, SY = WIDTH / IMG_W, HEIGHT / IMG_H


def img_rect(x, y, w, h):
    """Convert a rectangle in picture pixels to window pixels."""
    return pygame.Rect(round(x * SX), round(y * SY), round(w * SX), round(h * SY))


# ---- Vampire Survivors sprite animations (assets/vs/) ----
VS_DIR = os.path.join(ASSET_DIR, "vs")


class Animation:
    """A sequence of frames played back using the source GIF's own per-frame
    timing. Call update(dt) every frame, then current(facing_left) to draw."""

    def __init__(self, frames, durations_ms, loop=True):
        self.frames = frames  # facing right, as downloaded
        self.flipped = [pygame.transform.flip(f, True, False) for f in frames]
        self.durations = durations_ms
        self.loop = loop
        self.index = 0
        self.timer_ms = 0.0
        self.finished = False

    def reset(self):
        self.index = 0
        self.timer_ms = 0.0
        self.finished = False

    def update(self, dt):
        if self.finished or len(self.frames) <= 1:
            return
        self.timer_ms += dt * 1000
        while self.timer_ms >= self.durations[self.index]:
            self.timer_ms -= self.durations[self.index]
            self.index += 1
            if self.index >= len(self.frames):
                if self.loop:
                    self.index = 0
                else:
                    self.index = len(self.frames) - 1
                    self.finished = True
                    break

    def current(self, facing_left=False):
        frames = self.flipped if facing_left else self.frames
        return frames[self.index] if frames else None


def load_vs_animation(folder, name, target_height, loop=True):
    """Loads assets/vs/<folder>/<name>_N.png using that folder's meta.json for
    per-frame timing, scaled with nearest-neighbour so pixels stay sharp and
    each frame is target_height tall. Returns None if anything about it is
    missing, so callers fall back to a plain shape instead of crashing."""
    meta_path = os.path.join(VS_DIR, folder, "meta.json")
    if not os.path.exists(meta_path):
        return None
    try:
        with open(meta_path) as f:
            meta = json.load(f)
        info = meta[name]
        frames = []
        for fname in info["frames"]:
            img = pygame.image.load(os.path.join(VS_DIR, folder, fname)).convert_alpha()
            scale = target_height / img.get_height()
            size = (max(1, round(img.get_width() * scale)), target_height)
            frames.append(pygame.transform.scale(img, size))
        return Animation(frames, info["durations_ms"], loop=loop)
    except (KeyError, OSError, pygame.error):
        return None


# ---- Prison (prologue before level 1) ----
# Blockers: everything the player and guards cannot walk through.
PRISON_WALLS = [
    (300, 40, 1080, 95),     # top wall
    (300, 40, 80, 800),      # left wall
    (1295, 40, 90, 800),     # right wall
    (300, 740, 445, 120),    # bottom wall, left of gate (incl. brazier)
    (925, 740, 460, 120),    # bottom wall, right of gate (incl. brazier)
    (728, 40, 34, 300),      # pillar left of the banner
    (913, 40, 34, 300),      # pillar right of the banner
    (380, 262, 240, 78),     # top-left cell railing (left of the broken door)
    (682, 262, 48, 78),      # top-left cell railing (right of the broken door)
    (945, 262, 350, 78),     # top-right cell railing (door still locked)
    (380, 495, 290, 245),    # bottom-left cell (closed)
    (1000, 495, 295, 245),   # bottom-right cell (closed)
    (410, 380, 100, 95),     # crates left
    (1180, 335, 115, 115),   # crates + barrel right
]
PRISON_GATE = (745, 700, 180, 45)   # blocks the exit until both guards are dead
PRISON_GATE_ART = (745, 705, 180, 112)
PRISON_EXIT_Y = 830                  # walking below this line leaves the prison
PRISON_START = (560, 200)            # inside the top-left cell
GUARD_SPOTS = [(840, 420), (840, 620)]

WHITE = (240, 240, 240)
GOLD = (240, 200, 80)
BLUE = (110, 190, 255)
RED = (200, 60, 60)
GREEN = (70, 200, 110)
CYAN = (90, 230, 230)
DARK = (15, 12, 22)

# ---- Level 1: Tartarus arena (tartarus_arena.png) ----
# Blockers for the stone scenery: stairs/altar, pillars, statues, arches, ruins.
# Trees and the floor's lightning-circle emblem are left walkable on purpose.
TARTARUS_WALLS = [
    (545, 0, 580, 175),      # altar steps + the two banner pillars
    (15, 0, 220, 235),       # top-left broken arch and column
    (1495, 0, 177, 235),     # top-right broken arch and column
    (1250, 85, 85, 180),     # statue, top-right
    (248, 695, 90, 210),     # statue, bottom-left
    (195, 230, 165, 105),    # stepped ruin pile, left-mid
    (538, 335, 45, 95),      # lone column, left-mid
    (552, 590, 70, 100),     # lone column + rubble, left-mid-low
    (995, 295, 45, 110),     # lone column, right of altar
    (1055, 595, 48, 90),     # lone column, right-mid-low
    (95, 550, 140, 105),     # column + rubble cluster, lower-left
    (1385, 540, 85, 115),    # column + fallen log cluster, right
    (1020, 690, 90, 80),     # small column + hedge cluster, lower-mid-right
    (1265, 720, 175, 170),   # broken arch, bottom-right
    (1530, 265, 50, 125),    # column near the trees, right edge
    (1510, 585, 55, 110),    # column, lower-right edge
    (25, 385, 75, 100),      # torch pedestal, left edge
    (1570, 385, 77, 100),    # torch pedestal, right edge
]

# ---- Level 2: River Styx (styx_arena.png) ----
# No picture exists yet, so there's nothing to line blockers up against - the
# level just uses a flat color (see LEVELS below). Once styx_arena.png is
# added to assets/, place wall rects here the same way TARTARUS_WALLS was
# done above: turn on F1 in-game to see the rects drawn over the picture,
# and nudge the numbers until they match the rocks/banks/wreckage in it.
STYX_WALLS = []

# ---- Level 3: Gates of the Underworld (gates_arena.png) ----
# Same story as STYX_WALLS: fill this in once the picture exists.
GATES_WALLS = []

# Each level is just data, so adding a level means adding one dict.
LEVELS = [
    {
        "name": "Level 1: Tartar",
        "bg": (24, 18, 32),
        "bg_image": "tartarus_arena.png",
        "walls": TARTARUS_WALLS,
        "time": 60,            # seconds to survive before the boss appears
        "enemy_speed": 70,
        "spawn_delay": 1.2,
        "boss": {"name": "Kampe", "hp": 300, "speed": 55, "radius": 34,
                 "color": (150, 60, 170), "damage": 20},
    },
    {
        "name": "Level 2: River Styx",
        "bg": (8, 28, 42),
        "bg_image": "styx_arena.png",
        "walls": STYX_WALLS,
        "time": 75,
        "enemy_speed": 95,
        "spawn_delay": 1.0,
        "boss": {"name": "Cerberus", "hp": 450, "speed": 75, "radius": 42,
                 "color": (130, 80, 30), "damage": 25},
    },
    {
        "name": "Level 3: Gates of the Underworld",
        "bg": (30, 8, 14),
        "bg_image": "gates_arena.png",
        "walls": GATES_WALLS,
        "time": 90,             # the longest, hardest wave before the final boss
        "enemy_speed": 115,
        "spawn_delay": 0.8,
        "boss": {"name": "Hera", "hp": 600, "speed": 65, "radius": 38,
                 "color": (210, 170, 40), "damage": 28},
    },
]

# Gifts from the gods. Each can be taken up to MAX_GIFT_LEVEL times.
MAX_GIFT_LEVEL = 5
GIFTS = {
    "zeus":     {"name": "Zeus' Lightning",    "desc": "Lightning hits harder and faster"},
    "trident":  {"name": "Poseidon's Trident", "desc": "Throws a trident that pierces enemies"},
    "sword":    {"name": "Ares' Sword",        "desc": "Swords circle around you"},
    "arrows":   {"name": "Apollo's Arrows",    "desc": "Shoots arrows at enemies"},
    "shield":   {"name": "Athena's Shield",    "desc": "Take 15% less damage"},
    "sandals":  {"name": "Hermes' Sandals",    "desc": "Move 12% faster"},
    "ambrosia": {"name": "Ambrosia",           "desc": "+20 max HP and heal 40"},
}


CHARON_LINES = [
    "Few demigods make it this far. Fewer make it further.",
    "The river remembers every soul that crossed it. Don't join them yet.",
    "Rest a moment. What's ahead doesn't deserve a tired blade.",
    "Hera knows you're coming now. Hurry.",
]

CHARACTERS = [
    {"key": "leon", "name": "Leon", "sprite": "leon.png", "vs_folder": "leon", "color": WHITE},
    {"key": "elena", "name": "Elena", "sprite": "elena.png", "vs_folder": "elena", "color": (235, 150, 210)},
]
PLAYER_SPRITE_HEIGHT = 44


class Player:
    def __init__(self, sprite=None, color=WHITE, anim=None):
        self.sprite = sprite          # pygame Surface, or None to draw a circle instead
        self.color = color
        self.anim = anim              # Animation (walk cycle), takes over from sprite/color
        self.pos = pygame.Vector2(WIDTH / 2, HEIGHT / 2)
        self.facing = pygame.Vector2(1, 0)  # last direction moved (for the trident)
        self.radius = 16
        self.speed = 220
        self.max_hp = 100
        self.hp = self.max_hp
        self.hit_cooldown = 0.0  # short invincibility after being hit

        # Zeus lightning (starting weapon)
        self.attack_cooldown = 0.6
        self.attack_timer = 0.0
        self.attack_range = 260
        self.damage = 12

        # XP and gifts
        self.level = 1
        self.xp = 0
        self.xp_needed = 5
        self.gifts = {}  # gift key -> level

    def gift(self, key):
        return self.gifts.get(key, 0)

    def take_damage(self, amount):
        """Returns True if the hit actually landed (False during invincibility frames)."""
        if self.hit_cooldown > 0:
            return False
        reduction = 0.15 * self.gift("shield")
        self.hp -= amount * (1 - reduction)
        self.hit_cooldown = 0.8
        return True

    def hitbox(self, pos=None):
        pos = pos or self.pos
        return pygame.Rect(pos.x - 10, pos.y - 10, 20, 20)  # smaller than the drawing so doors fit

    def update(self, dt, keys, walls=()):
        move = pygame.Vector2(
            (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT]),
            (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP]),
        )
        moving = move.length() > 0
        if moving:
            move = move.normalize()  # same speed on diagonals
            self.facing = move
        self.pos = move_with_walls(self.pos, move * self.speed * dt, walls, self.hitbox)
        self.pos.x = max(self.radius, min(WIDTH - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(HEIGHT - self.radius, self.pos.y))
        self.attack_timer -= dt
        self.hit_cooldown -= dt
        if self.anim:
            if moving:
                self.anim.update(dt)
            else:
                self.anim.reset()  # idle: hold the first frame

    def draw(self, screen):
        if self.gift("shield"):
            pygame.draw.circle(screen, (200, 200, 120), self.pos, self.radius + 6, 2)
        blink = self.hit_cooldown > 0 and int(self.hit_cooldown * 20) % 2 == 0
        if blink:
            return
        if self.anim:
            frame = self.anim.current(facing_left=self.facing.x < 0)
            screen.blit(frame, frame.get_rect(center=self.pos))
        elif self.sprite:
            rect = self.sprite.get_rect(center=self.pos)
            screen.blit(self.sprite, rect)
        else:
            pygame.draw.circle(screen, self.color, self.pos, self.radius)
            pygame.draw.circle(screen, BLUE, self.pos, self.radius, 3)


def move_with_walls(pos, step, walls, hitbox):
    """Move one axis at a time, so you slide along a wall instead of sticking to it."""
    new = pygame.Vector2(pos)
    new.x += step.x
    if hitbox(new).collidelist(walls) != -1:
        new.x = pos.x
    new.y += step.y
    if hitbox(new).collidelist(walls) != -1:
        new.y = pos.y
    return new


class Enemy:
    def __init__(self, speed, hp, sprite=None, color=RED):
        # spawn just outside a random screen edge
        side = random.choice("tblr")
        if side == "t":
            self.pos = pygame.Vector2(random.randint(0, WIDTH), -20)
        elif side == "b":
            self.pos = pygame.Vector2(random.randint(0, WIDTH), HEIGHT + 20)
        elif side == "l":
            self.pos = pygame.Vector2(-20, random.randint(0, HEIGHT))
        else:
            self.pos = pygame.Vector2(WIDTH + 20, random.randint(0, HEIGHT))
        self.radius = 13
        self.speed = speed
        self.hp = hp
        self.damage = 8
        self.sprite = sprite    # picture to draw instead of a colored circle
        self.color = color

    def hitbox(self, pos=None):
        pos = pos or self.pos
        r = self.radius
        return pygame.Rect(pos.x - r, pos.y - r, r * 2, r * 2)

    def apply_damage(self, amount):
        self.hp -= amount

    def update(self, dt, target, walls=()):
        direction = target - self.pos
        if direction.length() > 0:
            step = direction.normalize() * self.speed * dt
            self.pos = move_with_walls(self.pos, step, walls, self.hitbox)

    def draw(self, screen):
        if self.sprite:
            screen.blit(self.sprite, self.sprite.get_rect(center=self.pos))
        else:
            pygame.draw.circle(screen, self.color, self.pos, self.radius)


class Skeleton(Enemy):
    """The common enemy: walks straight at you, nothing fancy."""

    def __init__(self, speed, hp, sprite=None):
        super().__init__(speed, hp, sprite, color=(225, 220, 195))


class Shadow(Enemy):
    """Fast and fragile - rushes in quickly but dies in a hit or two."""

    def __init__(self, speed, hp, sprite=None):
        super().__init__(speed * 1.6, max(6, int(hp * 0.5)), sprite, color=(90, 60, 130))
        self.radius = 10


class Harpy(Enemy):
    """Flies, so it ignores ground walls, and zigzags instead of flying straight in."""

    def __init__(self, speed, hp, sprite=None):
        super().__init__(speed, hp, sprite, color=(210, 130, 60))
        self.wobble_t = random.uniform(0, 10)

    def update(self, dt, target, walls=()):
        self.wobble_t += dt
        direction = target - self.pos
        if direction.length() == 0:
            return
        direction = direction.normalize()
        perpendicular = pygame.Vector2(-direction.y, direction.x)
        wobble = perpendicular * math.sin(self.wobble_t * 6) * 0.6
        move_dir = direction + wobble
        if move_dir.length() > 0:
            self.pos += move_dir.normalize() * self.speed * dt


class Guard(Enemy):
    """Skeleton guard in the prison. Stands still until the player comes close."""

    def __init__(self, pos):
        super().__init__(speed=85, hp=40)
        self.pos = pygame.Vector2(pos)
        self.radius = 15
        self.awake = False

    def hitbox(self, pos=None):
        pos = pos or self.pos
        return pygame.Rect(pos.x - 10, pos.y - 10, 20, 20)

    def update(self, dt, target, walls=()):
        if self.pos.distance_to(target) < 230:
            self.awake = True
        if not self.awake:
            return
        direction = target - self.pos
        if direction.length() > 0:
            step = direction.normalize() * self.speed * dt
            self.pos = move_with_walls(self.pos, step, walls, self.hitbox)

    def draw(self, screen):
        pygame.draw.circle(screen, (225, 220, 195), self.pos, self.radius)
        pygame.draw.circle(screen, (120, 30, 30), self.pos, self.radius, 3)


class Boss:
    """Base boss: chases the player, then every few seconds winds up a big
    attack (telegraph_timer, with a warning), fires it (unleash), and stands
    still for a moment afterward (stun_timer) - that pause is its weak spot,
    where it takes extra damage. Each boss subclass fills in its own attack."""

    def __init__(self, cfg):
        self.name = cfg["name"]
        self.max_hp = self.hp = cfg["hp"]
        self.speed = cfg["speed"]
        self.radius = cfg["radius"]
        self.color = cfg["color"]
        self.damage = cfg["damage"]
        self.sprite = None
        self.pos = pygame.Vector2(WIDTH / 2, -50)
        self.projectiles = []       # fireballs etc, reuses the Projectile class
        self.attack_timer = 3.0     # time left until the next attack begins
        self.telegraph_timer = 0.0  # >0: warning up, hasn't hit yet
        self.stun_timer = 0.0       # >0: just attacked, standing still (weak spot)
        self.warning = ""           # text shown on screen while telegraphing
        self.attack_event = None    # one-frame flag the Game reads to apply a hit

    @property
    def vulnerable(self):
        return self.stun_timer > 0

    def hitbox(self, pos=None):
        pos = pos or self.pos
        r = self.radius
        return pygame.Rect(pos.x - r, pos.y - r, r * 2, r * 2)

    def apply_damage(self, amount):
        if self.vulnerable:
            amount *= 1.5  # the weak spot: bonus damage while stunned
        self.hp -= amount

    def current_speed(self, dt):
        return self.speed

    def start_attack(self, target):
        """Overridden per boss: set self.warning and self.telegraph_timer."""

    def unleash(self, target):
        """Overridden per boss: actually deal the attack, then stand still."""
        self.stun_timer = 2.0
        self.warning = ""

    def update(self, dt, target, walls=()):
        self.attack_event = None
        if self.stun_timer > 0:
            self.stun_timer -= dt
        elif self.telegraph_timer > 0:
            self.telegraph_timer -= dt
            if self.telegraph_timer <= 0:
                self.unleash(target)
        else:
            self.attack_timer -= dt
            direction = target - self.pos
            if direction.length() > 0:
                step = direction.normalize() * self.current_speed(dt) * dt
                self.pos = move_with_walls(self.pos, step, walls, self.hitbox)
            if self.attack_timer <= 0:
                self.start_attack(target)
        for proj in self.projectiles:
            proj.update(dt)
        self.projectiles = [p for p in self.projectiles if p.alive]

    def draw(self, screen):
        color = (255, 255, 255) if self.vulnerable else self.color
        if self.sprite:
            screen.blit(self.sprite, self.sprite.get_rect(center=self.pos))
        else:
            pygame.draw.circle(screen, color, self.pos, self.radius)
            pygame.draw.circle(screen, WHITE, self.pos, self.radius, 3)
        for proj in self.projectiles:
            proj.draw(screen)


class Kampe(Boss):
    """Winds up, then swings all the way around herself - stay out of range."""

    def start_attack(self, target):
        self.warning = "Kampe swings!"
        self.telegraph_timer = 0.9

    def unleash(self, target):
        self.attack_event = {"kind": "swing", "radius": self.radius + 90, "damage": self.damage}
        self.stun_timer = 2.0
        self.warning = ""
        self.attack_timer = 4.5

    def draw(self, screen):
        super().draw(screen)
        if self.telegraph_timer > 0:
            pygame.draw.circle(screen, (255, 80, 80), self.pos, self.radius + 90, 3)


class Cerberus(Boss):
    """Lunges at the player between attacks, and breathes 3 fireballs."""

    def __init__(self, cfg):
        super().__init__(cfg)
        self.lunge_cooldown = 3.0
        self.lunge_left = 0.0

    def current_speed(self, dt):
        self.lunge_cooldown -= dt
        if self.lunge_cooldown <= 0:
            self.lunge_left = 0.6
            self.lunge_cooldown = 3.0
        if self.lunge_left > 0:
            self.lunge_left -= dt
            return self.speed * 3
        return self.speed

    def start_attack(self, target):
        self.warning = "Cerberus breathes fire!"
        self.telegraph_timer = 1.0

    def unleash(self, target):
        direction = target - self.pos
        if direction.length() == 0:
            direction = pygame.Vector2(0, 1)
        direction = direction.normalize()
        for angle in (-18, 0, 18):
            self.projectiles.append(Projectile(
                self.pos, direction.rotate(angle), 260, self.damage * 0.6,
                (255, 120, 40), length=20))
        self.stun_timer = 2.0
        self.warning = ""
        self.attack_timer = 5.0


class Hera(Boss):
    """Final boss: cycles through three attacks - a feather volley, summoning
    shadows, and a wave of divine energy - then stands still afterward."""

    ATTACKS = ["feathers", "summon", "wave"]

    def __init__(self, cfg):
        super().__init__(cfg)
        self.attack_index = 0
        self.pending_attack = "feathers"

    def start_attack(self, target):
        self.pending_attack = self.ATTACKS[self.attack_index % len(self.ATTACKS)]
        self.attack_index += 1
        self.warning = {
            "feathers": "Hera hurls peacock feathers!",
            "summon": "Hera summons shadows!",
            "wave": "Hera unleashes a wave of energy!",
        }[self.pending_attack]
        self.telegraph_timer = 1.1

    def unleash(self, target):
        if self.pending_attack == "feathers":
            direction = target - self.pos
            if direction.length() == 0:
                direction = pygame.Vector2(0, 1)
            direction = direction.normalize()
            for angle in (-40, -20, 0, 20, 40):
                self.projectiles.append(Projectile(
                    self.pos, direction.rotate(angle), 300, self.damage * 0.5,
                    (160, 90, 200), length=18))
        elif self.pending_attack == "summon":
            self.attack_event = {"kind": "summon", "count": 3}
        else:
            self.attack_event = {"kind": "wave", "radius": self.radius + 130, "damage": self.damage}
        self.stun_timer = 2.0
        self.warning = ""
        self.attack_timer = 5.5


BOSS_CLASSES = {"Kampe": Kampe, "Cerberus": Cerberus, "Hera": Hera}


class DamageNumber:
    """A small number that pops up and floats away when something gets hit."""

    def __init__(self, pos, amount, color=WHITE):
        self.pos = pygame.Vector2(pos)
        self.text = str(int(amount))
        self.color = color
        self.age = 0.0
        self.duration = 0.6

    @property
    def alive(self):
        return self.age < self.duration

    def update(self, dt):
        self.age += dt
        self.pos.y -= 40 * dt  # float upward as it fades

    def draw(self, screen, font):
        surf = font.render(self.text, True, self.color)
        surf.set_alpha(int(255 * max(0, 1 - self.age / self.duration)))
        screen.blit(surf, surf.get_rect(center=self.pos))


class XPOrb:
    def __init__(self, pos, value=1):
        self.pos = pygame.Vector2(pos)
        self.value = value
        self.radius = 5

    def update(self, dt, player):
        # orbs get pulled toward the player when close
        dist = self.pos.distance_to(player.pos)
        if 0 < dist < 100:
            self.pos += (player.pos - self.pos).normalize() * 300 * dt

    def draw(self, screen):
        pygame.draw.circle(screen, CYAN, self.pos, self.radius)


class Projectile:
    """Used by Apollo's arrows and Poseidon's trident."""

    def __init__(self, pos, direction, speed, damage, color, pierce=False, length=14):
        self.pos = pygame.Vector2(pos)
        self.vel = direction.normalize() * speed
        self.damage = damage
        self.color = color
        self.pierce = pierce     # trident goes through enemies
        self.length = length
        self.radius = 6
        self.already_hit = []    # so a piercing trident hits each enemy only once
        self.alive = True

    def update(self, dt):
        self.pos += self.vel * dt
        if not (-50 < self.pos.x < WIDTH + 50 and -50 < self.pos.y < HEIGHT + 50):
            self.alive = False

    def draw(self, screen):
        tail = self.pos - self.vel.normalize() * self.length
        pygame.draw.line(screen, self.color, tail, self.pos, 4)


class Game:
    def __init__(self):
        pygame.init()

        # settings + best score, loaded before the window so a saved
        # fullscreen preference can be applied right away
        self.music_volume = 0.6
        self.sound_volume = 0.6
        self.muted = False
        self.fullscreen = False
        self.best_level_index = -1  # -1 = never left the prison yet
        self.best_time = 0.0
        self.load_game()

        flags = pygame.FULLSCREEN if self.fullscreen else 0
        self.window = pygame.display.set_mode((WIDTH, HEIGHT), flags)  # the real OS window
        self.screen = self.window                                # what draw() draws to
        self.shake_surface = pygame.Surface((WIDTH, HEIGHT))      # used while screen-shaking
        pygame.display.set_caption("The Last Demigod")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 28)
        self.small_font = pygame.font.SysFont(None, 22)
        self.big_font = pygame.font.SysFont(None, 72)
        self.images = {}
        for name in BACKGROUND_FILES:
            path = os.path.join(ASSET_DIR, name)
            if os.path.exists(path):  # game still runs with plain colors if a picture is missing
                self.images[name] = pygame.transform.smoothscale(
                    pygame.image.load(path).convert(), (WIDTH, HEIGHT))
        for name in SPRITE_FILES:
            path = os.path.join(ASSET_DIR, name)
            if os.path.exists(path):  # game still runs with plain shapes if a sprite is missing
                self.images[name] = pygame.image.load(path).convert_alpha()
        self.anim_frame_cache = {}  # (folder, name, height) -> (frames, durations_ms) or None

        try:  # some machines have no audio device - the game should still run
            pygame.mixer.init()
            self.mixer_ok = True
        except pygame.error:
            self.mixer_ok = False
        self.sounds = {}
        if self.mixer_ok:
            for name in SOUND_NAMES:
                path = os.path.join(SOUND_DIR, name + ".wav")
                if os.path.exists(path):
                    self.sounds[name] = pygame.mixer.Sound(path)
        self.current_music = None

        self.show_walls = DEBUG  # F1 can still toggle this, see handle_key()
        self.prev_state = "playing"

        # main menu
        self.state = "menu"
        self.menu_items = ["Start", "Controls", "Settings", "Quit"]
        self.menu_index = 0
        self.settings_index = 0
        self.char_index = 0  # which character is highlighted on the select screen
        self.player_char = "leon"
        self.player = None
        self.pause_items = ["Resume", "Restart level", "Main menu", "Quit"]
        self.pause_index = 0

    def get_animation(self, folder, name, height, loop=True):
        """Returns a fresh Animation for this sprite, reusing already-loaded
        (and already-scaled) frames so the same files aren't read from disk
        and rescaled every time a new enemy/player is created."""
        key = (folder, name, height)
        if key not in self.anim_frame_cache:
            anim = load_vs_animation(folder, name, height)
            self.anim_frame_cache[key] = (anim.frames, anim.durations) if anim else None
        cached = self.anim_frame_cache[key]
        if cached is None:
            return None
        frames, durations = cached
        return Animation(frames, durations, loop=loop)

    def load_game(self):
        """Read saved settings/best score, if save.json exists. Keeps the
        defaults already set if the file is missing or can't be read."""
        try:
            with open(SAVE_PATH) as f:
                data = json.load(f)
        except (OSError, ValueError):
            return
        self.music_volume = data.get("music_volume", self.music_volume)
        self.sound_volume = data.get("sound_volume", self.sound_volume)
        self.muted = data.get("muted", self.muted)
        self.fullscreen = data.get("fullscreen", self.fullscreen)
        self.best_level_index = data.get("best_level_index", self.best_level_index)
        self.best_time = data.get("best_time", self.best_time)

    def save_game(self):
        data = {
            "music_volume": self.music_volume,
            "sound_volume": self.sound_volume,
            "muted": self.muted,
            "fullscreen": self.fullscreen,
            "best_level_index": self.best_level_index,
            "best_time": self.best_time,
        }
        try:
            with open(SAVE_PATH, "w") as f:
                json.dump(data, f)
        except OSError:
            pass  # can't write to disk here - not worth crashing the game over

    def update_best_score(self):
        """Called when a run ends (win or death). Keeps the best of all runs."""
        improved = False
        if self.level_index > self.best_level_index:
            self.best_level_index = self.level_index
            improved = True
        if self.run_time > self.best_time:
            self.best_time = self.run_time
            improved = True
        if improved:
            self.save_game()

    def reset(self):
        """Full restart from the prison, with whichever character was chosen."""
        char = next(c for c in CHARACTERS if c["key"] == self.player_char)
        sprite = self.images.get(char["sprite"])
        anim = self.get_animation(char["vs_folder"], "walk", PLAYER_SPRITE_HEIGHT)
        self.player = Player(sprite=sprite, color=char["color"], anim=anim)
        self.run_time = 0.0
        self.run_kills = 0
        self.end_items = ["Retry level", "Main menu"]
        self.end_index = 0
        self.charon_line = ""
        self.toast_text = ""
        self.toast_timer = 0.0
        self.damage_numbers = []
        self.flash_timer = 0.0   # white screen flash when the player is hit
        self.shake_timer = 0.0   # screen shake when the player is hit
        self.start_prison()

    # ---- prison prologue ----
    def start_prison(self):
        self.walls = [img_rect(*r) for r in PRISON_WALLS]
        self.gate = img_rect(*PRISON_GATE)
        self.gate_open = False
        self.level = {"name": "Escape the prison", "bg": (20, 16, 28), "bg_image": "prison.png"}
        self.level_index = -1
        self.enemies = [Guard((x * SX, y * SY)) for x, y in GUARD_SPOTS]
        self.boss = None
        self.orbs = []
        self.projectiles = []
        self.bolts = []
        self.choices = []
        self.player.pos = pygame.Vector2(PRISON_START[0] * SX, PRISON_START[1] * SY)
        self.banner_timer = 3.0
        self.state = "prison"
        self.play_music(-1)

    def update_prison(self, dt):
        p = self.player
        self.run_time += dt
        self.tick_effects(dt)
        walls = self.walls + ([] if self.gate_open else [self.gate])
        p.update(dt, pygame.key.get_pressed(), walls)
        self.banner_timer -= dt
        self.zeus_lightning()
        for g in self.enemies:
            g.update(dt, p.pos, walls)
            if p.pos.distance_to(g.pos) < p.radius + g.radius:
                self.hit_player(g.damage)
        dead = [g for g in self.enemies if g.hp <= 0]
        self.run_kills += len(dead)
        for g in dead:
            self.orbs.append(XPOrb(g.pos))
            self.play_sound("enemy_death")
        self.enemies = [g for g in self.enemies if g.hp > 0]
        self.bolts = [(a, b, t - dt) for a, b, t in self.bolts if t - dt > 0]
        self.collect_orbs(dt)

        if not self.enemies and not self.gate_open:
            self.gate_open = True
            self.banner_timer = 2.5
            self.play_sound("gate_open")
        if self.gate_open and p.pos.y > PRISON_EXIT_Y * SY:
            self.start_level(0)
        if p.hp <= 0:
            self.end_index = 0
            self.state = "gameover"
            self.play_sound("lose")
            self.update_best_score()

    def start_level(self, index):
        self.level_index = index
        self.level = LEVELS[index]
        self.walls = [img_rect(*r) for r in self.level["walls"]]
        self.enemies = []
        self.boss = None
        self.orbs = []
        self.projectiles = []
        self.bolts = []  # (start, end, time_left) lightning visuals
        self.time_left = self.level["time"]
        self.spawn_timer = 0.0
        self.arrow_timer = 0.0
        self.trident_timer = 0.0
        self.sword_angle = 0.0
        self.choices = []  # the 3 gifts offered on level-up
        self.player.hp = self.player.max_hp  # healed between levels
        self.player.pos = pygame.Vector2(WIDTH / 2, HEIGHT / 2)
        self.banner_timer = 2.5  # shows the level name for a moment
        self.state = "playing"  # playing / paused / choosing / gameover / level_done / win
        self.play_music(index)

    def clear_spawn_x(self, walls):
        """An x position whose path down from the top of the screen isn't
        already blocked by a wall, so a boss never spawns stuck in scenery."""
        for _ in range(30):
            x = random.randint(60, WIDTH - 60)
            probe = pygame.Rect(x - 40, 0, 80, 200)  # the area it falls through
            if probe.collidelist(walls) == -1:
                return x
        return WIDTH / 2  # fallback if the level is extremely crowded

    def hit_player(self, amount):
        """Damage the player and trigger the hit-flash/screen-shake if it lands."""
        if self.player.take_damage(amount):
            self.flash_timer = 0.12
            self.shake_timer = 0.2
            self.play_sound("hit")

    def resolve_boss_attack(self, event):
        """Apply whatever a boss's unleash() just set up in attack_event."""
        p = self.player
        if event["kind"] in ("swing", "wave"):
            if p.pos.distance_to(self.boss.pos) <= event["radius"]:
                self.hit_player(event["damage"])
        elif event["kind"] == "summon":
            for _ in range(event["count"]):
                shadow = Shadow(self.level["enemy_speed"], 15, self.images.get("shadow.png"))
                offset = pygame.Vector2(random.randint(-60, 60), random.randint(-60, 60))
                shadow.pos = self.boss.pos + offset
                self.enemies.append(shadow)

    def targets(self):
        return self.enemies + ([self.boss] if self.boss else [])

    # ---- difficulty: every 30 s more and faster enemies ----
    def difficulty_step(self):
        elapsed = self.level["time"] - self.time_left
        return int(elapsed // 30)

    def spawn_enemies(self, dt):
        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            step = self.difficulty_step()
            speed = self.level["enemy_speed"] + 25 * step + random.randint(0, 20)
            if len(self.enemies) < MAX_ENEMIES_ALIVE:
                for _ in range(1 + step):
                    self.enemies.append(self.make_enemy(speed, step))
            self.spawn_timer = max(0.5, self.level["spawn_delay"] - 0.25 * step)

    def make_enemy(self, speed, step):
        """Pick an enemy type. Skeletons are the baseline; shadows and harpies
        become more common later in the fight and in later levels."""
        rarity = step + self.level_index * 2
        weights = {"skeleton": 5, "shadow": 1 + rarity, "harpy": rarity}
        kind = random.choices(list(weights), weights=list(weights.values()))[0]
        if kind == "skeleton":
            return Skeleton(speed, 20, self.images.get("skeleton.png"))
        if kind == "shadow":
            return Shadow(speed, 20, self.images.get("shadow.png"))
        return Harpy(speed, 20, self.images.get("harpy.png"))

    # ---- weapons ----
    def zeus_lightning(self):
        p = self.player
        targets = self.targets()
        if p.attack_timer > 0 or not targets:
            return
        nearest = min(targets, key=lambda e: p.pos.distance_to(e.pos))
        if p.pos.distance_to(nearest.pos) <= p.attack_range:
            lvl = p.gift("zeus")
            dmg = p.damage + 5 * lvl
            nearest.apply_damage(dmg)
            self.damage_numbers.append(DamageNumber(nearest.pos, dmg, GOLD))
            self.bolts.append((p.pos.copy(), nearest.pos.copy(), 0.12))
            self.play_sound("lightning")
            p.attack_timer = p.attack_cooldown * (0.85 ** lvl)

    def apollo_arrows(self, dt):
        lvl = self.player.gift("arrows")
        targets = self.targets()
        if lvl == 0 or not targets:
            return
        self.arrow_timer -= dt
        if self.arrow_timer <= 0:
            # one arrow per level, each at a random enemy
            for target in random.sample(targets, min(lvl, len(targets))):
                direction = target.pos - self.player.pos
                if direction.length() > 0:
                    self.projectiles.append(Projectile(self.player.pos, direction, 500, 12, GOLD))
            self.arrow_timer = 1.2

    def poseidon_trident(self, dt):
        lvl = self.player.gift("trident")
        if lvl == 0:
            return
        self.trident_timer -= dt
        if self.trident_timer <= 0:
            self.projectiles.append(Projectile(self.player.pos, self.player.facing, 420,
                                               15 + 8 * lvl, CYAN, pierce=True, length=30))
            self.trident_timer = max(0.6, 2.2 - 0.3 * lvl)

    def sword_positions(self):
        lvl = self.player.gift("sword")
        return [self.player.pos + pygame.Vector2(70, 0).rotate(self.sword_angle + i * 360 / lvl)
                for i in range(lvl)]

    def ares_sword(self, dt):
        if self.player.gift("sword") == 0:
            return
        self.sword_angle = (self.sword_angle + 200 * dt) % 360
        for blade in self.sword_positions():
            for t in self.targets():
                if blade.distance_to(t.pos) < 14 + t.radius:
                    t.apply_damage(60 * dt)  # damage per second while touching

    def update_projectiles(self, dt):
        for proj in self.projectiles:
            proj.update(dt)
            for t in self.targets():
                if t in proj.already_hit:
                    continue
                if proj.pos.distance_to(t.pos) < proj.radius + t.radius:
                    t.apply_damage(proj.damage)
                    self.damage_numbers.append(DamageNumber(t.pos, proj.damage, proj.color))
                    proj.already_hit.append(t)
                    if not proj.pierce:
                        proj.alive = False
                        break
        self.projectiles = [pr for pr in self.projectiles if pr.alive]

    # ---- XP and level-up ----
    def collect_orbs(self, dt):
        p = self.player
        for orb in self.orbs:
            orb.update(dt, p)
        collected = [o for o in self.orbs if o.pos.distance_to(p.pos) < p.radius + o.radius]
        for orb in collected:
            p.xp += orb.value
            self.orbs.remove(orb)
            self.play_sound("xp_pickup")
        if p.xp >= p.xp_needed:
            p.xp -= p.xp_needed
            p.level += 1
            p.xp_needed = int(p.xp_needed * 1.5) + 2
            self.play_sound("level_up")
            self.offer_gifts()

    def offer_gifts(self):
        available = [k for k in GIFTS if self.player.gift(k) < MAX_GIFT_LEVEL]
        if not available:
            # every gift is already level 5 - heal instead of doing nothing
            self.player.hp = min(self.player.max_hp, self.player.hp + 30)
            self.show_toast("All gifts mastered! Healed instead.")
            return
        self.choices = random.sample(available, min(3, len(available)))
        self.prev_state = self.state
        self.state = "choosing"

    def show_toast(self, text, duration=2.0):
        self.toast_text = text
        self.toast_timer = duration

    def play_sound(self, name):
        if not self.mixer_ok or self.muted:
            return
        sound = self.sounds.get(name)
        if sound:
            sound.set_volume(self.sound_volume)
            sound.play()

    def play_music(self, key):
        """key is the level_index for the scene that just started (-1 = prison)."""
        if not self.mixer_ok or key == self.current_music:
            return
        self.current_music = key
        filename = MUSIC_FILES.get(key)
        path = os.path.join(SOUND_DIR, filename) if filename else None
        if path and os.path.exists(path):
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(0 if self.muted else self.music_volume)
            pygame.mixer.music.play(-1)
        else:
            pygame.mixer.music.stop()

    def toggle_mute(self):
        self.muted = not self.muted
        if self.mixer_ok:
            pygame.mixer.music.set_volume(0 if self.muted else self.music_volume)
        self.show_toast("Muted" if self.muted else "Unmuted", duration=1.0)
        self.save_game()

    def tick_effects(self, dt):
        """Advance short-lived visual effects: toast text, hit flash/shake, floating numbers."""
        self.toast_timer -= dt
        self.flash_timer -= dt
        self.shake_timer -= dt
        for dn in self.damage_numbers:
            dn.update(dt)
        self.damage_numbers = [dn for dn in self.damage_numbers if dn.alive]

    def choose_gift(self, index):
        if index >= len(self.choices):
            return
        key = self.choices[index]
        p = self.player
        p.gifts[key] = p.gift(key) + 1
        if key == "sandals":
            p.speed *= 1.12
        elif key == "ambrosia":
            p.max_hp += 20
            p.hp = min(p.max_hp, p.hp + 40)
        self.choices = []
        self.state = self.prev_state

    # ---- main update ----
    def update(self, dt):
        keys = pygame.key.get_pressed()
        p = self.player
        self.run_time += dt
        self.tick_effects(dt)
        p.update(dt, keys, self.walls)
        if self.boss is None:
            self.spawn_enemies(dt)
        self.banner_timer -= dt

        self.zeus_lightning()
        self.apollo_arrows(dt)
        self.poseidon_trident(dt)
        self.ares_sword(dt)
        self.update_projectiles(dt)

        for e in self.enemies:
            e.update(dt, p.pos, self.walls)
            if p.pos.distance_to(e.pos) < p.radius + e.radius:
                self.hit_player(e.damage)
        if self.boss:
            self.boss.update(dt, p.pos, self.walls)
            if p.pos.distance_to(self.boss.pos) < p.radius + self.boss.radius:
                self.hit_player(self.boss.damage)
            event = self.boss.attack_event
            if event:
                self.resolve_boss_attack(event)
            for proj in self.boss.projectiles:
                if proj.alive and p.pos.distance_to(proj.pos) < p.radius + proj.radius:
                    self.hit_player(proj.damage)
                    proj.alive = False

        # dead enemies drop XP orbs
        dead = [e for e in self.enemies if e.hp <= 0]
        self.run_kills += len(dead)
        for e in dead:
            self.orbs.append(XPOrb(e.pos))
            self.play_sound("enemy_death")
        self.enemies = [e for e in self.enemies if e.hp > 0]
        self.bolts = [(a, b, t - dt) for a, b, t in self.bolts if t - dt > 0]
        self.collect_orbs(dt)

        # timer runs out -> boss arrives; killing the boss finishes the level
        if self.boss is None:
            self.time_left -= dt
            if self.time_left <= 0:
                boss_cfg = self.level["boss"]
                self.boss = BOSS_CLASSES[boss_cfg["name"]](boss_cfg)
                self.boss.sprite = self.images.get(boss_cfg["name"].lower() + ".png")
                self.boss.pos.x = self.clear_spawn_x(self.walls)
                self.play_sound("boss_spawn")
        elif self.boss.hp <= 0:
            self.run_kills += 1
            self.end_index = 0
            if self.level_index < len(LEVELS) - 1:
                self.state = "level_done"
            else:
                self.state = "win"
                self.play_sound("win")
                self.update_best_score()

        if p.hp <= 0:
            self.end_index = 0
            self.state = "gameover"
            self.play_sound("lose")
            self.update_best_score()

    # ---- drawing ----
    def draw_text(self, text, font, color, center):
        img = font.render(text, True, color)
        self.screen.blit(img, img.get_rect(center=center))

    def draw_hud(self):
        p = self.player
        # HP bar
        pygame.draw.rect(self.screen, (60, 20, 20), (20, 20, 200, 18))
        pygame.draw.rect(self.screen, GREEN, (20, 20, 200 * max(p.hp, 0) / p.max_hp, 18))
        # XP bar along the bottom
        pygame.draw.rect(self.screen, DARK, (0, HEIGHT - 10, WIDTH, 10))
        pygame.draw.rect(self.screen, CYAN, (0, HEIGHT - 10, WIDTH * p.xp / p.xp_needed, 10))
        self.draw_text(f"LV {p.level}", self.font, CYAN, (WIDTH - 50, 28))
        # timer or boss bar
        if self.boss:
            bw = 400
            pygame.draw.rect(self.screen, (60, 20, 20), (WIDTH // 2 - bw // 2, 20, bw, 18))
            pygame.draw.rect(self.screen, (170, 60, 190),
                             (WIDTH // 2 - bw // 2, 20, bw * max(self.boss.hp, 0) / self.boss.max_hp, 18))
            self.draw_text(self.boss.name, self.font, WHITE, (WIDTH // 2, 55))
            if self.boss.warning:
                self.draw_text(self.boss.warning, self.font, (255, 90, 90), (WIDTH // 2, 80))
            elif self.boss.vulnerable:
                self.draw_text("Weak spot! Attack now", self.font, (255, 255, 120), (WIDTH // 2, 80))
        else:
            self.draw_text(f"{max(0, math.ceil(self.time_left))}s", self.font, WHITE, (WIDTH // 2, 28))
        if self.banner_timer > 0:
            self.draw_text(self.level["name"], self.big_font, WHITE, (WIDTH // 2, HEIGHT // 3))

    def draw_prison_hud(self):
        p = self.player
        pygame.draw.rect(self.screen, (60, 20, 20), (20, 20, 200, 18))
        pygame.draw.rect(self.screen, GREEN, (20, 20, 200 * max(p.hp, 0) / p.max_hp, 18))
        if self.gate_open:
            goal = "The gate is open! Escape through the bottom"
        else:
            goal = f"Kill the guards: {2 - len(self.enemies)}/2"
        self.draw_text(goal, self.font, GOLD, (WIDTH // 2, 28))
        if self.banner_timer > 0 and not self.gate_open:
            self.draw_text("The lightning broke your cell door...", self.font, WHITE, (WIDTH // 2, HEIGHT - 40))

    def gift_summary(self):
        parts = [f"{GIFTS[k]['name']} Lv{v}" for k, v in self.player.gifts.items()]
        if not parts:
            return "none"
        if len(parts) > 4:
            parts = parts[:4] + [f"+{len(parts) - 4} more"]
        return ", ".join(parts)

    def draw_end_screen(self, title, color):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))
        self.draw_text(title, self.big_font, color, (WIDTH // 2, 100))
        level_name = self.level["name"] if self.level_index >= 0 else "The Prison"
        minutes, seconds = divmod(int(self.run_time), 60)
        stats = [
            f"Reached: {level_name}",
            f"Time survived: {minutes:02d}:{seconds:02d}",
            f"Enemies defeated: {self.run_kills}",
            f"Gifts: {self.gift_summary()}",
        ]
        for i, line in enumerate(stats):
            self.draw_text(line, self.small_font, WHITE, (WIDTH // 2, 210 + i * 30))
        for i, label in enumerate(self.end_items):
            item_color = GOLD if i == self.end_index else WHITE
            text = ("> " + label + " <") if i == self.end_index else label
            self.draw_text(text, self.font, item_color, (WIDTH // 2, 380 + i * 50))

    def draw_paused(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))
        self.draw_text("PAUSED", self.big_font, WHITE, (WIDTH // 2, 170))
        for i, label in enumerate(self.pause_items):
            color = GOLD if i == self.pause_index else WHITE
            text = ("> " + label + " <") if i == self.pause_index else label
            self.draw_text(text, self.font, color, (WIDTH // 2, 280 + i * 50))

    def draw_gift_choice(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))
        self.draw_text("A gift from the gods!", self.big_font, GOLD, (WIDTH // 2, 120))
        card_w, card_h, gap = 260, 200, 30
        start_x = WIDTH // 2 - (3 * card_w + 2 * gap) // 2
        for i, key in enumerate(self.choices):
            x = start_x + i * (card_w + gap)
            rect = pygame.Rect(x, 220, card_w, card_h)
            pygame.draw.rect(self.screen, DARK, rect, border_radius=10)
            pygame.draw.rect(self.screen, GOLD, rect, 2, border_radius=10)
            cx = rect.centerx
            self.draw_text(f"[{i + 1}]", self.font, GOLD, (cx, 250))
            self.draw_text(GIFTS[key]["name"], self.font, WHITE, (cx, 295))
            self.draw_text(GIFTS[key]["desc"], self.small_font, (190, 190, 190), (cx, 335))
            lvl = self.player.gift(key)
            label = "NEW" if lvl == 0 else f"Level {lvl} -> {lvl + 1}"
            self.draw_text(label, self.small_font, CYAN, (cx, 380))

    def draw_menu_background(self):
        bg = self.images.get("title_screen.png")
        if bg:
            self.screen.blit(bg, (0, 0))
        else:
            self.screen.fill(DARK)

    def draw_menu_list(self, title, items, index, hint=""):
        self.draw_menu_background()
        self.draw_text(title, self.big_font, GOLD, (WIDTH // 2, 140))
        for i, label in enumerate(items):
            color = GOLD if i == index else WHITE
            text = ("> " + label + " <") if i == index else label
            self.draw_text(text, self.font, color, (WIDTH // 2, 280 + i * 50))
        if hint:
            self.draw_text(hint, self.small_font, (170, 170, 170), (WIDTH // 2, HEIGHT - 40))

    def draw_menu(self):
        self.draw_menu_list("THE LAST DEMIGOD", self.menu_items, self.menu_index,
                             "W/S or arrows to move, ENTER to select")

    def draw_controls(self):
        self.draw_menu_background()
        self.draw_text("CONTROLS", self.big_font, GOLD, (WIDTH // 2, 110))
        lines = [
            "WASD or Arrow Keys - move",
            "Attacks happen automatically - just get close to enemies",
            "1 / 2 / 3 - pick a gift from the gods when you level up",
            "P or ESC - pause the game",
            "M - mute/unmute sound",
            "ENTER - confirm on menus / continue after a cutscene",
        ]
        for i, line in enumerate(lines):
            self.draw_text(line, self.font, WHITE, (WIDTH // 2, 210 + i * 45))
        self.draw_text("Press ENTER or ESC to go back", self.small_font,
                        (170, 170, 170), (WIDTH // 2, HEIGHT - 40))

    def draw_settings(self):
        items = [
            f"Music volume: {round(self.music_volume * 100)}%",
            f"Sound volume: {round(self.sound_volume * 100)}%",
            f"Fullscreen: {'On' if self.fullscreen else 'Off'}",
            "Back",
        ]
        self.draw_menu_list("SETTINGS", items, self.settings_index,
                             "LEFT/RIGHT to change, ESC to go back")
        best_name = LEVELS[self.best_level_index]["name"] if self.best_level_index >= 0 else "The Prison"
        minutes, seconds = divmod(int(self.best_time), 60)
        self.draw_text(f"Best: reached {best_name}, survived {minutes:02d}:{seconds:02d}",
                        self.small_font, CYAN, (WIDTH // 2, 540))

    def charselect_frame(self, folder, height=130):
        """A time-based animation frame for menu screens, which don't run
        through update(dt) every tick the way gameplay does."""
        anim = self.get_animation(folder, "walk", height)
        if not anim:
            return None
        total = sum(anim.durations)
        if total <= 0:
            return anim.frames[0]
        t = pygame.time.get_ticks() % total
        acc = 0
        for i, d in enumerate(anim.durations):
            acc += d
            if t < acc:
                return anim.frames[i]
        return anim.frames[-1]

    def draw_charselect(self):
        self.draw_menu_background()
        self.draw_text("CHOOSE YOUR DEMIGOD", self.big_font, GOLD, (WIDTH // 2, 110))
        card_w, card_h, gap = 260, 320, 60
        start_x = WIDTH // 2 - (2 * card_w + gap) // 2
        for i, char in enumerate(CHARACTERS):
            x = start_x + i * (card_w + gap)
            rect = pygame.Rect(x, 190, card_w, card_h)
            selected = i == self.char_index
            pygame.draw.rect(self.screen, DARK, rect, border_radius=10)
            pygame.draw.rect(self.screen, GOLD if selected else (90, 90, 100), rect, 3, border_radius=10)
            sprite = self.charselect_frame(char["vs_folder"]) or self.images.get(char["sprite"])
            center = (rect.centerx, rect.centery - 30)
            if sprite:
                self.screen.blit(sprite, sprite.get_rect(center=center))
            else:
                pygame.draw.circle(self.screen, char["color"], center, 40)
                pygame.draw.circle(self.screen, BLUE, center, 40, 3)
            self.draw_text(char["name"], self.font, WHITE, (rect.centerx, rect.bottom - 40))
        self.draw_text("LEFT/RIGHT to choose, ENTER to confirm, ESC to go back",
                        self.small_font, (170, 170, 170), (WIDTH // 2, HEIGHT - 40))

    def draw_charon(self):
        self.draw_menu_background()
        self.draw_text("CHARON", self.big_font, GOLD, (WIDTH // 2, 110))
        sprite = self.images.get("charon.png")
        center = (WIDTH // 2, 260)
        if sprite:
            self.screen.blit(sprite, sprite.get_rect(center=center))
        else:
            pygame.draw.circle(self.screen, (120, 130, 140), center, 45)
            pygame.draw.circle(self.screen, DARK, center, 45, 3)
        self.draw_text(f'"{self.charon_line}"', self.font, WHITE, (WIDTH // 2, 380))
        self.draw_text("Your wounds close. Charon ferries you onward.",
                        self.small_font, CYAN, (WIDTH // 2, 420))
        self.draw_text("Press ENTER to continue", self.small_font,
                        (170, 170, 170), (WIDTH // 2, HEIGHT - 40))

    def draw(self):
        if self.state == "charon":
            self.draw_charon()
            pygame.display.flip()
            return
        if self.state == "menu":
            self.draw_menu()
            pygame.display.flip()
            return
        if self.state == "controls":
            self.draw_controls()
            pygame.display.flip()
            return
        if self.state == "settings":
            self.draw_settings()
            pygame.display.flip()
            return
        if self.state == "charselect":
            self.draw_charselect()
            pygame.display.flip()
            return

        # draw to a separate surface while shaking, so it can be offset as a whole
        self.screen = self.shake_surface if self.shake_timer > 0 else self.window

        bg = self.images.get(self.level.get("bg_image"))
        if bg:
            self.screen.blit(bg, (0, 0))
        else:
            self.screen.fill(self.level["bg"])
        if self.level_index == -1 and self.gate_open:
            # paint over the gate bars so it looks open
            pygame.draw.rect(self.screen, (40, 34, 52), img_rect(*PRISON_GATE_ART))
        for orb in self.orbs:
            orb.draw(self.screen)
        for e in self.enemies:
            e.draw(self.screen)
        if self.boss:
            self.boss.draw(self.screen)
        for proj in self.projectiles:
            proj.draw(self.screen)
        for a, b, _ in self.bolts:
            pygame.draw.line(self.screen, GOLD, a, b, 4)
        for blade in self.sword_positions() if self.player.gift("sword") else []:
            pygame.draw.circle(self.screen, (200, 205, 215), blade, 10)
            pygame.draw.circle(self.screen, WHITE, blade, 10, 2)
        for dn in self.damage_numbers:
            dn.draw(self.screen, self.small_font)
        self.player.draw(self.screen)
        if self.show_walls:
            for w in self.walls + ([self.gate] if self.level_index == -1 and not self.gate_open else []):
                pygame.draw.rect(self.screen, (255, 0, 0), w, 2)
        if self.level_index == -1:
            self.draw_prison_hud()
        else:
            self.draw_hud()
        if self.toast_timer > 0:
            self.draw_text(self.toast_text, self.small_font, GOLD, (WIDTH // 2, HEIGHT - 60))

        center = (WIDTH // 2, HEIGHT // 2)
        below = (WIDTH // 2, HEIGHT // 2 + 40)
        if self.state == "choosing":
            self.draw_gift_choice()
        elif self.state == "paused":
            self.draw_paused()
        elif self.state == "gameover":
            self.draw_end_screen("YOU DIED", RED)
        elif self.state == "level_done":
            self.draw_text(f"{self.boss.name} DEFEATED", self.big_font, GOLD, (WIDTH // 2, HEIGHT // 2 - 20))
            self.draw_text("Press ENTER for the next level", self.font, WHITE, below)
        elif self.state == "win":
            self.draw_end_screen("YOU WIN", GOLD)

        if self.flash_timer > 0:
            flash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            flash.fill((255, 255, 255, int(160 * self.flash_timer / 0.12)))
            self.screen.blit(flash, (0, 0))

        if self.screen is self.shake_surface:
            offset = (random.randint(-8, 8), random.randint(-8, 8))
            self.window.fill((0, 0, 0))
            self.window.blit(self.shake_surface, offset)
            self.screen = self.window
        pygame.display.flip()

    # ---- menu navigation ----
    def move_index(self, index, delta, length):
        return (index + delta) % length

    def activate_menu_item(self):
        item = self.menu_items[self.menu_index]
        if item == "Start":
            self.char_index = 0
            self.state = "charselect"
        elif item == "Controls":
            self.prev_state = "menu"
            self.state = "controls"
        elif item == "Settings":
            self.settings_index = 0
            self.prev_state = "menu"
            self.state = "settings"
        elif item == "Quit":
            pygame.quit()
            sys.exit()

    def activate_settings_item(self):
        if self.settings_index == 2:
            self.toggle_fullscreen()
            self.save_game()
        elif self.settings_index == 3:
            self.state = "menu"

    def adjust_setting(self, direction):
        """LEFT/RIGHT on the settings screen: direction is -1 or +1."""
        if self.settings_index == 0:
            self.music_volume = min(1.0, max(0.0, self.music_volume + 0.1 * direction))
            if self.mixer_ok and not self.muted:
                pygame.mixer.music.set_volume(self.music_volume)
        elif self.settings_index == 1:
            self.sound_volume = min(1.0, max(0.0, self.sound_volume + 0.1 * direction))
        elif self.settings_index == 2:
            self.toggle_fullscreen()
        else:
            return  # "Back" has nothing to adjust
        self.save_game()

    def activate_pause_item(self):
        item = self.pause_items[self.pause_index]
        if item == "Resume":
            self.state = self.prev_state
        elif item == "Restart level":
            self.restart_level()
        elif item == "Main menu":
            self.state = "menu"
        elif item == "Quit":
            pygame.quit()
            sys.exit()

    def activate_end_item(self):
        item = self.end_items[self.end_index]
        if item == "Retry level":
            self.restart_level()
        elif item == "Main menu":
            self.state = "menu"

    def enter_charon(self):
        """Charon ferries you to the next level and heals you while he's at it."""
        self.player.hp = self.player.max_hp
        self.charon_line = random.choice(CHARON_LINES)
        self.state = "charon"

    def restart_level(self):
        """Replay the level you died/paused in, not the whole game."""
        if self.level_index == -1:
            self.start_prison()
        else:
            self.start_level(self.level_index)

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        flags = pygame.FULLSCREEN if self.fullscreen else 0
        self.window = pygame.display.set_mode((WIDTH, HEIGHT), flags)
        self.screen = self.window

    def handle_key(self, key):
        if key == pygame.K_m:
            self.toggle_mute()
            return
        if self.state == "menu":
            if key in (pygame.K_UP, pygame.K_w):
                self.menu_index = self.move_index(self.menu_index, -1, len(self.menu_items))
            elif key in (pygame.K_DOWN, pygame.K_s):
                self.menu_index = self.move_index(self.menu_index, 1, len(self.menu_items))
            elif key == pygame.K_RETURN:
                self.activate_menu_item()
            return
        if self.state == "controls":
            if key in (pygame.K_RETURN, pygame.K_ESCAPE):
                self.state = "menu"
            return
        if self.state == "settings":
            if key in (pygame.K_UP, pygame.K_w):
                self.settings_index = self.move_index(self.settings_index, -1, 4)
            elif key in (pygame.K_DOWN, pygame.K_s):
                self.settings_index = self.move_index(self.settings_index, 1, 4)
            elif key == pygame.K_LEFT:
                self.adjust_setting(-1)
            elif key == pygame.K_RIGHT:
                self.adjust_setting(1)
            elif key == pygame.K_RETURN:
                self.activate_settings_item()
            elif key == pygame.K_ESCAPE:
                self.state = "menu"
            return
        if self.state == "charselect":
            if key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                self.char_index = 1 - self.char_index  # only two characters, so just flip
            elif key == pygame.K_RETURN:
                self.player_char = CHARACTERS[self.char_index]["key"]
                self.reset()
            elif key == pygame.K_ESCAPE:
                self.state = "menu"
            return
        if self.state == "paused":
            if key in (pygame.K_UP, pygame.K_w):
                self.pause_index = self.move_index(self.pause_index, -1, len(self.pause_items))
            elif key in (pygame.K_DOWN, pygame.K_s):
                self.pause_index = self.move_index(self.pause_index, 1, len(self.pause_items))
            elif key == pygame.K_RETURN:
                self.activate_pause_item()
            elif key in (pygame.K_ESCAPE, pygame.K_p):
                self.state = self.prev_state
            return

        if key in (pygame.K_ESCAPE, pygame.K_p):
            if self.state in ("playing", "prison"):
                self.prev_state = self.state
                self.pause_index = 0
                self.state = "paused"
        if key == pygame.K_F1 and DEBUG:
            self.show_walls = not self.show_walls
        if self.state == "choosing" and key in (pygame.K_1, pygame.K_2, pygame.K_3):
            self.choose_gift(key - pygame.K_1)
        if self.state in ("gameover", "win"):
            if key in (pygame.K_UP, pygame.K_w, pygame.K_DOWN, pygame.K_s):
                self.end_index = self.move_index(self.end_index, 1, len(self.end_items))
            elif key == pygame.K_RETURN:
                self.activate_end_item()
        if key == pygame.K_RETURN and self.state == "level_done":
            self.enter_charon()
        elif key == pygame.K_RETURN and self.state == "charon":
            self.start_level(self.level_index + 1)

    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    self.handle_key(event.key)
            if self.state == "playing":
                self.update(dt)
            elif self.state == "prison":
                self.update_prison(dt)
            self.draw()


if __name__ == "__main__":
    Game().run()
