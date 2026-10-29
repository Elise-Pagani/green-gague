"""Talks to the local Ollama server (fully offline once the model is pulled).

ask() never raises: if Ollama isn't running or is too slow, it returns a
short, readable error message so the GUI can just display the result.
"""
import json
import socket
import urllib.error
import urllib.request

from plant_db import list_plants, get_plant

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2:3b"   # if the Pi is too slow, try "llama3.2:1b"
TIMEOUT_SECONDS = 180   # first request is slow while the model loads


def build_system_prompt(selected_plant=None, reading=None):
    """Instructions + the plant table, so answers come from our database."""
    lines = []
    for name in list_plants():
        p = get_plant(name)
        lines.append(
            f"- {p['name']}: {p['min_temp']:.0f}-{p['max_temp']:.0f} °C, "
            f"{p['min_hum']:.0f}-{p['max_hum']:.0f}% RH. {p['notes'] or ''}".rstrip()
        )
    table = "\n".join(lines)

    prompt = (
        "You are the assistant for a greenhouse climate monitor. "
        "Answer in at most 2 short sentences, in plain text with no markdown. "
        "For the plants in the reference table, use ONLY the ranges in the table. "
        "If a plant is not in the table, say it isn't in your database, then give "
        "a rough answer clearly labelled as general guidance. "
        "Temperatures are in °C and humidity is % relative humidity (RH).\n\n"
        f"Reference table (ideal ranges):\n{table}\n"
    )
    if selected_plant:
        prompt += f"\nThe user is currently growing: {selected_plant}."
    if reading:
        prompt += (
            f"\nCurrent greenhouse reading: {reading[0]:.1f} °C, "
            f"{reading[1]:.1f}% RH."
        )
    return prompt


def ask(question, selected_plant=None, reading=None):
    """Send a question to the model and return its answer as a string."""
    body = {
        "model": MODEL,
        "stream": False,
        "keep_alive": "10m",  # keep the model loaded between questions
        "options": {"temperature": 0.3, "num_predict": 120},
        "messages": [
            {"role": "system", "content": build_system_prompt(selected_plant, reading)},
            {"role": "user", "content": question},
        ],
    }
    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            data = json.load(response)
        return data["message"]["content"].strip() or "I didn't get an answer. Try rephrasing."
    except (socket.timeout, TimeoutError):
        return "That took too long. The model may still be loading; try again."
    except urllib.error.URLError:
        return "Can't reach Ollama. Is it running? (try: ollama serve)"
    except (KeyError, ValueError):
        return "Got an unexpected reply from Ollama."


if __name__ == "__main__":
    # Quick test: python3 llm.py
    from plant_db import init_db
    init_db()
    print(ask("What humidity does basil like?", "Basil", (24.0, 60.0)))
