from json import JSONDecodeError

from kivy.uix.boxlayout import BoxLayout
from kivy.properties import NumericProperty, ObjectProperty, StringProperty
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.popup import Popup
from kivy.uix.button import Button
import json

"""Victory screen for display and manipulation of the permanent high scores.

This module implements the user interface and the file manipulation to display, update and store the 
all time high scores of the game.

The high scores are split based on the number of players at the start of the game.
So there are separate high scores for 2 player games, 3 player games etc.
"""


class VictoryEntry(BoxLayout):
    """Entry of the victory screen representing the victorious players in previous games.

    Entry with the rank, name and score of the victorious player from the previous games with score in the top 10.

    Attributes:
        number (NumericProperty): The rank of the player.
        name (StringProperty): Name given by the player.
        score (NumericProperty): Score of the player from the game. It represents kills per shot.
    """
    number = NumericProperty(0)
    name = StringProperty('---')
    score = NumericProperty(0)


class VictoryInput(BoxLayout):
    """Entry for the victory screen representing the victorious player in the game that just ended.

    Entry displaying the rank and score of the victorious player from the game that just finnished.
    Allows the user to enter his name.

        Attributes:
        number (NumericProperty): The rank of the player.
        name (StringProperty): Name given by the player.
        score (NumericProperty): Score of the player from the game. It represents kills per shot.
    """
    number = NumericProperty(0)
    name = StringProperty('anonymous')
    score = NumericProperty(0)


class Victory(Screen):
    """Screen displaying the high scores in the games with the given number of players.

    Displays the high scores in games with the `self.player_count` number of players.
    If the victor of the current game scored in the top ten, allows the user to enter the victors name to be
    stored in the persistent high scores.

    High scores are persisted in a file, separated for each possible number of players.
    """
    contents = ObjectProperty(None)
    show_scores = 10

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.entries = None
        self.leaderboards = None

    def on_pre_enter(self, *args):
        """Handles the initialization of the screen on it's transition.

        Loads the high scores from the file and creates the graphical representation.
        If no high score file is found, generates new file.

        Args:
            *args:
        """
        self.contents.add_widget(Label(text="Loading leaderboard."))
        # TODO: async loading

        try:
            with open('leaderboards.json', 'r', encoding='utf-8') as json_file:
                self.leaderboards = json.load(json_file)
        except IOError:
            self.leaderboards = self._create_leaderboards()
        except JSONDecodeError as e:
            self.leaderboards = self._create_leaderboards()
            # TODO: display or log

        self._display()

    def _display(self):
        """Creates the graphical representation of the high scores loaded in `self.leaderboards`.

        Creates the UI elements to display the high scores of the game size `self.player_count`.

        If the current player scored in the displayed top ten, inserts the input element at the appropriate rank.
        """
        self.contents.clear_widgets()
        self.contents.add_widget(Label(text=f"Leaderboard for {self.player_count:d} players", size_hint=(1, 2/(3 + self.show_scores))))
        leaderboard = self.leaderboards[str(self.player_count)]

        self.entries = []
        placed = False
        for idx, result in enumerate(leaderboard):
            score = result['score']
            # if we did not generate entry for current player, and the current high score is lower than new, generate input entry
            if not placed and score < self._get_score():
                entry = VictoryInput(number=idx + 1, score=self._get_score(), size_hint=(1, 1/(3 + self.show_scores)))
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
        btn.bind(on_press=self._exit)

    def _exit(self, instance):
        """Exits the screen, saving the leaderboards to the persistent storage.

        Args:
            instance (Widget): The widget triggering the event.
        """
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
            popup.bind(on_dismiss=self._switch_to_main_menu)
            popup.open()
            return

        self._switch_to_main_menu()

    def _create_leaderboards(self):
        """Generates new empty leaderboards.
        Returns: New empty generated leaderboards
        """
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

    def _switch_to_main_menu(self):
        """Clears all contents and switches to main menu.
        """
        self.contents.clear_widgets()
        self.entries = None
        self.leaderboards = None

        self.manager.current = 'menu'

    def _get_score(self):
        """Calculates the score
        """
        if self.shots != 0:
            return self.kills/self.shots
        else:
            return 0
