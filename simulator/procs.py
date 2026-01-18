import random

# -------------------------
# Define all available on-hit procs
# -------------------------
ALL_PROCS = {
    "Crusader": {
        "chance": 0.8,       # 1 ppm chance per melee hit
        "str_buff": 110,      # +120 Strength
        "duration": 15.0
    },
    "Crusader_OH": {
        "chance": 0.8,       # 1 ppm chance per melee hit
        "str_buff": 110,      # +120 Strength
        "duration": 15.0
    },
    "Empyrian Demolisher": {
        "chance": 1.2,       # 4,8% chance per melee hit
        "haste_buff": 0.155,       # +155 haste
        "duration": 10.0
    },
        "Flurry Axe": {
        "chance": 3,   # 13% per main-hand hit
        "mh_extra_hit": True  # This triggers one extra MH swing
    },
    "Wound": {
        "chance": 1.5,           #1.5 ppm
        "ap_based": True,          # flag to scale with AP
        "ap_multiplier": 0.365,    # 36.5% of your total AP
        "base_damage": 22,          # Base damage
        "weapon_multiplier": 1.0   # optional: scale differently for MH/OH
    },
    "Rend Garg": {
        "chance": 2,          # 1 ppm
        "bleed": True,            # flag to handle in fight loop
        "duration": 30,         # optional, for reference
        "tick_interval": 3.0      # optional, for reference
    },    
    "icon": {
        "flat_chance": True,
        "chance": 0.1,          # 10% on hit
        "ap_buff": 35,
        "crit_buff": 0.025,      # 2.5% crit
        "duration": 12.0,
        "cooldown": 45.0,
    },
    # Add more procs here as needed 
    "HoJ": {
        "flat_chance": True,
        "chance": .02,   # 2% per main-hand hit
        "mh_extra_hit": True  # This triggers one extra MH swing
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
        # Cooldown check
        cd = proc.get("cooldown")
        if cd is not None:
            if cooldowns.get(name, 0) > time:
                continue

        # Per-hit chance
        if proc.get("flat_chance"):
            if random.random() < (proc["chance"]):
                triggered.append({"name": name, **proc})
        else:
            if random.random() < ((proc["chance"]*weapon_speed)/60):
                triggered.append({"name": name, **proc})

            if cd is not None:
                cooldowns[name] = time + cd

    return triggered





def apply_on_hit_procs(triggered_procs, time, onhit_buffs, total_ap=None):
    for proc in triggered_procs:
        if "str_buff" in proc:
            onhit_buffs.add_buff(proc["name"], "strength", proc["str_buff"], proc["duration"], time)
        if "ap_buff" in proc:
            onhit_buffs.add_buff(proc["name"], "ap", proc["ap_buff"], proc["duration"], time)
        if "haste_buff" in proc:
            onhit_buffs.add_buff(proc["name"], "haste", proc["haste_buff"], proc["duration"], time)
        if "crit_buff" in proc:
            onhit_buffs.add_buff(proc["name"], "crit", proc["crit_buff"], proc["duration"], time)
    return 
            
