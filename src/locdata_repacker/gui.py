from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .cli import repack_file, unpack_file
from .format import ENCODING_LABELS, SUPPORTED_ENCODINGS, LocdataFormatError

AUTO_LABEL = "Detect automatically (recommended)"
ENCODING_CHOICES = [AUTO_LABEL] + [ENCODING_LABELS[name] for name in SUPPORTED_ENCODINGS]
_LABEL_TO_ENCODING = {ENCODING_LABELS[name]: name for name in SUPPORTED_ENCODINGS}


class RepackerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("Locdata Repacker")
        root.geometry("760x485")
        root.minsize(680, 440)
        self.unpack_source = tk.StringVar()
        self.unpack_target = tk.StringVar()
        self.repack_source = tk.StringVar()
        self.repack_target = tk.StringVar()
        self.unpack_encoding = tk.StringVar(value=AUTO_LABEL)
        self.status = tk.StringVar(value="Choose an operation and select your files.")

        outer = ttk.Frame(root, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Locdata Repacker", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text="Extract and rebuild Fantasy Wars locdata.md localization files.",
        ).pack(anchor="w", pady=(2, 14))
        tabs = ttk.Notebook(outer)
        tabs.pack(fill="both", expand=True)
        unpack_tab = ttk.Frame(tabs, padding=18)
        repack_tab = ttk.Frame(tabs, padding=18)
        tabs.add(unpack_tab, text="  Extract .md  ")
        tabs.add(repack_tab, text="  Repack .txt  ")
        self._operation(unpack_tab, "Source locdata.md", self.unpack_source, self._browse_unpack_source,
                        "Target editable .txt", self.unpack_target, self._browse_unpack_target,
                        "Extract localization", self._unpack, self._encoding_row)
        self._operation(repack_tab, "Source edited .txt", self.repack_source, self._browse_repack_source,
                        "Target locdata.md", self.repack_target, self._browse_repack_target,
                        "Repack localization", self._repack)
        status_frame = ttk.Frame(outer, padding=(10, 9))
        status_frame.pack(fill="x", pady=(12, 0))
        ttk.Label(status_frame, textvariable=self.status, wraplength=700).pack(anchor="w")

    def _operation(self, parent, source_label, source_var, source_command,
                   target_label, target_var, target_command, button_text, button_command,
                   extra=None) -> None:
        parent.columnconfigure(0, weight=1)
        ttk.Label(parent, text=source_label).grid(row=0, column=0, sticky="w")
        source_row = ttk.Frame(parent)
        source_row.grid(row=1, column=0, sticky="ew", pady=(4, 16))
        source_row.columnconfigure(0, weight=1)
        ttk.Entry(source_row, textvariable=source_var).grid(row=0, column=0, sticky="ew")
        ttk.Button(source_row, text="Browse...", command=source_command).grid(row=0, column=1, padx=(8, 0))
        ttk.Label(parent, text=target_label).grid(row=2, column=0, sticky="w")
        target_row = ttk.Frame(parent)
        target_row.grid(row=3, column=0, sticky="ew", pady=(4, 20))
        target_row.columnconfigure(0, weight=1)
        ttk.Entry(target_row, textvariable=target_var).grid(row=0, column=0, sticky="ew")
        ttk.Button(target_row, text="Browse...", command=target_command).grid(row=0, column=1, padx=(8, 0))
        next_row = extra(parent, 4) if extra else 4
        ttk.Button(parent, text=button_text, command=button_command).grid(row=next_row, column=0, sticky="e")

    def _encoding_row(self, parent, row: int) -> int:
        ttk.Label(parent, text="Text encoding").grid(row=row, column=0, sticky="w")
        ttk.Combobox(
            parent,
            textvariable=self.unpack_encoding,
            values=ENCODING_CHOICES,
            state="readonly",
        ).grid(row=row + 1, column=0, sticky="ew", pady=(4, 20))
        return row + 2

    def _browse_unpack_source(self) -> None:
        value = filedialog.askopenfilename(title="Select locdata.md", filetypes=(("Locdata files", "*.md"), ("All files", "*.*")))
        if value:
            self.unpack_source.set(value)
            self.unpack_target.set(str(Path(value).with_suffix(".txt")))

    def _browse_unpack_target(self) -> None:
        value = filedialog.asksaveasfilename(title="Save editable text", defaultextension=".txt", filetypes=(("Text files", "*.txt"), ("All files", "*.*")))
        if value:
            self.unpack_target.set(value)

    def _browse_repack_source(self) -> None:
        value = filedialog.askopenfilename(title="Select edited text", filetypes=(("Text files", "*.txt"), ("All files", "*.*")))
        if value:
            self.repack_source.set(value)
            self.repack_target.set(str(Path(value).with_name("locdata.md")))

    def _browse_repack_target(self) -> None:
        value = filedialog.asksaveasfilename(title="Save locdata.md", initialfile="locdata.md", defaultextension=".md", filetypes=(("Locdata files", "*.md"), ("All files", "*.*")))
        if value:
            self.repack_target.set(value)

    def _paths(self, source_value: str, target_value: str):
        if not source_value.strip() or not target_value.strip():
            raise LocdataFormatError("Choose both a source file and a target file.")
        source, target = Path(source_value), Path(target_value)
        if not source.is_file():
            raise LocdataFormatError("Source file does not exist: {}".format(source))
        if source.resolve() == target.resolve():
            raise LocdataFormatError("Source and target must be different files.")
        if target.exists() and not messagebox.askyesno("Replace existing file?", "{} already exists. Replace it?".format(target)):
            raise InterruptedError
        return source, target

    def _unpack(self) -> None:
        try:
            source, target = self._paths(self.unpack_source.get(), self.unpack_target.get())
            chosen = _LABEL_TO_ENCODING.get(self.unpack_encoding.get())
            count, encoding = unpack_file(source, target, chosen)
            template = target.with_suffix(".template")
            described = "{} ({})".format(
                ENCODING_LABELS[encoding], "forced" if chosen else "detected"
            )
            self.status.set(
                "Extracted {:,} entries to {} (template: {}, encoding: {})".format(
                    count, target, template.name, described
                )
            )
            messagebox.showinfo(
                "Extraction complete",
                "Wrote {:,} editable entries.\nEncoding: {}\n\n"
                "Keep {} beside the text file for repacking.".format(
                    count, described, template.name
                ),
            )
        except InterruptedError:
            return
        except (OSError, LocdataFormatError) as exc:
            self.status.set("Extraction failed: {}".format(exc))
            messagebox.showerror("Could not extract", str(exc))

    def _repack(self) -> None:
        try:
            source, target = self._paths(self.repack_source.get(), self.repack_target.get())
            count, encoding = repack_file(source, target)
            self.status.set(
                "Repacked {:,} entries to {} ({})".format(count, target, ENCODING_LABELS[encoding])
            )
            messagebox.showinfo(
                "Repack complete",
                "Wrote {:,} localization entries.\nEncoding: {}".format(
                    count, ENCODING_LABELS[encoding]
                ),
            )
        except InterruptedError:
            return
        except (OSError, LocdataFormatError) as exc:
            self.status.set("Repack failed: {}".format(exc))
            messagebox.showerror("Could not repack", str(exc))


def run_gui() -> None:
    root = tk.Tk()
    RepackerApp(root)
    root.mainloop()
