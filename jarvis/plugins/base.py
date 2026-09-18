"""Tiny plugin API.

A plugin matches text, then runs and returns a reply string.
To add one: create mything_plugin.py in this package with a
module-level `plugin = MyPlugin()` instance. It loads automatically.
"""


class Plugin:
    name = "base"
    description = ""

    def bind(self, brain):
        """Called once with the Brain that owns this plugin.

        Gives access to brain.config, and lets background work announce
        later via brain.alert(text) (spoken + logged + popup by the UI).
        The default just stores the brain; override only if you need it.
        """
        self.brain = brain

    def match(self, text: str) -> bool:
        """True if this plugin should handle the (lowercased) text."""
        return False

    def run(self, text: str) -> str:
        """Handle the text. Return the reply to speak and show."""
        return ""
