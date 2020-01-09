from kivy.uix.boxlayout import BoxLayout
from kivy.properties import NumericProperty, ObjectProperty, StringProperty, OptionProperty, AliasProperty
from kivy.uix.screenmanager import Screen

"""Implementation of the main menu screen.

The main menu screen is used to set up the parameters of the game, such as number of players,
gravity, shell aerodynamic drag, explosion radius etc. and then start the game.
"""


class MenuValueItem(BoxLayout):
    """UI element allowing user to input value using either text input or a slider.

    UI element consisting of a label, text input and a slider. The label describes the value that can be
    set using the remaining two elements. The input elements are connected so that the value set using one
    is reflected on the state of the other.

    You can set bounds on the allowed value.
    Attributes:
        input_filter (OptionProperty): Has value of `'float'` or `'int'`, which determines the text input validation format.
        step (NumericProperty): Step between values using the slider.
        value (NumericProperty): Current value set by the user.
        label (StringProperty): Text describing the meaning of the value.
        max (NumericProperty): Maximum value of the `value`.
        min (NumericProperty): Minimal value of the `value`.
    """
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


class MenuPercentItem(BoxLayout):
    """UI element allowing user input of percentage, with 100% being the middle point for the slider.

    UI element for convenient input of percentage values. Differs from `MenuValue item in that 100 is always
        in the middle of the slider.

    Attributes:
        value (NumericProperty): The percentage value set by the user, in range of [`min`, `max`].
        label (StringProperty): Text describing the meaning of the `value`.
        max (NumericProperty): Maximal value of the `value`.
        min (NumericProperty): Minimal value of the `value`.
    """
    value = NumericProperty(100)
    label = StringProperty("No name")
    max = NumericProperty(0)
    min = NumericProperty(0)
    text_in = ObjectProperty(None)
    slide_in = ObjectProperty(None)

    def manual_validate_text(self):
        """Manually triggers the text validation, simulating user ENTER press.
        """
        self.text_in.dispatch('on_text_validate')

    def _get_normalized_value(self):
        """Calculates normalized value in range 0-1 from the `self.value`.

        Calculates the position of the slider in the range from 0-1 based on the value of `self.value`,
        so that 100% is always 0.5.
        The percentages of `self.min` to 100% are then linearly distributed from 0 to 0.5,
        percentages of 100% to `self.max` are then linearly distributed from 0.5 to 1.

        Returns: Value in [0-1] representing the position of the slider so that 100% is always 0.5
        and the [`self.min`, 100] and [100, `self.max`] values are distributed linearly.
        """
        # functions from _set_normalized_value transformed so that we are calculating the norm_value from the rest
        if self.value <= 100:
            return ((self.value - self.min) / (100 - self.min))/2
        else:
            return ((self.value - 100) / (self.max - 100)) / 2 + 0.5

    def _set_normalized_value(self, norm_value):
        """Calculates `self.value` from the given `norm_value`.

        Calculates `self.value` from the given normalized value, distributing the values 0 - 0.5 linearly onto
        the interval [`self.min`, 100] and the values 0.5 - 1 linearly onto the interval [100, `self.max`].

        Args:
            norm_value (float): Normalized value [0,1] representing the position of the slider.
        """
        if norm_value <= 0.5:
            self.value = max(min(self.min + (100 - self.min)*(norm_value*2), self.max), self.min)
        else:
            # 100 to self.max
            self.value = max(min(100 + (self.max - 100)*(norm_value-0.5)*2, self.max), self.min)

    normalized_value = AliasProperty(_get_normalized_value, _set_normalized_value, bind=['value', 'max', 'min'])


class Menu(Screen):
    """The main menu screen.

    The initial screen the game starts at, allowing user to set properties of the game and start it.
    """
    num_players = ObjectProperty(None)
    gravity_perc = ObjectProperty(None)
    shell_vel_perc = ObjectProperty(None)
    drag_perc = ObjectProperty(None)
    wind = ObjectProperty(None)
    explosion_r = ObjectProperty(None)
    shell_mass_perc = ObjectProperty(None)

    def __init__(self, **kwargs):
        """
        Args:
            **kwargs: Arguments passed to the super constructor.
        """
        super().__init__(**kwargs)

    def start_game(self):
        """Reads values from the UI elements, sets up the game and starts it.

        This method reads the values from the UI elements set by the user,
        sets the game up using these values and changes the screen to game screen.
        """
        self.num_players.manual_validate_text()
        self.gravity_perc.manual_validate_text()
        self.shell_vel_perc.manual_validate_text()
        self.drag_perc.manual_validate_text()
        self.wind.manual_validate_text()
        self.explosion_r.manual_validate_text()
        self.shell_mass_perc.manual_validate_text()

        game = self.manager.get_screen('game')
        game.players = self.player_list[:self.num_players.value]
        game.gravity = self.GRAVITY * self.gravity_perc.value / 100
        game.max_muzzle_shell_vel = self.MAX_MUZZLE_SHELL_VEL * self.shell_vel_perc.value / 100
        game.drag_coef = self.DRAG_COEFFICIENT * self.drag_perc.value / 100
        game.max_wind = self.wind.value
        game.explosion_radius = self.explosion_r.value
        game.shell_mass = self.SHELL_MASS * self.shell_mass_perc.value / 100

        self.manager.current = 'game'

