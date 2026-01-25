from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Tuple
import numpy as np
from pynput import keyboard, mouse
import sound
import time
import voice_detect
import threading


# ----------------------------
# Configurable performance knobs
# ----------------------------
TARGET_FPS: int = 60  # <<< change this instead of hardcoding "60fps"
COLLISION_MAP_FPS: int = 5  # <<< change this instead of hardcoding "20fps"
DT: float = 1.0 / TARGET_FPS
COLLISION_MAP_DT: float = 1.0 / COLLISION_MAP_FPS

# Flying control
ENABLE_E_FOR_FLYING: bool = True  # <<< Set to False to disable 'd' key for flying
ENABLE_R_FOR_KAMEHAMEHA: bool = (
    True  # <<< Set to False to disable 'r' key for kamehameha
)


Vec2 = Tuple[float, float]
CollisionMap = np.ndarray  # expected shape (H, W) dtype=bool, True = solid/collision


@dataclass
class Stickman:
    damage_rects: list = field(default_factory=list)

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
    is_flying: bool = False
    facing_right: bool = True  # Track which direction stickman is facing
    is_punching: bool = False
    is_kamehameha: bool = False
    punch_direction: str = "horizontal"  # "horizontal", "up", or "down"
    _punch_timer: float = 0.0  # Timer to keep punch animation visible
    _kamehameha_timer: float = 0.0  # Timer for kamehameha animation
    _blast_pos: Optional[Tuple[int, int]] = field(
        default=None, init=False, repr=False
    )  # Position of blast
    _blast_facing_right: bool = field(
        default=True, init=False, repr=False
    )  # Direction of blast
    _blast_sound_channel: any = field(
        default=None, init=False, repr=False
    )  # Track blast sound
    _walk_sound_counter: int = 0  # Counter to play walk sound periodically
    _flying_sound_counter: int = 0  # Counter to play flying sound periodically
    _aura_sound_channel: any = field(
        default=None, init=False, repr=False
    )  # Track aura sound channel

    # Voice detection threading
    _voice_thread: Optional[threading.Thread] = field(
        default=None, init=False, repr=False
    )
    _is_listening: bool = field(default=False, init=False, repr=False)
    _hame_detected: bool = field(default=False, init=False, repr=False)
    _loud_sound_detected: bool = field(default=False, init=False, repr=False)

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

    # Most common background color (updated at 1 FPS)
    most_common_col: Tuple[int, int, int] = (128, 128, 128)  # Default gray

    # Internal timing for 20fps collision map updates
    _collision_accum: float = 0.0
    # Internal timing for 1fps color sampling
    _color_sample_accum: float = 0.0

    # Keyboard listener (use field default_factory to avoid mutable default)
    _keyboard_listener: Optional[keyboard.Listener] = field(
        default=None, init=False, repr=False
    )

    def __post_init__(self):
        """Start global keyboard listener for this stickman"""
        self.start_keyboard_listener()
        self.start_voice_listener()

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
        self.stop_voice_listener()

    def start_voice_listener(self):
        """Start continuous voice detection in background thread"""
        if self._voice_thread is None:
            self._is_listening = True
            self._voice_thread = threading.Thread(
                target=self._voice_detection_loop, daemon=True
            )
            self._voice_thread.start()

    def _voice_detection_loop(self):
        """Runs in background thread - continuously listens for voice commands"""
        while self._is_listening:
            try:
                # Check for "hame" word
                if voice_detect.detect_word_hame(
                    duration=2, similarity_threshold=0.0001
                ):
                    self._hame_detected = True
            except Exception:
                pass

            try:
                # Check for loud sound
                if voice_detect.detect_loud_sound(threshold=0.02, duration=0.1):
                    self._loud_sound_detected = True
            except Exception:
                pass

            time.sleep(0.05)  # Small delay to prevent CPU overuse

    def stop_voice_listener(self):
        """Stop the voice detection thread"""
        self._is_listening = False
        if self._voice_thread:
            self._voice_thread.join(timeout=2.0)
            self._voice_thread = None

    def get_blast_image_data(self):
        """Return blast image data for rendering: (x, y, facing_right) or None"""
        if self._blast_pos is not None:
            return (self._blast_pos[0], self._blast_pos[1], self._blast_facing_right)
        return None

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
                    self.punch_direction = "up"
                elif char == "a":
                    self.teleport_to_mouse()
                elif char == "s":
                    self.punch()
                elif char == "k":
                    self.punch_direction = "down"
                elif char == "e" and ENABLE_E_FOR_FLYING:
                    self.fly()
                elif char == "d":
                    self.is_flying = False  # Turn off flying
                    # Stop aura sound when flying is turned off
                    if self._aura_sound_channel is not None:
                        self._aura_sound_channel.stop()
                        self._aura_sound_channel = None
                elif char == "r" and ENABLE_R_FOR_KAMEHAMEHA:
                    self.kamehameha()
        except AttributeError:
            pass

    def teleport_to_mouse(self):
        """Teleport stickman to the left of the mouse cursor"""
        try:
            # Get current mouse position
            mouse_controller = mouse.Controller()
            mouse_x, mouse_y = mouse_controller.position

            # Teleport to the left of the mouse (50 pixels to the left)
            offset = 50
            new_x = mouse_x - offset - self.width
            new_y = mouse_y - self.height // 2  # Center vertically on mouse

            # Clamp to screen boundaries
            new_x = max(0, min(1920 - self.width, new_x))
            new_y = max(0, min(1200 - self.height, new_y))

            self.pos = (float(new_x), float(new_y))
            # Reset velocity when teleporting
            self.vel = (0.0, 0.0)
        except Exception as e:
            print(f"Error teleporting to mouse: {e}")

    def punch(self):
        """Move mouse to punch location, click, and return mouse to original position"""
        try:
            mouse_controller = mouse.Controller()
            # Save original mouse position
            original_pos = mouse_controller.position

            # Calculate stickman center
            x, y = self.pos
            center_x = x + self.width // 2
            center_y = y + self.height // 2

            pixels_in_direction = 25

            # Calculate target position based on punch direction
            if self.punch_direction == "up":
                target_x = int(center_x)
                target_y = int(center_y - pixels_in_direction)
            elif self.punch_direction == "down":
                target_x = int(center_x)
                target_y = int(center_y + pixels_in_direction)
            else:  # horizontal (left or right based on facing_right)
                if self.facing_right:
                    target_x = int(center_x + pixels_in_direction)
                else:
                    target_x = int(center_x - pixels_in_direction)
                target_y = int(center_y)

            # Move mouse to target, click, and return
            mouse_controller.position = (target_x, target_y)
            mouse_controller.click(mouse.Button.left, 1)
            mouse_controller.position = original_pos

            # Play punch sound
            sound.play_sound("assets/sounds/punch.wav", wait=False)

            # Set punching flag and timer (animation will last ~0.3 seconds)
            self.is_punching = True
            self._punch_timer = 0.3

        except Exception as e:
            print(f"Error punching: {e}")

    def kamehameha(self):
        """Execute kamehameha attack"""
        print("🔵 KAMEHAMEHA!!!")
        from pygame import mixer

        # Set kamehameha state
        self.is_kamehameha = True
        self._kamehameha_timer = 3.0  # Animation lasts 3 seconds

        # Calculate blast position (directly in front of stickman)
        x, y = self.pos
        center_y = int(
            y + self.height // 2 - 25
        )  # Center vertically (blast is 50px tall)

        if self.facing_right:
            blast_x = int(x + self.width)  # Right side of stickman
        else:
            blast_x = int(x - 1000)  # Left side of stickman (blast is 1000px wide)

        self._blast_pos = (blast_x, center_y)
        self._blast_facing_right = self.facing_right

        # Play blast sound
        if not mixer.get_init():
            mixer.init()
        blast_sound = mixer.Sound("assets/sounds/blast.wav")
        self._blast_sound_channel = blast_sound.play()

    def on_blast_end(self):
        """Called when the blast sound finishes playing"""
        print("💥 Blast ended!")
        self.damage_rects.append(
            (
                self._blast_pos[0],
                self._blast_pos[1],
            )
        )
        # Add your custom logic here

    def fly(self):
        """Toggle flying mode"""
        self.is_flying = not self.is_flying
        if self.is_flying:
            print("🚀 Flying mode ON!")
        else:
            print("🚀 Flying mode OFF!")
            # Stop aura sound when flying is turned off
            if self._aura_sound_channel is not None:
                self._aura_sound_channel.stop()
                self._aura_sound_channel = None

    def animate(self):
        """Update sprite based on movement state (placeholder)"""
        # This is a placeholder for animation logic.
        # You can expand this to cycle through frames based on movement.

        # Kamehameha animation takes highest priority
        if self.is_kamehameha:
            if self.animation_frame % 30 < 10:
                self.sprite_url = "assets/sprites/stickman_blask1.png"
            elif self.animation_frame % 30 < 20:
                self.sprite_url = "assets/sprites/stickman_blask2.png"
            else:
                self.sprite_url = "assets/sprites/stickman_blask3.png"
        # Flying animation takes high priority
        elif self.is_flying:
            if self.is_punching:
                # Flying punch animations
                if self.punch_direction == "up":
                    if self.animation_frame % 30 < 10:
                        self.sprite_url = "assets/sprites/stickman_fly_hit_up1.png"
                    elif self.animation_frame % 30 < 20:
                        self.sprite_url = "assets/sprites/stickman_fly_hit_up2.png"
                    else:
                        self.sprite_url = "assets/sprites/stickman_fly_hit_up3.png"
                elif self.punch_direction == "down":
                    if self.animation_frame % 30 < 10:
                        self.sprite_url = "assets/sprites/stickman_fly_hit_down1.png"
                    elif self.animation_frame % 30 < 20:
                        self.sprite_url = "assets/sprites/stickman_fly_hit_down2.png"
                    else:
                        self.sprite_url = "assets/sprites/stickman_fly_hit_down3.png"
                else:  # horizontal punch
                    if self.animation_frame % 30 < 10:
                        self.sprite_url = "assets/sprites/stickman_fly_hit1.png"
                    elif self.animation_frame % 30 < 20:
                        self.sprite_url = "assets/sprites/stickman_fly_hit2.png"
                    else:
                        self.sprite_url = "assets/sprites/stickman_fly_hit3.png"
            else:
                # Flying idle/movement - single sprite
                if self.animation_frame % 30 < 10:
                    self.sprite_url = "assets/sprites/sprite_fly_idle1.png"
                elif self.animation_frame % 30 < 20:
                    self.sprite_url = "assets/sprites/sprite_fly_idle2.png"
                else:
                    self.sprite_url = "assets/sprites/sprite_fly_idle3.png"
        # Punching animation takes priority
        elif self.is_punching:
            # Different animations for different punch directions
            if self.punch_direction == "up":
                if self.animation_frame % 30 < 10:
                    self.sprite_url = "assets/sprites/stickman_punch_up1.png"
                elif self.animation_frame % 30 < 20:
                    self.sprite_url = "assets/sprites/stickman_punch_up2.png"
                else:
                    self.sprite_url = "assets/sprites/stickman_punch_up3.png"
            elif self.punch_direction == "down":
                if self.animation_frame % 30 < 10:
                    self.sprite_url = "assets/sprites/stickman_punch_down1.png"
                elif self.animation_frame % 30 < 20:
                    self.sprite_url = "assets/sprites/stickman_punch_down2.png"
                else:
                    self.sprite_url = "assets/sprites/stickman_punch_down3.png"
            else:  # horizontal punch
                if self.animation_frame % 30 < 10:
                    self.sprite_url = "assets/sprites/stickman_punch1.png"
                elif self.animation_frame % 30 < 20:
                    self.sprite_url = "assets/sprites/stickman_punch2.png"
                else:
                    self.sprite_url = "assets/sprites/stickman_punch3.png"
        elif self.wants_jump:
            if self.animation_frame % 30 < 10:
                self.sprite_url = "assets/sprites/stickman_jump1.png"
            elif self.animation_frame % 30 < 20:
                self.sprite_url = "assets/sprites/stickman_jump2.png"
            elif self.animation_frame % 30 < 30:
                self.sprite_url = "assets/sprites/stickman_jump3.png"
        elif self.is_moving_left or self.is_moving_right:
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
                elif char == "k":
                    self.punch_direction = "horizontal"  # reset to default
                elif char == "i":
                    self.punch_direction = "horizontal"  # reset to default
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

        # Update most common color at 1 FPS
        self._color_sample_accum += dt
        if self._color_sample_accum >= 1.0:  # 1 second = 1 FPS
            self._color_sample_accum %= 1.0
            self.update_background_color()

        # Physics step
        self.apply_gravity(dt)

        # Jump request (only if on ground)
        if self.wants_jump:
            self.try_jump()
            self.wants_jump = False  # consume the request

        # Horizontal movement intent -> velocity
        vx, vy = self.vel
        desired_vx = 0.0
        desired_vy = vy  # Keep current vertical velocity by default

        if self.is_moving_left and not self.is_moving_right:
            desired_vx = -self.speed
            self.facing_right = False  # Face left when moving left
        elif self.is_moving_right and not self.is_moving_left:
            desired_vx = self.speed
            self.facing_right = True  # Face right when moving right

        # When flying, handle vertical movement with down key (k sets punch_direction to "down")
        if self.is_flying:
            if self.punch_direction == "down":
                desired_vy = self.speed  # Move down when k is held
            elif self.punch_direction == "up":
                desired_vy = (
                    -self.speed
                )  # Move up when i is held (handled in try_jump but also here)
            else:
                desired_vy = 0.0  # Stop vertical movement when no key pressed

        vx = desired_vx
        vy = desired_vy
        self.vel = (vx, vy)

        # Play flying aura sound when flying, otherwise play walk sound
        if self.is_flying:
            # Check if aura sound is already playing
            if (
                self._aura_sound_channel is None
                or not self._aura_sound_channel.get_busy()
            ):
                from pygame import mixer

                if not mixer.get_init():
                    mixer.init()
                aura_sound = mixer.Sound("assets/sounds/aura_real.mp3")
                self._aura_sound_channel = aura_sound.play()
            self._walk_sound_counter = 0  # Reset walk counter
            self._flying_sound_counter = 0
        elif (self.is_moving_left or self.is_moving_right) and self.is_on_ground():
            self._walk_sound_counter += 1
            if self._walk_sound_counter >= 15:  # Play every ~15 frames (quarter second)
                sound.play_sound("assets/sounds/walking_real.mp3", wait=False)
                self._walk_sound_counter = 0
            self._flying_sound_counter = 0  # Reset flying counter
        else:
            self._walk_sound_counter = 0
            self._flying_sound_counter = 0

        # Move + collide
        self._move_and_collide(dt)

        # Update punch timer
        if self._punch_timer > 0:
            self._punch_timer -= dt
            if self._punch_timer <= 0:
                self.is_punching = False
                self._punch_timer = 0.0

        # Update kamehameha timer and handle blast
        if self._kamehameha_timer > 0:
            self._kamehameha_timer -= dt

            # Check if blast sound finished playing
            if (
                self._blast_sound_channel is not None
                and not self._blast_sound_channel.get_busy()
            ):
                if self._blast_pos is not None:
                    self.on_blast_end()
                    self._blast_pos = None  # Clear blast position
                    self._blast_sound_channel = None

            if self._kamehameha_timer <= 0:
                self.is_kamehameha = False
                self._kamehameha_timer = 0.0
                self._blast_pos = None

        # Check voice detection flags (non-blocking, just reads flags set by background thread)
        if self._hame_detected:
            self.kamehameha()
            self._hame_detected = False  # Reset flag

        if self._loud_sound_detected:
            self.fly()
            self._loud_sound_detected = False  # Reset flag

        self.animate()

    # -----------------------
    # Collision / world update
    # -----------------------
    def update_collision_map(self) -> None:
        """Refresh the collision_map (called ~20fps)."""
        if self.collision_map_provider is not None:
            self.collision_map = self.collision_map_provider(self)

    def update_background_color(self) -> None:
        """Sample the most common background color (called at 1 FPS)."""

        # Run in background thread to avoid blocking game loop
        def sample_color():
            import screen_read

            screenshot = screen_read.screenshot_to_numpy()
            color = screen_read.get_most_common_color(screenshot)
            self.most_common_col = color

        # Start thread but don't wait for it
        color_thread = threading.Thread(target=sample_color, daemon=True)
        color_thread.start()

    # -----------------------
    # Physics helpers
    # -----------------------
    def apply_gravity(self, dt: float) -> None:
        if self.is_flying:
            return  # No gravity when flying
        vx, vy = self.vel
        vy += self.gravity * dt
        if vy > self.max_fall_speed:
            vy = self.max_fall_speed
        self.vel = (vx, vy)

    def try_jump(self) -> None:
        """Apply jump impulse if standing on solid ground, or move up when flying."""
        if self.is_flying:
            # When flying, jump button moves up
            vx, _vy = self.vel
            self.vel = (vx, -self.speed)  # Move up at walking speed
        elif self.is_on_ground():
            vx, _vy = self.vel
            self.vel = (vx, -self.jump_velocity)
            # Play jump sound
            sound.play_sound("assets/sounds/jump.wav", wait=False)

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
