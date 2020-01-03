from kivy.app import App
from kivy.clock import Clock
from kivy.graphics.context_instructions import Color
from kivy.graphics.vertex_instructions import Point
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.widget import Widget
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import NumericProperty, ReferenceListProperty, ObjectProperty, StringProperty, AliasProperty, \
    BooleanProperty
from kivy.vector import Vector
from kivy.uix.actionbar import ActionItem
from collections import deque

MAX_SHELL_VELOCITY = 1000
GRAVITY = 200
DRAG_COEFFICIENT = 0.00002
INIT_ANGLE = 90
INIT_POWER = 50


def clamp(value, min_val, max_val):
    return max(min(value, max_val), min_val)


class ValueItem(BoxLayout, ActionItem):
    value = NumericProperty(0)
    label = StringProperty("No name")
    max = NumericProperty(0)
    min = NumericProperty(0)
    reverse = BooleanProperty()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class TextItem(Label, ActionItem):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class Shell(Image):

    velocity_x = NumericProperty(0)
    velocity_y = NumericProperty(0)
    velocity = ReferenceListProperty(velocity_x, velocity_y)

    def __init__(self, power, angle, gravity, wind, drag_coef, **kwargs):
        super().__init__(**kwargs)
        self.init_power = power
        self.init_angle = angle
        self.gravity = gravity
        self.wind = wind
        self.drag_coef = drag_coef
        vel_vec = Vector(power/100 * MAX_SHELL_VELOCITY, 0).rotate(angle)
        self.velocity = (vel_vec.x, vel_vec.y)

    def update(self, dt):
        self.center = Vector(*self.center) + Vector(*self.velocity) * dt
        self.velocity_y -= self.gravity * dt

        vel_vec = Vector(self.velocity_x + self.wind, self.velocity_y)
        # based on https://en.wikipedia.org/wiki/Drag_equation
        # hides the density, area and other constants for the shell into the drag coefficient
        drag = vel_vec.normalize() * self.drag_coef * vel_vec.length2()
        vel_vec = vel_vec - drag
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


class GunBarrel(Image):
    angle = NumericProperty(0)
    b_length = NumericProperty(0.5)
    b_width = NumericProperty(0.2)
    b_size = ReferenceListProperty(b_length, b_width)


class TankBody(Image):
    pass


class Tank(RelativeLayout):
    body = ObjectProperty(None)
    barrel = ObjectProperty(None)

    def __init__(self, color, barrel_angle, **kwargs):
        super().__init__(**kwargs)
        self.body.color = color
        self.barrel.color = color
        self.barrel.angle = barrel_angle

    def get_muzzle_pos(self):
        rel_pos = Vector(self.barrel.b_length * self.width, 0).rotate(self.barrel.angle)
        rel_pos += Vector(*self.center)
        return rel_pos


class Player:
    MAX_TRACES = 10

    def __init__(self, name, color):
        self.name = name
        self.color = color
        self.tank = None
        self.traces = deque([], self.MAX_TRACES)

    def add_trace(self, trace):
        self.traces.append(trace)

    def set_tank(self, tank):
        self.tank = tank

    def collide_with(self, shell):
        #TODO: Collision
        return False


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


class Map(RelativeLayout):
    foreground_image = ObjectProperty(
        Image(source=''))
    trace_display = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def terrain_collision(self, shell):
        #TODO: Proper collision
        return shell.y < 20


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
        self.update_event = None
        self.players = []
        self.c_player_idx = 0
        self.angle_in.bind(value=self.on_angle_input)
        self.fire_button.bind(on_press=self.on_fire)

    def on_pre_enter(self, *args):
        for idx, player in enumerate(self.players):
            tank = Tank(player.color, self.angle_in.value)
            self.map.add_widget(tank)
            player.set_tank(tank)
            tank.pos = (idx * 100, 20)
        self.c_player_idx = len(self.players) + 1
        self.switch_player()
        self.update_event = Clock.schedule_interval(self.update, self.FRAME_RATE)

    def end(self):
        self.update_event.cancel()

    def update(self, dt):
        if self.shell is not None:
            # TODO: SWitch back to real dt
            self.shell.update(dt)
            if self.check_collisions(self.shell):
                self.tracer.end()
                self.get_c_player().add_trace(Trace(self.shell.init_power,
                                                    self.shell.init_angle,
                                                    self.shell.wind,
                                                    self.tracer.trace_points))
                self.map.remove_widget(self.shell)
                self.tracer = None
                self.shell = None
                self.switch_player()

    def check_collisions(self, shell):
        if self.collide_players(shell):
            return True
        if self.map.terrain_collision(shell):
            return True
        return False

    def switch_player(self):
        self.c_player_idx = (self.c_player_idx + 1) % len(self.players)
        self.player_out.text = self.get_c_player().name
        self.map.trace_display.clear()
        if len(self.get_c_player().traces) > 0:
            last_trace = self.get_c_player().traces[-1]
            self.map.trace_display.draw_trace(last_trace.points,
                                              self.map.trace_display.colors["previous"])
            self.angle_in.value = last_trace.angle
            self.power_in.value = last_trace.power
        else:
            # first switch of players
            self.angle_in.value = INIT_ANGLE
            self.power_in.value = INIT_POWER

        self.enable_input()

    def shoot(self, player):
        self.shell = Shell(self.power_in.value, self.angle_in.value, GRAVITY, 0, DRAG_COEFFICIENT)
        self.map.add_widget(self.shell, canvas='after')
        # update the size of the shell based on the map size
        self.map.do_layout()
        self.shell.center = player.tank.get_muzzle_pos()
        # draw the shell above everything else
        self.tracer = Tracer(self.map.trace_display, self.shell)

    def collide_players(self, shell):
        for player in self.players:
            if player.collide_with(shell):
                return True
        return False

    def on_angle_input(self, instance, value):
        self.get_c_player().tank.barrel.angle = value

    def on_fire(self, instance):
        self.disable_input()
        self.shoot(self.get_c_player())

    def get_c_player(self):
        return self.players[self.c_player_idx]

    def disable_input(self):
        self.power_in.disabled = True
        self.angle_in.disabled = True
        self.fire_button.disabled = True

    def enable_input(self):
        self.power_in.disabled = False
        self.angle_in.disabled = False
        self.fire_button.disabled = False


class Menu(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def start_game(self):
        players = [Player('Player one', (1, 0, 0, 1)), Player('Player two', (0, 1, 0, 1))]
        self.manager.get_screen('game').players = players
        self.manager.current = 'game'


class SEApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(Menu(name='menu'))
        sm.add_widget(Game(name='game'))
        return sm


if __name__ == '__main__':
    SEApp().run()
