"""
Enshrouded unlock lister.

Reads your character save (characterN.ksd) while the game is closed, pulls out
the character's "known items" table, turns the item IDs into their in-game
English names, and writes them into an [Unlocked] section of an ini file.
Every other section of that ini is left exactly as it was.

Names come from the Endless Chests mod you already have installed: its DLL
carries a table of item ID -> display name, which this script reads at run time.

Requires: Python 3.9+ and `pip install zstandard`
"""
import argparse
import datetime as dt
import glob
import os
import re
import struct
import sys

try:
    import zstandard
except ImportError:
    sys.exit("Missing package: run  pip install zstandard")

ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"
BLOCK_MAGIC = b"S2BH"
STEAM_APP_ID = "1203620"

# Flag bits seen in the known-items table. Bit 1 is set on every entry.
# Bits 2 and 4 have not been confirmed yet; they are kept in the debug section.
FLAG_KNOWN = 1


# ---------------------------------------------------------------- save files

def find_save_dirs():
    dirs = []
    for steam in (r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam",
                  os.path.expandvars(r"%ProgramFiles(x86)%\Steam")):
        dirs += glob.glob(os.path.join(steam, "userdata", "*", STEAM_APP_ID, "remote"))
    dirs.append(os.path.expandvars(r"%USERPROFILE%\Saved Games\Enshrouded"))
    return [d for d in dict.fromkeys(dirs) if os.path.isdir(d)]


def iter_blocks(data):
    """Yield (type, version, payload_bytes) for each S2BH block that holds a zstd frame."""
    dctx = zstandard.ZstdDecompressor()
    i = 0
    while True:
        j = data.find(BLOCK_MAGIC, i)
        if j < 0:
            return
        i = j + 4
        if len(data) < j + 14:
            return
        btype, compressed = data[j + 8], data[j + 9]
        version = struct.unpack_from("<I", data, j + 10)[0]
        start = j + 14
        if compressed and data[start:start + 4] == ZSTD_MAGIC:
            try:
                obj = dctx.decompressobj()
                payload = obj.decompress(data[start:])
            except zstandard.ZstdError:
                continue
            yield btype, version, payload


def character_name(data):
    for btype, _, payload in iter_blocks(data):
        if btype == 0x0A and len(payload) > 9:
            n = struct.unpack_from("<I", payload, 5)[0]
            if 0 < n < 64:
                return payload[9:9 + n].decode("utf-8", "replace")
    return None


def known_items(data):
    """Return {item_id: flags} from the character's known-items table."""
    best = None
    for btype, _, payload in iter_blocks(data):
        if len(payload) < 8:
            continue
        _, n = struct.unpack_from("<II", payload, 0)
        if n and len(payload) == 8 + 8 * n:          # u32 ver, u32 n, n keys, n values
            keys = struct.unpack_from(f"<{n}I", payload, 8)
            vals = struct.unpack_from(f"<{n}I", payload, 8 + 4 * n)
            table = dict(zip(keys, vals))
            if btype == 0x0F:
                return table
            best = best or table
    if best is None:
        raise ValueError("known-items table not found (save format may have changed)")
    return best


# ---------------------------------------------------------------- names

def load_names_from_dll(path, strip_loot=True):
    """Read the ID -> name table embedded in the Endless Chests DLL."""
    d = open(path, "rb").read()
    pe = struct.unpack_from("<I", d, 0x3C)[0]
    nsec = struct.unpack_from("<H", d, pe + 6)[0]
    opt = pe + 24
    base = struct.unpack_from("<Q", d, opt + 24)[0]
    size_img = struct.unpack_from("<I", d, opt + 56)[0]
    sec_tab = opt + struct.unpack_from("<H", d, pe + 20)[0]
    sections = []
    for k in range(nsec):
        s = sec_tab + 40 * k
        vsize, vaddr, rsize, raddr = struct.unpack_from("<IIII", d, s + 8)
        sections.append((vaddr, max(vsize, rsize), raddr))

    def cstr(va):
        if not base <= va < base + size_img:
            return None
        rva = va - base
        for vaddr, size, raddr in sections:
            if vaddr <= rva < vaddr + size:
                o = raddr + rva - vaddr
                e = d.find(b"\0", o, o + 200)
                if e < 0:
                    return None
                try:
                    return d[o:e].decode("utf-8")
                except UnicodeDecodeError:
                    return None
        return None

    names = {}
    hi = base + 0x10000000
    for e in range(0, len(d) - 32, 8):
        p1 = struct.unpack_from("<Q", d, e)[0]
        if not base <= p1 < hi:
            continue
        iid = struct.unpack_from("<I", d, e + 8)[0]
        if not iid or struct.unpack_from("<Q", d, e + 16)[0]:
            continue
        internal = cstr(struct.unpack_from("<Q", d, e + 24)[0])
        if not internal or " " in internal or "_" not in internal:
            continue
        name = cstr(p1)
        if name:
            # The mod tags picked-up copies "X Loot"; in game both are just "X",
            # and finding the loot copy is what unlocks X at the crafter.
            if strip_loot and name.endswith(" Loot"):
                name = name[:-5]
            names[iid] = name
    return names


def load_extra_names(path):
    """Optional ID=Name file (e.g. a later full export from the game data)."""
    names = {}
    if path and os.path.isfile(path):
        for line in open(path, encoding="utf-8"):
            m = re.match(r"\s*(\d+)\s*=\s*(.+?)\s*$", line)
            if m:
                names[int(m.group(1))] = m.group(2)
    return names


# ---------------------------------------------------------------- ini output

def replace_section(text, section, body_lines):
    """Replace (or append) [section] in ini text, leaving everything else alone."""
    lines = text.splitlines()
    out, i, done = [], 0, False
    header = re.compile(r"^\s*\[(.+?)\]\s*$")
    while i < len(lines):
        m = header.match(lines[i])
        if m and m.group(1).strip().lower() == section.lower():
            out.append(f"[{section}]")
            out += body_lines
            out.append("")
            i += 1
            while i < len(lines) and not header.match(lines[i]):
                i += 1
            done = True
            continue
        out.append(lines[i])
        i += 1
    if not done:
        if out and out[-1].strip():
            out.append("")
        out.append(f"[{section}]")
        out += body_lines
        out.append("")
    return "\n".join(out).rstrip("\n") + "\n"


BLOCK_START = "; >>> unlock-filter (generated by enshrouded_unlocks.py; edits here are overwritten)"
BLOCK_END = "; <<< unlock-filter"


def allowed_names(raw_names, table):
    """Names the character has unlocked, in the mod's own labels.

    Finding "X Loot" is what unlocks X at a crafter, so it also allows "X"
    and its "X Crafted N" tiers.
    """
    known = {raw_names[k] for k, v in table.items() if v & FLAG_KNOWN and k in raw_names}
    bases = {n[:-5] for n in known if n.endswith(" Loot")}
    allow = set(known) | bases
    for n in set(raw_names.values()):
        m = re.match(r"^(.*) Crafted \d+$", n)
        if m and (m.group(1) in allow):
            allow.add(n)
    return {n.lower() for n in allow}


def filter_chest_ini(path, raw_names, table):
    """Rebuild endless-chests.ini from a master copy so chests only supply unlocked items.

    The first run saves your current file as endless-chests.master.ini. Every run
    then starts from that master (make your own edits there), and:
      * trims each [Groups] line to the members you have unlocked;
      * a group with nothing unlocked keeps its line and is added to [DisabledGroups];
      * every other not-unlocked item goes into [DisabledItems], so typing an
        individual item or a built-in group name can't bypass the filter.
    Generated entries sit between marker comments.
    """
    import shutil
    master = os.path.join(os.path.dirname(os.path.abspath(path)), "endless-chests.master.ini")
    if not os.path.exists(master):
        shutil.copyfile(path, master)
    lines = open(master, encoding="utf-8-sig").read().splitlines()

    allow = allowed_names(raw_names, table)
    header = re.compile(r"^\s*\[(.+?)\]\s*$")

    out, sec, dead, live_items = [], None, [], set()
    existing = {"disabledgroups": set(), "disableditems": set()}
    ends = {}
    for ln in lines:
        m = header.match(ln)
        if m:
            if sec in existing:
                ends[sec] = len(out)
            sec = m.group(1).strip().lower()
            out.append(ln)
            continue
        body = ln.strip()
        if sec in existing and "=" in body and not body.startswith(";"):
            existing[sec].add(body.split("=", 1)[0].strip().lower())
        if sec == "groups" and "=" in body and not body.startswith(";"):
            name, members = ln.split("=", 1)
            ms = [x.strip() for x in members.split("|") if x.strip()]
            keep = [x for x in ms if x.lower() in allow]
            if keep:
                out.append(f"{name.strip()} = {' | '.join(keep)}")
            else:
                out.append(ln)
                dead.append(name.strip())
            continue
        out.append(ln)
    if sec in existing:
        ends[sec] = len(out)

    dead_members = set()
    for ln in lines:
        if "=" in ln and ln.split("=", 1)[0].strip() in dead:
            dead_members |= {x.strip().lower() for x in ln.split("=", 1)[1].split("|")}

    gen_groups = sorted(g for g in dead if g.lower() not in existing["disabledgroups"])
    gen_items = sorted({n for n in raw_names.values()
                        if n.lower() not in allow
                        and n.lower() not in dead_members
                        and n.lower() not in existing["disableditems"]}, key=str.lower)

    # insert later section first so earlier indexes stay valid
    for sec_name, entries in sorted((("disabledgroups", gen_groups), ("disableditems", gen_items)),
                                    key=lambda x: -ends.get(x[0], 10**9)):
        block = [BLOCK_START] + [f"{n} = 1" for n in entries] + [BLOCK_END]
        if sec_name in ends:
            i = ends[sec_name]
            # step back over blank lines and the next section's leading comments
            while i > 0 and (not out[i - 1].strip() or out[i - 1].lstrip().startswith(";")) \
                    and not header.match(out[i - 1]):
                i -= 1
            out[i:i] = block
        else:
            out += ["", "[DisabledGroups]" if sec_name == "disabledgroups" else "[DisabledItems]"] + block

    text = "\n".join(out) + "\n"
    if len(text.encode("utf-8")) > 128 * 1024:
        raise SystemExit("Filtered endless-chests.ini would exceed the mod's 128 KiB limit; nothing written.")
    with open(path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(text)
    return len(gen_items) + len(dead_members - allow)


def main():
    ap = argparse.ArgumentParser(description="Write your Enshrouded character's unlocked items to an ini file.")
    ap.add_argument("--ini", required=True, help="ini file to update (created if missing)")
    ap.add_argument("--dll", required=True, help="path to endless-chests-solo.dll (used for item names)")
    ap.add_argument("--save", help="characterN.ksd to read (default: newest one found)")
    ap.add_argument("--extra-names", help="optional ID=Name file for items the DLL does not name")
    ap.add_argument("--chest-ini", help="endless-chests.ini to rebuild so chests only supply unlocked items")
    ap.add_argument("--debug", action="store_true", help="also write raw flags and unnamed IDs")
    a = ap.parse_args()

    save = a.save
    if not save:
        cands = [f for d in find_save_dirs() for f in glob.glob(os.path.join(d, "character*.ksd"))]
        if not cands:
            sys.exit("No character*.ksd found; pass --save with the full path.")
        save = max(cands, key=os.path.getmtime)

    data = open(save, "rb").read()
    table = known_items(data)
    names = load_names_from_dll(a.dll)
    names.update(load_extra_names(a.extra_names))

    unlocked = sorted({names[k] for k, v in table.items() if v & FLAG_KNOWN and k in names},
                      key=str.lower)
    unnamed = sorted(k for k in table if k not in names)

    text = open(a.ini, encoding="utf-8").read() if os.path.isfile(a.ini) else ""
    text = replace_section(text, "UnlockInfo", [
        f"Character={character_name(data) or 'unknown'}",
        f"SaveFile={save}",
        f"Updated={dt.datetime.now():%Y-%m-%d %H:%M}",
        f"Named={len(unlocked)}",
        f"Unnamed={len(unnamed)}",
    ])
    text = replace_section(text, "Unlocked", [f"{n}=1" for n in unlocked])
    if a.debug:
        text = replace_section(text, "UnlockedDebug",
                               [f"{names.get(k, k)}={v}" for k, v in sorted(table.items())])
    with open(a.ini, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(text)
    if a.chest_ini:
        raw = load_names_from_dll(a.dll, strip_loot=False)
        n = filter_chest_ini(a.chest_ini, raw, table)
        print(f"Endless Chests: blocked {n} items you have not unlocked yet")
    print(f"{character_name(data)}: wrote {len(unlocked)} names ({len(unnamed)} IDs without a name) to {a.ini}")


if __name__ == "__main__":
    main()
