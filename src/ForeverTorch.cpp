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
 * Carrying (ForeverTorch.Carry.Enable): from dusk to dawn nobody has to light a torch, or own
 * one. It is in every player's hand whenever the hand is free, and has no timer. The client
 * tells the server when weapons are drawn or put back (the sheath state), so a few times a
 * second the player hook below puts the torch away while weapons are drawn, in combat, in water,
 * in a capital city or in an animal form, and brings it back out afterwards. Right-clicking the
 * buff puts it away for good, kept as a character setting; ".torch on" or using the item takes
 * it out again. With ForeverTorch.Carry.RequireItem only players with the item in their bags
 * carry one. Bots carry none.
 *
 * The item is for lighting a torch by hand, by day or in a cave. General goods vendors sell it
 * (rows in the module's SQL), and a fallen Night Watch Guard in Duskwood has one for free
 * (creature 9503100, quest 9503100). The quest can be done once. A player who has done it and
 * no longer has a torch, in bags or bank, can take another from the body: that is the gossip
 * option below.
 *
 * Released under the MIT License.
 */

#include "Chat.h"
#include "ChatCommand.h"
#include "CommandScript.h"
#include "Config.h"
#include "Creature.h"
#include "DBCStores.h"
#include "Log.h"
#include "Player.h"
#include "ScriptMgr.h"
#include "ScriptedGossip.h"
#include "SpellAuraEffects.h"
#include "SpellAuras.h"
#include "SpellScript.h"
#include "SpellScriptLoader.h"
#include "Timer.h"
#include "WorldSession.h"

using namespace Acore::ChatCommands;

namespace
{
    constexpr uint32 SPELL_NIGHT_WATCHMANS_TORCH = 90400;
    constexpr uint32 ITEM_NIGHT_WATCHMANS_TORCH = 90400;
    constexpr uint32 QUEST_A_LIGHT_ON_THE_ROAD = 9503100;
    constexpr uint32 NPC_TEXT_FALLEN_WATCHMAN = 9503100;
    constexpr uint32 GOSSIP_ACTION_TAKE_TORCH = GOSSIP_ACTION_INFO_DEF + 1;

    // How often a player's carried torch is looked at, in milliseconds. This is the longest a
    // torch and a drawn weapon share a hand.
    constexpr uint32 CARRY_UPDATE_INTERVAL = 250;

    // Character setting (character_settings, kept only with EnablePlayerSettings = 1 in
    // worldserver.conf; without it the choice lasts until logout).
    const std::string SETTING_SOURCE = "mod-forever-torch";
    constexpr uint32 SETTING_PUT_AWAY = 0;

    struct Config
    {
        bool enabled = true;
        bool inCities = false;
        bool inCombat = false;
        bool carry = true;
        bool carryNightOnly = true;
        bool carryRequireItem = false;
        uint32 nightStart = 19;
        uint32 nightEnd = 6;
    };

    Config config;

    struct CarryState : public DataMap::Base
    {
        uint32 timer = 0;
    };

    CarryState* GetCarryState(Player* player)
    {
        return player->CustomData.GetDefault<CarryState>("mod-forever-torch");
    }

    // Bot sessions: IsHeadless() on current playerbots cores, IsBot() on older ones.
    template <typename Session, typename = void>
    struct HasIsHeadless : std::false_type { };

    template <typename Session>
    struct HasIsHeadless<Session, std::void_t<decltype(std::declval<Session&>().IsHeadless())>> : std::true_type { };

    template <typename Session, typename = void>
    struct HasIsBot : std::false_type { };

    template <typename Session>
    struct HasIsBot<Session, std::void_t<decltype(std::declval<Session&>().IsBot())>> : std::true_type { };

    template <typename Session>
    bool IsBotSession(Session* session)
    {
        if constexpr (HasIsHeadless<Session>::value)
            return session->IsHeadless();
        else if constexpr (HasIsBot<Session>::value)
            return session->IsBot();
        else
            return false;
    }

    bool IsRealPlayer(Player* player)
    {
        WorldSession* session = player->GetSession();
        return session && !IsBotSession(session);
    }

    bool IsCapitalCity(uint32 zoneId)
    {
        AreaTableEntry const* zone = sAreaTableStore.LookupEntry(zoneId);
        return zone && (zone->flags & AREA_FLAG_CAPITAL);
    }

    // Server time is the time on the client's clock.
    bool IsCarryHour()
    {
        if (!config.carryNightOnly)
            return true;

        uint32 hour = Acore::Time::GetHours();
        if (config.nightStart <= config.nightEnd)
            return hour >= config.nightStart && hour < config.nightEnd;

        return hour >= config.nightStart || hour < config.nightEnd;
    }

    // A hand to hold the torch in, and nothing that puts a torch out.
    bool HasHandFree(Player* player)
    {
        return player->IsAlive()
            && player->GetSheath() == SHEATH_STATE_UNARMED
            && (config.inCombat || !player->IsInCombat())
            && !player->IsInWater()
            && (config.inCities || !IsCapitalCity(player->GetZoneId()))
            && !player->IsInDisallowedMountForm()
            && !player->HasStealthAura()
            && !player->GetVehicle();
    }

    // Brings the carried torch out or puts it away. A carried torch is the same aura as a lit
    // one, without the five minutes; that is also how the two are told apart.
    void UpdateCarriedTorch(Player* player)
    {
        Aura* torch = player->GetAura(SPELL_NIGHT_WATCHMANS_TORCH);

        if (!config.enabled || !config.carry || !IsCarryHour())
        {
            // carrying was switched off, or the night is over
            if (torch && torch->IsPermanent())
                player->RemoveAura(torch);
            return;
        }

        bool handFree = HasHandFree(player);
        if (!handFree && !torch)
            return;

        // the bags are searched last. Reading the setting gives the character a row in
        // character_settings.
        if ((config.carryRequireItem && !player->HasItemCount(ITEM_NIGHT_WATCHMANS_TORCH, 1, false))
            || player->GetPlayerSetting(SETTING_SOURCE, SETTING_PUT_AWAY).value)
        {
            // banked or destroyed while it was out. A torch lit by hand burns on.
            if (torch && torch->IsPermanent())
                player->RemoveAura(torch);
            return;
        }

        if (!handFree)
        {
            player->RemoveAura(torch);
            return;
        }

        if (!torch)
            torch = player->AddAura(SPELL_NIGHT_WATCHMANS_TORCH, player);

        if (torch && !torch->IsPermanent())
        {
            torch->SetMaxDuration(-1);
            torch->SetDuration(-1);
        }
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

    // Lighting it takes back an earlier "put away", and the carry update runs on the next tick
    // instead of up to a quarter of a second later.
    void HandleAfterCast()
    {
        Player* player = GetCaster()->ToPlayer();
        if (!player || !config.carry)
            return;

        player->UpdatePlayerSetting(SETTING_SOURCE, SETTING_PUT_AWAY, 0);
        GetCarryState(player)->timer = CARRY_UPDATE_INTERVAL;
    }

    void Register() override
    {
        OnCheckCast += SpellCheckCastFn(spell_forever_torch::CheckCast);
        AfterCast += SpellCastFn(spell_forever_torch::HandleAfterCast);
    }
};

class spell_forever_torch_aura : public AuraScript
{
    PrepareAuraScript(spell_forever_torch_aura);

    // Only the player's own right-click on the buff. Everything that puts the torch away for a
    // while (weapons, combat, water, cities) removes the aura in the default mode.
    void HandleRemove(AuraEffect const* /*aurEff*/, AuraEffectHandleModes /*mode*/)
    {
        if (!config.carry || GetTargetApplication()->GetRemoveMode() != AURA_REMOVE_BY_CANCEL)
            return;

        // only a carried torch: one lit by hand has its five minutes and is simply put out
        Player* player = GetTarget()->ToPlayer();
        if (!player || !GetAura()->IsPermanent())
            return;

        player->UpdatePlayerSetting(SETTING_SOURCE, SETTING_PUT_AWAY, 1);
        ChatHandler(player->GetSession()).SendSysMessage("You put your torch away. Type .torch on to carry it again.");
    }

    void Register() override
    {
        AfterEffectRemove += AuraEffectRemoveFn(spell_forever_torch_aura::HandleRemove, EFFECT_0, SPELL_AURA_DUMMY, AURA_EFFECT_HANDLE_REAL);
    }
};

class ForeverTorchPlayerScript : public PlayerScript
{
public:
    ForeverTorchPlayerScript() : PlayerScript("ForeverTorchPlayerScript",
        { PLAYERHOOK_ON_PLAYER_ENTER_COMBAT, PLAYERHOOK_ON_UPDATE_ZONE, PLAYERHOOK_ON_UPDATE }) { }

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

    void OnPlayerUpdate(Player* player, uint32 diff) override
    {
        if (!IsRealPlayer(player))
            return;

        CarryState* state = GetCarryState(player);
        state->timer += diff;
        if (state->timer < CARRY_UPDATE_INTERVAL)
            return;

        state->timer = 0;
        UpdateCarriedTorch(player);
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

class ForeverTorchCommandScript : public CommandScript
{
public:
    ForeverTorchCommandScript() : CommandScript("ForeverTorchCommandScript") { }

    ChatCommandTable GetCommands() const override
    {
        static ChatCommandTable commandTable =
        {
            { "torch", HandleTorchCommand, SEC_PLAYER, Console::No },
        };

        return commandTable;
    }

    // .torch, .torch on, .torch off: the same choice as right-clicking the buff and using the
    // item. Without a word it switches.
    static bool HandleTorchCommand(ChatHandler* handler, Optional<bool> carry)
    {
        Player* player = handler->GetPlayer();
        if (!config.enabled || !config.carry)
        {
            handler->SendSysMessage("Torches are not carried on this server.");
            return true;
        }

        bool putAway = carry ? !*carry : !player->GetPlayerSetting(SETTING_SOURCE, SETTING_PUT_AWAY).value;
        player->UpdatePlayerSetting(SETTING_SOURCE, SETTING_PUT_AWAY, putAway ? 1 : 0);
        GetCarryState(player)->timer = CARRY_UPDATE_INTERVAL;

        if (putAway)
            handler->SendSysMessage("You put your torch away. Type .torch on to carry it again.");
        else if (config.carryRequireItem && !player->HasItemCount(ITEM_NIGHT_WATCHMANS_TORCH, 1, false))
            handler->SendSysMessage("You have no torch in your bags. General goods vendors sell them.");
        else if (config.carryNightOnly)
            handler->SendSysMessage("You will carry a torch from dusk to dawn, whenever your weapons are sheathed.");
        else
            handler->SendSysMessage("You will carry a torch whenever your weapons are sheathed.");

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
        config.carry = sConfigMgr->GetOption<bool>("ForeverTorch.Carry.Enable", true);
        config.carryNightOnly = sConfigMgr->GetOption<bool>("ForeverTorch.Carry.NightOnly", true);
        config.carryRequireItem = sConfigMgr->GetOption<bool>("ForeverTorch.Carry.RequireItem", false);
        config.nightStart = sConfigMgr->GetOption<uint32>("ForeverTorch.Carry.NightStart", 19) % 24;
        config.nightEnd = sConfigMgr->GetOption<uint32>("ForeverTorch.Carry.NightEnd", 6) % 24;

        LOG_INFO("server.loading", "mod-forever-torch: {}, in capital cities: {}, in combat: {}, carried with weapons sheathed: {}{}",
            config.enabled ? "enabled" : "disabled", config.inCities ? "stays lit" : "goes out",
            config.inCombat ? "stays lit" : "goes out",
            !config.carry ? "no" : config.carryNightOnly ? "at night" : "yes",
            !config.carry ? "" : config.carryRequireItem ? " (with the item)" : " (everyone)");
    }
};

void AddForeverTorchScripts()
{
    RegisterSpellAndAuraScriptPair(spell_forever_torch, spell_forever_torch_aura);
    new ForeverTorchPlayerScript();
    new npc_forever_torch_watchman();
    new ForeverTorchCommandScript();
    new ForeverTorchWorldScript();
}
