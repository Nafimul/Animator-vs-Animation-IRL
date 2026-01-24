from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Tuple
import numpy as np
from pynput import keyboard


# ----------------------------
# Configurable performance knobs
# ----------------------------
TARGET_FPS: int = 60  # <<< change this instead of hardcoding "60fps"
COLLISION_MAP_FPS: int = 5  # <<< change this instead of hardcoding "20fps"
DT: float = 1.0 / TARGET_FPS
COLLISION_MAP_DT: float = 1.0 / COLLISION_MAP_FPS


Vec2 = Tuple[float, float]
CollisionMap = np.ndarray  # expected shape (H, W) dtype=bool, True = solid/collision


@dataclass
class Stickman:
    # Core state
    pos: Vec2 = (1000.0, 200.0)  # (x, y) in pixels (top-left of the stickman AABB)
    width: int = 21
    height: int = 30

    # Collision world (True = solid)
    collision_map: Optional[CollisionMap] = (
        None  # Location of the collision map in screen coordinates
    )
    collision_map_x: int = 0  # Screen X coordinate where collision map starts
    collision_map_y: int = 0  # Screen Y coordinate where collision map starts
    # Sprite (for overlay rendering)
    sprite_url: str = "assets/sprites/stickman_idle.png"
    animation_frame: int = 0

    # Input flags (set these from your keyboard/controller code)
    is_moving_left: bool = False
    is_moving_right: bool = False
    wants_jump: bool = False

    # Physics
    speed: float = 280.0  # horizontal speed px/s
    jump_velocity: float = 500.0  # px/s upward impulse
    gravity: float = 1800.0  # px/s^2 downward
    max_fall_speed: float = 500.0

    # Velocity
    vel: Vec2 = (0.0, 0.0)

    # Optional hook to refresh collision map (e.g., from screen pixels)
    # Should return a boolean collision map (H,W) where True=solid.
    collision_map_provider: Optional[Callable[[], CollisionMap]] = None

    # Internal timing for 20fps collision map updates
    _collision_accum: float = 0.0

    # Keyboard listener (use field default_factory to avoid mutable default)
    _keyboard_listener: Optional[keyboard.Listener] = field(
        default=None, init=False, repr=False
    )

    def __post_init__(self):
        """Start global keyboard listener for this stickman"""
        self.start_keyboard_listener()

    def start_keyboard_listener(self):
        """Start global keyboard listener (works regardless of focus)"""
        if self._keyboard_listener is None:
            self._keyboard_listener = keyboard.Listener(
                on_press=self._on_press, on_release=self._on_release
            )
            self._keyboard_listener.start()

    def stop_keyboard_listener(self):
        """Stop the keyboard listener"""
        if self._keyboard_listener:
            self._keyboard_listener.stop()
            self._keyboard_listener = None

    def _on_press(self, key):
        """Handle key press events"""
        try:
            if hasattr(key, "char") and key.char:
                char = key.char.lower()

                if char == "j":
                    self.is_moving_left = True
                elif char == "l":
                    self.is_moving_right = True
                elif char == "i":
                    self.wants_jump = True
        except AttributeError:
            pass

    def animate(self):
        """Update sprite based on movement state (placeholder)"""
        # This is a placeholder for animation logic.
        # You can expand this to cycle through frames based on movement.
        if self.wants_jump:
            if self.animation_frame % 30 < 10:
                self.sprite_url = "assets/sprites/stickman_jump1.png"
            elif self.animation_frame % 30 < 20:
                self.sprite_url = "assets/sprites/stickman_jump2.png"
            elif self.animation_frame % 30 < 30:
                self.sprite_url = "assets/sprites/stickman_jump3.png"
        if self.is_moving_left or self.is_moving_right:
            if self.animation_frame % 30 < 10:
                self.sprite_url = "assets/sprites/stickman_run1.png"
            elif self.animation_frame % 30 < 20:
                self.sprite_url = "assets/sprites/stickman_run2.png"
            elif self.animation_frame % 30 < 30:
                self.sprite_url = "assets/sprites/stickman_run3.png"
        else:
            self.sprite_url = "assets/sprites/stickman_idle.png"

        self.animation_frame += 3

    def _on_release(self, key):
        """Handle key release events"""
        try:
            if hasattr(key, "char") and key.char:
                char = key.char.lower()

                if char == "j":
                    self.is_moving_left = False
                elif char == "l":
                    self.is_moving_right = False
        except AttributeError:
            pass

    def update(self, dt: float = DT) -> None:
        """
        Call this at ~TARGET_FPS. It:
          - occasionally refreshes collision map (~COLLISION_MAP_FPS)
          - applies gravity
          - handles horizontal movement flags
          - handles jump
          - resolves collisions via can_move_* checks
        """
        # Update collision map at ~20fps (configurable)
        self._collision_accum += dt
        if self._collision_accum >= COLLISION_MAP_DT:
            # keep remainder so it stays stable if dt varies
            self._collision_accum %= COLLISION_MAP_DT
            self.update_collision_map()

        # Physics step
        self.apply_gravity(dt)

        # Jump request (only if on ground)
        if self.wants_jump:
            self.try_jump()
            self.wants_jump = False  # consume the request

        # Horizontal movement intent -> velocity
        vx, vy = self.vel
        desired_vx = 0.0
        if self.is_moving_left and not self.is_moving_right:
            desired_vx = -self.speed
        elif self.is_moving_right and not self.is_moving_left:
            desired_vx = self.speed
        vx = desired_vx
        self.vel = (vx, vy)

        # Move + collide
        self._move_and_collide(dt)
        self.animate()

    # -----------------------
    # Collision / world update
    # -----------------------
    def update_collision_map(self) -> None:
        """Refresh the collision_map (called ~20fps)."""
        if self.collision_map_provider is not None:
            self.collision_map = self.collision_map_provider(self)

    # -----------------------
    # Physics helpers
    # -----------------------
    def apply_gravity(self, dt: float) -> None:
        vx, vy = self.vel
        vy += self.gravity * dt
        if vy > self.max_fall_speed:
            vy = self.max_fall_speed
        self.vel = (vx, vy)

    def try_jump(self) -> None:
        """Apply jump impulse if standing on solid ground."""
        if self.is_on_ground():
            vx, _vy = self.vel
            self.vel = (vx, -self.jump_velocity)

    # -----------------------
    # Movement / collision core
    # -----------------------
    def _move_and_collide(self, dt: float) -> None:
        x, y = self.pos
        vx, vy = self.vel

        # Horizontal move first
        dx = vx * dt
        if dx != 0:
            if self.can_move_horizontal(dx):
                x += dx
            else:
                # Step toward until blocked (simple discrete resolution)
                x = self._resolve_horizontal(x, y, dx)
                vx = 0.0

        # Vertical move second
        dy = vy * dt
        if dy != 0:
            if self.can_move_vertical(dy):
                y += dy
            else:
                y = self._resolve_vertical(x, y, dy)
                vy = 0.0

        # Clamp to screen boundaries (0, 0) to (1920, 1200)
        x = max(0, min(1920 - self.width, x))
        y = max(0, min(1200 - self.height, y))

        # Stop velocity if hitting screen edge
        if x == 0 or x == 1920 - self.width:
            vx = 0.0
        if y == 0 or y == 1200 - self.height:
            vy = 0.0

        self.pos = (x, y)
        self.vel = (vx, vy)

    def can_move_horizontal(self, dx: float) -> bool:
        """Return True if stickman AABB can move by dx without colliding."""
        if self.collision_map is None:
            return True
        x, y = self.pos
        return not self._aabb_collides(x + dx, y)

    def can_move_vertical(self, dy: float) -> bool:
        """Return True if stickman AABB can move by dy without colliding."""
        if self.collision_map is None:
            return True
        x, y = self.pos
        return not self._aabb_collides(x, y + dy)

    def is_on_ground(self) -> bool:
        """True if there is solid pixel just below the stickman."""
        if self.collision_map is None:
            return False
        x, y = self.pos
        # check 1px below
        return self._aabb_collides(x, y + 1.0)

    # -----------------------
    # Collision primitives
    # -----------------------
    def _aabb_collides(self, x: float, y: float) -> bool:
        """
        Checks whether the AABB at (x,y,width,height) overlaps any True pixel.
        collision_map is indexed [row=y, col=x].
        Accounts for collision_map_x and collision_map_y offsets.
        """
        cm = self.collision_map
        if cm is None:
            return False

        H, W = cm.shape[:2]

        # Convert screen coordinates to collision map local coordinates
        left = int(np.floor(x)) - self.collision_map_x
        top = int(np.floor(y)) - self.collision_map_y
        right = int(np.ceil(x + self.width)) - self.collision_map_x
        bottom = int(np.ceil(y + self.height)) - self.collision_map_y

        # Clamp to map bounds
        if right <= 0 or bottom <= 0 or left >= W or top >= H:
            return False  # outside map, treat as empty (or change to True if you want walls)

        left_c = max(0, left)
        top_c = max(0, top)
        right_c = min(W, right)
        bottom_c = min(H, bottom)

        # Safety check: ensure we have a valid region
        if right_c <= left_c or bottom_c <= top_c:
            return False

        region = cm[top_c:bottom_c, left_c:right_c]
        return bool(region.any())

    def _resolve_horizontal(self, x: float, y: float, dx: float) -> float:
        """Move 1px steps until blocked (simple, robust)."""
        step = 1 if dx > 0 else -1
        target = x + dx
        # walk toward target in pixel steps
        cur = x
        while cur < target if step > 0 else cur > target:
            nxt = cur + step
            # Check collision but ignore bottom 5 rows
            if self._aabb_collides_ignore_bottom(nxt, y, ignore_rows=5):
                return cur
            cur = nxt
        return cur

    def _aabb_collides_ignore_bottom(
        self, x: float, y: float, ignore_rows: int = 5
    ) -> bool:
        """
        Like _aabb_collides but ignores the bottom N rows of the stickman's AABB.
        """
        cm = self.collision_map
        if cm is None:
            return False

        H, W = cm.shape[:2]

        # Convert screen coordinates to collision map local coordinates
        left = int(np.floor(x)) - self.collision_map_x
        top = int(np.floor(y)) - self.collision_map_y
        right = int(np.ceil(x + self.width)) - self.collision_map_x
        bottom = int(np.ceil(y + self.height)) - self.collision_map_y - ignore_rows

        # Clamp to map bounds
        if right <= 0 or bottom <= 0 or left >= W or top >= H:
            return False

        left_c = max(0, left)
        top_c = max(0, top)
        right_c = min(W, right)
        bottom_c = min(H, bottom)

        if bottom_c <= top_c:  # No rows left to check after ignoring bottom
            return False

        region = cm[top_c:bottom_c, left_c:right_c]
        return bool(region.any())

    def _resolve_vertical(self, x: float, y: float, dy: float) -> float:
        """Move 1px steps until blocked (simple, robust)."""
        step = 1 if dy > 0 else -1
        target = y + dy
        cur = y
        while cur < target if step > 0 else cur > target:
            nxt = cur + step
            if self._aabb_collides(x, nxt):
                return cur
            cur = nxt
        return cur
