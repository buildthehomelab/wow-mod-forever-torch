#!/usr/bin/env python3
"""The client side of the Night Watchman's Torch: its rows and its model for your realm's spell
patch, and the spell's row for the server.

    python3 build_patch.py --patch-w patch-W.MPQ --client /path/to/client --out patch-W-new.MPQ \\
        --sql ../data/sql/db-world/mod_forever_torch_spell.sql

--patch-w is the patch that carries your realm's Spell.dbc, Item.dbc and the SpellVisual tables
(patch-W.MPQ above is an example name). A patch MPQ replaces whole files, so the new rows go into its copies; every
other file in it is copied unchanged. It gains:

- Spell.dbc 90400, Night Watchman's Torch: a five minute aura on yourself that does nothing but
  show the torch. It starts as a copy of Has Flaming Torch (45275), the Midsummer torch.
- SpellVisual.dbc, SpellVisualKit.dbc and SpellVisualEffectName.dbc 90400: the torch in the left
  hand while the aura lasts, so a weapon in the right hand stays where it is.
- Item.dbc 90400: the item, so the client has its icon. It borrows the Dim Torch's display.
- Spells\\ForeverTorch.m2 and its .skin: the client's hand torch (Spells\\TorchSpell.m2, taken
  from --client) with a light that reaches. The stock light fades out at 2.2 yards; this one runs
  from 1 to 22 yards, three times its colour's strength, in a deeper orange. Only the light
  differs from the stock model. Quest torches that use the stock model are not touched.

--sql writes the spell's spell_dbc row from the same Spell.dbc row, so client and server can't
disagree about it.

Running it again on its own output adds nothing: every file inside comes out the same (the MPQ's
own bytes differ, StormLib stamps the time). Needs Python 3 and StormLib (`STORMLIB`, default
/usr/local/lib/libstorm.dylib).
"""

import argparse
import ctypes
import glob
import os
import struct
import sys
import tempfile

SPELL = ITEM = VISUAL = KIT = EFFECT_NAME = 90400
NAME = "Night Watchman's Torch"
DESCRIPTION = ("Light the torch and carry it for $d. It lights the ground around you. "
               "Fighting, swimming or entering a capital city puts it out.")
AURA_TEXT = "Carrying a lit torch."

TEMPLATE_SPELL = 45275          # Has Flaming Torch: instant, self, one dummy aura
TEMPLATE_EFFECT_NAME = 3032     # "Torch", Spells\TorchSpell.mdx
ICON = 1887                     # SpellIcon.dbc: Interface\Icons\INV_Torch_Lit
ITEM_DISPLAY = 12312            # ItemDisplayInfo.dbc: the Dim Torch's, icon INV_Torch_Lit
DURATION_FIVE_MINUTES = 5       # SpellDuration.dbc row
AURA_INTERRUPT_SWIMMING = 0x80  # AURA_INTERRUPT_FLAG_NOT_ABOVEWATER
ITEM_CLASS_MISC, ITEM_SUBCLASS_OTHER = 15, 4
UNSET = 0xFFFFFFFF

BASE_ARCHIVES = ["common.mpq", "common-2.mpq", "expansion.mpq", "lichking.mpq", "patch.mpq"]
STOCK_MODEL, STOCK_SKIN = "Spells\\TorchSpell.m2", "Spells\\TorchSpell00.skin"
MODEL, SKIN = "Spells\\ForeverTorch.m2", "Spells\\ForeverTorch00.skin"
MODEL_IN_DBC = "Spells\\ForeverTorch.mdx"   # the client reads .mdx in this table as .m2
# The light: fade start and end in yards, strength, colour.
LIGHT = (1.0, 22.0, 3.0, (1.0, 0.55, 0.18))
# 3.3.5 M2 (version 264): the header's light array, and the tracks inside an M2Light
M2_LIGHTS, M2_LIGHT_SIZE, POINT_LIGHT = 0x108, 156, 1
DIFFUSE_COLOUR, DIFFUSE_INTENSITY, ATTENUATION_START, ATTENUATION_END = 56, 76, 96, 116

SPELL_FIELDS = 234
F_ATTRIBUTES, F_ATTRIBUTES_LAST = 4, 11
F_AURA_INTERRUPT, F_DURATION = 32, 40
F_VISUAL, F_ICON, F_ACTIVE_ICON, F_NAME, F_DESCRIPTION, F_AURA_TEXT = 131, 133, 134, 136, 170, 187
STRING_FIELDS = set(range(136, 152)) | set(range(153, 169)) | set(range(170, 186)) | set(range(187, 203))
FLOAT_FIELDS = {47, 77, 78, 79, 101, 102, 103, 119, 120, 121, 216, 217, 218, 229, 230, 231}
# Plain `int` columns of AC's spell_dbc; every other integer column is unsigned.
SIGNED_FIELDS = {0, 13, 15, 41, *range(52, 71), 74, 75, 76, 80, 81, 82, *range(110, 116), 224, 228}
# SpellVisual.dbc: the kit shown while the spell's aura lasts.
# SpellVisualKit.dbc: the model on the left hand, and the one on the right hand's weapon.
V_STATE_KIT, K_LEFT_HAND, K_RIGHT_WEAPON = 4, 6, 10


# --- DBC ---------------------------------------------------------------------------------------

def read_dbc(path):
    data = open(path, "rb").read()
    magic, count, fields, size, strsize = struct.unpack_from("<4s4I", data, 0)
    if magic != b"WDBC" or size != fields * 4:
        sys.exit("%s isn't a plain WDBC file" % path)
    rows = [list(struct.unpack_from("<%dI" % fields, data, 20 + i * size)) for i in range(count)]
    strings = bytearray(data[20 + count * size:20 + count * size + strsize])
    return rows, strings, fields


def write_dbc(path, rows, strings, fields):
    rows = sorted(rows, key=lambda r: r[0])
    with open(path, "wb") as f:
        f.write(struct.pack("<4s4I", b"WDBC", len(rows), fields, fields * 4, len(strings)))
        for r in rows:
            f.write(struct.pack("<%dI" % fields, *r))
        f.write(strings)


def string_at(strings, at):
    return strings[at:strings.index(b"\0", at)].decode("utf-8")


def add_string(strings, text):
    """Offset of text in the string block, appended unless it is already there as a whole string."""
    raw = text.encode("utf-8") + b"\0"
    at = strings.find(b"\0" + raw)
    if at >= 0:
        return at + 1
    at = len(strings)
    strings.extend(raw)
    return at


def template(rows, row_id, what):
    for r in rows:
        if r[0] == row_id:
            return list(r)
    sys.exit("%s %d missing" % (what, row_id))


def upsert(rows, row):
    rows[:] = [r for r in rows if r[0] != row[0]]
    rows.append(row)


def claim(rows, row_id, table, ours):
    """Stops if the patch already uses one of our ids for something else."""
    old = next((r for r in rows if r[0] == row_id), None)
    if old and not ours(old):
        sys.exit("%s.dbc row %d is taken by something else" % (table, row_id))


# --- MPQ ---------------------------------------------------------------------------------------

def stormlib():
    lib = ctypes.CDLL(os.environ.get("STORMLIB", "/usr/local/lib/libstorm.dylib"))
    H = ctypes.c_void_p
    lib.SFileOpenArchive.argtypes = [ctypes.c_char_p, ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(H)]
    lib.SFileExtractFile.argtypes = [H, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
    lib.SFileHasFile.argtypes = [H, ctypes.c_char_p]
    lib.SFileFindFirstFile.argtypes = [H, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_char_p]
    lib.SFileFindFirstFile.restype = H
    lib.SFileFindNextFile.argtypes = [H, ctypes.c_void_p]
    lib.SFileFindClose.argtypes = [H]
    lib.SFileCreateArchive.argtypes = [ctypes.c_char_p, ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(H)]
    lib.SFileAddFileEx.argtypes = [H, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint]
    lib.SFileCloseArchive.argtypes = [H]
    for fn in (lib.SFileOpenArchive, lib.SFileExtractFile, lib.SFileHasFile, lib.SFileFindNextFile,
               lib.SFileFindClose, lib.SFileCreateArchive, lib.SFileAddFileEx, lib.SFileCloseArchive):
        fn.restype = ctypes.c_bool
    return lib, H


def open_mpq(lib, H, mpq):
    h = H()
    if not lib.SFileOpenArchive(mpq.encode(), 0, 0x100, ctypes.byref(h)):
        sys.exit("can't open " + mpq)
    return h


def unpack(mpq, folder):
    """Extracts every file; returns {archive name: local path}."""
    lib, H = stormlib()
    h = open_mpq(lib, H, mpq)
    names = []
    found = ctypes.create_string_buffer(2048)  # SFILE_FIND_DATA starts with the name (1024 bytes)
    find = lib.SFileFindFirstFile(h, b"*", found, None)
    while find:
        name = found.value.decode("latin-1")
        if name not in ("(listfile)", "(attributes)", "(signature)"):
            names.append(name)
        if not lib.SFileFindNextFile(find, found):
            lib.SFileFindClose(find)
            break
    files = {}
    for i, name in enumerate(names):
        local = os.path.join(folder, "%05d" % i)
        if not lib.SFileExtractFile(h, name.encode("latin-1"), local.encode(), 0):
            sys.exit("can't extract %s from %s" % (name, mpq))
        files[name] = local
    lib.SFileCloseArchive(h)
    if not files:
        sys.exit("%s has no files (or no listfile)" % mpq)
    return files


def load_order(client):
    """The client's archives, first loaded first: the base ones, then patch-2, patch-3, patch-A..."""
    found = {os.path.basename(p).lower(): p for p in glob.glob(os.path.join(client, "Data", "*"))
             if p.lower().endswith(".mpq")}
    order = [found.pop(name) for name in BASE_ARCHIVES if name in found]
    return order + [found[name] for name in sorted(found) if name.startswith("patch-")]


def client_model(client, name, dst):
    """The client's own copy of a model file: from the last archive it loads that has it."""
    lib, H = stormlib()
    for mpq in reversed(load_order(client)):
        h = open_mpq(lib, H, mpq)
        ok = lib.SFileHasFile(h, name.encode("latin-1")) and lib.SFileExtractFile(h, name.encode("latin-1"), dst.encode(), 0)
        lib.SFileCloseArchive(h)
        if ok:
            return mpq
    sys.exit("no %s in %s" % (name, os.path.join(client, "Data")))


def pack(out, files):
    """files: [(local path, archive name)]. zlib-compressed, with listfile and attributes."""
    lib, H = stormlib()
    if os.path.exists(out):
        os.remove(out)
    h = H()
    if not lib.SFileCreateArchive(out.encode(), 0x00300000, max(64, len(files) * 2), ctypes.byref(h)):
        sys.exit("can't create " + out)
    for src, name in files:
        if not lib.SFileAddFileEx(h, src.encode(), name.encode("latin-1"), 0x80000200, 0x02, 0x02):
            lib.SFileCloseArchive(h)
            os.remove(out)
            sys.exit("can't add " + name)
    if not lib.SFileCloseArchive(h):
        os.remove(out)
        sys.exit("can't finish " + out)


# --- the torch ---------------------------------------------------------------------------------

def track_keys(data, at, size):
    """File offsets of every key of the M2Track at `at`."""
    count, offset = struct.unpack_from("<II", data, at + 12)
    keys = []
    for i in range(count):
        n, first = struct.unpack_from("<II", data, offset + i * 8)
        keys += [first + k * size for k in range(n)]
    return keys


def torch_model(path):
    """Gives the stock hand torch's light its reach, strength and colour, in place."""
    data = bytearray(open(path, "rb").read())
    magic, version = struct.unpack_from("<4sI", data, 0)
    count, light = struct.unpack_from("<II", data, M2_LIGHTS)
    if magic != b"MD20" or version != 264 or count != 1 or struct.unpack_from("<H", data, light)[0] != POINT_LIGHT:
        sys.exit("%s should be a 3.3.5 model with one point light" % STOCK_MODEL)
    start, end, strength, colour = LIGHT
    for track, value in ((ATTENUATION_START, start), (ATTENUATION_END, end), (DIFFUSE_INTENSITY, strength)):
        keys = track_keys(data, light + track, 4)
        if not keys:
            sys.exit("%s: the light has an empty track" % STOCK_MODEL)
        for key in keys:
            struct.pack_into("<f", data, key, value)
    for key in track_keys(data, light + DIFFUSE_COLOUR, 12):
        struct.pack_into("<3f", data, key, *colour)
    with open(path, "wb") as f:
        f.write(data)


def patch_w(files, args, tmp):
    """Adds the torch's rows and model to the unpacked spell patch. Returns the spell row."""
    def dbc(table):
        return "DBFilesClient\\%s.dbc" % table

    tables = {}
    for table in ("Spell", "SpellVisual", "SpellVisualKit", "SpellVisualEffectName", "Item"):
        if dbc(table) not in files:
            sys.exit("%s has no %s.dbc" % (args.patch_w, table))
        tables[table] = read_dbc(files[dbc(table)])
    spells, spell_str, spell_fields = tables["Spell"]
    visuals, _, _ = tables["SpellVisual"]
    kits, _, _ = tables["SpellVisualKit"]
    effects, effect_str, _ = tables["SpellVisualEffectName"]
    items, _, _ = tables["Item"]
    if spell_fields != SPELL_FIELDS:
        sys.exit("Spell.dbc has %d fields, not %d" % (spell_fields, SPELL_FIELDS))

    claim(spells, SPELL, "Spell", lambda r: string_at(spell_str, r[F_NAME]) == NAME)
    claim(effects, EFFECT_NAME, "SpellVisualEffectName", lambda r: string_at(effect_str, r[2]) == MODEL_IN_DBC)
    claim(kits, KIT, "SpellVisualKit", lambda r: r[K_LEFT_HAND] == EFFECT_NAME)
    claim(visuals, VISUAL, "SpellVisual", lambda r: r[V_STATE_KIT] == KIT)
    claim(items, ITEM, "Item", lambda r: r[5] == ITEM_DISPLAY)

    stock = template(spells, TEMPLATE_SPELL, "Spell.dbc row")
    stock_visual = template(visuals, stock[F_VISUAL], "SpellVisual.dbc row")
    stock_kit = template(kits, stock_visual[V_STATE_KIT], "SpellVisualKit.dbc row")
    if stock_kit[K_RIGHT_WEAPON] != TEMPLATE_EFFECT_NAME or stock_kit[K_LEFT_HAND] != 0:
        sys.exit("spell %d no longer shows the torch the way this tool expects" % TEMPLATE_SPELL)

    effect = template(effects, TEMPLATE_EFFECT_NAME, "SpellVisualEffectName.dbc row")
    effect[0] = EFFECT_NAME
    effect[1] = add_string(effect_str, NAME)
    effect[2] = add_string(effect_str, MODEL_IN_DBC)
    upsert(effects, effect)

    kit = stock_kit
    kit[0] = KIT
    kit[K_RIGHT_WEAPON] = 0
    kit[K_LEFT_HAND] = EFFECT_NAME
    upsert(kits, kit)

    visual = stock_visual
    visual[0] = VISUAL
    visual[V_STATE_KIT] = KIT
    upsert(visuals, visual)

    spell = stock
    spell[0] = SPELL
    # The Midsummer torch hides its buff and ignores immunities; ours is a plain buff the player
    # sees and can click off.
    for field in range(F_ATTRIBUTES, F_ATTRIBUTES_LAST + 1):
        spell[field] = 0
    spell[F_AURA_INTERRUPT] = AURA_INTERRUPT_SWIMMING
    spell[F_DURATION] = DURATION_FIVE_MINUTES
    spell[F_VISUAL] = VISUAL
    spell[F_ICON] = ICON
    spell[F_ACTIVE_ICON] = 0
    spell[F_NAME] = add_string(spell_str, NAME)
    spell[F_DESCRIPTION] = add_string(spell_str, DESCRIPTION)
    spell[F_AURA_TEXT] = add_string(spell_str, AURA_TEXT)
    upsert(spells, spell)

    upsert(items, [ITEM, ITEM_CLASS_MISC, ITEM_SUBCLASS_OTHER, UNSET, UNSET, ITEM_DISPLAY, 0, 0])

    for table in tables:
        rows, strings, fields = tables[table]
        write_dbc(files[dbc(table)], rows, strings, fields)

    for stock_name, name in ((STOCK_MODEL, MODEL), (STOCK_SKIN, SKIN)):
        local = os.path.join(tmp, os.path.basename(name.replace("\\", "/")))
        source = client_model(args.client, stock_name, local)
        print("%s: from %s in %s" % (name, stock_name, os.path.basename(source)))
        files[name] = local
    torch_model(files[MODEL])
    return spell


# --- SQL ---------------------------------------------------------------------------------------

def sql_str(s):
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


def write_sql(path, spell):
    def value(i, v):
        if i in STRING_FIELDS:
            return "''"
        if i in FLOAT_FIELDS:
            return "%g" % struct.unpack("<f", struct.pack("<I", v))[0]
        return str(struct.unpack("<i", struct.pack("<I", v))[0] if i in SIGNED_FIELDS else v)

    values = [value(i, v) for i, v in enumerate(spell)]
    values[F_NAME] = sql_str(NAME)
    values[F_DESCRIPTION] = sql_str(DESCRIPTION)
    values[F_AURA_TEXT] = sql_str(AURA_TEXT)
    with open(path, "w", encoding="utf-8") as f:
        f.write("-- mod-forever-torch: the Night Watchman's Torch spell (%d), as the server needs it.\n" % SPELL)
        f.write("-- Generated by tools/build_patch.py from the same Spell.dbc row the client patch gets:\n")
        f.write("-- run the tool again, don't edit this file. A five minute dummy aura on the caster that\n")
        f.write("-- swimming removes; the module's script handles combat and capital cities.\n\n")
        f.write("DELETE FROM `spell_dbc` WHERE `ID` = %d;\n" % SPELL)
        f.write("INSERT INTO `spell_dbc` VALUES\n(" + ", ".join(values) + ");\n")
    print("wrote", path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--patch-w", required=True, help="your realm's live spell patch (e.g. patch-W.MPQ)")
    ap.add_argument("--client", required=True, help="the base client folder (has Data/)")
    ap.add_argument("--out", required=True, help="the new spell patch")
    ap.add_argument("--sql", help="write the spell's server row here")
    args = ap.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        unpacked = os.path.join(tmp, "w")
        os.mkdir(unpacked)
        files = unpack(args.patch_w, unpacked)
        spell = patch_w(files, args, tmp)
        pack(args.out, [(local, name) for name, local in sorted(files.items())])
        print("%s: %d files, %.1f MB" % (args.out, len(files), os.path.getsize(args.out) / 1e6))
        if args.sql:
            write_sql(args.sql, spell)


if __name__ == "__main__":
    main()
