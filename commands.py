"""Turns a line of text into an action for the greenhouse assistant.

Everything the user says or types goes through handle_command(). Voice
input can be added later by feeding its text into this one function, so
the GUI never has to change.
"""
import re

from plant_db import list_plants

QUESTION_WORDS = {
    "what", "how", "why", "when", "where", "which", "who",
    "should", "can", "could", "is", "are", "does", "do", "will", "would",
}


def looks_like_question(text):
    words = re.findall(r"[a-z']+", text.lower())
    return "?" in text or (bool(words) and words[0] in QUESTION_WORDS)


def find_plant(text):
    """Return the plant name mentioned in text, or None."""
    text = text.lower()
    # Longer names first so "bell pepper" wins over any shorter match
    for name in sorted(list_plants(), key=len, reverse=True):
        # Allow simple plurals: tomato -> tomatoes
        pattern = r"\b" + re.escape(name.lower()) + r"(e?s)?\b"
        if re.search(pattern, text):
            return name
    return None


def handle_command(text):
    """Return (plant_name_or_None, reply_message, ask_llm).

    ask_llm is True when the text should be sent to the local LLM; the
    reply is empty in that case because the LLM provides the answer.
    """
    text = text.strip()
    if not text:
        return None, "", False

    plant = find_plant(text)
    question = looks_like_question(text)

    if question:
        return plant, "", True
    if plant:
        return plant, f"Okay, checking conditions for {plant}.", False
    return None, "I don't know that plant yet. Try the dropdown to see what's available.", False


if __name__ == "__main__":
    # Quick self-test: python3 commands.py
    from plant_db import init_db
    init_db()
    for line in [
        "I'm planting basil",
        "growing Tomatoes this year",
        "what about bell pepper?",
        "How humid should it be for lettuce",
        "Is it too hot in here?",
        "dragon fruit",
        "",
    ]:
        print(repr(line), "->", handle_command(line))
