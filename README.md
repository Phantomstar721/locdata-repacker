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
4. Leave **Text encoding** on *Detect automatically* unless you have a reason
   not to. See [Language releases](#language-releases).
5. Click **Extract localization**.

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

Both commands report the code page they used. Pass `--encoding cp1251` or
`--encoding cp1252` to `unpack` to override detection. `repack` needs no flag:
it reads the code page recorded in the `.txt` file.

## Language releases

The Western release stores text in Windows-1252 and the Russian release stores
it in Windows-1251. The container gives no explicit marker, so the tool infers
the code page from the text itself: Windows-1251 puts the Russian alphabet in
`0xC0-0xFF` and those bytes arrive in word-length runs, while Western text uses
the high range only for isolated punctuation like curly quotes.

The detected code page is recorded as `"encoding"` in the editable `.txt` and
reused on repack, so extract and rebuild always agree.

If you see Latin gibberish such as `Ðàòóøà` where Cyrillic belongs, detection
picked Windows-1252 for a Russian file. Re-extract with `--encoding cp1251`, or
pick *Windows-1251 (Cyrillic)* in the GUI. The reverse mistake looks like
Cyrillic gibberish in place of accented Western characters.

A wrong guess cannot corrupt anything. Both code pages are single-byte and
byte-preserving across a decode/encode round trip, so repacking an unedited file
reproduces the original bytes either way. Only text you actually edit depends on
the code page being right.

Editable files produced before code-page support have no `"encoding"` field and
are treated as Windows-1252, which is what they were written with.

Not every `?` is an encoding fault. The Western release ships 27 entries whose
Russian source text was already flattened to literal `?` bytes by the
publisher's own conversion, among them `#PARIS_NAME`, `#BATTLE_TEST_DESC`, and
`#SOMEVALUE`. Those are leftover development keys, the data is gone in the
shipped file, and no code page will bring it back.

## Format notes

Fantasy Wars stores 3,439 localization keys in this container. Keys and values
use separate single-byte XOR encodings over single-byte text, in the code page
of the language release (see [Language releases](#language-releases)). Keys
themselves are always ASCII. The file also
contains fixed-size lookup nodes whose string-pool offsets must be preserved or
remapped when text lengths change. This tool retains the untouched binary
template and rebuilds only the localization pool and its affected references.

## Building the executable

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\Build-Exe.ps1
```

This creates `dist\Locdata Repacker.exe` using PyInstaller.
