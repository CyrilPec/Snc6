from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

class ConfirmScreen(ModalScreen[bool]):
    CSS = '''
    ConfirmScreen { align: center middle; }
    #dialog { width: 64; height: auto; padding: 2; border: thick $warning; background: $surface; }
    #title { color: $warning; text-style: bold; margin-bottom: 1; }
    #message { margin-bottom: 2; }
    Button { margin-right: 1; }
    '''

    def __init__(self, message: str):
        super().__init__()
        self.message = message

    def compose(self):
        with Vertical(id="dialog"):
            yield Label("PHYSICAL ACTION", id="title")
            yield Static(self.message, id="message")
            with Horizontal():
                yield Button("CONFIRM", id="confirm", variant="warning")
                yield Button("CANCEL", id="cancel")

    def on_button_pressed(self, event: Button.Pressed):
        self.dismiss(event.button.id == "confirm")
