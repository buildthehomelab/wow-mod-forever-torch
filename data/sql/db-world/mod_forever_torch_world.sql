-- mod-forever-torch: the Night Watchman's Torch, and the fallen Night Watch Guard who has it.
--
--   item 90400      Night Watchman's Torch: keep it, use it as often as you like (30 second
--                   cooldown). Using it casts spell 90400, a five minute aura that shows a lit
--                   torch in your left hand. The spell's own row is in
--                   mod_forever_torch_spell.sql, written by tools/build_patch.py.
--   creature 9503100  Night Watch Guard, dead, lying on the ground. Friendly to both factions.
--   quest 9503100   A Light on the Road: take his torch. No objectives, so it is complete as
--                   soon as it is accepted; he gives it and ends it.
--
-- Where and when he lies: on one of five spots in the west and south of Duskwood, and only at
-- night. His five spawns are a pool that shows one of them, and the pool belongs to game event
-- 25. Stock AzerothCore calls that event "Pyrewood Village" (it turns Pyrewood's villagers into
-- worgen); it runs every night from 21:00 to 06:00 server time, and nothing else in the core is
-- a plain night clock. Each night the pool picks again: the abandoned town of Raven Hill four
-- times in ten, otherwise a lamp post on the roads.
--
-- The spots are on open ground, away from buildings and trees. Heights are the client's terrain
-- height at each spot plus 0.05.
--
-- This module's ids: item and spell 90400 (reserved to 90409); creature, quest, npc_text, pool
-- and creature spawn guids 9503100 (reserved to 9503199). No stock rows are changed, game event
-- 25 included. Idempotent. Undo with data/sql/uninstall/mod_forever_torch_uninstall_world.sql.

-- ---------------------------------------------------------------------------------------------
-- The torch
-- ---------------------------------------------------------------------------------------------

-- Miscellaneous, bind on pickup, unique. Flags 64: its spell is cast by the player. Display
-- 12312 is the Dim Torch's (the lit torch icon). The 30 seconds are the item's own cooldown.
DELETE FROM `item_template` WHERE `entry` = 90400;
INSERT INTO `item_template` (`entry`, `class`, `subclass`, `name`, `displayid`, `Quality`, `Flags`, `BuyPrice`, `SellPrice`, `ItemLevel`, `maxcount`, `stackable`, `delay`, `spellid_1`, `spelltrigger_1`, `spellcharges_1`, `spellcooldown_1`, `spellcategory_1`, `spellcategorycooldown_1`, `bonding`, `description`, `Material`) VALUES
(90400, 15, 4, 'Night Watchman''s Torch', 12312, 2, 64, 0, 0, 1, 1, 1, 0, 90400, 0, 0, 30000, 0, -1, 1, 'The Night Watch dips its torches in pitch thick enough to last until morning.', -1);

DELETE FROM `spell_script_names` WHERE `spell_id` = 90400;
INSERT INTO `spell_script_names` (`spell_id`, `ScriptName`) VALUES
(90400, 'spell_forever_torch');

-- ---------------------------------------------------------------------------------------------
-- The fallen watchman
-- ---------------------------------------------------------------------------------------------

-- The living Night Watch Guard's model (2381) and gear: sword 2180, and in the off hand the
-- watch's own torch (2081, "Monster - Torch, Offhand"). Faction 35 so the Horde can take a torch
-- too. npcflag 3: quest giver, and gossip for the spare torch. unit_flags 768: nothing can
-- attack him. flags_extra 2: no one is called for help. bytes1 7 lays him down dead.
DELETE FROM `creature_template` WHERE `entry` = 9503100;
INSERT INTO `creature_template` (`entry`, `name`, `subname`, `minlevel`, `maxlevel`, `faction`, `npcflag`, `speed_walk`, `speed_run`, `BaseAttackTime`, `RangeAttackTime`, `unit_class`, `unit_flags`, `unit_flags2`, `type`, `flags_extra`, `ScriptName`) VALUES
(9503100, 'Night Watch Guard', 'The Night Watch', 30, 30, 35, 3, 1, 1.14286, 2000, 2000, 1, 768, 2048, 7, 2, 'npc_forever_torch_watchman');

DELETE FROM `creature_template_model` WHERE `CreatureID` = 9503100;
INSERT INTO `creature_template_model` (`CreatureID`, `Idx`, `CreatureDisplayID`, `DisplayScale`, `Probability`, `VerifiedBuild`) VALUES
(9503100, 0, 2381, 1, 1, 0);

DELETE FROM `creature_equip_template` WHERE `CreatureID` = 9503100;
INSERT INTO `creature_equip_template` (`CreatureID`, `ID`, `ItemID1`, `ItemID2`, `ItemID3`, `VerifiedBuild`) VALUES
(9503100, 1, 2180, 2081, 0, 0);

DELETE FROM `creature_template_addon` WHERE `entry` = 9503100;
INSERT INTO `creature_template_addon` (`entry`, `path_id`, `mount`, `bytes1`, `bytes2`, `emote`, `visibilityDistanceType`, `auras`) VALUES
(9503100, 0, 0, 7, 1, 0, 0, NULL);

-- What the spare torch menu says above its one option.
DELETE FROM `npc_text` WHERE `ID` = 9503100;
INSERT INTO `npc_text` (`ID`, `text0_0`, `text0_1`, `Probability0`) VALUES
(9503100, 'The watchman lies where he fell. His pack is still strapped to his back, and the handle of a second torch sticks out of it.', 'The watchman lies where he fell. His pack is still strapped to his back, and the handle of a second torch sticks out of it.', 1);

-- ---------------------------------------------------------------------------------------------
-- Where he lies
-- ---------------------------------------------------------------------------------------------

DELETE FROM `game_event_pool` WHERE `pool_entry` = 9503100;
DELETE FROM `pool_creature` WHERE `pool_entry` = 9503100;
DELETE FROM `pool_template` WHERE `entry` = 9503100;
DELETE FROM `creature` WHERE `guid` BETWEEN 9503100 AND 9503104;

INSERT INTO `creature` (`guid`, `id`, `map`, `spawnMask`, `phaseMask`, `equipment_id`, `position_x`, `position_y`, `position_z`, `orientation`, `spawntimesecs`, `wander_distance`, `MovementType`, `Comment`) VALUES
(9503100, 9503100, 0, 1, 1, 1, -10706.5, 376.1, 38.19, 1.2, 300, 0, 0, 'mod-forever-torch: Raven Hill, by the outhouse behind the inn'),
(9503101, 9503100, 0, 1, 1, 1, -10817.5, 366.3, 29.84, 4.4, 300, 0, 0, 'mod-forever-torch: lamp post on the road west of Raven Hill'),
(9503102, 9503100, 0, 1, 1, 1, -10755.0, 92.3, 28.67, 0.6, 300, 0, 0, 'mod-forever-torch: lamp post on the road east of Raven Hill'),
(9503103, 9503100, 0, 1, 1, 1, -10968.4, -357.9, 40.88, 2.9, 300, 0, 0, 'mod-forever-torch: lamp post on the road south to Stranglethorn'),
(9503104, 9503100, 0, 1, 1, 1, -11095.2, -376.9, 44.62, 5.3, 300, 0, 0, 'mod-forever-torch: lamp post further down the road south');

-- One of the five at a time. The chances have to add up to 100.
INSERT INTO `pool_template` (`entry`, `max_limit`, `description`) VALUES
(9503100, 1, 'mod-forever-torch: fallen Night Watch Guard, one spot a night');

INSERT INTO `pool_creature` (`guid`, `pool_entry`, `chance`, `description`) VALUES
(9503100, 9503100, 40, 'Fallen Night Watch Guard - Raven Hill'),
(9503101, 9503100, 15, 'Fallen Night Watch Guard - road west of Raven Hill'),
(9503102, 9503100, 15, 'Fallen Night Watch Guard - road east of Raven Hill'),
(9503103, 9503100, 15, 'Fallen Night Watch Guard - road south'),
(9503104, 9503100, 15, 'Fallen Night Watch Guard - road further south');

-- Only at night: 21:00 to 06:00 server time.
INSERT INTO `game_event_pool` (`eventEntry`, `pool_entry`) VALUES
(25, 9503100);

-- ---------------------------------------------------------------------------------------------
-- The quest
-- ---------------------------------------------------------------------------------------------

-- QuestLevel -1 follows the player's level, and with no experience set it gives none. QuestSortID
-- 10 files it under Duskwood.
DELETE FROM `quest_template` WHERE `ID` = 9503100;
INSERT INTO `quest_template` (`ID`, `QuestType`, `QuestLevel`, `MinLevel`, `QuestSortID`, `QuestInfoID`, `RewardItem1`, `RewardAmount1`, `LogTitle`, `LogDescription`, `QuestDescription`, `QuestCompletionLog`, `VerifiedBuild`) VALUES
(9503100, 2, -1, 1, 10, 0, 90400, 1,
 'A Light on the Road',
 'Take the fallen watchman''s torch.',
 'Whatever killed this watchman did not give him time to turn around. His blade is clean.$B$BHis torch lies in the grass beside him, still burning. The Night Watch dips its torches in pitch thick enough to last until morning, because out here the dark is the first thing that kills you.$B$BHe has no more use for it. You might.',
 'Take the torch from the fallen Night Watch Guard.',
 0);

DELETE FROM `quest_offer_reward` WHERE `ID` = 9503100;
INSERT INTO `quest_offer_reward` (`ID`, `Emote1`, `Emote2`, `Emote3`, `Emote4`, `EmoteDelay1`, `EmoteDelay2`, `EmoteDelay3`, `EmoteDelay4`, `RewardText`, `VerifiedBuild`) VALUES
(9503100, 0, 0, 0, 0, 0, 0, 0, 0, 'You work the torch free of the watchman''s grip and turn it over. The pitch is thick and the wood is sound. It will light again, as often as you need it to.$B$BSomewhere to the east, Darkshire will be counting its patrols.', 0);

DELETE FROM `creature_queststarter` WHERE `quest` = 9503100;
INSERT INTO `creature_queststarter` (`id`, `quest`) VALUES
(9503100, 9503100);

DELETE FROM `creature_questender` WHERE `quest` = 9503100;
INSERT INTO `creature_questender` (`id`, `quest`) VALUES
(9503100, 9503100);
