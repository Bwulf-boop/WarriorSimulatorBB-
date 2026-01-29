import random

# -------------------------
# Define all available on-hit procs
# -------------------------
ALL_PROCS = {
    "Crusader": {
        "chance": 1,       # 1 ppm chance per melee hit
        "str_buff": 100,      # 
        "duration": 15.0,
        "ignore_if_active" :False
    },
    "Crusader_OH": {
        "chance": 1,      # 1 ppm chance per melee hit
        "str_buff": 100,     
        "duration": 15.0,
        "ignore_if_active": False
    },
    "Brutal_OH": {
        "chance": 0.9,       # 1 ppm chance per melee hit
        "str_buff": 110,     
        "duration": 15.0,
        "ignore_if_active": False
    },
    "Brutal": {
        "chance": 0.9,       # 0.9 ppm chance per melee hit
        "str_buff": 110,      
        "duration": 15.0,
        "ignore_if_active": False
    },
    "Empyrian Demolisher": {
        "chance": 1.2,       # 4,8% chance per melee hit
        "haste_buff": 0.155,       # +155 haste
        "duration": 10.0,
        "ignore_if_active": False
    },
        "Flurry Axe": {
        "chance": 3,   # 13% per main-hand hit
        "mh_extra_hit": True,
        "ignore_if_active": False  # This triggers one extra MH swing
    },
    "Wound": {
        "chance": 1.5,           #1.5 ppm
        "ap_based": True,          # flag to scale with AP
        "ap_multiplier": 0.36,    # 36.5% of your total AP
        "base_damage": 22,          # Base damage
        "weapon_multiplier": 1.0,
        "ignore_if_active": False   # optional: scale differently for MH/OH
    },
    "Rend Garg": {
        "chance": 1.5,          # 1 ppm
        "bleed": True,            # flag to handle in fight loop
        "duration": 30,         # optional, for reference
        "tick_interval": 3.0,
        "ignore_if_active" : False      # optional, for reference
    },    
    "icon": {
        "flat_chance": True,
        "chance": 0.1,          # 10% on hit
        "crit_buff": 0.025,      # 2.5% crit
        "ap_buff": 35,
        "duration": 12.0,
        "cooldown": 45.0,
        "ignore_if_active" : True
    },
    "HoJ": {
        "flat_chance": True,
        "chance": 0.02,   # 2% per main-hand hit
        "mh_extra_hit": True,
        "ignore_if_active" : False
            # This triggers one extra MH swing
        },
    "DB": {
        "chance": 1.5,           #1.5 ppm
        "magic_based": True,          # flag for magic dmg
        "ap_multiplier": 0.24,      # 0.24% of your total AP
        "base_damage": 154,          # Base damage
        "weapon_multiplier": 1.0,   # optional: scale differently for MH/OH
        "ignore_if_active": False   
    },
    "Maelstrom": {
        "chance": 1.5,           #1.5 ppm
        "magic_based": True,          # flag for magic dmg
        "ap_multiplier": 0.15,      # 0.15% of your total AP
        "base_damage": 250,          # Base damage
        "weapon_multiplier": 1.0,   # optional: scale differently for MH/OH
        "ignore_if_active": False   
        }
    }


# -------------------------
# On-hit proc resolver
# -------------------------
def resolve_on_hit_procs(time, weapon_speed, procs_to_check=None, cooldowns=None):
    if cooldowns is None:
        cooldowns = {}
    triggered = []

    procs = ALL_PROCS if procs_to_check is None else {
        k: ALL_PROCS[k] for k in procs_to_check if k in ALL_PROCS
    }

    for name, proc in procs.items():
        cd = proc.get("cooldown")

        # Only trigger if cooldown has passed
        if cd is not None and cooldowns.get(name, 0) > time:
            continue

        triggered_now = False
        if proc.get("flat_chance"):
            if random.random() < proc["chance"]:
                triggered_now = True
        else:
            if random.random() < (proc["chance"] * weapon_speed / 60):
                triggered_now = True

        if triggered_now:
            triggered.append({"name": name, **proc})
            if cd is not None:
                cooldowns[name] = time + cd


    return triggered





def apply_on_hit_procs(triggered_procs, time, onhit_buffs):
    for proc in triggered_procs:
        if "str_buff" in proc:
            onhit_buffs.add_buff(proc["name"], "strength", proc["str_buff"], proc["duration"], time, ignore_if_active=proc.get("ignore_if_active", False))
        if "ap_buff" in proc:
            onhit_buffs.add_buff(proc["name"], "ap", proc["ap_buff"], proc["duration"], time, ignore_if_active=proc.get("ignore_if_active", False))
        if "haste_buff" in proc:
            onhit_buffs.add_buff(proc["name"], "haste", proc["haste_buff"], proc["duration"], time, ignore_if_active=proc.get("ignore_if_active", False))
        if "crit_buff" in proc:
            buff_name = "icon crit" if proc["name"] == "icon" else proc["name"]
            onhit_buffs.add_buff(
                buff_name,          # Name of the buff
                "crit",             # Stat
                proc["crit_buff"],  # Amount
                proc["duration"],   # Duration
                time,               # Start time
                ignore_if_active=proc.get("ignore_if_active", False)
            )
