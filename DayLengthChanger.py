import hashlib
import os
import shutil
import struct
import tempfile
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


EXPECTED_WORLD_VERSION = 249
EXPECTED_SANDBOX_VERSION = 6
MAX_OPTION_COUNT = 4096

DAY_LENGTHS = {
    1: "15 minutes",
    2: "30 minutes",
    3: "1 hour",
    4: "1 hour, 30 minutes",
    **{value: f"{value - 3} hours" for value in range(5, 27)},
    27: "Real-time (24 hours)",
}


def read_pz_string(data: bytes, offset: int) -> tuple[str, int, int]:
    if offset + 2 > len(data):
        raise ValueError("The file ended before a complete string could be read.")

    length = int.from_bytes(data[offset:offset + 2], "big")
    value_start = offset + 2
    value_end = value_start + length
    if value_end > len(data):
        raise ValueError("The file contains a truncated string.")

    try:
        value = data[value_start:value_end].decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("The file contains invalid text. Nothing was changed.") from error

    return value, value_start - 2, value_end


def parse_sandbox(data: bytes) -> dict:
    if len(data) < 16 or data[:4] != b"SAND":
        raise ValueError("This does not appear to be a valid map_sand.bin file.")

    world_version, sandbox_version, option_count = struct.unpack_from(">III", data, 4)
    if option_count == 0 or option_count > MAX_OPTION_COUNT:
        raise ValueError("The option count in this file is invalid.")

    offset = 16
    options = []
    day_length = None
    day_length_record = None

    for _ in range(option_count):
        name, _, name_end = read_pz_string(data, offset)
        value, value_record_start, value_end = read_pz_string(data, name_end)
        options.append((name, value))

        if name == "DayLength":
            if day_length is not None:
                raise ValueError("The file contains more than one DayLength option. Nothing was changed.")
            try:
                day_length = int(value)
            except ValueError as error:
                raise ValueError("The current DayLength value is not an integer.") from error
            day_length_record = (value_record_start, value_end)

        offset = value_end

    if day_length is None or day_length_record is None:
        raise ValueError("The DayLength option was not found in this file.")

    return {
        "world_version": world_version,
        "sandbox_version": sandbox_version,
        "options": options,
        "day_length": day_length,
        "day_length_record": day_length_record,
    }


def replace_day_length(data: bytes, new_value: int) -> bytes:
    if new_value not in DAY_LENGTHS:
        raise ValueError("The selected duration is not a valid Build 42.21 option.")

    parsed = parse_sandbox(data)
    if (parsed["world_version"], parsed["sandbox_version"]) != (
        EXPECTED_WORLD_VERSION,
        EXPECTED_SANDBOX_VERSION,
    ):
        raise ValueError(
            "This tool is validated for Build 42.21 "
            f"(world {EXPECTED_WORLD_VERSION}, sandbox {EXPECTED_SANDBOX_VERSION}). "
            "This save uses different versions, so it was left unchanged for safety."
        )

    start, end = parsed["day_length_record"]
    encoded_value = str(new_value).encode("utf-8")
    replacement = len(encoded_value).to_bytes(2, "big") + encoded_value
    updated = data[:start] + replacement + data[end:]

    verified = parse_sandbox(updated)
    expected_options = [
        (name, str(new_value) if name == "DayLength" else value)
        for name, value in parsed["options"]
    ]
    if verified["day_length"] != new_value or verified["options"] != expected_options:
        raise ValueError("Internal validation failed. The original file was preserved.")

    return updated


def create_backup(path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.name}.backup-{timestamp}")
    suffix = 1
    while backup.exists():
        backup = path.with_name(f"{path.name}.backup-{timestamp}-{suffix}")
        suffix += 1
    shutil.copy2(path, backup)
    return backup


def replace_file_atomically(path: Path, data: bytes) -> None:
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(data)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


class DayLengthChanger:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Project Zomboid — Day Length Changer")
        self.root.resizable(False, False)

        self.path_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Select the save's map_sand.bin file.")
        self.current_var = tk.StringVar(value="Current day length: —")
        self.choice_var = tk.StringVar()
        self.loaded_digest = None
        self.loaded_path = None
        self.loaded_day_length = None

        frame = ttk.Frame(root, padding=16)
        frame.grid(sticky="nsew")

        ttk.Label(
            frame,
            text="Change only the day length in a Project Zomboid Build 42.21 save.",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))

        ttk.Label(frame, text="Save file:").grid(row=1, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.path_var, width=58, state="readonly").grid(
            row=1, column=1, sticky="ew", padx=8
        )
        ttk.Button(frame, text="Browse...", command=self.browse).grid(row=1, column=2)

        ttk.Label(frame, textvariable=self.status_var, wraplength=520).grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(12, 4)
        )
        ttk.Label(frame, textvariable=self.current_var).grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(0, 12)
        )

        ttk.Label(frame, text="New day length:").grid(row=4, column=0, sticky="w")
        self.choice_box = ttk.Combobox(
            frame,
            textvariable=self.choice_var,
            values=[f"{value} — {label}" for value, label in DAY_LENGTHS.items()],
            state="readonly",
            width=30,
        )
        self.choice_box.grid(row=4, column=1, sticky="w", padx=8)
        self.choice_box.bind("<<ComboboxSelected>>", self.update_button)

        self.apply_button = ttk.Button(
            frame, text="Apply with backup", command=self.apply, state="disabled"
        )
        self.apply_button.grid(row=5, column=0, columnspan=3, sticky="e", pady=(16, 0))

        ttk.Label(
            frame,
            text="Close the game before applying. A backup will be created next to the file.",
        ).grid(row=6, column=0, columnspan=3, sticky="w", pady=(12, 0))

        frame.columnconfigure(1, weight=1)
        root.bind("<Return>", lambda _event: self.apply())

    def browse(self):
        selected = filedialog.askopenfilename(
            title="Select map_sand.bin",
            filetypes=[("Project Zomboid save", "map_sand.bin"), ("All files", "*.*")],
        )
        if selected:
            self.path_var.set(selected)
            self.load_file()

    def load_file(self):
        path = Path(self.path_var.get().strip().strip('"'))
        self.apply_button.configure(state="disabled")
        self.loaded_digest = None
        self.loaded_path = None
        self.loaded_day_length = None

        try:
            data = path.read_bytes()
            parsed = parse_sandbox(data)
            if (parsed["world_version"], parsed["sandbox_version"]) != (
                EXPECTED_WORLD_VERSION,
                EXPECTED_SANDBOX_VERSION,
            ):
                raise ValueError(
                    "This tool is validated for Build 42.21 "
                    f"(world {EXPECTED_WORLD_VERSION}, sandbox {EXPECTED_SANDBOX_VERSION}). "
                    f"The file reports world {parsed['world_version']} and "
                    f"sandbox {parsed['sandbox_version']}; nothing was changed."
                )

            label = DAY_LENGTHS.get(parsed["day_length"], f"unknown value ({parsed['day_length']})")
            self.current_var.set(f"Current day length: {label} — world {parsed['world_version']}, sandbox {parsed['sandbox_version']}")
            self.status_var.set("Valid file. All other settings will be preserved byte-for-byte.")
            self.loaded_digest = hashlib.sha256(data).digest()
            self.loaded_path = path.resolve()
            self.loaded_day_length = parsed["day_length"]
            self.choice_var.set(
                f"{parsed['day_length']} — {label}" if parsed["day_length"] in DAY_LENGTHS else ""
            )
            self.update_button()
        except (OSError, ValueError) as error:
            self.current_var.set("Current day length: —")
            self.status_var.set(str(error))

    def update_button(self, _event=None):
        selection = self.choice_var.get()
        if self.loaded_digest is not None and selection:
            selected_value = int(selection.split(" — ", 1)[0])
            state = "normal" if selected_value != self.loaded_day_length else "disabled"
            self.apply_button.configure(state=state)
        else:
            self.apply_button.configure(state="disabled")

    def apply(self):
        if self.loaded_digest is None or self.loaded_path is None:
            return

        try:
            new_value = int(self.choice_var.get().split(" — ", 1)[0])
            original = self.loaded_path.read_bytes()
            if hashlib.sha256(original).digest() != self.loaded_digest:
                raise ValueError("The file changed after it was loaded. Select it again.")

            parsed = parse_sandbox(original)
            if parsed["day_length"] == new_value:
                messagebox.showinfo("No changes", "The save already uses this day length.", parent=self.root)
                return

            if not messagebox.askyesno(
                "Confirm change",
                "The game must be closed so it does not overwrite the save.\n\n"
                f"Change the day length to {DAY_LENGTHS[new_value]} and create a backup?",
                parent=self.root,
            ):
                return

            updated = replace_day_length(original, new_value)
            backup = create_backup(self.loaded_path)
            try:
                replace_file_atomically(self.loaded_path, updated)
                if self.loaded_path.read_bytes() != updated:
                    raise OSError("The post-write validation failed.")
            except Exception:
                shutil.copy2(backup, self.loaded_path)
                raise

            self.load_file()
            messagebox.showinfo(
                "Done",
                f"Day length changed to {DAY_LENGTHS[new_value]}.\n\nBackup created at:\n{backup}",
                parent=self.root,
            )
        except (OSError, ValueError) as error:
            messagebox.showerror("Could not change the save", str(error), parent=self.root)


if __name__ == "__main__":
    window = tk.Tk()
    DayLengthChanger(window)
    window.mainloop()
