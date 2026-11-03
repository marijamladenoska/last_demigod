# The Last Demigod
# Top-down survival game: WASD / arrows to move, attacks are automatic.
# 1/2/3 = choose a gift on level-up, P/ESC = pause, R = restart, ENTER = next level.
# Shapes are placeholders for the Kenney sprites.

import math
import os
import random
import sys

import pygame

WIDTH, HEIGHT = 1152, 648  # 16:9, same shape as the background pictures
FPS = 60
ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
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

# Background pictures are 1672 x 941. Wall positions below are written in
# picture pixels and scaled to the window, so they stay correct at any size.
IMG_W, IMG_H = 1672, 941
SX, SY = WIDTH / IMG_W, HEIGHT / IMG_H


def img_rect(x, y, w, h):
    """Convert a rectangle in picture pixels to window pixels."""
    return pygame.Rect(round(x * SX), round(y * SY), round(w * SX), round(h * SY))


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

# Each level is just data, so adding level 3 later means adding one dict.
LEVELS = [
    {
        "name": "Level 1: Tartar",
        "bg": (24, 18, 32),
        "bg_image": "tartarus_arena.png",
        "time": 60,            # seconds to survive before the boss appears
        "enemy_speed": 70,
        "spawn_delay": 1.2,
        "boss": {"name": "Kampe", "hp": 300, "speed": 55, "radius": 34,
                 "color": (150, 60, 170), "damage": 20, "charge": False},
    },
    {
        "name": "Level 2: River Styx",
        "bg": (8, 28, 42),
        "time": 75,
        "enemy_speed": 95,
        "spawn_delay": 1.0,
        "boss": {"name": "Cerberus", "hp": 450, "speed": 75, "radius": 42,
                 "color": (130, 80, 30), "damage": 25, "charge": True},
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


CHARACTERS = [
    {"key": "leon", "name": "Leon", "sprite": "leon.png", "color": WHITE},
    {"key": "elena", "name": "Elena", "sprite": "elena.png", "color": (235, 150, 210)},
]


class Player:
    def __init__(self, sprite=None, color=WHITE):
        self.sprite = sprite          # pygame Surface, or None to draw a circle instead
        self.color = color
        self.pos = pygame.Vector2(WIDTH / 2, HEIGHT / 2)
        self.facing = pygame.Vector2(1, 0)  # last direction moved (for the trident)
        self.radius = 16
        self.speed = 220
        self.max_hp = 100
        self.hp = self.max_hp
        self.hit_cooldown = 0.0  # short invincibility after being hit

        # Zeus lightning (starting weapon)
        self.attack_cooldown = 0.7
        self.attack_timer = 0.0
        self.attack_range = 260
        self.damage = 10

        # XP and gifts
        self.level = 1
        self.xp = 0
        self.xp_needed = 5
        self.gifts = {}  # gift key -> level

    def gift(self, key):
        return self.gifts.get(key, 0)

    def take_damage(self, amount):
        if self.hit_cooldown > 0:
            return
        reduction = 0.15 * self.gift("shield")
        self.hp -= amount * (1 - reduction)
        self.hit_cooldown = 0.8

    def hitbox(self, pos=None):
        pos = pos or self.pos
        return pygame.Rect(pos.x - 10, pos.y - 10, 20, 20)  # smaller than the drawing so doors fit

    def update(self, dt, keys, walls=()):
        move = pygame.Vector2(
            (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT]),
            (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP]),
        )
        if move.length() > 0:
            move = move.normalize()  # same speed on diagonals
            self.facing = move
        self.pos = move_with_walls(self.pos, move * self.speed * dt, walls, self.hitbox)
        self.pos.x = max(self.radius, min(WIDTH - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(HEIGHT - self.radius, self.pos.y))
        self.attack_timer -= dt
        self.hit_cooldown -= dt

    def draw(self, screen):
        if self.gift("shield"):
            pygame.draw.circle(screen, (200, 200, 120), self.pos, self.radius + 6, 2)
        blink = self.hit_cooldown > 0 and int(self.hit_cooldown * 20) % 2 == 0
        if blink:
            return
        if self.sprite:
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
    def __init__(self, speed, hp):
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
        self.damage = 10

    def update(self, dt, target):
        direction = target - self.pos
        if direction.length() > 0:
            self.pos += direction.normalize() * self.speed * dt

    def draw(self, screen):
        pygame.draw.circle(screen, RED, self.pos, self.radius)


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
    def __init__(self, cfg):
        self.name = cfg["name"]
        self.max_hp = self.hp = cfg["hp"]
        self.speed = cfg["speed"]
        self.radius = cfg["radius"]
        self.color = cfg["color"]
        self.damage = cfg["damage"]
        self.charges = cfg["charge"]  # Cerberus periodically lunges at the player
        self.pos = pygame.Vector2(WIDTH / 2, -50)
        self.charge_timer = 3.0       # counts down to the next lunge
        self.lunge_left = 0.0

    def update(self, dt, target):
        speed = self.speed
        if self.charges:
            self.charge_timer -= dt
            if self.charge_timer <= 0:
                self.lunge_left = 0.6
                self.charge_timer = 3.0
            if self.lunge_left > 0:
                self.lunge_left -= dt
                speed *= 3
        direction = target - self.pos
        if direction.length() > 0:
            self.pos += direction.normalize() * speed * dt

    def draw(self, screen):
        pygame.draw.circle(screen, self.color, self.pos, self.radius)
        pygame.draw.circle(screen, WHITE, self.pos, self.radius, 3)


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
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
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
        self.show_walls = DEBUG  # F1 can still toggle this, see handle_key()
        self.prev_state = "playing"

        # main menu
        self.state = "menu"
        self.menu_items = ["Start", "Controls", "Settings", "Quit"]
        self.menu_index = 0
        self.settings_index = 0
        self.fullscreen = False
        self.char_index = 0  # which character is highlighted on the select screen
        self.player_char = "leon"
        self.player = None

    def reset(self):
        """Full restart from the prison, with whichever character was chosen."""
        char = next(c for c in CHARACTERS if c["key"] == self.player_char)
        sprite = self.images.get(char["sprite"])
        self.player = Player(sprite=sprite, color=char["color"])
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

    def update_prison(self, dt):
        p = self.player
        walls = self.walls + ([] if self.gate_open else [self.gate])
        p.update(dt, pygame.key.get_pressed(), walls)
        self.banner_timer -= dt
        self.zeus_lightning()
        for g in self.enemies:
            g.update(dt, p.pos, walls)
            if p.pos.distance_to(g.pos) < p.radius + g.radius:
                p.take_damage(g.damage)
        for g in self.enemies:
            if g.hp <= 0:
                self.orbs.append(XPOrb(g.pos))
        self.enemies = [g for g in self.enemies if g.hp > 0]
        self.bolts = [(a, b, t - dt) for a, b, t in self.bolts if t - dt > 0]
        self.collect_orbs(dt)

        if not self.enemies and not self.gate_open:
            self.gate_open = True
            self.banner_timer = 2.5
        if self.gate_open and p.pos.y > PRISON_EXIT_Y * SY:
            self.start_level(0)
        if p.hp <= 0:
            self.state = "gameover"

    def start_level(self, index):
        self.walls = []
        self.level_index = index
        self.level = LEVELS[index]
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
            for _ in range(1 + step):
                self.enemies.append(Enemy(speed, hp=20))
            self.spawn_timer = max(0.5, self.level["spawn_delay"] - 0.25 * step)

    # ---- weapons ----
    def zeus_lightning(self):
        p = self.player
        targets = self.targets()
        if p.attack_timer > 0 or not targets:
            return
        nearest = min(targets, key=lambda e: p.pos.distance_to(e.pos))
        if p.pos.distance_to(nearest.pos) <= p.attack_range:
            lvl = p.gift("zeus")
            nearest.hp -= p.damage + 5 * lvl
            self.bolts.append((p.pos.copy(), nearest.pos.copy(), 0.12))
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
                    t.hp -= 60 * dt  # damage per second while touching

    def update_projectiles(self, dt):
        for proj in self.projectiles:
            proj.update(dt)
            for t in self.targets():
                if t in proj.already_hit:
                    continue
                if proj.pos.distance_to(t.pos) < proj.radius + t.radius:
                    t.hp -= proj.damage
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
        if p.xp >= p.xp_needed:
            p.xp -= p.xp_needed
            p.level += 1
            p.xp_needed = int(p.xp_needed * 1.5) + 2
            self.offer_gifts()

    def offer_gifts(self):
        available = [k for k in GIFTS if self.player.gift(k) < MAX_GIFT_LEVEL]
        if not available:
            return
        self.choices = random.sample(available, min(3, len(available)))
        self.prev_state = self.state
        self.state = "choosing"

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
        p.update(dt, keys)
        if self.boss is None:
            self.spawn_enemies(dt)
        self.banner_timer -= dt

        self.zeus_lightning()
        self.apollo_arrows(dt)
        self.poseidon_trident(dt)
        self.ares_sword(dt)
        self.update_projectiles(dt)

        for e in self.enemies:
            e.update(dt, p.pos)
            if p.pos.distance_to(e.pos) < p.radius + e.radius:
                p.take_damage(e.damage)
        if self.boss:
            self.boss.update(dt, p.pos)
            if p.pos.distance_to(self.boss.pos) < p.radius + self.boss.radius:
                p.take_damage(self.boss.damage)

        # dead enemies drop XP orbs
        for e in self.enemies:
            if e.hp <= 0:
                self.orbs.append(XPOrb(e.pos))
        self.enemies = [e for e in self.enemies if e.hp > 0]
        self.bolts = [(a, b, t - dt) for a, b, t in self.bolts if t - dt > 0]
        self.collect_orbs(dt)

        # timer runs out -> boss arrives; killing the boss finishes the level
        if self.boss is None:
            self.time_left -= dt
            if self.time_left <= 0:
                self.boss = Boss(self.level["boss"])
        elif self.boss.hp <= 0:
            self.state = "level_done" if self.level_index < len(LEVELS) - 1 else "win"

        if p.hp <= 0:
            self.state = "gameover"

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
        items = [f"Fullscreen: {'On' if self.fullscreen else 'Off'}", "Back"]
        self.draw_menu_list("SETTINGS", items, self.settings_index,
                             "LEFT/RIGHT or ENTER to change, ESC to go back")

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
            sprite = self.images.get(char["sprite"])
            center = (rect.centerx, rect.centery - 30)
            if sprite:
                self.screen.blit(sprite, sprite.get_rect(center=center))
            else:
                pygame.draw.circle(self.screen, char["color"], center, 40)
                pygame.draw.circle(self.screen, BLUE, center, 40, 3)
            self.draw_text(char["name"], self.font, WHITE, (rect.centerx, rect.bottom - 40))
        self.draw_text("LEFT/RIGHT to choose, ENTER to confirm, ESC to go back",
                        self.small_font, (170, 170, 170), (WIDTH // 2, HEIGHT - 40))

    def draw(self):
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
        self.player.draw(self.screen)
        if self.show_walls:
            for w in self.walls + ([self.gate] if self.level_index == -1 and not self.gate_open else []):
                pygame.draw.rect(self.screen, (255, 0, 0), w, 2)
        if self.level_index == -1:
            self.draw_prison_hud()
        else:
            self.draw_hud()

        center = (WIDTH // 2, HEIGHT // 2)
        below = (WIDTH // 2, HEIGHT // 2 + 40)
        if self.state == "choosing":
            self.draw_gift_choice()
        elif self.state == "paused":
            self.draw_text("PAUSED", self.big_font, WHITE, center)
        elif self.state == "gameover":
            self.draw_text("YOU DIED", self.big_font, RED, (WIDTH // 2, HEIGHT // 2 - 20))
            self.draw_text("Press R to restart", self.font, WHITE, below)
        elif self.state == "level_done":
            self.draw_text(f"{self.boss.name} DEFEATED", self.big_font, GOLD, (WIDTH // 2, HEIGHT // 2 - 20))
            self.draw_text("Press ENTER for the next level", self.font, WHITE, below)
        elif self.state == "win":
            self.draw_text("YOU WIN", self.big_font, GOLD, (WIDTH // 2, HEIGHT // 2 - 20))
            self.draw_text("Press R to restart", self.font, WHITE, below)
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

    def activate_settings_item(self, toggle_direction=1):
        if self.settings_index == 0:
            self.toggle_fullscreen()
        else:
            self.state = "menu"

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        flags = pygame.FULLSCREEN if self.fullscreen else 0
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)

    def handle_key(self, key):
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
                self.settings_index = self.move_index(self.settings_index, -1, 2)
            elif key in (pygame.K_DOWN, pygame.K_s):
                self.settings_index = self.move_index(self.settings_index, 1, 2)
            elif key in (pygame.K_RETURN, pygame.K_LEFT, pygame.K_RIGHT):
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

        if key in (pygame.K_ESCAPE, pygame.K_p):
            if self.state in ("playing", "prison"):
                self.prev_state = self.state
                self.state = "paused"
            elif self.state == "paused":
                self.state = self.prev_state
        if key == pygame.K_F1:
            self.show_walls = not self.show_walls
        if self.state == "choosing" and key in (pygame.K_1, pygame.K_2, pygame.K_3):
            self.choose_gift(key - pygame.K_1)
        if key == pygame.K_r and self.state in ("gameover", "win"):
            self.reset()
        if key == pygame.K_RETURN and self.state == "level_done":
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
