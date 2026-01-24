from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Tuple
import numpy as np


# ----------------------------
# Configurable performance knobs
# ----------------------------
TARGET_FPS: int = 60                 # <<< change this instead of hardcoding "60fps"
COLLISION_MAP_FPS: int = 20          # <<< change this instead of hardcoding "20fps"
DT: float = 1.0 / TARGET_FPS
COLLISION_MAP_DT: float = 1.0 / COLLISION_MAP_FPS


Vec2 = Tuple[float, float]
CollisionMap = np.ndarray  # expected shape (H, W) dtype=bool, True = solid/collision


@dataclass
class Stickman:
    # Core state
    pos: Vec2 = (100.0, 100.0)  # (x, y) in pixels (top-left of the stickman AABB)
    width: int = 48
    height: int = 80

    # Collision world (True = solid)
    collision_map: Optional[CollisionMap] = None

    # Sprite (for overlay rendering)
    sprite_url: str = "assets/sprites/stickman_idle.png"

    # Input flags (set these from your keyboard/controller code)
    is_moving_left: bool = False
    is_moving_right: bool = False
    wants_jump: bool = False

    # Physics
    speed: float = 280.0          # horizontal speed px/s
    jump_velocity: float = 520.0  # px/s upward impulse
    gravity: float = 1800.0       # px/s^2 downward
    max_fall_speed: float = 1200.0

    # Velocity
    vel: Vec2 = (0.0, 0.0)

    # Optional hook to refresh collision map (e.g., from screen pixels)
    # Should return a boolean collision map (H,W) where True=solid.
    collision_map_provider: Optional[Callable[[], CollisionMap]] = None

    # Internal timing for 20fps collision map updates
    _collision_accum: float = 0.0

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

    # -----------------------
    # Collision / world update
    # -----------------------
    def update_collision_map(self) -> None:
        """Refresh the collision_map (called ~20fps)."""
        if self.collision_map_provider is not None:
            self.collision_map = self.collision_map_provider()

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
        """
        cm = self.collision_map
        if cm is None:
            return False

        H, W = cm.shape[:2]

        left = int(np.floor(x))
        top = int(np.floor(y))
        right = int(np.ceil(x + self.width))
        bottom = int(np.ceil(y + self.height))

        # Clamp to map bounds
        if right <= 0 or bottom <= 0 or left >= W or top >= H:
            return False  # outside map, treat as empty (or change to True if you want walls)

        left_c = max(0, left)
        top_c = max(0, top)
        right_c = min(W, right)
        bottom_c = min(H, bottom)

        region = cm[top_c:bottom_c, left_c:right_c]
        return bool(region.any())

    def _resolve_horizontal(self, x: float, y: float, dx: float) -> float:
        """Move 1px steps until blocked (simple, robust)."""
        step = 1 if dx > 0 else -1
        target = x + dx
        # walk toward target in pixel steps
        cur = x
        while (cur < target if step > 0 else cur > target):
            nxt = cur + step
            if self._aabb_collides(nxt, y):
                return cur
            cur = nxt
        return cur

    def _resolve_vertical(self, x: float, y: float, dy: float) -> float:
        """Move 1px steps until blocked (simple, robust)."""
        step = 1 if dy > 0 else -1
        target = y + dy
        cur = y
        while (cur < target if step > 0 else cur > target):
            nxt = cur + step
            if self._aabb_collides(x, nxt):
                return cur
            cur = nxt
        return cur
