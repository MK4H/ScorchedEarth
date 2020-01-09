from kivy.uix.widget import Widget
from kivy.graphics.context_instructions import Color
from kivy.graphics.vertex_instructions import Point
from kivy.clock import Clock


"""Implements shell tracers

This module implements the ability to record, store and display shell tracers, which trace the flight path of
a shell.

"""


class Tracer:
    """Samples the shell position during the flight, creating shell trace.

    This class periodically samples the `self.shell` position and records it,
    while also pushing it into the give `self.display`, displaying it to the user.

    Attributes:
        TIME_STEP (float): Time interval between samples in seconds.
        display (TraceDisplay): Display used to display the trace to the user.
        shell (Shell): The traced shell.
        trace_points (list of (float, float)): The trace points in chronological order.
    """
    TIME_STEP = 0.1

    def __init__(self, trace_display, shell):
        """Starts the sampling

        Initializes the Tracer and starts the sampling.

        Args:
            trace_display (TraceDisplay): Display used to display the trace to the user.
            shell (Shell): The shell to trace.
        """
        self.display = trace_display
        self.shell = shell
        self.trace_points = []
        self._event = Clock.schedule_interval(self.sample, self.TIME_STEP)

    def sample(self, dt):
        """The sampling method

        Called with `self.TIME_STEP` period, samples the position of the `self.shell`.

        Args:
            dt: Time elapsed since the last invocation of this method.
        """
        self.display.draw_point(self.shell.center, self.display.colors['current'])
        self.trace_points.append((self.shell.center_x, self.shell.center_y))

    def end(self):
        """Stops the sampling.
        """
        self._event.cancel()


class Trace:
    """Class representing one flight of a shell.

    Contains all data representing a shot.

    Attributes:
        power (float): Power the shell was shot with.
        angle (float): The angle from the x axis in degrees the shell was shot at.
        wind (float): Power and direction of the wind while the shell was in flight.
        points (list of (float, float)): Samples of shell position at constant time interval.
    """
    def __init__(self, power, angle, wind, points):
        self.power = power
        self.angle = angle
        self.wind = wind
        self.points = points


class TraceDisplay(Widget):
    """Displays lists of position samples as a trace of the shell onto the display.

    Displays given list of positions as a trace of a shell.

    Attributes:
        POINT_SIZE (int): Size of the point representing each position.
        colors (dict of (str,(float, float, float, float))): Preset colors that can be used to
            consistently display traces of previous shells or shell currently in flight.

    """
    POINT_SIZE = 2

    colors = {
        "current": (0.0, 0.4, 0.0, 0.5),
        "previous": (0.0, 0.0, 0.0, 0.5)
    }

    def __init__(self, **kwargs):
        """

        Args:
            **kwargs: Arguments passed to super constructor.
        """
        super().__init__(**kwargs)

    def clear(self):
        """Clears the display.
        """
        self.canvas.clear()

    def draw_trace(self, trace_points, color):
        """Draws the given list of points `trace_points` as a sequence of points on the display.

        Args:
            trace_points (list of (float, float)): List of points to display.
            color (float, float, float, float): Color of the displayed points. You can use one of the
                color presets from `TraceDisplay.colors`.
        """
        # flatten
        flattened = [coord for point in trace_points for coord in point]
        with self.canvas:
            Color(color[0],
                  color[1],
                  color[2],
                  color[3])
            Point(points=flattened, pointsize=self.POINT_SIZE)

    def draw_point(self, point, color):
        """Draws additional point onto the display.

        Args:
            point (float, float): The position to draw the point at.
            color (float, float, float, float): Color of the displayed point.
        """
        self.draw_trace([point], color)
