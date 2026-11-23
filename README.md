# Enshrouded Unlock Tracker

A small Python tool for **Enshrouded** (PC) that:

1. Reads your character save while the game is closed and writes everything your character has discovered (by official in-game name) to an ini file.
2. Optionally rebuilds the **Endless Chests** mod's `endless-chests.ini` so chests only fill with items you've actually unlocked.

It runs automatically each time you press **Play** in Steam.

## How it works

- Enshrouded doesn't save "recipe unlocked" directly. It saves each item your character has *found*, and recipes become available from that (for example, picking up a weapon unlocks its recipe at the Blacksmith). The script reads that known-items table from `characterN.ksd`.
- Item IDs are turned into names using the table built into the Endless Chests mod's DLL, read from your installed copy at run time. **You need the Endless Chests mod installed.** Nothing from the mod is included in this repo.
- Finding the loot version of an item ("X Loot") also allows its crafted versions ("X", "X Crafted N").

## Requirements

- Windows, Python 3.9+ (`py` launcher), and `py -m pip install zstandard`
- The Endless Chests (solo) mod installed in your Enshrouded folder

## Files

| File | Purpose |
|---|---|
| `enshrouded_unlocks.py` | The script |
| `steam-prelaunch.bat` | Hook for Steam's Launch Options (recommended) |
| `update-and-launch.bat` | Use from a desktop shortcut instead of Steam's Play button |

## Setup (Steam)

1. Put the files in a folder, e.g. inside your Enshrouded folder.
2. Edit the paths at the top of `steam-prelaunch.bat`:
   - `INI`: where to write your unlock list (any new file, **not** `endless-chests.ini`)
   - `MOD`: your `endless-chests-solo` mod folder
   - `PYTHON`: only if Steam can't find Python on its own
3. In Steam: Enshrouded → Properties → Launch Options:
   ```
   "C:\Path\To\steam-prelaunch.bat" %command%
   ```
4. Press Play. A command window stays open while the game runs; that's normal. Each launch writes `last-launch.txt` next to the batch file for troubleshooting.

If you install Python while Steam is running, fully exit and restart Steam so it can find Python.

Don't put `update-and-launch.bat` in Launch Options. It starts the game through Steam, so Steam would run it again in a loop.

## Endless Chests filtering

With `--chest-ini`, the first run saves your current `endless-chests.ini` as `endless-chests.master.ini`. **Make your own edits in the master from then on**, because `endless-chests.ini` is rebuilt from it on every launch:

- Each `[Groups]` line is trimmed to the members you've unlocked.
- A group with nothing unlocked is added to `[DisabledGroups]`.
- Every other locked item goes into `[DisabledItems]`, so naming a chest after a single item or a built-in group can't get around the filter.

Generated entries sit between `; >>> unlock-filter` and `; <<< unlock-filter` markers. To undo the filter, copy `endless-chests.master.ini` back over `endless-chests.ini` and remove `--chest-ini` from the batch file.

Custom groups go in `[Groups]` in the master, for example:

```
Ores = Copper Ore | Iron Ore | Tin Ore | Silver Ore | Gold Ore | Celestium Ore
```

`[Aliases]` entries can only point to a single item or group (e.g. `Ore = Ores`), not a list.

After the first filtered launch, check the mod's `automatic-refill-status.txt` to confirm chests are still being filled.

## Command line

```
py enshrouded_unlocks.py --ini unlocks.ini --dll "<mod>\bin\endless-chests-solo.dll" [--chest-ini "<mod>\endless-chests.ini"] [--save "<path>\character0.ksd"] [--debug]
```

Without `--save`, the newest `character*.ksd` in your Steam `userdata\...\1203620\remote` or `Saved Games\Enshrouded` folder is used.

## Limitations

- Items the mod doesn't know about (lore, quest items, some upgrade tiers) aren't named, so they don't appear in the list.
- Anything a chest has ever handed you counts as discovered to the game.
- The save format is undocumented and may change with game updates.
- Not affiliated with Keen Games or the Endless Chests author. Back up your saves.
