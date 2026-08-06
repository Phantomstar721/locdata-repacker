# Locdata Repacker

A small Windows app for extracting **Fantasy Wars** `locdata.md` localization
data into an editable UTF-8 `.txt` file and rebuilding it after text changes.

## Download and run

[Download `Locdata Repacker.exe`](./Locdata%20Repacker.exe?raw=1) from this
repository and double-click it. Nothing needs to be installed.

When running from source, double-click `Locdata Repacker.bat` or run:

```powershell
python run_repacker.py
```

## Extract localization

1. Open the **Extract .md** tab.
2. Select the game's `locdata.md` file.
3. Choose where to save the editable `.txt` file.
4. Click **Extract localization**.

The app creates two files next to each other:

- `locdata.txt` contains the readable JSON-formatted UTF-8 localization;
- `locdata.template` contains the untouched binary structure needed to rebuild
  the game file.

Edit only the `text` values in `locdata.txt`; keys and their order are
validated because the game uses them as identifiers. Empty values are
intentional and are preserved. Keep the `.txt` and `.template` files together.

## Repack edited text

1. Open the **Repack .txt** tab.
2. Select the edited `.txt` file.
3. Choose where to save the rebuilt `locdata.md`.
4. Click **Repack localization**.

The app automatically loads the `.template` companion named inside the
editable file. It does not need the original `.md` again during repacking.
Internal offsets are adjusted when replacement text is longer or shorter. The
app validates the template checksum, entry count, key order, encoding, and
available container capacity before it writes anything.

Keep a backup of the game's original file. The app never overwrites its source
and asks before replacing an existing target.

## Command line

```powershell
python run_repacker.py unpack locdata.md -o locdata.txt
python run_repacker.py repack locdata.txt -o locdata.md
```

## Format notes

Fantasy Wars stores 3,439 localization keys in this container. Keys and values
use separate single-byte XOR encodings over Windows-1252 text. The file also
contains fixed-size lookup nodes whose string-pool offsets must be preserved or
remapped when text lengths change. This tool retains the untouched binary
template and rebuilds only the localization pool and its affected references.

A locally supplied English corpus reproduces byte-for-byte after an unchanged
extract/repack cycle. Automated tests also cover both longer and shorter edits.
Original game data is used only for local validation and is not distributed in
this repository.

## Building the executable

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\Build-Exe.ps1
```

This creates `dist\Locdata Repacker.exe` using PyInstaller.
