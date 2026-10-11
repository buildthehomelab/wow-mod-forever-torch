/*
 * mod-forever-torch: the Night Watchman's Torch.
 *
 * The torch is an item (90400) that casts a five minute aura on its bearer (spell 90400). The
 * aura does nothing on the server; the client shows a lit torch in the bearer's left hand for as
 * long as it lasts, and that torch model carries a light. Item, spell and model are data: the
 * module's SQL and its client patch. What the data can't say is when the torch goes out:
 *
 *   swimming        the spell's own aura interrupt flag, handled by the core
 *   entering combat the player hook below
 *   capital cities  the zone hook below
 *
 * The same three things stop it being lit, in the spell script's cast check.
 *
 * The torch comes from a fallen Night Watch Guard in Duskwood (creature 9503100, quest 9503100).
 * The quest can be done once. A player who has done it and no longer has a torch, in bags or
 * bank, can take another from the body: that is the gossip option below.
 *
 * Released under the MIT License.
 */

#include "Config.h"
#include "Creature.h"
#include "DBCStores.h"
#include "Log.h"
#include "Player.h"
#include "ScriptMgr.h"
#include "ScriptedGossip.h"
#include "SpellScript.h"
#include "SpellScriptLoader.h"

namespace
{
    constexpr uint32 SPELL_NIGHT_WATCHMANS_TORCH = 90400;
    constexpr uint32 ITEM_NIGHT_WATCHMANS_TORCH = 90400;
    constexpr uint32 QUEST_A_LIGHT_ON_THE_ROAD = 9503100;
    constexpr uint32 NPC_TEXT_FALLEN_WATCHMAN = 9503100;
    constexpr uint32 GOSSIP_ACTION_TAKE_TORCH = GOSSIP_ACTION_INFO_DEF + 1;

    struct Config
    {
        bool enabled = true;
        bool inCities = false;
        bool inCombat = false;
    };

    Config config;

    bool IsCapitalCity(uint32 zoneId)
    {
        AreaTableEntry const* zone = sAreaTableStore.LookupEntry(zoneId);
        return zone && (zone->flags & AREA_FLAG_CAPITAL);
    }

    // Has done the quest and has no torch left anywhere.
    bool CanTakeSpareTorch(Player* player)
    {
        return config.enabled && player->GetQuestRewardStatus(QUEST_A_LIGHT_ON_THE_ROAD)
            && !player->HasItemCount(ITEM_NIGHT_WATCHMANS_TORCH, 1, true);
    }
}

// 90400 - Night Watchman's Torch
class spell_forever_torch : public SpellScript
{
    PrepareSpellScript(spell_forever_torch);

    SpellCastResult CheckCast()
    {
        Unit* caster = GetCaster();

        if (!config.enabled)
            return SPELL_FAILED_SPELL_UNAVAILABLE;

        if (caster->IsInWater())
            return SPELL_FAILED_ONLY_ABOVEWATER;

        if (!config.inCombat && caster->IsInCombat())
            return SPELL_FAILED_AFFECTING_COMBAT;

        if (!config.inCities && IsCapitalCity(caster->GetZoneId()))
            return SPELL_FAILED_NOT_HERE;

        return SPELL_CAST_OK;
    }

    void Register() override
    {
        OnCheckCast += SpellCheckCastFn(spell_forever_torch::CheckCast);
    }
};

class ForeverTorchPlayerScript : public PlayerScript
{
public:
    ForeverTorchPlayerScript() : PlayerScript("ForeverTorchPlayerScript",
        { PLAYERHOOK_ON_PLAYER_ENTER_COMBAT, PLAYERHOOK_ON_UPDATE_ZONE }) { }

    void OnPlayerEnterCombat(Player* player, Unit* /*enemy*/) override
    {
        if (!config.inCombat)
            player->RemoveAurasDueToSpell(SPELL_NIGHT_WATCHMANS_TORCH);
    }

    void OnPlayerUpdateZone(Player* player, uint32 newZone, uint32 /*newArea*/) override
    {
        if (!config.inCities && IsCapitalCity(newZone))
            player->RemoveAurasDueToSpell(SPELL_NIGHT_WATCHMANS_TORCH);
    }
};

// 9503100 - Night Watch Guard (the fallen one)
class npc_forever_torch_watchman : public CreatureScript
{
public:
    npc_forever_torch_watchman() : CreatureScript("npc_forever_torch_watchman") { }

    bool OnGossipHello(Player* player, Creature* creature) override
    {
        // nothing of ours to offer: let the core open the quest as it does for any quest giver
        if (!CanTakeSpareTorch(player))
            return false;

        if (creature->IsQuestGiver())
            player->PrepareQuestMenu(creature->GetGUID());

        AddGossipItemFor(player, GOSSIP_ICON_CHAT, "Take another torch from the watchman's pack.", GOSSIP_SENDER_MAIN, GOSSIP_ACTION_TAKE_TORCH);
        SendGossipMenuFor(player, NPC_TEXT_FALLEN_WATCHMAN, creature->GetGUID());
        return true;
    }

    bool OnGossipSelect(Player* player, Creature* /*creature*/, uint32 /*sender*/, uint32 action) override
    {
        ClearGossipMenuFor(player);

        // checked again: the menu can have been open for a while. AddItem tells the player
        // itself when the bags are full.
        if (action == GOSSIP_ACTION_TAKE_TORCH && CanTakeSpareTorch(player))
            player->AddItem(ITEM_NIGHT_WATCHMANS_TORCH, 1);

        CloseGossipMenuFor(player);
        return true;
    }
};

class ForeverTorchWorldScript : public WorldScript
{
public:
    ForeverTorchWorldScript() : WorldScript("ForeverTorchWorldScript", { WORLDHOOK_ON_AFTER_CONFIG_LOAD }) { }

    void OnAfterConfigLoad(bool /*reload*/) override
    {
        config.enabled = sConfigMgr->GetOption<bool>("ForeverTorch.Enable", true);
        config.inCities = sConfigMgr->GetOption<bool>("ForeverTorch.AllowInCities", false);
        config.inCombat = sConfigMgr->GetOption<bool>("ForeverTorch.AllowInCombat", false);

        LOG_INFO("server.loading", "mod-forever-torch: {}, in capital cities: {}, in combat: {}",
            config.enabled ? "enabled" : "disabled", config.inCities ? "stays lit" : "goes out",
            config.inCombat ? "stays lit" : "goes out");
    }
};

void AddForeverTorchScripts()
{
    RegisterSpellScript(spell_forever_torch);
    new ForeverTorchPlayerScript();
    new npc_forever_torch_watchman();
    new ForeverTorchWorldScript();
}
