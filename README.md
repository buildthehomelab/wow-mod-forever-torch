# Forever Torch

An [AzerothCore](https://www.azerothcore.org/) (WotLK 3.3.5a) module that adds the **Night
Watchman's Torch**: a torch players carry in their off hand that lights the ground around them.
It follows the torch of the same name in World of Warcraft: Forever.

On a stock client the nights are bright enough that nobody needs one. It is made for a realm
whose client has dark nights; see [Dark nights](#dark-nights).

## The torch

| | |
| --- | --- |
| Item | Night Watchman's Torch: bind on pickup, unique, not used up |
| Carried | With the torch in your bags it is in your hand whenever your weapons are sheathed. No timer |
| Use | Takes the torch out again after you put it away. 30 second cooldown |
| Light | Warm orange, strongest at your feet, gone at 22 yards. Everyone nearby sees it |
| Hand | Left. A weapon in the right hand stays visible |
| Put away | While your weapons are drawn (melee or ranged), in combat, while swimming, in a capital city, in an animal form, in stealth, in a vehicle. It comes back out by itself |
| Can't be lit | In combat, while swimming, in a capital city |

Press your sheathe key (Z by default) to put your weapons away and take the torch out, and again
to swap back. After a fight the torch returns when your character sheathes its weapons.

Right-click the buff to put the torch away for good. It stays away, through logging out, until
you use the item. A torch in the bank is not carried either.

Carrying is a setting, and so are the combat and city rules. With carrying off, or outside the
night hours when it is set to nights only, using the torch lights it for 5 minutes, and it goes
out for good when you enter combat, start swimming or enter a capital city.

## Where it comes from

A **Night Watch Guard** lies dead in Duskwood with his torch still burning. He has a quest, **A
Light on the Road**, with nothing to do but accept it and hand it in: take his torch. Both
factions can.

- He is only there **at night**, from 21:00 to 06:00 server time.
- He is in **one of five places**, picked again every night: behind the inn in the abandoned town
  of Raven Hill, next to the outhouse (four nights in ten), or under a lamp post on the road west
  of Raven Hill, east of it, or at one of two on the road south to Stranglethorn.
- The quest can be done once. If you destroy your torch, talk to him again: he has a spare in his
  pack for anyone who has done the quest and has no torch in bags or bank.

## Requirements

- AzerothCore 3.3.5a.
- **A client patch.** The torch is a new spell, a new item and a model, and a 3.3.5a client only
  knows the ones in its own files. Without the patch the item shows a question mark, and using it
  does nothing a player can see.

## Install

```bash
cd azerothcore-wotlk/modules
git clone https://github.com/buildthehomelab/wow-mod-forever-torch.git mod-forever-torch
```

Clone into `mod-forever-torch`, without the `wow-`: AzerothCore names the module's loader after
the folder. Re-run CMake, build, and copy `conf/mod_forever_torch.conf.dist` to your config
folder as `mod_forever_torch.conf`. The world database changes apply themselves at the next
start.

### The client patch

`tools/build_patch.py` adds the torch to the patch MPQ that carries your realm's `Spell.dbc`:

```bash
python3 tools/build_patch.py --patch-w patch-W.MPQ --client /path/to/client --out patch-W-new.MPQ \
    --sql data/sql/db-world/mod_forever_torch_spell.sql
```

- `--patch-w` is that patch. A patch MPQ replaces whole files, so the torch's rows go into its
  copies of `Spell.dbc`, `SpellVisual.dbc`, `SpellVisualKit.dbc`, `SpellVisualEffectName.dbc` and
  `Item.dbc`. All five have to be in it. Everything else in the patch is copied unchanged.
- `--client` is a 3.3.5a client folder. The torch model is the client's own hand torch
  (`Spells\TorchSpell.m2`) with a stronger light, saved under a new name
  (`Spells\ForeverTorch.m2`), so the quest torches that use the stock model stay as they are.
- `--sql` writes the spell's server row from the same data. The file in this repo is already
  built; you only need the option if you change the tool.

Give players the new patch in place of the old one. Needs Python 3 and
[StormLib](https://github.com/ladislav-zezula/StormLib).

## Configuration

`mod_forever_torch.conf`:

| Setting | Default | |
| --- | --- | --- |
| `ForeverTorch.Enable` | `1` | With `0` the torch can't be lit and the watchman hands out no spares |
| `ForeverTorch.AllowInCities` | `0` | With `1` it can be lit and stays lit in capital cities |
| `ForeverTorch.AllowInCombat` | `0` | With `1` it can be lit and stays lit in combat. A carried torch is still put away while weapons are drawn |
| `ForeverTorch.Carry.Enable` | `1` | Carry the torch whenever weapons are sheathed. With `0` it is only lit by using it |
| `ForeverTorch.Carry.NightOnly` | `0` | With `1` it is only carried at night |
| `ForeverTorch.Carry.NightStart` / `NightEnd` | `19` / `6` | The night for `NightOnly`, in hours of server time |

All of them reload with `.reload config`.

Whether a character has put the torch away is a character setting (source `mod-forever-torch`
in `character_settings`). AzerothCore only saves those with `EnablePlayerSettings = 1` in
`worldserver.conf`; without it the torch comes back out at the next login.

## Dark nights

The torch's light is a point light on its model, which a 3.3.5a client draws on the ground,
buildings and characters around it. How much that shows depends on how dark the client's night
is. This module does not change the night, and it does not light lamp posts or campfires: those
are client patches of their own, built for our realm in
[wow-server](https://github.com/buildthehomelab/wow-server)'s `tools/client-patches`.

The client lights the ground at points about 4 yards apart, further apart on city floors, so the
edge of the light is soft on open ground and can look blocky on paving.

## What it adds to the world database

- Item 90400, Night Watchman's Torch, and its spell 90400 (`spell_dbc`) with a
  `spell_script_names` row.
- Creature 9503100, Night Watch Guard, with its model, gear and five spawns (guids 9503100 to
  9503104) in a pool (9503100) that shows one of them. The pool belongs to game event 25, which
  runs every night from 21:00 to 06:00. Stock AzerothCore calls that event "Pyrewood Village";
  the module doesn't change it.
- Quest 9503100, A Light on the Road, and `npc_text` 9503100.
- This module's id ranges: 90400 to 90409 for items and spells (and, in the client patch, the
  spell visual rows), 9503100 to 9503199 for everything else. No stock rows are changed.

## Uninstalling

Remove the module folder and rebuild, then run
`data/sql/uninstall/mod_forever_torch_uninstall_world.sql` on the world database by hand. Do
both: with the module gone and its rows still there, the torch can be lit anywhere and never
goes out in combat or in cities.

On the characters database, ``DELETE FROM `character_settings` WHERE `source` =
'mod-forever-torch';`` removes the put-away choices.

## Troubleshooting

- **The item is a question mark, or nothing happens when it's used:** the client doesn't have the
  patch, or has an older copy of it.
- **The buff appears but there is no torch:** the patch's `Spell.dbc` row is there but the model
  or the spell visual rows are not. Build the patch with this tool again.
- **The torch lights nothing:** the client's night isn't dark enough to show it. Try a cave.
- **The watchman isn't there:** he only appears between 21:00 and 06:00 server time, in one of
  five places. `.event activelist` should list event 25 at night; `.go creature 9503100` takes a
  game master to tonight's spot. If the event has been stopped or moved, he follows it.
- **He's there but floats, or is sunk into the ground:** tell us which spot. The heights come
  from the client's terrain data and have not all been checked in game.
- **"You can't do that here":** you're in a capital city.
- **The torch isn't in my hand:** your weapons are drawn (press Z), the torch is in the bank, or
  you put it away by right-clicking the buff: use the item. In a capital city, in water and in
  animal forms it stays away.
- **The torch has a 5 minute timer:** you don't have a torch in your bags, carrying is off, or it
  is daytime with `ForeverTorch.Carry.NightOnly = 1`.
- **The torch never goes out in combat or in cities:** the module isn't built in, or
  `ForeverTorch.AllowInCombat` / `AllowInCities` is `1`. Look for the `mod-forever-torch:` line
  in the worldserver log.
- **The module doesn't build or load:** the folder must be named `mod-forever-torch`.

## Patch Notes: Night Watchman's Torch

Category: World

- Added the **Night Watchman's Torch**. With it in your bags you carry a lit torch in your off
  hand whenever your weapons are sheathed. The torch lights the ground around you and can be
  seen by other players.
- The torch is put away when you draw your weapons, enter combat, start swimming or enter a
  capital city, and comes back out afterwards. Right-click the buff to put it away for good; use
  the torch to take it out again.
- A fallen **Night Watch Guard** can be found somewhere in Duskwood at night. Take his torch by
  completing **A Light on the Road**. Players who lose their torch can return to him for another.

> The nights are getting darker. This is the first thing we wanted you to have in your bags
> before they do.

## Credits

Author: [buildthehomelab](https://github.com/buildthehomelab)

The torch is modelled on the Night Watchman's Torch in World of Warcraft: Forever.

## License

MIT, see [LICENSE](LICENSE).
