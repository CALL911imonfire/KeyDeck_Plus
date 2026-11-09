# KeyDeck Music

KeyDeck Music is [KeyDeck Plus](README.md) with extras for learning and playing notes. It keeps everything KeyDeck Plus does (swipe typing, dwell clicking, switch scanning, macros, speech, picture keys, shareable layouts) and adds sheet-music layouts that drive the **NoteDeck** keyboard entry. It keeps its own settings and layouts (in `%APPDATA%\KeyDeckMusic`), so it never mixes with KeyDeck Plus.

## Install

1. Python 3 for Windows, then `python -m pip install pillow` (the staff pictures line up with the keys only with Pillow).
2. Keep `keydeck_music.py`, `keydeck_words.py` and the `music layouts` folder together.
3. Run `python keydeck_music.py`. The first start installs the music layouts and opens **Music - Treble**. **Loadouts → Install the music layouts** refreshes them later.

To build an `.exe`: `pyinstaller --noconsole --onefile --name KeyDeckMusic --add-data "music layouts;music layouts" keydeck_music.py`

## Set up NoteDeck once

Each key presses a length key and then a note letter in NoteDeck's **Keyboard entry**, so NoteDeck needs:

- **Keyboard entry** switched on, **Octave 4**, and **Follow last note OFF** (otherwise the octave jumps when you move the selection).
- **Shift makes: the black key** (the default), which the sharps and flats layouts rely on.

## The layouts

Every key sits where its note sits on a drawn staff. The five staff lines run through the line-note keys, ledger lines sit behind the top and bottom keys, and each column is a note length (½, 1, 2, 3, 4 beats, drawn above the column). The right-hand block has play, stop, restart, previous/next note, lane, speed, delete, octave and undo keys, and purple keys that switch layouts.

| Layout | What it is |
|---|---|
| `Music - Treble` | Treble clef, C4 to A5, with note names |
| `Music - Treble quiz` | Same positions, no names: each key shows a note picture and **reveals its name for a moment after you press it** |
| `Music - Treble sharps and flats` | The black keys on their staff positions (C♯ D♯ E♭ F♯ G♯ A♭ B♭) |
| `Music - Bass`, `... quiz`, `... sharps and flats` | The same three for the bass clef, C4 down to E2 |

The purple keys on the right switch between natural / sharps and flats / quiz, and between the clefs.

## Practice

**Practice** menu → pick a tune (Hot Cross Buns, Mary Had a Little Lamb, Twinkle Twinkle, Ode to Joy (easy), C major scale). The key to press next lights up yellow, wrong keys are counted, and the window title shows your progress. The "(low)" versions are one octave lower, for the bass clef. A tune needs a layout that has all its notes, and tells you if the one you're on doesn't.

## Good to know

- Pressing a note key in KeyDeck Music adds that note to NoteDeck's selected lane; NoteDeck has to be the window you were typing into (KeyDeck never takes focus).
- Octave 2 and 3 notes use NoteDeck's `[` key and then put the octave back, so the keys work whatever the previous note was.
- The sheet-music pictures are normal background pictures, so you can also build your own with **Loadouts → Set background picture**.
- Not included: time signatures and bar lines. They belong on NoteDeck's timeline, not on a fixed grid of keys.
