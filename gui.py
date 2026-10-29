import queue
import threading
import tkinter as tk
from tkinter import font
from datetime import datetime

import background
from sensor import get_sensor, ON_PI
from plant_db import init_db, list_plants, get_plant, check_conditions
from commands import handle_command
from llm import ask
from zones import TextZone, RowZone

# Real DHT22 on the Pi, simulated sensor on a PC/Mac
sensor = get_sensor()

# Make sure the plant database exists and is filled
init_db()

# ---------------------------------------------------------------- theme
# Every theme draws its text on a backdrop: a soft gradient (Light, Dark) or
# a blurred photo (Nature). Text colors were checked for WCAG AA contrast
# (4.5:1 or better) against the WORST point of the backdrop: along the whole
# gradient, or, for the photo, after lightening it just enough (see
# background.py). The reading cards stay solid so the numbers are always crisp.
# GRAD_TOP / GRAD_BOTTOM are the two ends of the gradient.
THEMES = {
    "light": dict(
        BG="#F1F8EF", CARD="#FFFFFF", BORDER="#C5D9C8",
        GRAD_TOP="#F8FCF6", GRAD_BOTTOM="#E9F4E7",
        TEXT="#1E3A2B", MUTED="#4F6B58",
        TEMP="#B8500A", HUM="#0B6E99",
        OK="#1B7541", WARN="#B3261E", WAIT="#8F5700",
        ACCENT="#2A7549", ON_ACCENT="#FFFFFF",
    ),
    "dark": dict(
        BG="#12211A", CARD="#1B3026", BORDER="#2E4A3A",
        GRAD_TOP="#0D1913", GRAD_BOTTOM="#183024",
        TEXT="#E6F2E8", MUTED="#A9C2B0",
        TEMP="#F6A35B", HUM="#67C7E8",
        OK="#5FD08A", WARN="#FF8A80", WAIT="#F2B84B",
        ACCENT="#4CAF73", ON_ACCENT="#0E1A13",
    ),
    "nature": dict(
        BG="#F4FAF2", CARD="#FFFFFF", BORDER="#9DBFA6",
        TEXT="#0F2418", MUTED="#2D4636",
        TEMP="#B8500A", HUM="#0B6E99",
        OK="#0F5530", WARN="#8A1710", WAIT="#6B4000",
        ACCENT="#14532F", ON_ACCENT="#FFFFFF",
    ),
}
# Colors of text that sits directly on the photo in the Nature theme
NATURE_TEXT_COLORS = [THEMES["nature"][role] for role in
                      ("TEXT", "MUTED", "ACCENT", "OK", "WARN", "WAIT")]
SIZES = {"Small": 0.85, "Medium": 1.0, "Large": 1.2}

# Current settings (changed from the Settings menu)
current = {"theme": "light", "size": "Medium"}

NO_PLANT = "Select a plant..."

root = tk.Tk()
root.title("Climate Monitor")
root.geometry("800x480")   # the size the professor's original code used
if ON_PI:
    root.attributes("-fullscreen", True)
else:
    root.resizable(False, False)   # on a PC/Mac, keep it at the Pi's size


def color(role):
    return THEMES[current["theme"]][role]


# Every widget registers which color ROLE each option uses (e.g. fg="MUTED").
# Switching theme then just re-applies the roles with the new palette.
ROLES = {}


def paint(widget, **roles):
    ROLES.setdefault(widget, {}).update(roles)
    widget.config(**{opt: color(role) for opt, role in roles.items()})


def repaint_all():
    for widget, roles in ROLES.items():
        widget.config(**{opt: color(role) for opt, role in roles.items()})


# Fonts are shared objects, so resizing one resizes every widget using it.
FONTS = {}

# The big-number size fit_readings last applied (remembered here because we
# never read sizes back from Tk; apply_scale clears it when it resets fonts)
fit_state = {"size": None}


def px(size, scale=1.0):
    """Font size in PIXELS (negative = pixels in Tk).

    The window is a fixed 800x480 pixels, so fonts are sized in pixels too.
    Point sizes would change with each screen's DPI setting and make the
    layout fit on one computer but overflow on another. `size` is the
    familiar point size at 96 DPI; 4/3 converts it to pixels."""
    return -max(9, round(size * 4 / 3 * scale))


def get_font(size, bold=False):
    key = (size, bold)
    if key not in FONTS:
        FONTS[key] = font.Font(
            family="DejaVu Sans", size=px(size),
            weight="bold" if bold else "normal"
        )
    return FONTS[key]


def apply_scale():
    scale = SIZES[current["size"]]
    for (size, _bold), f in FONTS.items():
        # The big reading numbers are already huge, so they never grow
        # past their normal size (this keeps the cards from clipping).
        s = min(scale, 1.0) if size >= 40 else scale
        f.configure(size=px(size, s))
    fit_state["size"] = None   # the big number was just reset; refit it


def make_label(parent, text, size, fg, bold=False, bg="BG"):
    """A normal Label (used inside the solid reading cards)."""
    label = tk.Label(parent, text=text, font=get_font(size, bold))
    paint(label, fg=fg, bg=bg)
    return label


def make_line(zone, text, size, fg, bold=False, gap=0, wraplength=0):
    """A line of text drawn straight onto a zone (no box around it)."""
    line = zone.add_line(text, get_font(size, bold), color(fg), gap=gap,
                         wraplength=wraplength)
    paint(line, fg=fg)
    return line


def make_row_text(zone, text, size, fg, bold=False, padx=(0, 0)):
    part = zone.add_text(text, get_font(size, bold), color(fg), padx=padx)
    paint(part, fg=fg)
    return part


def say(label, text, fg):
    """Set a label's text and color role together."""
    label.config(text=text)
    paint(label, fg=fg)


paint(root, bg="BG")

# --------------------------------------------------------------- layout
# One grid, two columns, four rows:
#   header zone (title + subtitle)
#   reading cards (take all the spare room)
#   plant picker zone
#   status zone (reply, ideal range, warnings, sensor status, clock)
# The zones are canvases (see zones.py): their text is drawn directly on the
# background, so on the Nature theme there are no boxes around it.
root.columnconfigure((0, 1), weight=1, uniform="cols")
root.rowconfigure(1, weight=1)

header = TextZone(root, pad_top=16, pad_bottom=3)
paint(header, bg="BG")
header.grid(row=0, column=0, columnspan=2, sticky="ew")
make_line(header, "CLIMATE MONITOR", 24, "ACCENT", True)
make_line(header, "LIVE ENVIRONMENTAL READINGS", 10, "MUTED")

# Reading cards (solid, so the numbers are always easy to read)
temp_card = tk.Frame(root, highlightthickness=1)
paint(temp_card, bg="CARD", highlightbackground="BORDER")
temp_card.grid(row=1, column=0, sticky="nsew", padx=(35, 10), pady=(10, 8))

hum_card = tk.Frame(root, highlightthickness=1)
paint(hum_card, bg="CARD", highlightbackground="BORDER")
hum_card.grid(row=1, column=1, sticky="nsew", padx=(10, 35), pady=(10, 8))

# Plant picker
selected_plant = tk.StringVar(value=NO_PLANT)

picker = RowZone(root, pad_top=4, pad_bottom=2)
paint(picker, bg="BG")
picker.grid(row=2, column=0, columnspan=2, sticky="ew")

menu_font = get_font(12)
make_row_text(picker, "PLANT:", 11, "MUTED", True, padx=(0, 10))
plant_menu = tk.OptionMenu(
    picker, selected_plant, NO_PLANT, *list_plants(),
    command=lambda _choice: refresh_plant_status()
)
plant_menu.config(font=menu_font, width=18, bd=0, relief="flat",
                  highlightthickness=1)
paint(plant_menu, bg="CARD", fg="TEXT",
      activebackground="CARD", activeforeground="TEXT",
      highlightbackground="BORDER", highlightcolor="ACCENT")
plant_menu["menu"].config(font=menu_font)
paint(plant_menu["menu"], bg="CARD", fg="TEXT",
      activebackground="ACCENT", activeforeground="ON_ACCENT")
picker.add_widget(plant_menu)

# Text command box: type e.g. "I'm planting basil" and press Enter
make_row_text(picker, "OR TYPE:", 11, "MUTED", True, padx=(20, 10))
command_entry = tk.Entry(picker, font=menu_font, width=24, relief="flat",
                         highlightthickness=1)
paint(command_entry, bg="CARD", fg="TEXT", insertbackground="TEXT",
      highlightbackground="BORDER", highlightcolor="ACCENT")
picker.add_widget(command_entry, extra_height=10)

# Reply, ideal range, status lines
status_zone = TextZone(root, pad_top=2, pad_bottom=10)
paint(status_zone, bg="BG")
status_zone.grid(row=3, column=0, columnspan=2, sticky="ew")

reply_label = make_line(status_zone, "", 10, "MUTED", gap=2, wraplength=700)
plant_range = make_line(status_zone, "", 10, "MUTED")
plant_status = make_line(status_zone, "Pick a plant to check conditions",
                         12, "MUTED", True, gap=2)
status = make_line(status_zone, "Connecting to sensor...", 11, "OK", gap=4)
clock = make_line(status_zone, "", 10, "MUTED", gap=3)

ZONES = [header, picker, status_zone]


def build_reading(card, title, color_role, unit):
    """One reading card: title, big number and unit, centered in the card."""
    inner = tk.Frame(card)
    paint(inner, bg="CARD")
    inner.pack(expand=True)   # expand without fill = centered in the card
    make_label(inner, title, 13, "MUTED", True, bg="CARD").pack(pady=(0, 4))
    row = tk.Frame(inner)
    paint(row, bg="CARD")
    row.pack()
    value = make_label(row, "--.-", 48, color_role, True, bg="CARD")
    value.pack(side="left")
    make_label(row, unit, 18, color_role, bg="CARD").pack(
        side="left", anchor="s", padx=(8, 0), pady=(0, 14))
    return inner, value


temp_inner, temp_value = build_reading(temp_card, "TEMPERATURE", "TEMP", "°C")
hum_inner, hum_value = build_reading(hum_card, "HUMIDITY", "HUM", "% RH")


def fit_readings(event=None):
    """Shrink the big numbers if the cards are too short to hold them.

    Point sizes turn into different pixel heights on different screens, so
    instead of guessing we measure font heights and pick the largest number
    size that fits (this only measures; it never touches the layout while
    testing sizes, so it can't trigger itself in a loop)."""
    available = temp_card.winfo_height() - 16   # border + breathing room
    if available <= 16:
        return   # window not drawn yet

    title_h = get_font(13, True).metrics("linespace") + 4
    unit_h = get_font(18).metrics("linespace") + 14
    top = round(48 * min(SIZES[current["size"]], 1.0))

    chosen = 24
    probe = font.Font(family="DejaVu Sans", size=px(top), weight="bold")
    for size in range(top, 23, -2):
        probe.configure(size=px(size))
        if title_h + max(probe.metrics("linespace"), unit_h) <= available:
            chosen = size
            break

    if fit_state["size"] != chosen:
        fit_state["size"] = chosen   # remembered here; never read back from Tk
        get_font(48, True).configure(size=px(chosen))


temp_card.bind("<Configure>", fit_readings)

# ------------------------------------------------------------- backdrop
# The picture behind everything: a gradient for Light and Dark, a blurred
# photo for Nature. One big label shows it behind the cards, and the text
# zones (see zones.py) show the same picture lined up with their position,
# so text looks printed right on it.
backdrops = {}              # theme name -> PhotoImage, built the first time
backdrop_label = {"widget": None}


def screen_size():
    if ON_PI:
        return root.winfo_screenwidth(), root.winfo_screenheight()
    return 800, 480


def make_gradient(width, height, top, bottom):
    """A top-to-bottom gradient, built with plain Tk (no Pillow needed)."""
    image = tk.PhotoImage(width=width, height=height)
    top_rgb = [int(top[i:i + 2], 16) for i in (1, 3, 5)]
    bottom_rgb = [int(bottom[i:i + 2], 16) for i in (1, 3, 5)]
    for y in range(height):
        t = y / max(1, height - 1)
        r, g, b = (round(a + (c - a) * t) for a, c in zip(top_rgb, bottom_rgb))
        image.put(f"#{r:02x}{g:02x}{b:02x}", to=(0, y, width, y + 1))
    return image


def build_backdrop(theme):
    width, height = screen_size()
    if theme == "nature":
        data = background.build_background(
            width, height, text_colors=NATURE_TEXT_COLORS)
        return tk.PhotoImage(data=data)
    return make_gradient(width, height,
                         THEMES[theme]["GRAD_TOP"], THEMES[theme]["GRAD_BOTTOM"])


def show_backdrop(theme):
    """Put the theme's backdrop behind everything."""
    if theme not in backdrops:
        backdrops[theme] = build_backdrop(theme)   # built first: if it fails,
    photo = backdrops[theme]                       # nothing is half-changed
    if backdrop_label["widget"] is None:
        backdrop_label["widget"] = tk.Label(root, bd=0)
    label = backdrop_label["widget"]
    label.config(image=photo)
    label.place(x=0, y=0, relwidth=1, relheight=1)
    label.lower()   # behind every other widget
    for zone in ZONES:
        zone.set_photo(photo)


show_backdrop(current["theme"])


# ------------------------------------------------------- settings menu
theme_var = tk.StringVar(value=current["theme"])
size_var = tk.StringVar(value=current["size"])


def on_theme_change():
    name = theme_var.get()
    try:
        show_backdrop(name)
    except Exception as error:   # e.g. Pillow missing or a bad image file
        theme_var.set(current["theme"])
        say(reply_label, f"Couldn't load the {name.title()} background ({error}).", "WARN")
        return
    current["theme"] = name
    repaint_all()


def on_size_change():
    current["size"] = size_var.get()
    apply_scale()
    root.update_idletasks()
    for zone in ZONES:
        zone.relayout()
    root.update_idletasks()
    fit_readings()


settings_btn = tk.Menubutton(root, text="Settings ▾", font=get_font(10, True),
                             relief="flat", bd=0, padx=12, pady=6,
                             highlightthickness=1)
paint(settings_btn, bg="CARD", fg="TEXT",
      activebackground="ACCENT", activeforeground="ON_ACCENT",
      highlightbackground="BORDER")

settings_menu = tk.Menu(settings_btn, tearoff=0, font=get_font(11))
paint(settings_menu, bg="CARD", fg="TEXT",
      activebackground="ACCENT", activeforeground="ON_ACCENT",
      disabledforeground="MUTED", selectcolor="ACCENT")
settings_btn["menu"] = settings_menu

settings_menu.add_command(label="THEME", state="disabled")
settings_menu.add_radiobutton(label="Light", variable=theme_var,
                              value="light", command=on_theme_change)
settings_menu.add_radiobutton(label="Dark", variable=theme_var,
                              value="dark", command=on_theme_change)
if background.pillow_available():
    settings_menu.add_radiobutton(label="Nature", variable=theme_var,
                                  value="nature", command=on_theme_change)
else:
    settings_menu.add_radiobutton(label="Nature (needs Pillow)",
                                  variable=theme_var, value="nature",
                                  state="disabled")
settings_menu.add_separator()
settings_menu.add_command(label="TEXT SIZE", state="disabled")
for size_name in SIZES:
    settings_menu.add_radiobutton(label=size_name, variable=size_var,
                                  value=size_name, command=on_size_change)

settings_btn.place(relx=1.0, x=-15, y=12, anchor="ne")

# ------------------------------------------------------ asking the LLM
# The LLM can take several seconds, so it runs in a background thread and
# hands its answer back through this queue (keeps the window responsive).
answers = queue.Queue()
llm_busy = {"value": False}

# Most recent good sensor reading: (temperature, humidity) or None
state = {"reading": None}


def ask_llm_in_background(text):
    plant = selected_plant.get()
    plant = None if plant == NO_PLANT else plant
    reading = state["reading"]

    def worker():
        answers.put(ask(text, plant, reading))

    llm_busy["value"] = True
    say(reply_label, "Thinking...", "MUTED")
    threading.Thread(target=worker, daemon=True).start()


def check_for_answer():
    try:
        answer = answers.get_nowait()
        say(reply_label, answer, "TEXT")
        llm_busy["value"] = False
    except queue.Empty:
        pass
    root.after(200, check_for_answer)


def submit_command(event=None):
    if llm_busy["value"]:
        return  # still answering the last question

    plant_name, reply, ask_llm = handle_command(command_entry.get())
    if plant_name is not None:
        selected_plant.set(plant_name)
        refresh_plant_status()
    if ask_llm:
        ask_llm_in_background(command_entry.get())
    else:
        say(reply_label, reply, "MUTED")
    command_entry.delete(0, "end")


command_entry.bind("<Return>", submit_command)

# ------------------------------------------------- readings and warnings
def refresh_plant_status():
    name = selected_plant.get()
    plant = get_plant(name) if name != NO_PLANT else None

    if plant is None:
        plant_range.config(text="")
        say(plant_status, "Pick a plant to check conditions", "MUTED")
        return

    plant_range.config(
        text=(
            f"Ideal for {plant['name']}: "
            f"{plant['min_temp']:.0f}-{plant['max_temp']:.0f} °C, "
            f"{plant['min_hum']:.0f}-{plant['max_hum']:.0f}% RH"
        )
    )

    if state["reading"] is None:
        say(plant_status, "Waiting for first reading...", "MUTED")
        return

    ok, messages = check_conditions(plant, *state["reading"])
    if ok:
        say(plant_status, f"✔ Conditions are ideal for {plant['name']}", "OK")
    else:
        say(plant_status, "⚠ " + "  |  ".join(messages), "WARN")


def update_display():
    clock.config(
        text="Last check: " + datetime.now().strftime("%H:%M:%S")
    )

    try:
        temperature = sensor.temperature
        humidity = sensor.humidity

        if temperature is not None and humidity is not None:
            temp_value.config(text=f"{temperature:.1f}")
            hum_value.config(text=f"{humidity:.1f}")
            say(status, "● SENSOR CONNECTED", "OK")
            state["reading"] = (temperature, humidity)
            refresh_plant_status()

    except RuntimeError:
        # DHT22 readings can occasionally fail.
        say(status, "Waiting for sensor reading...", "WAIT")

    root.after(2500, update_display)


def close_app(event=None):
    try:
        sensor.exit()
    finally:
        root.destroy()


root.bind("<Escape>", close_app)
root.protocol("WM_DELETE_WINDOW", close_app)

update_display()
check_for_answer()
root.mainloop()

