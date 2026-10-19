-- mod-forever-torch: undo the module's world database changes. Run it by hand on the world
-- database after removing the module. It isn't applied automatically: AzerothCore only runs the
-- module's db-world folder.
--
-- Removes the Night Watchman's Torch (item and spell), the fallen Night Watch Guard with his
-- spawns and pool, and his quest. Torches that players already own stay in their bags as items
-- the server no longer knows; delete those from the characters database if you want them gone
-- (item_instance.itemEntry = 90400). It also forgets that the module's updates were applied, so
-- installing the module again applies them again. Idempotent: safe to run again.

DELETE FROM `game_event_pool` WHERE `pool_entry` = 9503100;
DELETE FROM `pool_creature` WHERE `pool_entry` = 9503100;
DELETE FROM `pool_template` WHERE `entry` = 9503100;
DELETE FROM `creature` WHERE `guid` BETWEEN 9503100 AND 9503104;

DELETE FROM `creature_queststarter` WHERE `quest` = 9503100;
DELETE FROM `creature_questender` WHERE `quest` = 9503100;
DELETE FROM `quest_offer_reward` WHERE `ID` = 9503100;
DELETE FROM `quest_template` WHERE `ID` = 9503100;

DELETE FROM `npc_text` WHERE `ID` = 9503100;
DELETE FROM `creature_template_addon` WHERE `entry` = 9503100;
DELETE FROM `creature_equip_template` WHERE `CreatureID` = 9503100;
DELETE FROM `creature_template_model` WHERE `CreatureID` = 9503100;
DELETE FROM `creature_template` WHERE `entry` = 9503100;

DELETE FROM `npc_vendor` WHERE `item` = 90400;
DELETE FROM `spell_script_names` WHERE `spell_id` IN (90400, 90401);
DELETE FROM `spell_dbc` WHERE `ID` IN (90400, 90401);
DELETE FROM `item_template` WHERE `entry` = 90400;

DELETE FROM `updates` WHERE `name` LIKE 'mod\_forever\_torch\_%'
   OR `name` = '2026_10_19_00_forever_torch_mouth.sql';
