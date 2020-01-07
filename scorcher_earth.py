import math

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics.context_instructions import Color
from kivy.graphics.vertex_instructions import Point, Line, Rectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import NumericProperty, ReferenceListProperty, ObjectProperty, StringProperty, AliasProperty, \
    BooleanProperty, OptionProperty
from kivy.vector import Vector
from kivy.uix.actionbar import ActionItem
from kivy.core.window import Window
from collections import deque
from random import random, randrange
from terrain_generation import generate_terrain
import collisions
import json

MAX_MUZZLE_SHELL_VEL = 750
SHELL_MASS = 100
GRAVITY = 200
DRAG_COEFFICIENT = 0.0025
MAX_WIND = 10
INIT_ANGLE = 90
INIT_POWER = 50
DEFAULT_SHELL_EXPLOSION_RADIUS = 50
TANK_BODY_SIZE = (25, 25)

Window.minimum_width = 800
Window.minimum_height = 600


def clamp(value, min_val, max_val):
    return max(min(value, max_val), min_val)


def get_wind_text(wind):
    if wind > 0:
        return f"{wind:3.2f} >"
    elif wind < 0:
        return f"< {-wind:3.2f}"
    else:
        return 'NO WIND'

class MenuValueItem(BoxLayout):
    input_filter = OptionProperty('float', options=['int', 'float'])
    step = NumericProperty(1)
    value = NumericProperty(0)
    label = StringProperty("No name")
    max = NumericProperty(0)
    min = NumericProperty(0)
    text_in = ObjectProperty(None)
    slide_in = ObjectProperty(None)

    def manual_validate_text(self):
        self.text_in.dispatch('on_text_validate')


class ValueItem(BoxLayout, ActionItem):
    value = NumericProperty(0)
    label = StringProperty("No name")
    max = NumericProperty(0)
    min = NumericProperty(0)
    reverse = BooleanProperty()
    # difference between the displayed value and the value of the value property
    # +90 means displayed value of 90 equals the real value of 0
    value_offset = NumericProperty(0)
    text_in = ObjectProperty(None)
    slide_in = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def manual_validate_text(self):
        self.text_in.dispatch('on_text_validate')


class TextItem(Label, ActionItem):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class Shell(Image):

    velocity_x = NumericProperty(0)
    velocity_y = NumericProperty(0)
    velocity = ReferenceListProperty(velocity_x, velocity_y)

    def __init__(self, player, power, angle, start_vel, mass, gravity, wind, drag_coef, explosion_radius, **kwargs):
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
        self.center = Vector(*self.center) + Vector(*self.velocity) * dt
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
        return Vector(*self.velocity).angle((1,0))

    angle = AliasProperty(get_angle, None, bind=["velocity"])

    def get_rectangle(self):
        return collisions.Rectangle(Vector(*self.center), Vector(*self.size), Vector(-self.width/2, -self.height/2), self.get_angle())


class GunBarrel(Image):
    angle = NumericProperty(INIT_ANGLE)
    b_length = NumericProperty(0.5)
    b_width = NumericProperty(0.2)
    b_size = ReferenceListProperty(b_length, b_width)

    def get_shell_size(self):
        return self.size[1], self.size[1] / 2


class TankBody(Image):
    pass


class Tank(RelativeLayout):
    body = ObjectProperty(None)
    barrel = ObjectProperty(None)

    def __init__(self, color, barrel_angle, body_size, **kwargs):
        super().__init__(**kwargs)
        self.body.color = color
        self.barrel.color = color
        self.barrel.angle = barrel_angle
        self.size = (2*body_size[0], 2*body_size[1])

    def get_muzzle_pos(self, shell_length):
        rel_pos = Vector(self.barrel.b_length * self.width + shell_length / 2, 0).rotate(self.barrel.angle)
        rel_pos += Vector(*self.center)
        return rel_pos

    def collide_with(self, shell):
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
        self.pos = (pos[0] - self.size[0] / 4, pos[1] - self.size[1] / 4)


class Player:
    MAX_TRACES = 10

    def __init__(self, name, color):
        self.name = name
        self.color = color
        self.tank = None
        self.traces = deque([], self.MAX_TRACES)
        self.kills = 0
        self.shots = 0

    def add_trace(self, trace):
        self.traces.append(trace)

    def set_tank(self, tank):
        self.tank = tank

    def collide_with(self, shell):
        return self.tank.collide_with(shell)

    def reset(self):
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


class Tracer:
    TIME_STEP = 0.1

    def __init__(self, trace_display, shell):
        self.display = trace_display
        self.shell = shell
        self.trace_points = []
        self.event = Clock.schedule_interval(self.sample, self.TIME_STEP)

    def sample(self, dt):
        self.display.draw_point(self.shell.center, self.display.colors['current'])
        self.trace_points.append((self.shell.center_x, self.shell.center_y))

    def end(self):
        self.event.cancel()


class Trace:
    def __init__(self, power, angle, wind, points):
        self.power = power
        self.angle = angle
        self.wind = wind
        self.points = points


class TraceDisplay(Widget):
    POINT_SIZE = 2

    colors = {
        "current": (0.0, 0.4, 0.0, 0.5),
        "previous": (0.0, 0.0, 0.0, 0.5)
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def clear(self):
        self.canvas.clear()

    def draw_trace(self, trace_points, color):
        # flatten
        flattened = [coord for point in trace_points for coord in point]
        with self.canvas:
            Color(color[0],
                  color[1],
                  color[2],
                  color[3])
            Point(points=flattened, pointsize=self.POINT_SIZE)

    def draw_point(self, point, color):
        self.draw_trace([point], color)


class Terrain(Image):
    """Terrain representation

    Attributes:
        solid_parts (:obj:`list` of :obj:`list` of :obj: `int`): Represents the solid parts of th
            terrain. The outer list is indexed by x coordinates, the inner list contains ordered
            list of y coordinates of start/end of the terrain. The list is ordered in increasing order
            i.e. from bottom to top of the screen.

            In other words, represents vertical slices of the map, where in each slice we remember
            where the terrain starts/ends. First value is always 0 ,representing the start of the terrain at 0.
    """

    background_image = ObjectProperty(Image(source='singlecolor.png'))

    def __init__(self, **kwargs):
        """

        Args:
            solid_parts (:obj:`list` of :obj:`list` of :obj: `int`): Represents the solid parts of th
            terrain. The outer list is indexed by x coordinates, the inner list contains ordered
            list of y coordinates of start/end of the terrain. The list is ordered in increasing order
            i.e. from bottom to top of the screen.
        """
        super().__init__(**kwargs)

    @staticmethod
    def get_segments(transitions):
        assert len(transitions) % 2 == 0
        for i in range(len(transitions) // 2):
            yield transitions[i * 2], transitions[i * 2 + 1]

    def redraw(self, color):
        self.canvas.clear()
        with self.canvas:
            Rectangle(texture=self.background_image.texture, pos=self.pos, size=self.size)
            Color(color[0], color[1], color[2], color[3])
            for x in range(len(self.solid_parts)):
                for segment in self.get_segments(self.solid_parts[x]):
                    # TODO: use GL_LINES to just push all lines into a buffer and draw then with one call
                    Line(points=[x, segment[0], x, segment[1]])

    def collide_with(self, rectangle):
        min_x, min_y, max_x, max_y = rectangle.get_bbox()
        for x in range(max(math.floor(min_x), 0), min(math.ceil(max_x), len(self.solid_parts))):
            for segment in self.get_segments(self.solid_parts[x]):
                if rectangle.collide_line_segment(Vector(x, segment[0]), Vector(x, segment[1])):
                    return True
        return False

    def explode(self, circle):
        """

        Args:
            cicle;

        Returns:

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
                    del transitions[i * 2 : i * 2 + 2]
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
                    transitions[i*2 + 1 : i*2 + 1] = n_trans

class Map(RelativeLayout):
    terrain = ObjectProperty(None)
    trace_display = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def terrain_collision(self, shell):
        rect = shell.get_rectangle()
        min_x, min_y, max_x, max_y = rect.get_bbox()
        if min_y < 0:
            return True
        if not self.terrain.collide_with(rect):
            return False
        self.terrain.explode(collisions.Circle(rect.center, shell.explosion_radius))
        return True

    def redraw(self):
        self.terrain.redraw((0.5, 0.5, 0.5, 1))


class Game(Screen):
    FRAME_RATE = 1.0/60.0

    map = ObjectProperty(None)
    power_in = ObjectProperty(None)
    angle_in = ObjectProperty(None)
    wind_out = ObjectProperty(None)
    player_out = ObjectProperty(None)
    fire_button = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tracer = None
        self.shell = None
        self.wind = None
        self.update_event = None
        self.init_player_count = 0
        self.players = []
        self.c_player_idx = 0
        self.angle_in.bind(value=self.on_angle_input)
        self.fire_button.bind(on_press=self.on_fire)
        self.max_wind = MAX_WIND
        self.gravity = GRAVITY
        self.max_muzzle_shell_vel = MAX_MUZZLE_SHELL_VEL
        self.drag_coef = DRAG_COEFFICIENT
        self.explosion_radius = DEFAULT_SHELL_EXPLOSION_RADIUS
        self.shell_mass = SHELL_MASS

    def reset(self):
        self.tracer = None
        self.shell = None
        self.wind = None
        self.update_event = None
        self.init_player_count = 0
        self.players = []
        self.c_player_idx = 0
        self.max_wind = MAX_WIND
        self.gravity = GRAVITY
        self.max_muzzle_shell_vel = MAX_MUZZLE_SHELL_VEL
        self.drag_coef = DRAG_COEFFICIENT
        self.explosion_radius = DEFAULT_SHELL_EXPLOSION_RADIUS
        self.shell_mass = SHELL_MASS
        self.enable_input()

    def on_pre_enter(self, *args):
        self.init_player_count = len(self.players)
        tank_x_pos = []
        avg_tank_dist = math.floor(self.map.size[0] / (len(self.players) + 1))
        for i in range(len(self.players)):
            tank_x_pos.append((i + 1) * avg_tank_dist + randrange(math.ceil(-avg_tank_dist/4), math.floor(avg_tank_dist/4)))

        SPACE_AROUND = 4
        self.map.terrain.solid_parts, tank_pos = generate_terrain(self.map.size, tank_x_pos, (TANK_BODY_SIZE[0] + SPACE_AROUND, TANK_BODY_SIZE[1]))
        for idx, player in enumerate(self.players):
            tank = Tank(player.color, INIT_ANGLE, TANK_BODY_SIZE)
            self.map.add_widget(tank)
            player.set_tank(tank)
            tank.set_position((tank_pos[idx][0] + SPACE_AROUND/2, tank_pos[idx][1]))

        self.c_player_idx = randrange(len(self.players))
        self.switch_player()
        self.map.redraw()
        self.update_event = Clock.schedule_interval(self.update, self.FRAME_RATE)

    def end(self):
        self.update_event.cancel()
        if self.tracer is not None:
            self.tracer.end()

        if self.shell is not None:
            self.map.remove_widget(self.shell)

        for player in self.players.copy():
            self.remove_player(player)

        self.map.trace_display.clear()
        self.reset()

    def exit_to_menu(self):
        self.end()
        self.manager.current = 'menu'

    def victory(self, player_count, player):
        victory = self.manager.get_screen('victory')
        victory.player_count = player_count
        victory.player = player
        victory.kills = player.kills
        victory.shots = player.shots

        self.end()
        self.manager.current = 'victory'

    def update(self, dt):
        if self.shell is not None:
            self.shell.update(dt)
            collided, player = self.check_collisions(self.shell)
            if not collided:
                return

            if len(self.players) == 1:
                self.victory(self.init_player_count, self.players[0])
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
            self.switch_player()

    def check_collisions(self, shell):
        player = self.collide_players(shell)
        if player is not None:
            self.get_c_player().kills += 1
            self.remove_player(player)
            return True, player
        if self.map.terrain_collision(shell):
            self.map.redraw()
            return True, None
        return False, None

    def switch_player(self):
        self.c_player_idx = (self.c_player_idx + 1) % len(self.players)
        self.wind = self.generate_wind()
        self.map.trace_display.clear()

        if len(self.get_c_player().traces) > 0:
            last_trace = self.get_c_player().traces[-1]
            self.map.trace_display.draw_trace(last_trace.points,
                                              self.map.trace_display.colors["previous"])
            self.set_bar_display(self.get_c_player().name,
                                 self.get_c_player().color,
                                 last_trace.angle,
                                 last_trace.power,
                                 self.wind)

        else:
            # first switch of players
            self.set_bar_display(self.get_c_player().name,
                                 self.get_c_player().color,
                                 INIT_ANGLE,
                                 INIT_POWER,
                                 self.wind)
        self.enable_input()

    def set_bar_display(self, player_name, player_color, angle, power, wind):
        self.player_out.text = player_name
        self.player_out.color = player_color
        self.wind_out.text = get_wind_text(wind)
        self.angle_in.value = angle
        self.power_in.value = power

    def shoot(self, player, power, angle):
        player.shots += 1
        self.shell = Shell(player,
                           power,
                           angle,
                           self.max_muzzle_shell_vel * power/100,
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

    def collide_players(self, shell):
        for player in self.players:
            if player.collide_with(shell):
                return player
        return None

    def on_angle_input(self, instance, value):
        self.get_c_player().tank.barrel.angle = value

    def on_fire(self, instance):
        self.disable_input()
        # check if player was writing angle value and forgot to hit enter
        self.angle_in.manual_validate_text()
        self.shoot(self.get_c_player(), self.power_in.value, self.angle_in.value)

    def get_c_player(self):
        return self.players[self.c_player_idx]

    def remove_player(self, player):
        idx = self.players.index(player)
        if idx <= self.c_player_idx:
            self.c_player_idx -= 1
        self.map.remove_widget(player.tank)
        del self.players[idx]
        player.reset()

    def generate_wind(self):
        return (random() - 0.5) * self.max_wind

    def disable_input(self):
        self.power_in.disabled = True
        self.angle_in.disabled = True
        self.fire_button.disabled = True

    def enable_input(self):
        self.power_in.disabled = False
        self.angle_in.disabled = False
        self.fire_button.disabled = False


class Menu(Screen):
    num_players = ObjectProperty(None)
    gravity = ObjectProperty(None)
    shell_vel = ObjectProperty(None)
    drag = ObjectProperty(None)
    wind = ObjectProperty(None)
    explosion_r = ObjectProperty(None)
    shell_mass = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def start_game(self):
        self.num_players.manual_validate_text()
        self.gravity.manual_validate_text()
        self.drag.manual_validate_text()
        self.wind.manual_validate_text()

        game = self.manager.get_screen('game')
        game.players = player_list[:self.num_players.value]
        game.gravity = GRAVITY * self.gravity.value
        game.max_muzzle_shell_vel = MAX_MUZZLE_SHELL_VEL * self.shell_vel.value
        game.drag_coef = DRAG_COEFFICIENT * self.drag.value
        game.max_wind = self.wind.value
        game.explosion_radius = self.explosion_r.value
        game.shell_mass = SHELL_MASS * self.shell_mass.value

        self.manager.current = 'game'


class VictoryEntry(BoxLayout):
    number = NumericProperty(0)
    name = StringProperty('---')
    score = NumericProperty(0)


class VictoryInput(BoxLayout):
    number = NumericProperty(0)
    name = StringProperty('anonymous')
    score = NumericProperty(0)


class Victory(Screen):
    contents = ObjectProperty(None)
    show_scores = 10

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.entries = None
        self.leaderboards = None

    def on_pre_enter(self, *args):
        self.contents.add_widget(Label(text="Loading leaderboard."))
        # TODO: async loading

        try:
            with open('leaderboards.json', 'r', encoding='utf-8') as json_file:
                self.leaderboards = json.load(json_file)
        except IOError:
            # TODO: Handle failed JSON parsing
            self.leaderboards = self.create_leaderboards()

        self.display()

    def display(self):
        self.contents.clear_widgets()
        self.contents.add_widget(Label(text=f"Leaderboard for {self.player_count:d} players", size_hint=(1, 2/(3 + self.show_scores))))
        leaderboard = self.leaderboards[str(self.player_count)]

        self.entries = []
        placed = False
        for idx, result in enumerate(leaderboard):
            score = result['score']
            if not placed and score < self.get_score():
                entry = VictoryInput(number=idx + 1, score=self.get_score(), size_hint=(1, 1/(3 + self.show_scores)))
                self.entries.append(entry)
                self.contents.add_widget(entry)
                placed = True
            number = idx + 1 if not placed else idx + 2
            if number <= self.show_scores:
                entry = VictoryEntry(number=number, name=result['name'], score=score, size_hint=(1, 1/(3 + self.show_scores)))
                self.entries.append(entry)
                self.contents.add_widget(entry)

        btn = Button(text="Main menu", size_hint=(1, 1 / (3 + self.show_scores)))
        self.contents.add_widget(btn)
        btn.bind(on_press=self.exit)

    def exit(self, instance):
        leaderboard = []
        for entry in self.entries:
            leaderboard.append({'name': entry.name, 'score': entry.score})

        self.leaderboards[self.player_count] = leaderboard
        try:
            with open('leaderboards.json', 'w+', encoding='utf-8') as json_file:
                json.dump(self.leaderboards, json_file)
        except IOError:
            popup = Popup(title='Error',
                          content=Label(text='Could not save leaderboard.'),
                          size_hint=(None, None), size=(400, 400))
            popup.bind(on_dismiss=self.switch_to_main_menu)
            popup.open()
            return

        self.switch_to_main_menu()

    def create_leaderboards(self):
        new_leaderboards = {}

        for num_players in range(2, 11):
            players = []
            for player in range(10):
                players.append({
                    "name": "---",
                    "score": 0
                })
            new_leaderboards[str(num_players)] = players

        return new_leaderboards

    def switch_to_main_menu(self):
        self.contents.clear_widgets()
        self.entries = None
        self.leaderboards = None

        self.manager.current = 'menu'

    def get_score(self):
        if self.shots != 0:
            return self.kills/self.shots
        else:
            return 0


class SEApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(Menu(name='menu'))
        sm.add_widget(Game(name='game'))
        sm.add_widget(Victory(name='victory'))
        return sm


if __name__ == '__main__':
    SEApp().run()
