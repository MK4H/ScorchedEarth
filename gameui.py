from kivy.properties import NumericProperty, ObjectProperty, StringProperty, BooleanProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.actionbar import ActionItem
from kivy.uix.label import Label

"""Implementation of the UI elements used for the control of the game.

This module contains the implementations of UI elements that are used to control the tanks during the game.
"""


class ValueItem(BoxLayout, ActionItem):
    """Action bar item with value input.

    Allows user to input a value using slider or textinput.
    The two input methods are connected and setting one changes the other to the same value.

    Attributes:
        value (NumericProperty): Current value set by the user.

    """
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
        """Manually triggers the text validation, simulating user ENTER press.
        """
        self.text_in.dispatch('on_text_validate')


class TextItem(Label, ActionItem):
    """UI Action item for displaying text in the action bar.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
