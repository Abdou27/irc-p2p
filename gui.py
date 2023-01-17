import tkinter as tk
import sys

MAX_WIDTH = 800
MAX_HEIGHT = 800


class GUI(tk.Tk):
    def __init__(self, **options):
        # GUI Setup
        super().__init__()
        on_submit = options.get("on_submit")
        on_close = options.get("on_close")
        self.on_submit = on_submit if callable(on_submit) else lambda x: print(f"Unimplemented on_submit.")
        self.on_close = on_close if callable(on_close) else lambda x: print(f"Unimplemented on_close.")
        self.set_window_properties(options)
        self.input_content = tk.StringVar()
        self.input_box, self.text_box_frame, self.text_box, self.scrollbar = (None,) * 4
        self.init_input_box()
        self.init_text_box()

    def set_window_properties(self, options):
        self.title(options.get("title", f"{self.title}"))
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.set_geometry()

    def set_geometry(self):
        width = int(self.winfo_screenwidth() - 200)
        width = MAX_WIDTH if width > MAX_WIDTH else width
        height = int(self.winfo_screenheight() - 200)
        height = MAX_HEIGHT if height > MAX_HEIGHT else height
        self.geometry(f"{width}x{height}+100+100")

    def init_input_box(self):
        self.input_box = tk.Entry(self, textvariable=self.input_content)
        self.input_box.bind("<Return>", self.submit_message)
        self.input_box.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        self.input_box.focus_set()
        self.bind("<1>", lambda x: self.input_box.focus_set())

    def init_text_box(self):
        self.text_box_frame = tk.Frame(self)
        self.text_box_frame.pack(fill=tk.BOTH, expand=True)
        self.text_box_frame.pack_propagate(False)
        self.text_box = tk.Text(self.text_box_frame, background="black", foreground="white", state=tk.NORMAL)
        self.text_box.delete("0.0", tk.END)
        self.scrollbar = tk.Scrollbar(self.text_box_frame, command=self.text_box.yview, orient=tk.VERTICAL)
        self.text_box['yscrollcommand'] = self.scrollbar.set
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_box.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=1)

    def add_line(self, line):
        self.text_box["state"] = tk.NORMAL
        self.text_box.insert(tk.END, line + "\n")
        self.text_box["state"] = tk.DISABLED
        self.text_box.see(tk.END)

    def submit_message(self, _):
        message = self.input_content.get()
        self.input_content.set("")
        self.add_line("> " + message)
        self.on_submit(message)
