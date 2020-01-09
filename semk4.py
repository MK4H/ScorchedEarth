import math

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics.context_instructions import Color
from kivy.graphics.vertex_instructions import Line, Rectangle
from kivy.uix.image import Image
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import NumericProperty, ReferenceListProperty, ObjectProperty, AliasProperty
from kivy.vector import Vector

from kivy.core.window import Window
from collections import deque
from random import random, randrange
from shell_tracing import Trace, Tracer, TraceDisplay
from terrain_generation import generate_terrain
from menu import Menu
from victory import Victory
from gameui import ValueItem, TextItem
import collisions

"""Scorched earth reimplementation

This module reimplements the good old Scorched earth game.

Attributes:
    MAX_MUZZLE_SHELL_VEL (float): Default muzzle shell velocity, i.e. shell velocity when leaving the gun barrel's muzzle.
    
    SHELL_MASS (float): Default shell mass, used for calculating the effects of drag and wind on the shell.
    
    GRAVITY (float): Default gravitational acceleration.
    
    DRAG_COEFFICIENT (float): Drag coefficient of the shell, used for drag calculation (which includes wind interaction).
    
    MAX_WIND (float): Default maximum of the speed of the wind. During the game, wind direction and speed changes randomly,
        but the speed will always be lower than the maximum speed.
        
    INIT_ANGLE (float): Initial angle of the gun barrels of the player tanks when the game loads.
    
    INIT_POWER (float): Initial value of the power input.
    
    DEFAULT_SHELL_EXPLOSION_RADIUS  (float): Default radius of the shell explosions.
    
    TANK_BODY_SIZE (float): Default size of the visible tank body, without the gun barrel.
"""

MAX_MUZZLE_SHELL_VEL = 750
SHELL_MASS = 100
GRAVITY = 200
DRAG_COEFFICIENT = 0.0025
MAX_WIND = 10
INIT_ANGLE = 90
INIT_POWER = 50
DEFAULT_SHELL_EXPLOSION_RADIUS = 50
TANK_BODY_SIZE = (25, 25)




def clamp(value, min_val, max_val):
    """Clamp the value between min_val and max_val.

    Args:
        value: The value to clamp.
        min_val: Lower bound.
        max_val: Upper bound.

    Returns: `value` between `min_val` and `max_val` or `min_val` or `max_val`.

    """
    return max(min(value, max_val), min_val)


def get_wind_text(wind):
    """Get text representation of wind.

    Transforms the wind value into a text representation.

    Args:
        wind: The wind value to transform.

    Returns: Text representation of the `wind`.

    """
    if wind > 0:
        return f"{wind:3.2f} >"
    elif wind < 0:
        return f"< {-wind:3.2f}"
    else:
        return 'NO WIND'


class Shell(Image):
    """Class implementing shell graphics and behavior.

    Provides shell ballistics, aerodynamics and resources for hit detection.

    Attributes:
        velocity_x (NumericProperty): Shell velocity in the x axis.
        velocity_y (NumericProperty): Shell velocity in the y axis.
        velocity (ReferenceListProperty): Shell velocity vector.
        player: Owner of the shell.
        init_power: Power the shell was shot with.
        init_angle: Angle the shell was shot at, in degrees from the x axis.
        mass: Mass of the shell.
        gravity: Gravitational acceleration applied to shell each update.
        wind: Wind acting on the shell during it's flight.
        drag_coef: Drag coefficient of the shell.
        explosion_radius: The radius of the terrain destroyed on detonation.
    """

    velocity_x = NumericProperty(0)
    velocity_y = NumericProperty(0)
    velocity = ReferenceListProperty(velocity_x, velocity_y)

    def __init__(self, player, power, angle, start_vel, mass, gravity, wind, drag_coef, explosion_radius, **kwargs):
        """

        Args:
            player: Owner of the shell.
            power: Power the shell was shot with.
            angle: Angle the shell was shot at, in degrees from the x axis.
            start_vel: Initial velocity vector.
            mass: Mass of the shell.
            gravity: Gravitational acceleration applied to shell each update.
            wind: Wind acting on the shell during it's flight.
            drag_coef: Drag coefficient of the shell.
            explosion_radius: The radius of the terrain destroyed on detonation.
            **kwargs: Arguments passed to the super() constructor.
        """
        super().__init__(**kwargs)
        self.player = player
        self.init_power = power
        self.init_angle = angle
        self.mass = mass
        self.gravity = gravity
        self.wind = wind
        self.drag_coef = drag_coef
        vel_vec = Vector(start_vel, 0).rotate(angle)
        self.velocity = (vel_vec.x, vel_vec.y)
        self.explosion_radius = explosion_radius

    def update(self, dt):
        """Updates the position and the velocity of the shell.

        Moves the shell based on it's current velocity and the time passed (`dt`).
        Updates the velocity based on `self.gravity`, `self.wind`, `self.drag_coef` and the time passed.

        Args:
            dt: Delta t, the change of time the shell should be updated by.
        """
        # move the shell based on the current velocity and change of time
        self.center = Vector(*self.center) + Vector(*self.velocity) * dt
        # apply gravitational acceleration
        self.velocity_y -= self.gravity * dt

        air_vel = Vector(self.velocity_x - self.wind, self.velocity_y)

        # based on https://en.wikipedia.org/wiki/Drag_equation
        # hides the density, area and other constants for the shell into the drag coefficient
        drag = air_vel.normalize() * self.drag_coef * air_vel.length2()
        vel_vec = Vector(*self.velocity) - (drag / self.mass)
        self.velocity = (vel_vec.x, vel_vec.y)

        # bounce off the walls
        if (self.x < 0) or (self.right > self.parent.width):
            self.velocity_x *= -1
            self.right = clamp(self.right, 0, self.parent.width)
            self.x = clamp(self.x, 0, self.parent.width)

        if self.top > self.parent.height:
            self.velocity_y *= -1
            self.top = clamp(self.top, 0, self.parent.height)

    def get_angle(self):
        """
        Returns: The current angle of the shell from the x axis.
        """
        return Vector(*self.velocity).angle((1, 0))

    angle = AliasProperty(get_angle, None, bind=["velocity"])

    def get_rectangle(self):
        """Returns `Rectangle` for collision detection.
        Returns: `Rectangle` representing the part of space occupied by the shell for collision detection.
        """
        return collisions.Rectangle(Vector(*self.center), Vector(*self.size), Vector(-self.width / 2, -self.height / 2),
                                    self.get_angle())


class GunBarrel(Image):
    """
    Implements the behavior and graphical representation of the gun barrel of the tank.

    Attributes:
        angle (NumericProperty): Current angle between the barrel and the x axis, in degrees.
    """

    angle = NumericProperty(INIT_ANGLE)
    b_length = NumericProperty(0.5)
    b_width = NumericProperty(0.2)
    b_size = ReferenceListProperty(b_length, b_width)

    def get_shell_size(self):
        """Returns shell size matching the size of the barrel.

        Returns: Size of the shell to be shot from this barrel.

        """
        return self.size[1], self.size[1] / 2


class TankBody(Image):
    """Graphical representation of the body of the tank.
    """
    pass


class Tank(RelativeLayout):
    """Widget representing the whole tank.

    Implements the behavior and contains the parts of graphical representation of the tank.

    Attributes:
        body (TankBody): body of the tank.
        barrel (GunBarrel): Gun barrel of the tank.
    """
    body = ObjectProperty(None)
    barrel = ObjectProperty(None)

    def __init__(self, color, barrel_angle, body_size, **kwargs):
        """

        Args:
            color (float, float, float, float): Color of the tank body and barrel.
            barrel_angle (float): Initial angle of the barrel from the x axis in degrees.
            body_size (float, float): Width and height of the tank body, everything is then scaled
                based on this size.
            **kwargs: Arguments passet to the super constructor.
        """
        super().__init__(**kwargs)
        self.body.color = color
        self.barrel.color = color
        self.barrel.angle = barrel_angle
        self.size = (2 * body_size[0], 2 * body_size[1])

    def get_muzzle_pos(self, shell_length):
        """Get the spawn position of the shell.

        Calculates the position to spawn the shell at based on the `self.barrel` angle,
        barrel length and the shell length, so that it does not collide with the barrel
        immediately.

        Args:
            shell_length (float): Length of the shell to be shot from the barrel.

        Returns (Vector): Position to spawn the shell at.

        """
        # the barrel size is given in the base position, where width is the length of the barrel
        rel_pos = Vector(self.barrel.width + shell_length / 2 + 1, 0).rotate(self.barrel.angle)
        rel_pos += Vector(*self.center)
        return rel_pos

    def collide_with(self, shell):
        """Checks if the tank is colliding with the `shell`.

        Calculates if the shapes representing parts of the tank and the `shell` overlap.

        Args:
            shell (Shell): Shell to check the collisions with.

        Returns:
            bool: True if part of the tank is colliding with the shell, False otherwise.

        """
        body_rect = collisions.Rectangle(Vector(*self.to_parent(self.body.center_x, self.body.center_y)),
                                         Vector(*self.body.size),
                                         -Vector(*self.body.size) / 2,
                                         0)
        barrel_rect = collisions.Rectangle(Vector(*self.to_parent(self.barrel.x, self.barrel.center_y)),
                                           Vector(*self.barrel.size),
                                           Vector(0, -self.barrel.height / 2),
                                           self.barrel.angle)
        shell_rect = shell.get_rectangle()
        return shell_rect.collide_rectangle(body_rect) or shell_rect.collide_rectangle(barrel_rect)

    def set_position(self, pos):
        """Sets the position of the bottom left corner of the tank body to `pos`.

        Args:
            pos (float, float): The position to move the bottom left corner to.
        """
        # the tank body size is set as half the size of the tank widget in the kv file
        self.pos = (pos[0] - self.size[0] / 4, pos[1] - self.size[1] / 4)


class Player:
    """Class representing one of the players.

    Attributes:
        color (float, float, float, float): Color representing the player.
        tank (Tank): Tank that belongs to the player.
        traces (deque): Last `self.MAX_TRACES` traces of the shells fired by this player.
        kills (int): Number of players killed by this player.
        shots (int): Number of shots this player fired.
    """
    MAX_TRACES = 10

    def __init__(self, name, color):
        self.name = name
        self.color = color
        self.tank = None
        self.traces = deque([], self.MAX_TRACES)
        self.kills = 0
        self.shots = 0

    def add_trace(self, trace):
        """Add trace to history of traces.

        Adds the trace to `traces`. If `traces` already contains
        `self.MAX_TRACES` traces, the oldes trace is discarded.

        Args:
            trace: The new trace to add.
        """
        self.traces.append(trace)

    def set_tank(self, tank):
        """Sets the tank owned by this player.

        Args:
            tank: The tank to set as owned by this player.
        """
        self.tank = tank

    def collide_with(self, shell):
        """Checks for collision of the `shell` with the players tank.

        Args:
            shell: The shell to check the collision with.

        Returns:
            bool: True if players tank is colliding with the `shell`, False otherwise.

        """
        return self.tank.collide_with(shell)

    def reset(self):
        """Clears game specific state from the player.

        Clears player to initial state as if the instance was just created.
        """
        self.traces = deque([], self.MAX_TRACES)
        self.tank = None
        self.kills = 0
        self.shots = 0


player_list = [
    Player('Alfa', (1, 0, 0, 1)),
    Player('Bravo', (0, 1, 0, 1)),
    Player('Charlie', (0, 0, 1, 1)),
    Player('Delta', (1, 0.5, 0, 1)),
    Player('Echo', (1, 0, 0.5, 1)),
    Player('Foxtrot', (0.5, 1, 0, 1)),
    Player('Golf', (0, 1, 0.5, 1)),
    Player('Hotel', (0.5, 0, 1, 1)),
    Player('India', (0, 0.5, 1, 1)),
    Player('Juliett', (0, 1, 1, 1))
]
"""
List of available player instances.
"""


class Terrain(Image):
    """Terrain representation

    Attributes:
        solid_parts (list of list of int): Represents the solid parts of th
            terrain. The outer list is indexed by x coordinates, the inner list contains ordered
            list of y coordinates of start/end of the terrain. The list is ordered in increasing order
            i.e. from bottom to top of the screen.

            In other words, represents vertical slices of the map, where in each slice we remember
            where the terrain starts/ends. First value is always 0 ,representing the start of the terrain at 0.
    """

    background_image = ObjectProperty(Image(source='singlecolor.png'))

    def __init__(self, **kwargs):
        """Initializes the instance.

        Args:
            **kwargs: Arguments passed to the super constructor.
        """
        super().__init__(**kwargs)

    @staticmethod
    def _get_segments(transitions):
        """Generates segments of solid ground from the transitions.

        Generates segments of solid ground from the given transitions, which represent
        just the transitions from empty space to solid ground.

        Segments are generated from bottom to top, i.e. from lower y values to higher y values.
        Each segment is represented by two y values, first of the bottom edge, second of the top edge.

        Args:
            transitions (list of float): The transitions from empty space to solid ground.

        Yields:
            float, float: Y coordinate of bottom, top part of the segment.
        """
        assert len(transitions) % 2 == 0
        for i in range(len(transitions) // 2):
            yield transitions[i * 2], transitions[i * 2 + 1]

    def redraw(self, color):
        """Redraw the terrain.

        Redraws the terrain onto the canvas using the `color`.

        Args:
            color (float, float, float, float): Color to draw the terrain with.
        """
        self.canvas.clear()
        with self.canvas:
            Rectangle(texture=self.background_image.texture, pos=self.pos, size=self.size)
            Color(color[0], color[1], color[2], color[3])
            for x in range(len(self.solid_parts)):
                for segment in self._get_segments(self.solid_parts[x]):
                    # TODO: use GL_LINES to just push all lines into a buffer and draw then with one call
                    Line(points=[x, segment[0], x, segment[1]])

    def collide_with(self, rectangle):
        """Checks if the `rectangle` is colliding with any solid part of the terrain.

        Args:
            rectangle (Rectangle): The rectangle to check.

        Returns:
            bool: True if the `rectangle` is colliding with the terrain, False otherwise.
        """
        min_x, min_y, max_x, max_y = rectangle.get_bbox()
        for x in range(max(math.floor(min_x), 0), min(math.ceil(max_x), len(self.solid_parts))):
            for segment in self._get_segments(self.solid_parts[x]):
                if rectangle.collide_line_segment(Vector(x, segment[0]), Vector(x, segment[1])):
                    return True
        return False

    def explode(self, circle):
        """Removes the terrain inside the `circle`.

        Removes any terrain that is inside the given `circle`.

        Args:
            circle (Circle); Circle to remove the terrain in.
        """
        min_x, min_y, max_x, max_y = circle.get_bbox()
        for x in range(max(math.floor(min_x), 0), min(math.ceil(max_x) + 1, len(self.solid_parts))):
            # go through the segments backwards and change/delete them
            transitions = self.solid_parts[x]
            assert len(transitions) % 2 == 0
            for i in range(len(transitions) // 2 - 1, -1, -1):
                bot = Vector(x, transitions[i * 2])
                top = Vector(x, transitions[i * 2 + 1])
                if not circle.collide_line_segment(bot, top):
                    continue

                # does collide
                bot_col = circle.collide_point(bot)
                top_col = circle.collide_point(top)
                if bot_col and top_col:
                    # delete segment
                    del transitions[i * 2: i * 2 + 2]
                elif bot_col:
                    # move bot above the circle
                    transitions[i * 2] = circle.get_y_at(bot.x)[1]
                elif top_col:
                    # move top below the circle
                    transitions[i * 2 + 1] = circle.get_y_at(top.x)[2]
                else:
                    # split the existing segment
                    c_y = circle.get_y_at(x)
                    n_trans = [c_y[2], c_y[1]]
                    transitions[i * 2 + 1: i * 2 + 1] = n_trans


class Map(RelativeLayout):
    """Class representing the whole playing field.

    Root class containing the terrain, tanks, shells and traces.

    Attributes:
        terrain (Terrain): Terrain of the map.
        trace_display (TraceDisplay): Component for displaying the traces of shells.
    """
    terrain = ObjectProperty(None)
    trace_display = ObjectProperty(None)
    _terrain_color = (0.1, 0.64, 0.23, 1.0)

    def __init__(self, **kwargs):
        """
        Args:
            **kwargs: Arguments are passed to the super constructor.
        """
        super().__init__(**kwargs)

    def terrain_collision(self, shell):
        """Checks if the shell is colliding with any terrain.

        Checks if the shell is colliding with any part of the terrain.
        If it is, detonates the shell and removes any terrain in it's explosion radius.

        Args:
            shell (Shell): The shell to check the collision with and possibly detonate.

        Returns:
            bool: True if the shell is colliding with any part of the terrain or is underneath the map, False otherwise.
        """
        rect = shell.get_rectangle()
        min_x, min_y, max_x, max_y = rect.get_bbox()
        if min_y < 0:
            return True
        if not self.terrain.collide_with(rect):
            return False
        self.terrain.explode(collisions.Circle(rect.center, shell.explosion_radius))
        return True

    def redraw(self):
        """Redraws the terrain of the map.
        """
        self.terrain.redraw(self._terrain_color)


class Game(Screen):
    """Central class of the game logic and graphics.

    This class handles the event dispatching, user input, and also serves as the root widget for
    all widgets that are part of the current level.

    Attributes:
        map (Map): Map of the level currently played.
        tracer (Tracer, optional): Instance tracing the path of the current shell. Is present only when `shell` is present.
        shell (Shell, optional): The shell currently in flight. There can only be one. May not be present.
        wind (float, optional): Strength of the wind. Negative value represents wind direction towards lower values of x,
            positive towards higher values of x.
        init_players_count (int): Number of players the current level was started with. Is 0 when no level is currently
            being played.
        players (list of Player): List of players in the current level.
        max_wind (float): Maximum strength of the wind in the current level.
        gravity (float): Gravitational acceleration in the current level.
        max_muzzle_shell_vel (float): Muzzle velocity of the shells at maximum power in the current level.
        drag_coef (float): Drag coefficient of shells in the current level.
        explosion_radius (float): Radius of the circle of destroyed terrain by shell explosions in the current level.
        shell_mass (float): Mass of the shells in the current level.
    """
    _FRAME_RATE = 1.0 / 60.0

    map = ObjectProperty(None)
    power_in = ObjectProperty(None)
    angle_in = ObjectProperty(None)
    wind_out = ObjectProperty(None)
    player_out = ObjectProperty(None)
    fire_button = ObjectProperty(None)
    act_bar = ObjectProperty(None)

    def __init__(self, **kwargs):
        """Initializes all attributes of the instance.

        Initializes all attributes of the instance.
        Binds the handlers to UI elements.
        Sets defaults for game properties.

        Args:
            **kwargs: Arguments passed to the super constructor.
        """
        super().__init__(**kwargs)
        self.tracer = None
        self.shell = None
        self.wind = None
        self.update_event = None
        self.init_player_count = 0
        self.players = []
        self._c_player_idx = 0
        self.angle_in.bind(value=self._on_angle_input)
        self.fire_button.bind(on_press=self._on_fire)
        self.max_wind = MAX_WIND
        self.gravity = GRAVITY
        self.max_muzzle_shell_vel = MAX_MUZZLE_SHELL_VEL
        self.drag_coef = DRAG_COEFFICIENT
        self.explosion_radius = DEFAULT_SHELL_EXPLOSION_RADIUS
        self.shell_mass = SHELL_MASS

    def reset(self):
        """Resets the instance to the state as it was after construction.
        """
        self.tracer = None
        self.shell = None
        self.wind = None
        self.update_event = None
        self.init_player_count = 0
        self.players = []
        self._c_player_idx = 0
        self.max_wind = MAX_WIND
        self.gravity = GRAVITY
        self.max_muzzle_shell_vel = MAX_MUZZLE_SHELL_VEL
        self.drag_coef = DRAG_COEFFICIENT
        self.explosion_radius = DEFAULT_SHELL_EXPLOSION_RADIUS
        self.shell_mass = SHELL_MASS
        self._enable_input()

    def on_pre_enter(self, *args):
        """Handles the pre_enter event of the screen.

        This method is called when the transition moving the screen into user's view has just begun.
        Initializes and starts new level.

        Args:
            *args:
        """
        self.init_player_count = len(self.players)
        tank_x_pos = []
        # space the tank across the whole map, adding random noise to their x position
        avg_tank_dist = math.floor(self.map.size[0] / (len(self.players) + 1))
        for i in range(len(self.players)):
            tank_x_pos.append(
                (i + 1) * avg_tank_dist + randrange(math.ceil(-avg_tank_dist / 4), math.floor(avg_tank_dist / 4)))

        # generate terrain with flat spaces at the tank possitions, SPACE_AROUND larger than the tanks
        SPACE_AROUND = 4
        self.map.terrain.solid_parts, tank_pos = generate_terrain(self.map.size, tank_x_pos,
                                                                  (TANK_BODY_SIZE[0] + SPACE_AROUND, TANK_BODY_SIZE[1]))
        for idx, player in enumerate(self.players):
            tank = Tank(player.color, INIT_ANGLE, TANK_BODY_SIZE)
            self.map.add_widget(tank)
            player.set_tank(tank)
            tank.set_position((tank_pos[idx][0] + SPACE_AROUND / 2, tank_pos[idx][1]))

        # start with random player
        self._c_player_idx = randrange(len(self.players))
        self._switch_player()
        self.map.redraw()
        self.update_event = Clock.schedule_interval(self.update, self._FRAME_RATE)

    def _end(self):
        """Ends the current level.

        Removes all tracers, shells, players.
        Stops update events.
        """
        self.update_event.cancel()
        if self.tracer is not None:
            self.tracer.end()

        if self.shell is not None:
            self.map.remove_widget(self.shell)

        for player in self.players.copy():
            self._remove_player(player)

        self.map.trace_display.clear()
        self.reset()

    def exit_to_menu(self):
        """Ends the level and switches to main menu.
        """
        self._end()
        self.manager.current = 'menu'

    def _victory(self, player_count, player):
        """Ends the level and switches to victory screen.

        Ends the level, recording the stats of the winner.
        Switches to victory screen.

        Args:
            player_count (int): Number of players the level started with.
            player (Player): The victorious player.
        """
        victory = self.manager.get_screen('victory')
        victory.player_count = player_count
        victory.player = player
        victory.kills = player.kills
        victory.shots = player.shots

        self._end()
        self.manager.current = 'victory'

    def update(self, dt):
        """Updates the state of the game, moving it by `dt` in time.

        Updates the state of the game, moving the current shell,
        possibly calculating collisions and switching to other players.

        Args:
            dt (float): Time elapsed since the last call of this method.
        """
        if self.shell is not None:
            self.shell.update(dt)
            collided, player = self._check_collisions(self.shell)
            if not collided:
                return

            if len(self.players) == 1:
                self._victory(self.init_player_count, self.players[0])
                return

            self.tracer.end()
            if player is not self.shell.player:
                self.shell.player.add_trace(Trace(self.shell.init_power,
                                                  self.shell.init_angle,
                                                  self.shell.wind,
                                                  self.tracer.trace_points))
            self.map.remove_widget(self.shell)
            self.tracer = None
            self.shell = None
            self._switch_player()

    def _check_collisions(self, shell):
        """Checks if `shell` is colliding with anything.

        Checks whether the `shell` is colliding with any tank or the terrain.

        Args:
            shell (Shell): The shell to check for collisions.

        Returns:
            bool, Player: True, player if the shell collided with players tank,
                True, None if the shell collided with terrain,
                False, None if shell did not collide with anything.
        """
        player = self._collide_players(shell)
        if player is not None:
            self._get_c_player().kills += 1
            self._remove_player(player)
            return True, player
        if self.map.terrain_collision(shell):
            self.map.redraw()
            return True, None
        return False, None

    def _switch_player(self):
        """Switches current player.

        Switches the player currently receiving user input.
        """

        self._c_player_idx = (self._c_player_idx + 1) % len(self.players)
        self.wind = self._generate_wind()
        self.map.trace_display.clear()

        if len(self._get_c_player().traces) > 0:
            last_trace = self._get_c_player().traces[-1]
            self.map.trace_display.draw_trace(last_trace.points,
                                              self.map.trace_display.colors["previous"])
            self._set_bar_display(self._get_c_player().name,
                                  self._get_c_player().color,
                                  last_trace.angle,
                                  last_trace.power,
                                  self.wind)

        else:
            # first switch of players
            self._set_bar_display(self._get_c_player().name,
                                  self._get_c_player().color,
                                  INIT_ANGLE,
                                  INIT_POWER,
                                  self.wind)
        self._enable_input()

    def _set_bar_display(self, player_name, player_color, angle, power, wind):
        """Sets values on the UI bar.
        Args:
            player_name (str): Name of the current player.
            player_color (float, float, float, float): Color representing the current player.
            angle (float): Angle value displayed by the angle input element.
            power (float): Power value displayed by the power input element.
            wind (float): Wind value to be displayed by the wind element.
        """
        self.player_out.text = player_name
        self.player_out.color = player_color
        self.wind_out.text = get_wind_text(wind)
        self.angle_in.value = angle
        self.power_in.value = power

    def _shoot(self, player, power, angle):
        """Shoots shell from the tank owned by the `player`.

        Creates new shell at the position given by the tank belonging to `player`.
        Initial movement is given by the percentage of `power`, and is percentage of `self.max_muzzle_shell_vel`,
        and the `angle` from the x axis in degrees.

        Args:
            player (Player): Owner of the shell.
            power (float): Percentage of the `self.max_muzzle_shell_vel` velocity the shell will initially have.
            angle (float): Angle from the x axis in degrees the shell should be fired at. Specifies the direction of
                the initial shell velocity vector.
        """
        player.shots += 1
        self.shell = Shell(player,
                           power,
                           angle,
                           self.max_muzzle_shell_vel * power / 100,
                           self.shell_mass,
                           self.gravity,
                           self.wind,
                           self.drag_coef,
                           self.explosion_radius)
        self.shell.size = player.tank.barrel.get_shell_size()
        self.map.add_widget(self.shell, canvas='after')
        # update the size of the shell based on the map size
        self.map.do_layout()
        self.shell.center = player.tank.get_muzzle_pos(self.shell.width)
        # draw the shell above everything else
        self.tracer = Tracer(self.map.trace_display, self.shell)

    def _collide_players(self, shell):
        """Checks for collisions between `shell` and all players.
        Args:
            shell (Shell): The shell to check for collisions.

        Returns:
            Player: Player if the `shell` collided with the player, None if the shell did not collide with any players.
        """
        for player in self.players:
            if player.collide_with(shell):
                return player
        return None

    def _on_angle_input(self, instance, value):
        """Handles change in the angle input UI element.

        Moves the gun barrel of the tank based on the value given by the UI element.
        Args:
            instance (Widget): Instance of the UI element that triggered this event.
            value (float): New value of the UI element.
        """
        self._get_c_player().tank.barrel.angle = value

    def _on_fire(self, instance):
        """Handles the press of the FIRE button.

        Switches the game to shell flight mode, with disabled input and shell flying.

        Args:
            instance (Widget): The widget that triggered the event.
        """
        self._disable_input()
        # check if player was writing angle value and forgot to hit enter
        self.angle_in.manual_validate_text()
        self._shoot(self._get_c_player(), self.power_in.value, self.angle_in.value)

    def _get_c_player(self):
        """Gets the currently active player.

        Returns the player currently receiving user input.

        Returns:
            Player: Current active player.
        """
        return self.players[self._c_player_idx]

    def _remove_player(self, player):
        """Removes `player` from the game.

        Removes `player` from the game, i.e. the list of players in this game, deleting any resources that belong to him,
        including the trace history and his tank.

        Args:
            player (Player): The player to remove from the game.
        """
        idx = self.players.index(player)
        if idx <= self._c_player_idx:
            self._c_player_idx -= 1
        self.map.remove_widget(player.tank)
        del self.players[idx]
        player.reset()

    def _generate_wind(self):
        """Generates new random value of wind.

        Returns: New random value of wind, with random strength and dirrection, bounded by `self.max_wind`.

        """
        return (random() - 0.5) * self.max_wind

    def _disable_input(self):
        """Disables all user input.
        """
        self.power_in.disabled = True
        self.angle_in.disabled = True
        self.fire_button.disabled = True

    def _enable_input(self):
        """Enables all user input.
        """
        self.power_in.disabled = False
        self.angle_in.disabled = False
        self.fire_button.disabled = False


class SEApp(App):
    """The class representing the whole application.
    """
    def build(self):
        """Sets up the app window and builds the root element of the Widget hierarchy.

        Returns: The screen manager as the root widget of the hierarchy, with the menu, game and victory screens loaded
            and the menu screen displayed first.
        """
        # sets the minimum size of the window so that the user input's fit on the action bar
        Window.minimum_width = 800
        Window.minimum_height = 600
        self.icon = "tank_icon.png"
        self.title = "Scorched Earth MK4"

        sm = ScreenManager()
        menu = Menu(name='menu')
        sm.add_widget(menu)
        sm.add_widget(Game(name='game'))
        sm.add_widget(Victory(name='victory'))

        menu.player_list = player_list
        menu.GRAVITY = GRAVITY
        menu.MAX_MUZZLE_SHELL_VEL = MAX_MUZZLE_SHELL_VEL
        menu.DRAG_COEFFICIENT = DRAG_COEFFICIENT
        menu.SHELL_MASS = SHELL_MASS
        return sm


if __name__ == '__main__':
    SEApp().run()
