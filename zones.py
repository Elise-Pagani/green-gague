"""Strips of the window whose text is drawn straight onto the background.

Normal Tk widgets (Labels, Frames) always have a solid background, so text
on a photo ends up in little boxes. A Canvas can draw text AND show a
picture, so each zone here shows the same full-window background photo,
shifted to line up with where the zone sits. The result looks like the text
is printed directly on the photo.

On the Light and Dark themes there is no photo; the zone is just a canvas
in the window color, which looks exactly like ordinary labels.
"""
import tkinter as tk


class CanvasText:
    """A line of text on a zone. Understands the bits of the Label API the
    app uses (text=, fg=, wraplength=, justify=), so it can be used the
    same way as a Label."""

    def __init__(self, zone, text, font, fill, anchor, wraplength=0):
        self.zone = zone
        self.font = font
        self.item = zone.create_text(
            0, 0, text=text, font=font, fill=fill,
            anchor=anchor, width=wraplength, justify="center",
        )

    def config(self, **options):
        relayout = False
        if "text" in options:
            self.zone.itemconfigure(self.item, text=options["text"])
            relayout = True
        if "fg" in options:
            self.zone.itemconfigure(self.item, fill=options["fg"])
        if "wraplength" in options:
            self.zone.itemconfigure(self.item, width=options["wraplength"])
            relayout = True
        if "justify" in options:
            self.zone.itemconfigure(self.item, justify=options["justify"])
        # Anything else (like bg) doesn't apply: the text has no background
        if relayout:
            self.zone.schedule_relayout()

    configure = config

    def min_height(self):
        """Even empty text keeps one line of height, like a Label does."""
        return self.font.metrics("linespace")


class Zone(tk.Canvas):
    def __init__(self, master, pad_top=0, pad_bottom=0):
        # Start tiny and set the real height ourselves: Tk's default canvas
        # size is "7c" (centimeters) on some versions, and we never want that
        super().__init__(master, highlightthickness=0, bd=0, width=1, height=1)
        self._height = 1   # the height we last set (we don't read it back from Tk)
        self.pad_top = pad_top
        self.pad_bottom = pad_bottom
        # Created first, so it sits underneath everything else on the zone
        self._photo_item = self.create_image(0, 0, anchor="nw", state="hidden")
        self._relayout_pending = False
        self.bind("<Configure>", self._on_configure)

    # -- the photo ------------------------------------------------------
    def set_photo(self, photo):
        """Show the shared background photo (or None to hide it)."""
        if photo is None:
            self.itemconfigure(self._photo_item, state="hidden")
        else:
            self.itemconfigure(self._photo_item, image=photo, state="normal")
            self._align_photo()

    def _align_photo(self):
        # Shift the full-window photo so this zone shows its own piece of it
        self.coords(self._photo_item, -self.winfo_x(), -self.winfo_y())

    def _on_configure(self, _event):
        self._align_photo()
        self.relayout()

    # -- layout ---------------------------------------------------------
    def schedule_relayout(self):
        """Re-lay out once, soon, however many changes just happened."""
        if not self._relayout_pending:
            self._relayout_pending = True
            self.after_idle(self._run_scheduled_relayout)

    def _run_scheduled_relayout(self):
        self._relayout_pending = False
        self.relayout()

    def relayout(self):
        raise NotImplementedError

    def _set_height(self, total):
        total = int(round(total))
        if total != self._height:
            self._height = total
            self.config(height=total)


class TextZone(Zone):
    """Lines of centered text stacked top to bottom."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._lines = []

    def add_line(self, text, font, fill, gap=0, wraplength=0):
        line = CanvasText(self, text, font, fill, anchor="n",
                          wraplength=wraplength)
        self._lines.append((line, gap))
        return line

    def relayout(self):
        center = self.winfo_width() / 2
        y = self.pad_top
        for line, gap in self._lines:
            y += gap
            self.coords(line.item, center, y)
            box = self.bbox(line.item)
            measured = (box[3] - box[1]) if box else 0
            y += max(measured, line.min_height())
        self._set_height(y + self.pad_bottom)


class RowZone(Zone):
    """One centered row of text and widgets (like a dropdown or entry box)."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._parts = []

    def add_text(self, text, font, fill, padx=(0, 0)):
        text_part = CanvasText(self, text, font, fill, anchor="w")
        self._parts.append(("text", text_part, None, padx, 0))
        return text_part

    def add_widget(self, widget, padx=(0, 0), extra_height=0):
        item = self.create_window(0, 0, window=widget, anchor="w")
        self._parts.append(("window", item, widget, padx, extra_height))

    def relayout(self):
        sizes = []
        for kind, part, widget, _padx, extra in self._parts:
            if kind == "text":
                box = self.bbox(part.item)
                width = (box[2] - box[0]) if box else 0
                height = max((box[3] - box[1]) if box else 0, part.min_height())
            else:
                width = widget.winfo_reqwidth()
                height = widget.winfo_reqheight() + extra
            sizes.append((width, height))

        total_width = sum(w + p[3][0] + p[3][1]
                          for (w, _h), p in zip(sizes, self._parts))
        row_height = max((h for _w, h in sizes), default=0)

        x = max(0, (self.winfo_width() - total_width) / 2)
        y = self.pad_top + row_height / 2
        for (width, height), (kind, part, _widget, padx, _extra) in zip(
                sizes, self._parts):
            x += padx[0]
            if kind == "text":
                self.coords(part.item, x, y)
            else:
                self.coords(part, x, y)
                self.itemconfigure(part, width=width, height=height)
            x += width + padx[1]

        self._set_height(row_height + self.pad_top + self.pad_bottom)
