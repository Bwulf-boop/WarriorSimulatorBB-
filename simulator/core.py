import random
import multiprocessing as mp
from math import ceil
from queue import PriorityQueue
from simulator.procs import resolve_on_hit_procs, apply_on_hit_procs

# -------------------------
# Enrage tracker class
# -------------------------
class EnrageTracker:
    def __init__(self, duration=5.0):
        self.duration = duration
        self.active = False
        self.end_time = 0.0
        self.total_uptime = 0.0
        self.last_update_time = 0.0

    def update(self, current_time):
        if self.active:
            self.total_uptime += current_time - self.last_update_time
        self.last_update_time = current_time

        if self.active and current_time >= self.end_time:
            self.active = False

    def trigger(self, current_time):
        self.update(current_time)
        self.active = True
        self.end_time = current_time + self.duration

class RendBleed:
    def __init__(self, duration=30, tick_interval=3.0):
        self.duration = duration
        self.tick_interval = tick_interval
        self.end_time = 0.0
        self.tick_times = []         # times at which ticks will happen
        self.damage_per_tick = 0.0
        self.active = False
        self.total_damage = 0.0
        self.total_uptime = 0.0      
        self.last_update_time = 0.0  

    def trigger(self, current_time, total_ap, multi, trauma):
        """
        Start or refresh the bleed.
        Tick schedule does NOT reset — existing ticks stay in place.
        If no ticks exist yet, schedule them now.
        """
        num_ticks = int(self.duration / self.tick_interval)
        if trauma: total_proc_damage = (260 + 1.3 * total_ap) * multi * 1.3
        else: total_proc_damage = (260 + 1.3 * total_ap) * multi

        self.damage_per_tick = total_proc_damage / num_ticks

        # Refresh duration
        self.end_time = current_time + self.duration
        self.active = True

        # Schedule ticks only if first proc
        if not self.tick_times:
            self.tick_times = [current_time + i * self.tick_interval for i in range(1, num_ticks + 1)]

    def update(self, current_time):
            # Update uptime
        if self.active:
            self.total_uptime += current_time - self.last_update_time
        self.last_update_time = current_time
        """
        Apply damage for all ticks that have passed.
        """
        remaining_ticks = []
        for t in self.tick_times:
            if current_time >= t:
                self.total_damage += self.damage_per_tick
            else:
                remaining_ticks.append(t)
        self.tick_times = remaining_ticks

        # Deactivate if no future ticks
        if not self.tick_times:
            self.active = False
# -------------------------
# Blood Fury class
# ------------------------

class Bloodfury:
    def __init__(self, duration=15.0, ap_bonus=242, cooldown=120.0, onhit_buffs=None):
        self.duration = duration
        self.ap_bonus = ap_bonus
        self.cooldown = cooldown        # seconds
        self.active = False
        self.end_time = 0.0
        self.uptime = 0.0
        self.last_update_time = 0.0
        self.last_trigger_time = -float('inf')  # tracks when it was last triggered
        self.onhit_buffs = onhit_buffs

    def trigger(self, current_time):
        self.active = True
        self.end_time = current_time + self.duration
        self.last_trigger_time = current_time
        self.last_update_time = current_time

        if self.onhit_buffs is not None:
            self.onhit_buffs.add_buff(
                "Bloodfury",
                "ap",
                self.ap_bonus,
                self.duration,
                current_time,
                ignore_if_active=False   # allow refresh after cooldown
            )


    def update(self, current_time):
        if self.active:
            dt = current_time - self.last_update_time
            self.uptime += dt
            if current_time >= self.end_time:
                self.active = False
        self.last_update_time = current_time

    def get_bonus_ap(self):
        return self.ap_bonus if self.active else 0


# -------------------------
# Bloolust class
# -------------------------
class Bloodlust:
    def __init__(self, duration=40.0, haste_bonus=0.3, cooldown=600.0):
        self.duration = duration
        self.haste_bonus = haste_bonus
        self.active = False
        self.end_time = 0.0
        self.uptime = 0.0
        self.last_update_time = 0.0
        self.next_available = 0.0
        self.cooldown = cooldown

    def trigger(self, current_time):
        self.active = True
        self.end_time = current_time + self.duration
        self.last_update_time = current_time
        self.next_available = current_time + self.cooldown


    def update(self, current_time):
        if self.active:
            dt = current_time - self.last_update_time
            self.uptime += dt
            if current_time >= self.end_time:
                self.active = False
        self.last_update_time = current_time

    def get_bonus_haste(self):
        return self.haste_bonus if self.active else 0.0

# -------------------------
# Deathwish tracker class
# -------------------------        

class DeathWish:
    def __init__(self, duration=30.0, cooldown=120.0):
        self.duration = duration
        self.cooldown = cooldown
        self.active = False
        self.end_time = 0.0
        self.next_available = 0.0
        self.total_uptime = 0.0
        self.last_update_time = 0.0

    def update(self, current_time):
        if self.active:
            active_until = min(current_time, self.end_time)
            if active_until > self.last_update_time:
                self.total_uptime += active_until - self.last_update_time

            if current_time >= self.end_time:
                self.active = False

        self.last_update_time = current_time


    def can_cast(self, current_time):
        return current_time >= self.next_available

    def cast(self, current_time):
        self.update(current_time)
        self.active = True
        self.end_time = current_time + self.duration
        self.next_available = current_time + self.cooldown

# -------------------------
# Buff tracker for on-hit effects (Crusader, HoJ, etc.)
# -------------------------
class BuffTracker:
    def __init__(self):
        self.active_buffs = []
        self.uptime = {}  # Track total uptime per buff name
        self.last_update_time = 0.0

    def add_buff(self, name, stat, amount, duration, start_time, ignore_if_active=False):
        """
        Add a new buff or refresh an existing one.
        If ignore_if_active is True, do not refresh an existing buff.
        """
        self.update(start_time)  # update uptime before changing buffs

        for buff in self.active_buffs:
            if buff["name"] == name:
                if ignore_if_active:
                    return  # do not refresh
                buff["start_time"] = start_time
                buff["duration"] = duration
                buff["amount"] = amount
                return

        # Add new buff
        self.active_buffs.append({
            "name": name,
            "stat": stat,
            "amount": amount,
            "duration": duration,
            "start_time": start_time
        })

    def update(self, current_time):
        """
        Update active buffs, calculate uptime, and remove expired buffs.
        Returns a dict of total stats from active buffs.
        """
        dt = current_time - self.last_update_time

        for buff in self.active_buffs:
            active_time = min(current_time, buff["start_time"] + buff["duration"]) - max(self.last_update_time, buff["start_time"])
            if active_time > 0:
                self.uptime[buff["name"]] = self.uptime.get(buff["name"], 0) + active_time

        # Remove expired buffs
        self.active_buffs = [b for b in self.active_buffs if current_time < b["start_time"] + b["duration"]]

        self.last_update_time = current_time

        # Aggregate stats
        totals = {}
        for buff in self.active_buffs:
            totals[buff["stat"]] = totals.get(buff["stat"], 0) + buff["amount"]

        return totals

    def get_uptime(self, buff_name, fight_length):
        if fight_length <= 0:
                return 0.0
        """Return the uptime percentage of a buff over the fight."""
        return self.uptime.get(buff_name, 0.0) / fight_length



# -------------------------
# Deep Wounds tracker class
# -------------------------
class DeepWounds:
    def __init__(self, duration=6.0, percent=0.48):
        self.duration = duration      # DW lasts 6s
        self.percent = percent        # 48% of MH damage
        self.active_ticks = []        # list of (tick_time, damage_per_tick)
        self.total_damage = 0.0

    def trigger(self, current_time, weapon_dmg):
        """
        Trigger DW based on MH total damage including AP.
        48% of MH damage over duration, split into 3 ticks.
        """
        tick_damage = (self.percent * weapon_dmg) / 6   
        for i in range(1, 7):
            self.active_ticks.append((current_time + i * 1, tick_damage))  # ticks every 1

    def update(self, current_time):
        remaining_ticks = []
        for tick_time, dmg in self.active_ticks:
            if current_time >= tick_time:
                self.total_damage += dmg
            else:
                remaining_ticks.append((tick_time, dmg))
        self.active_ticks = remaining_ticks


# -------------------------
# HS-triggered OH damage buff: Ambidextrous
# -------------------------
class Ambidextrous:
    def __init__(self, duration=8.0, max_stacks=3, per_stack=0.05):
        self.duration = duration      # 8s per stack
        self.max_stacks = max_stacks
        self.per_stack = per_stack    # 5% OH damage per stack
        self.stacks = 0
        self.active = False
        self.end_times = []           # list of expiration times per stack
        self.total_uptime = 0.0
        self.last_update_time = 0.0

    def update(self, current_time):
        """
        Update uptime and remove expired stacks
        """
        if self.active:
            dt = current_time - self.last_update_time
            self.total_uptime += dt * self.stacks  # each active stack counts
        self.last_update_time = current_time

        # Remove expired stacks
        self.end_times = [et for et in self.end_times if et > current_time]
        self.stacks = len(self.end_times)
        self.active = self.stacks > 0

    def trigger(self, current_time):
        """
        Add a stack when HS hits, up to max_stacks
        """
        self.update(current_time)
        if self.stacks < self.max_stacks:
            self.end_times.append(current_time + self.duration)
            self.stacks += 1
            self.active = True

    def get_multiplier(self):
        """
        Return OH damage multiplier from this buff
        """
        return 1 + self.stacks * self.per_stack

# -------------------------
# Fight State & Event Handlers
# -------------------------

class FightState:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

        # Core simulation state
        self.time = 0.0
        self.event_id = 0
        self.queue = PriorityQueue()
        self.rage = self.Starting_rage

        # Damage tracking
        self.total_damage = 0.0
        self.proc_damage_count = 0.0
        self.white_MH_damage = 0.0
        self.white_OH_damage = 0.0
        self.hs_damage = 0.0
        self.WW_damage = 0.0
        self.BT_damage = 0.0
        self.DR_damage = 0.0
        self.slam_damage_MH = 0.0
        self.slam_damage_OH = 0.0
        self.total_ambi = 0.0

        # Cooldowns and state flags
        self.slam_lockout_until = 0.0
        self.HS_queue = 0
        self.WW_CD_UP = 0.0
        self.DR_CD_UP = 0.0
        self.BT_CD_UP = 0.0
        self.slam_proc = 0
        self.flurry_hits_remaining = 0
        self.last_event_time = 0.0

        # Base stats and multipliers
        self.base_crit = self.crit
        self.current_total_ap = self.total_ap
        self.base_multi = self.multi
        self.multi_oh = self.multi

        # Trackers and Buffs
        self.deep_wounds = DeepWounds()
        self.rend_bleed = RendBleed()
        self.enrage = EnrageTracker()
        self.onhit_buffs = BuffTracker()
        self.death_wish = DeathWish()
        self.bloodlust = Bloodlust()
        self.bloodfury = Bloodfury(onhit_buffs=self.onhit_buffs)
        self.ambidextrous = Ambidextrous()

        # Attack counts
        self.attack_counts = {k: 0 for k in ["MH", "OH", "HS", "SLAM_MH", "SLAM_OH", "WW", "BT", "DR"]}
        self.crit_counts = {k: 0 for k in ["MH_CRIT", "OH_CRIT", "HS_CRIT", "SLAM_MH_CRIT", "SLAM_OH_CRIT", "WW_CRIT", "BT_CRIT", "DR_CRIT"]}
        self.miss_counts = {k: 0 for k in ["MH_MISS", "OH_MISS", "HS_MISS", "SLAM_MH_MISS", "SLAM_OH_MISS", "WW_MISS", "BT_MISS", "DR_MISS"]}

        # Procs
        self.proc_cooldowns = {}
        if not hasattr(self, 'MH_procs') or self.MH_procs is None: self.MH_procs = ["Crusader"]
        if not hasattr(self, 'OH_procs') or self.OH_procs is None: self.OH_procs = ["Crusader_OH"]
        self.MH_PROCS = set(self.MH_procs)
        self.OH_PROCS = set(self.OH_procs)
        self.MH_EXTRA_PROCS = set(self.MH_procs) # For extra attacks
        self.sunder_procs = set(self.MH_procs) # For battering ram
        if self.icon:
            self.MH_PROCS.add("icon")
            self.OH_PROCS.add("icon")
            self.MH_EXTRA_PROCS.add("icon")
        if self.HoJ:
            self.MH_PROCS.add("HoJ")
            self.OH_PROCS.add("HoJ")
            self.MH_EXTRA_PROCS.add("HoJ")
        if self.maelstrom:
            self.MH_PROCS.add("Maelstrom")
            self.OH_PROCS.add("Maelstrom")
            self.MH_EXTRA_PROCS.add("Maelstrom")

        # Armor and enrage setup
        if not hasattr(self, 'mob_level'): self.mob_level = 63
        if not hasattr(self, 'armor'): self.armor = 4644
        if self.bashguuder: self.armor -= 668
        if self.sunders: self.armor *= 0.8
        if self.faeri: self.armor *= 0.95
        if not hasattr(self, 'armor_penetration'): self.armor_penetration = 0.0
        if self.battering_ram: self.armor_penetration += 0.025
        self.enrage_multi = 1.1 * 1.05 if self.outrage else 1.1

        # Uptime tracking
        self.flurry_time = 0.0

    def next_id(self):
        self.event_id += 1
        return self.event_id

def _handle_procs(triggered, state):
    dmg = 0.0
    for proc in triggered:
        if proc.get("Ironfoe"):
            state.queue.put((state.time, state.next_id(), "Extra_Attack", {"source_proc": proc.get("name")}))
            state.queue.put((state.time, state.next_id(), "Extra_Attack", {"source_proc": proc.get("name")}))

        if proc.get("mh_extra_hit"):
            state.queue.put((state.time, state.next_id(), "Extra_Attack", {"source_proc": proc.get("name")}))

        if proc.get("name") == "Rend Garg":
            state.rend_bleed.trigger(state.time, state.current_total_ap, state.multi, state.trauma)

        if proc.get("ap_based"):
            proc_dmg = proc.get("base_damage", 0) + state.current_total_ap * proc["ap_multiplier"] * proc.get("weapon_multiplier", 1.0)
            DR = _calc_dr(state.armor, state.armor_penetration, state.mob_level)
            proc_dmg *= (1 - DR)
            if random.random() < state.crit:
                state.deep_wounds.trigger(state.time, state.mh_base_avg)
                proc_dmg *= 2
            dmg += proc_dmg

        if proc.get("magic_based"):
            proc_dmg = proc.get("base_damage", 0) + state.current_total_ap * proc["ap_multiplier"] * proc.get("weapon_multiplier", 1.0)
            proc_dmg /= state.multi
            proc_dmg *= 1.2475
            if random.random() < state.crit:
                proc_dmg *= 1.5
            dmg += proc_dmg

    return dmg * state.multi


def _cast_death_wish(state):
    if state.death_wish.can_cast(state.time) and state.rage >= state.DW_COST:
        state.death_wish.cast(state.time)
        state.rage -= state.DW_COST
        return True
    return False

def _cast_instant_slam(state):
    if state.rage >= state.slam_COST and state.slam_proc >= 1:
        state.slam_proc = 0
        dmg, crit_flag, proc_flag = _resolve_slam(state.min_dmg, state.max_dmg, state.current_total_ap, state.crit, state.hit, state.armor, state.armor_penetration, state.mh_speed, False, state.mob_level, multi=state.multi)
        dmg *= state.undending_fury
        state.total_damage += dmg
        state.slam_damage_MH += dmg
        state.attack_counts["SLAM_MH"] += 1
        if crit_flag:
            state.crit_counts["SLAM_MH_CRIT"] += 1
            state.deep_wounds.trigger(state.time, state.mh_base_avg)
            state.flurry_hits_remaining = 3
        triggered = resolve_on_hit_procs(state.time, state.mh_speed, procs_to_check=state.MH_PROCS, cooldowns=state.proc_cooldowns)
        apply_on_hit_procs(triggered, state.time, state.onhit_buffs)
        proc_dmg = _handle_procs(triggered, state)
        state.proc_damage_count += proc_dmg
        state.total_damage += proc_dmg

        if state.battering_ram:
            triggered = resolve_on_hit_procs(state.time, state.mh_speed, procs_to_check=state.sunder_procs, cooldowns=state.proc_cooldowns)
            apply_on_hit_procs(triggered, state.time, state.onhit_buffs)
            proc_dmg = _handle_procs(triggered, state)
            state.proc_damage_count += proc_dmg
            state.total_damage += proc_dmg

        if dmg > 0 and state.skull_cracker:
            state.death_wish.next_available = max(state.time, state.death_wish.next_available - 4.0)

        if proc_flag:
            state.enrage.trigger(state.time)
            state.slam_proc = 1

        # Offhand
        if state.smf:
            state.proc_damage_count += proc_dmg
            state.total_damage += proc_dmg
            dmg, crit_flag, proc_flag = _resolve_slam(state.oh_min_dmg, state.oh_max_dmg, state.current_total_ap, state.crit, state.hit, state.armor, state.armor_penetration, state.oh_speed, True, state.mob_level, multi=state.multi_oh)
            dmg *= state.undending_fury
            state.total_damage += dmg
            state.slam_damage_OH += dmg
            state.attack_counts["SLAM_OH"] += 1
            if crit_flag:
                state.crit_counts["SLAM_OH_CRIT"] += 1
                state.deep_wounds.trigger(state.time, state.oh_base_avg)
                state.flurry_hits_remaining = 3
            triggered = resolve_on_hit_procs(state.time, state.oh_speed, procs_to_check=state.OH_PROCS, cooldowns=state.proc_cooldowns)
            apply_on_hit_procs(triggered, state.time, state.onhit_buffs)
            proc_dmg = _handle_procs(triggered, state)
            state.proc_damage_count += proc_dmg
            state.total_damage += proc_dmg
            if state.battering_ram:
                triggered = resolve_on_hit_procs(state.time, state.oh_speed, procs_to_check=state.sunder_procs, cooldowns=state.proc_cooldowns)
                apply_on_hit_procs(triggered, state.time, state.onhit_buffs)
                proc_dmg = _handle_procs(triggered, state)
    
            if proc_flag:
                state.enrage.trigger(state.time)
                state.slam_proc = 1
    
        state.rage -= state.slam_COST
        if state.rage < state.HS_COST:
            state.HS_queue = 0
        return True
    return False

def _cast_bt(state):
    if state.rage >= state.BT_COST and state.time >= state.BT_CD_UP:
        bt_base = state.current_total_ap * 0.5
        DR = _calc_dr(state.armor, state.armor_penetration, state.mob_level)
        dmg = bt_base * (1 - DR) * state.multi * state.undending_fury
        if random.random() < state.crit:
            dmg *= 2.2
            state.crit_counts["BT_CRIT"] += 1
            state.deep_wounds.trigger(state.time, state.mh_base_avg)
            state.flurry_hits_remaining = 3
        state.total_damage += dmg
        state.BT_damage += dmg
        state.attack_counts["BT"] += 1

        triggered = resolve_on_hit_procs(state.time, state.mh_speed, procs_to_check=state.MH_PROCS, cooldowns=state.proc_cooldowns)
        apply_on_hit_procs(triggered, state.time, state.onhit_buffs)
        proc_dmg = _handle_procs(triggered, state)
        state.proc_damage_count += proc_dmg
        state.total_damage += proc_dmg

        state.rage -= state.BT_COST
        if state.rage < state.HS_COST:
            state.HS_queue = 0
        state.BT_CD_UP = state.time + 6.0
        return True
    return False

def _cast_ww(state):
    if state.rage >= state.ww_COST and state.time >= state.WW_CD_UP:
        DR = _calc_dr(state.armor, state.armor_penetration, state.mob_level)
        
        norm_speed = 3.3 if getattr(state, "tg", False) else 2.4

        ww_base_mh = random.randint(int(state.min_dmg), int(state.max_dmg)) + state.current_total_ap / 14 * norm_speed
        ww_base_mh *= state.undending_fury * state.imp_ww
        dmg_mh = ww_base_mh * (1 - DR) * state.multi
        crit_flag_mh = random.random() < state.crit
        if crit_flag_mh:
            dmg_mh *= 2.2
            state.deep_wounds.trigger(state.time, state.mh_base_avg)
            state.flurry_hits_remaining = 3

        ww_base_oh = random.randint(int(state.oh_min_dmg), int(state.oh_max_dmg)) + state.current_total_ap / 14 * norm_speed
        ww_base_oh *= state.undending_fury * state.imp_ww
        dmg_oh = ww_base_oh * (1 - DR) * state.multi_oh
        crit_flag_oh = random.random() < state.crit
        if crit_flag_oh:
            dmg_oh *= 2
            state.deep_wounds.trigger(state.time, state.oh_base_avg)
            state.flurry_hits_remaining = 3

        total_ww_dmg = dmg_mh + dmg_oh
        state.total_damage += total_ww_dmg
        state.WW_damage += total_ww_dmg
        state.attack_counts["WW"] += 1
        if crit_flag_mh or crit_flag_oh: state.crit_counts["WW_CRIT"] += 1

        if random.random() < 0.2: state.slam_proc = 1
        if random.random() < 0.2: state.slam_proc = 1

        triggered = resolve_on_hit_procs(state.time, state.mh_speed, procs_to_check=state.MH_PROCS, cooldowns=state.proc_cooldowns)
        apply_on_hit_procs(triggered, state.time, state.onhit_buffs)
        proc_dmg = _handle_procs(triggered, state)
        state.proc_damage_count += proc_dmg
        state.total_damage += proc_dmg

        state.rage -= state.ww_COST
        if state.rage < state.HS_COST:
            state.HS_queue = 0
        
        ww_cd = 6.0 if getattr(state, "dragon_roar", False) else 8.0
        state.WW_CD_UP = state.time + ww_cd

        if getattr(state, "dragon_warrior", False):
            state.DR_CD_UP = max(state.time, state.DR_CD_UP - 5.0)
        return True
    return False

def _cast_dragon_roar(state):
    if not getattr(state, "dragon_roar", False): return False
    if state.time >= state.DR_CD_UP:
        # Damage: 0.84 * AP
        base_dmg = state.current_total_ap * 0.84
        DR = _calc_dr(state.armor, state.armor_penetration, state.mob_level)
        dmg = base_dmg * (1 - DR) * state.multi
        
        if random.random() < state.crit:
            dmg *= 2.2
            state.crit_counts["DR_CRIT"] += 1
            state.deep_wounds.trigger(state.time, state.mh_base_avg)
            state.flurry_hits_remaining = 3
            
        state.total_damage += dmg
        state.DR_damage += dmg
        state.attack_counts["DR"] += 1
        
        # Resets the cooldown for WW
        state.WW_CD_UP = 0.0
        
        # 30s Cooldown
        state.DR_CD_UP = state.time + 30.0

        if getattr(state, "dragon_warrior", False) and not state.death_wish.active:
            state.death_wish.active = True
            state.death_wish.end_time = state.time + 5.0
            state.death_wish.last_update_time = state.time

        return True
    return False

def _cast_hard_slam(state):
    if state.rage >= state.slam_COST:
        slam_cast_time = 1.5
        state.slam_lockout_until = state.time + slam_cast_time
        
        dmg, crit_flag, proc_flag = _resolve_slam(state.min_dmg, state.max_dmg, state.current_total_ap, state.crit, state.hit, state.armor, state.armor_penetration, state.mh_speed, False, state.mob_level, multi=state.multi)
        dmg *= state.undending_fury
        state.total_damage += dmg
        state.slam_damage_MH += dmg
        state.attack_counts["SLAM_MH"] += 1
        
        if dmg > 0:
            if crit_flag:
                state.crit_counts["SLAM_MH_CRIT"] += 1
                state.deep_wounds.trigger(state.time, state.mh_base_avg)
                state.flurry_hits_remaining = 3
            triggered = resolve_on_hit_procs(state.time, state.mh_speed, procs_to_check=state.MH_PROCS, cooldowns=state.proc_cooldowns)
            apply_on_hit_procs(triggered, state.time, state.onhit_buffs)
            proc_dmg = _handle_procs(triggered, state)
            state.proc_damage_count += proc_dmg
            state.total_damage += proc_dmg

            if state.battering_ram:
                triggered = resolve_on_hit_procs(state.time, state.mh_speed, procs_to_check=state.sunder_procs, cooldowns=state.proc_cooldowns)
                apply_on_hit_procs(triggered, state.time, state.onhit_buffs)
                proc_dmg = _handle_procs(triggered, state)
                state.proc_damage_count += proc_dmg
                state.total_damage += proc_dmg

            if state.skull_cracker:
                state.death_wish.next_available = max(state.time, state.death_wish.next_available - 4.0)
        
        if proc_flag:
            state.enrage.trigger(state.time)
            state.slam_proc = 1
        if state.smf:
            dmg, crit_flag, proc_flag = _resolve_slam(state.oh_min_dmg, state.oh_max_dmg, state.current_total_ap, state.crit, state.hit, state.armor, state.armor_penetration, state.oh_speed, True, state.mob_level, multi=state.multi_oh)
            dmg *= state.undending_fury
            state.total_damage += dmg
            state.slam_damage_OH += dmg
            state.attack_counts["SLAM_OH"] += 1

            if dmg > 0:
                if crit_flag:
                    state.crit_counts["SLAM_OH_CRIT"] += 1
                    state.deep_wounds.trigger(state.time, state.oh_base_avg)
                    state.flurry_hits_remaining = 3
            triggered = resolve_on_hit_procs(state.time, state.oh_speed, procs_to_check=state.OH_PROCS, cooldowns=state.proc_cooldowns)
            apply_on_hit_procs(triggered, state.time, state.onhit_buffs)
            proc_dmg = _handle_procs(triggered, state)
            state.proc_damage_count += proc_dmg
            state.total_damage += proc_dmg

            if state.battering_ram:
                triggered = resolve_on_hit_procs(state.time, state.oh_speed, procs_to_check=state.sunder_procs, cooldowns=state.proc_cooldowns)
                apply_on_hit_procs(triggered, state.time, state.onhit_buffs)
                proc_dmg = _handle_procs(triggered, state)
                state.proc_damage_count += proc_dmg
                state.total_damage += proc_dmg

        state.rage -= state.slam_COST
        if state.rage < state.HS_COST:
            state.HS_queue = 0
        return True
    return False

GCD_ACTIONS = {
    "DW": _cast_death_wish,
    "SLAM_PROC": _cast_instant_slam,
    "BT": _cast_bt,
    "WW": _cast_ww,
    "SLAM_HARD": _cast_hard_slam,
    "DR": _cast_dragon_roar,
}

def _handle_gcd(state, payload):
    used_gcd = False
    for ability_name in state.ability_priority:
        action = GCD_ACTIONS.get(ability_name)
        if action and action(state):
            used_gcd = True
            break

    next_time = state.time + (state.gcd + state.gcd_delay if used_gcd else 0.02)
    if next_time <= state.fight_length:
        state.queue.put((next_time, state.next_id(), "GCD", False))

def _handle_mh_swing(state, payload):
    swing_speed = state.mh_speed / state.current_haste

    if state.flurry_hits_remaining > 0:
        state.flurry_hits_remaining -= 1
    
    if state.time < state.slam_lockout_until:
        state.queue.put((state.slam_lockout_until, state.next_id(), "MH_SWING", False))
        return

    if state.HS_queue == 1 and state.rage >= state.HS_COST:
        state.HS_queue = 0 # Consume the queue
        hs_base = random.randint(int(state.min_dmg), int(state.max_dmg)) + 201 + state.current_total_ap / 14 * state.mh_speed
        
        triggered = resolve_on_hit_procs(state.time, state.mh_speed, procs_to_check=state.MH_PROCS, cooldowns=state.proc_cooldowns)
        apply_on_hit_procs(triggered, state.time, state.onhit_buffs)
        proc_dmg = _handle_procs(triggered, state)
        state.proc_damage_count += proc_dmg
        state.total_damage += proc_dmg

        DR = _calc_dr(state.armor, state.armor_penetration, state.mob_level)
        hs_dmg_val = hs_base * (1 - DR)
        
        hs_crit = random.random() < (state.crit + 0.15)
        if hs_crit:
            hs_dmg_val *= 2.2
            state.deep_wounds.trigger(state.time, state.mh_base_avg)
            state.rage += 10
            if state.rage > 100: state.rage = 100
            state.flurry_hits_remaining = 3
        
        hs_dmg_val *= state.multi
        state.hs_damage += hs_dmg_val
        state.total_damage += hs_dmg_val
        state.rage -= state.HS_COST
        if random.random() < 0.2: state.slam_proc = 1
        if state.rage < state.HS_COST:
            state.HS_queue = 0
        
        state.attack_counts["HS"] += 1
        if hs_crit: state.crit_counts["HS_CRIT"] += 1

        if state.ambi_ME:
            ambi_dmg = random.randint(int(state.oh_min_dmg), int(state.oh_max_dmg)) + (state.current_total_ap / 14 * state.oh_speed)
            ambi_dmg *= state.multi_oh * 0.6
            ambi_dmg *= (1 - DR)
            ambi_crit = random.random() < state.crit
            if ambi_crit:
                ambi_dmg *= 2
                state.deep_wounds.trigger(state.time, state.oh_base_avg)
                state.flurry_hits_remaining = 3
            
            triggered = resolve_on_hit_procs(state.time, state.oh_speed, procs_to_check=state.OH_PROCS, cooldowns=state.proc_cooldowns)
            apply_on_hit_procs(triggered, state.time, state.onhit_buffs)
            proc_dmg = _handle_procs(triggered, state)
            state.proc_damage_count += proc_dmg
            state.total_damage += proc_dmg
            
            state.total_damage += ambi_dmg
            state.total_ambi += ambi_dmg
            state.ambidextrous.trigger(state.time)

        next_time = state.time + swing_speed
        if next_time <= state.fight_length:
            state.queue.put((next_time, state.next_id(), "MH_SWING", False))
    else:
        # If we intended to HS but couldn't, unqueue
        if state.HS_queue == 1:
            state.HS_queue = 0
        dmg, was_crit, was_miss = _resolve_swing(state.min_dmg, state.max_dmg, state.current_total_ap, state.crit, state.hit, state.dual_wield, state.armor, state.armor_penetration, 0, state.mh_speed, state.mob_level, multi=state.multi)
        state.total_damage += dmg
        state.white_MH_damage += dmg
        state.attack_counts["MH"] += 1
        
        if was_crit:
            state.crit_counts["MH_CRIT"] += 1
            state.flurry_hits_remaining = 3
            state.deep_wounds.trigger(state.time, state.mh_base_avg)
        
        if was_miss:
            state.miss_counts["MH_MISS"] += 1
        else:
            triggered = resolve_on_hit_procs(state.time, state.mh_speed, procs_to_check=state.MH_PROCS, cooldowns=state.proc_cooldowns)
            apply_on_hit_procs(triggered, state.time, state.onhit_buffs)
            proc_dmg = _handle_procs(triggered, state)
            state.proc_damage_count += proc_dmg
            state.total_damage += proc_dmg

        state.rage += _generate_rage_classic(dmg, state.mh_speed, offhand=False, is_crit=was_crit)
        if state.rage > 100.0: state.rage = 100.0

        # After generating rage, check if we can queue HS
        if state.rage >= state.HS_COST:
            state.HS_queue = 1
        
        next_time = state.time + swing_speed
        if next_time <= state.fight_length:
            state.queue.put((next_time, state.next_id(), "MH_SWING", False))

def _handle_oh_swing(state, payload):
    if not state.dual_wield:
        return

    swing_speed = state.oh_speed / state.current_haste

    if state.flurry_hits_remaining > 0:
        state.flurry_hits_remaining -= 1
    
    if state.time < state.slam_lockout_until:
        state.queue.put((state.slam_lockout_until, state.next_id(), "OH_SWING", False))
        return

    dmg, was_crit, was_miss = _resolve_swing(state.oh_min_dmg, state.oh_max_dmg, state.current_total_ap, state.crit, state.hit, state.dual_wield, state.armor, state.armor_penetration, state.HS_queue, state.oh_speed, state.mob_level, multi=state.multi_oh)

    state.total_damage += dmg
    state.white_OH_damage += dmg
    state.attack_counts["OH"] += 1

    if was_crit:
        state.crit_counts["OH_CRIT"] += 1
        state.deep_wounds.trigger(state.time, state.oh_base_avg)
        state.flurry_hits_remaining = 3
    
    if was_miss:
        state.miss_counts["OH_MISS"] += 1
    else:
        triggered = resolve_on_hit_procs(state.time, state.oh_speed, procs_to_check=state.OH_PROCS, cooldowns=state.proc_cooldowns)
        apply_on_hit_procs(triggered, state.time, state.onhit_buffs)
        proc_dmg = _handle_procs(triggered, state)
        state.proc_damage_count += proc_dmg
        state.total_damage += proc_dmg

    state.rage += _generate_rage_classic(dmg, state.oh_speed, offhand=True, is_crit=was_crit)
    if state.rage > 100.0: state.rage = 100.0

    # After generating rage, check if we can queue HS
    if state.rage >= state.HS_COST:
        state.HS_queue = 1
    next_time = state.time + swing_speed
    if next_time <= state.fight_length:
        state.queue.put((next_time, state.next_id(), "OH_SWING", False))

def _handle_extra_attack(state, payload):
    if state.flurry_hits_remaining > 0:
        state.flurry_hits_remaining -= 1
    
    dmg, was_crit, was_miss = _resolve_swing(state.min_dmg, state.max_dmg, state.current_total_ap, state.crit, state.hit, state.dual_wield, state.armor, state.armor_penetration, state.HS_queue, state.mh_speed, state.mob_level, multi=state.multi)
    
    state.total_damage += dmg
    state.white_MH_damage += dmg
    state.attack_counts["MH"] += 1

    if was_crit:
        state.crit_counts["MH_CRIT"] += 1
        state.flurry_hits_remaining = 3
        state.deep_wounds.trigger(state.time, state.mh_base_avg)

    if was_miss:
        state.miss_counts["MH_MISS"] += 1
    else:
        procs = state.MH_EXTRA_PROCS.copy()
        source_proc = payload.get("source_proc")
        if source_proc:
            procs.discard(source_proc)
        
        triggered = resolve_on_hit_procs(state.time, state.mh_speed, procs_to_check=procs, cooldowns=state.proc_cooldowns)
        apply_on_hit_procs(triggered, state.time, state.onhit_buffs)
        proc_dmg = _handle_procs(triggered, state)
        state.total_damage += proc_dmg
        state.proc_damage_count += proc_dmg

    state.rage += _generate_rage_classic(dmg, state.mh_speed, offhand=False, is_crit=was_crit)
    if state.rage > 100.0: state.rage = 100.0

    # After generating rage, check if we can queue HS
    if state.rage >= state.HS_COST:
        state.HS_queue = 1

def _handle_tank_dummy(state, payload):
    state.rage += 60
    if state.rage > 100: state.rage = 100
    next_time = state.time + 1.5
    if state.rage >= state.HS_COST:
        state.HS_queue = 1
    if next_time <= state.fight_length:
        state.queue.put((next_time, state.next_id(), "Tank_dummy", False))


# -------------------------
# Single fight simulation
# -------------------------
def _run_single_fight(**kwargs):
    state = FightState(**kwargs)

    # Schedule first events
    state.queue.put((0, state.next_id(), "MH_SWING", False))
    state.queue.put((0.1, state.next_id(), "GCD", False))
    if state.tank_dummy:
        state.queue.put((0.05, state.next_id(), "Tank_dummy", False))

    if state.dual_wield:
        state.queue.put((0.18, state.next_id(), "OH_SWING", False))
    
    event_handlers = {
        "MH_SWING": _handle_mh_swing,
        "OH_SWING": _handle_oh_swing,
        "Extra_Attack": _handle_extra_attack,
        "GCD": _handle_gcd,
        "Tank_dummy": _handle_tank_dummy,
    }

    while not state.queue.empty():
        time, _, event, payload = state.queue.get()

        if time > state.fight_length:
            break

        state.time = time

        # --- Universal Updates ---
        active_mods = state.onhit_buffs.update(time)

        # Update flurry,enrage, dw , ambi uptime
        delta = time - state.last_event_time
        if state.flurry_hits_remaining > 0:
            state.flurry_time += delta
        state.enrage.update(time)
        state.ambidextrous.update(time)
        state.death_wish.update(time)
        state.last_event_time = time

        # Apply deep wounds and dots damage
        state.deep_wounds.update(time)
        state.rend_bleed.update(time)

        #Bloodlust
        if time >= state.bloodlust_time and time >= state.bloodlust.next_available:
            state.bloodlust.trigger(time)
        state.bloodlust.update(time)

        # Bloodfury activation
        if time >= state.bloodfury_time and not state.bloodfury.active and (time - state.bloodfury.last_trigger_time >= state.bloodfury.cooldown):
            state.bloodfury.trigger(time)
        # Update its state every event
        state.bloodfury.update(time)


       # STR -> AP convertion with buffs before event
        state.crit = state.base_crit
        state.crit += active_mods.get("crit", 0.0)
        
        current_strength = state.strength
        if state.kings and state.str_earth:
            current_strength = (state.strength + 88) * 1.1
            state.crit += ((state.agility + 88) * 1.1 / 20 / 100)
        elif state.kings:
            current_strength = state.strength * 1.1
            state.crit += (state.agility / 20 / 100)
        elif state.str_earth:
            current_strength = state.strength + 88 * 1.2
            state.crit += ((state.agility + 88) / 20 / 100)
        else:
            state.crit += (state.agility / 20 / 100)

        current_strength += active_mods.get("strength", 0)
        state.current_total_ap = state.total_ap + current_strength * 2 + active_mods.get("ap", 0)

        if state.bloodfury.active:
             state.current_total_ap += state.bloodfury.get_bonus_ap()
        if state.shamanistic_rage: state.current_total_ap *= 1.1

        #Calc haste before event
        proced_haste = state.haste + active_mods.get("haste", 0)
        state.current_haste = (state.FLURRY_MULT if state.flurry_hits_remaining > 0 else 1.0) * proced_haste * state.wf
        state.current_haste *= (1 + state.bloodlust.get_bonus_haste())

        # Mh base dmg each start for wounds calc
        state.mh_base_avg = ((state.min_dmg + state.max_dmg)/2 + state.current_total_ap / 14 * state.mh_speed) * state.multi / state.PVE_PWR
        if state.trauma: state.mh_base_avg *= 1.3
        state.oh_base_avg = ((state.oh_min_dmg + state.oh_max_dmg)/2 + state.current_total_ap / 14 * state.oh_speed) * state.multi_oh / state.PVE_PWR
        if state.trauma: state.oh_base_avg *= 1.3

        # -------------------------
        # Set Damage Multi on each event
        # -------------------------
        state.multi = state.base_multi
        if state.enrage.active:
            state.multi *= state.enrage_multi
        if state.death_wish.active:
            state.multi *= 1.20
        state.multi *= state.PVE_PWR
        state.multi *= state.SMF
        if getattr(state, "tg", False):
            state.multi *= 0.9
        state.multi *= getattr(state, "hunting_pack", 1.0)
        state.multi_oh = state.multi
        state.multi_oh *= 0.5 * state.impwield * state.ambidextrous.get_multiplier()
    

        handler = event_handlers.get(event)
        if handler:
            handler(state, payload)


    # -------------------------
    # Final averages
    # -------------------------
    state.onhit_buffs.update(state.fight_length)
    avg_MH_dmg = state.white_MH_damage / max(state.attack_counts["MH"], 1)
    avg_OH_dmg = state.white_OH_damage / max(state.attack_counts["OH"], 1)

    # -------------------------
    # Last update for all buffs 
    # -------------------------

    # Track On hit buff uptime
    crusader_uptime = state.onhit_buffs.get_uptime("Crusader", state.fight_length) + state.onhit_buffs.get_uptime("Brutal", state.fight_length)
    crusader_oh_uptime = state.onhit_buffs.get_uptime("Crusader_OH", state.fight_length) + state.onhit_buffs.get_uptime("Brutal_OH", state.fight_length)
    Empyrian_Demolisher_uptime = state.onhit_buffs.get_uptime("Empyrian Demolisher", state.fight_length)

    return {
        "slam_MH_dps": state.slam_damage_MH / state.fight_length,
        "slam_OH_dps": state.slam_damage_OH / state.fight_length,
        "white_MH_dps": state.white_MH_damage / state.fight_length,
        "white_OH_dps": state.white_OH_damage / state.fight_length,
        "avg_MH_dmg": avg_MH_dmg,
        "avg_OH_dmg": avg_OH_dmg,
        "hs_dps": state.hs_damage / state.fight_length,
        "WW_dps": state.WW_damage / state.fight_length,
        "BT_dps": state.BT_damage / state.fight_length,
        "DR_dps": state.DR_damage / state.fight_length,
        "Ambi_dps": state.total_ambi / state.fight_length,
        "all_attack_counts": [
            {
                atk: {
                    "hits": state.attack_counts[atk],
                    "crits": state.crit_counts[f"{atk}_CRIT"],
                    "misses": state.miss_counts[f"{atk}_MISS"]
                }
                for atk in state.attack_counts
            }
        ],
        "flurry_uptime": state.flurry_time / state.fight_length,
        "enrage_uptime": state.enrage.total_uptime / state.fight_length,
        "total_dps": (state.total_damage + state.deep_wounds.total_damage + state.rend_bleed.total_damage) / state.fight_length,
        "deep_wounds_dps": state.deep_wounds.total_damage / state.fight_length,
        "crusader_uptime": crusader_uptime,
        "crusader_oh_uptime": crusader_oh_uptime,
        "Empyrian_Demolisher_uptime": Empyrian_Demolisher_uptime,
        "death_wish_uptime": state.death_wish.total_uptime / state.fight_length,
        "Rend_dps": state.rend_bleed.total_damage / state.fight_length,
        "Proc_dmg_dps": state.proc_damage_count / state.fight_length,
    }


# -------------------------
# Swing, Slam resolution
# -------------------------
def _resolve_swing(min_dmg, max_dmg, current_total_ap, crit, hit, dual_wield, armor, armor_penetration,
                   HS_queue, base_speed, mob_level, multi=1.0, forced_crit=None):
    roll = random.random()
    if HS_queue ==1: hit+=0.19
    if dual_wield:dual_wield_penalty=0.19
    else:
        dual_wield_penalty=0
    MISS = max(0.08+dual_wield_penalty - hit, 0)
    GLANCE = 0.25
    base_damage = random.randint(int(min_dmg), int(max_dmg)) + current_total_ap  / 14 * base_speed
    DR = _calc_dr(armor, armor_penetration, mob_level)

    if forced_crit is not None:
        was_crit = 1 if forced_crit else 0
        dmg = base_damage * (2 if was_crit else 1) * (1 - DR)
        was_miss = 0
    else:
        if roll < MISS:
            dmg = 0.0
            was_crit = 0
            was_miss = 1
        elif roll < MISS + GLANCE:
            dmg = base_damage * 0.75 * (1 - DR)
            was_crit = 0
            was_miss = 0
        elif roll < MISS + GLANCE + crit:
            dmg = base_damage * 2 * (1 - DR)
            was_crit = 1
            was_miss = 0
        else:
            dmg = base_damage * (1 - DR)
            was_crit = 0
            was_miss = 0

    dmg *= multi
    return dmg, was_crit, was_miss

def _resolve_slam(min_dmg, max_dmg, current_total_ap, crit, hit, armor, armor_penetration, base_speed,oh=False,
                  mob_level=63, multi=1.0, forced_crit=None, was_miss=0):
    """
    Resolves a slam, returns (damage, crit_flag, proc_flag)
    """
    roll = random.random()
    MISS = max(0.08 - hit, 0)
    is_crit = forced_crit if forced_crit is not None else (roll < crit)
    if oh:
        base_damage = random.randint(int(min_dmg), int(max_dmg)) + 78 + current_total_ap / 14 * base_speed
    else:
        base_damage = random.randint(int(min_dmg), int(max_dmg)) + 87 + current_total_ap / 14 * base_speed

    DR = _calc_dr(armor, armor_penetration, mob_level)
    # Slam proc: 50% chance per slam
    proc_flag = random.random() < 0.5

    if roll < MISS:
        dmg = 0.0
        is_crit = 0
    elif  forced_crit is not None or roll < crit + MISS:
    # On a hit, roll for crit
        dmg = base_damage * 2.2 * (1 - DR)
        is_crit= 1
    else:
        dmg = base_damage * (1 - DR)

    dmg *= multi
    return dmg, is_crit, proc_flag


def _calc_dr(armor, armor_penetration, mob_level):
    DR = armor / (armor + 5882.5)
    DR = min(DR, 0.75)
    return DR * (1 - min(armor_penetration, 1.0))

def _generate_rage_classic(damage, weapon_speed, offhand=False, is_crit=False):
    c = 230.6
    f = 6 if offhand and is_crit else 3 if offhand else 14 if is_crit else 7
    rage = (15 * damage) / (4 * c) + (f * weapon_speed) / 2
    max_rage = (15 * damage) / c
    if damage == 0:
        return 0.0
    #weapon = "OH" if offhand else "MH"
    #crit_str = "CRIT" if is_crit else "hit"
    #(f"print{weapon} {crit_str}: dmg={damage:.1f}, generated_rage={rage:.2f}")
    return min(rage, max_rage)


# -------------------------
# Handle on hit procs
# ------------------------
def trigger_extra_mh_swing(queue, time, next_id):
    queue.put((time, next_id(), "MH_SWING", True))


# -------------------------
# Worker function
# ------------------------
def _worker(args):
    iterations_chunk, seed, kwargs = args
    random.seed(seed)

    results_total = []
    results_white_MH = []
    results_white_OH = []
    results_slam_MH = []
    results_slam_OH = []
    results_BT = []
    results_WW = []
    results_DR = []
    results_hs = []
    results_ambi = []
    result_proc_dmg = []
    results_avg_MH_dmg = []
    results_avg_OH_dmg = []
    results_deep_wounds_dps = []
    results_rend = []
    flurry_uptime_total = 0.0
    enrage_uptime_total = 0.0
    crusader_uptime_total = 0.0
    crusader_oh_uptime_total = 0.0
    Empyrian_Demolisher_uptime_total = 0.0
    death_wish_uptime_total = 0.0
    all_attack_counts = []

    for _ in range(iterations_chunk):
        fight = _run_single_fight(**kwargs)

        results_total.append(fight["total_dps"])
        results_white_MH.append(fight["white_MH_dps"])
        results_white_OH.append(fight["white_OH_dps"])
        results_slam_MH.append(fight["slam_MH_dps"])
        results_slam_OH.append(fight["slam_OH_dps"])
        results_BT.append(fight["BT_dps"])
        results_WW.append(fight["WW_dps"])
        results_DR.append(fight["DR_dps"])
        results_hs.append(fight["hs_dps"])
        results_ambi.append(fight["Ambi_dps"])
        result_proc_dmg.append(fight["Proc_dmg_dps"])
        results_avg_MH_dmg.append(fight["avg_MH_dmg"])
        results_avg_OH_dmg.append(fight["avg_OH_dmg"])
        results_deep_wounds_dps.append(fight["deep_wounds_dps"])
        results_rend.append(fight["Rend_dps"])

        flurry_uptime_total += fight["flurry_uptime"]
        enrage_uptime_total += fight["enrage_uptime"]
        crusader_uptime_total += fight["crusader_uptime"]
        crusader_oh_uptime_total += fight["crusader_oh_uptime"]
        Empyrian_Demolisher_uptime_total += fight["Empyrian_Demolisher_uptime"]
        death_wish_uptime_total += fight["death_wish_uptime"]
        all_attack_counts.append(fight["all_attack_counts"][0])

    return {
        "results_total": results_total,
        "results_white_MH": results_white_MH,
        "results_white_OH": results_white_OH,
        "results_slam_MH": results_slam_MH,
        "results_slam_OH": results_slam_OH,
        "results_BT": results_BT,
        "results_WW": results_WW,
        "results_DR": results_DR,
        "results_hs": results_hs,
        "results_ambi": results_ambi,
        "result_proc_dmg": result_proc_dmg,
        "results_avg_MH_dmg": results_avg_MH_dmg,
        "results_avg_OH_dmg": results_avg_OH_dmg,
        "results_deep_wounds_dps": results_deep_wounds_dps,
        "results_rend": results_rend,
        "flurry_uptime_total": flurry_uptime_total,
        "enrage_uptime_total": enrage_uptime_total,
        "crusader_uptime_total": crusader_uptime_total,
        "crusader_oh_uptime_total": crusader_oh_uptime_total,
        "Empyrian_Demolisher_uptime_total": Empyrian_Demolisher_uptime_total,
        "death_wish_uptime_total": death_wish_uptime_total,
        "all_attack_counts": all_attack_counts,
        "iterations_chunk": iterations_chunk
    }

# -------------------------
# Multiprocess-ready run_simulation
# -------------------------
def run_simulation(iterations=1000, mh_speed=2.6, oh_speed=2.7,
                   fight_length=60.0, stats=None, ability_priority=None,
                   dual_wield=True, battering_ram=True, ambi_ME=True, skull_cracker=True, tank_dummy=False,
                   kings=False, str_earth=False, shamanistic_rage=False, outrage=False,
                   bashguuder=False, faeri=False, sunders=False, icon=False, trauma=False, HoJ=False, maelstrom=False,
                   multi=1.0, BT_COST=30.0, slam_COST=15.0, ww_COST=25.0, HS_COST=15.0, smf=False, tg=False,
                   hunting_pack=False, retri_crit=False, starting_rage=50.0, dragon_roar=False,
                   dragon_warrior=False):

    if stats is None:
        stats = {}
    
    # Default ability priority if not provided
    if ability_priority is None:
        ability_priority = ["DW", "DR", "SLAM_PROC", "BT", "WW", "SLAM_HARD"]

    # Deconstruct character sheet stats to get base values for simulation
    strength = stats.get("strength", 0)
    agility = stats.get("Agility", 121)
    attack_power = stats.get("attack_power", 2800)
    crit = stats.get("crit", 31)/100 - 0.048
    crit -=agility/20/100
    hit = stats.get("hit", 8)/100
    your_armor = stats.get("Your_Armor", 4000)

    ap_from_armor = your_armor / 102 * 3
    base_ap = 60 * 3 - 20  # Lvl 60 warrior base AP

    # Handle extra stats from consumables/buffs entered in GUI
    extra_str = stats.get("Add_Str", 0)
    extra_agi = stats.get("Add_Agi", 0)
    extra_ap = stats.get("Add_AP", 0)
    extra_crit = stats.get("Add_Crit", 0) / 100

    # Calculate the portion of AP that does NOT come from strength
    gear_ap = attack_power - base_ap - (strength * 2) - ap_from_armor
    total_ap_base = gear_ap + ap_from_armor + base_ap + extra_ap

    # Calculate total base stats before fight simulation
    strength_total = strength + extra_str * 1.2  # Assuming 1.2x is for a talent/buff
    agility_total = agility + extra_agi
    crit_total = crit + extra_crit
    if retri_crit:
        crit_total += 0.03

    # Prepare fight arguments
    fight_kwargs = {
        "mh_speed": mh_speed,
        "oh_speed": oh_speed,
        "total_ap": total_ap_base,
        "strength": strength_total,
        "agility": agility_total,
        "crit": crit_total,
        "hit": hit,
        "min_dmg": stats.get("min_dmg", 96),
        "max_dmg": stats.get("max_dmg", 152),
        "oh_min_dmg": stats.get("oh_min_dmg", 100),
        "oh_max_dmg": stats.get("oh_max_dmg", 157),
        "armor": stats.get("boss_armor", 4644),
        "armor_penetration": stats.get("armor_penetration", 10)/5/100,
        "haste": 1 + stats.get("haste", 0)/1000,
        "wf": 1 + stats.get("wf", 0)/1000,
        "dual_wield": dual_wield,
        "battering_ram": battering_ram,
        "ambi_ME": ambi_ME,
        "skull_cracker": skull_cracker,
        "fight_length": fight_length,
        "tank_dummy": tank_dummy,
        "kings": kings,
        "str_earth": str_earth,
        "shamanistic_rage": shamanistic_rage,
        "outrage": outrage,
        "bashguuder": bashguuder,
        "faeri": faeri,
        "sunders": sunders,
        "icon": icon,
        "trauma": trauma,
        "HoJ": HoJ,
        "maelstrom": maelstrom,
        "multi": multi,
        "BT_COST": BT_COST,
        "slam_COST": slam_COST,
        "ww_COST": ww_COST,
        "HS_COST": HS_COST,
        "MH_procs": stats.get("MH_procs"),
        "OH_procs": stats.get("OH_procs"),
        "bloodlust_time": stats.get("bloodlust_time", 10.0),
        "bloodfury_time": stats.get("bloodfury_time", 10.0),
        "ability_priority": ability_priority,
        "Starting_rage": starting_rage,
        "impwield": 1.25,
        "DW_COST": 10.0,
        "gcd": 1.5,
        "gcd_delay": 0.05,
        "FLURRY_MULT": 1.25,
        "undending_fury": 1.1,
        "imp_ww": 1.2,
        "PVE_PWR": 1.2475,
        "SMF": 1.05 if smf else 1.0,
        "smf": smf,
        "tg": tg,
        "hunting_pack": 1.03 if hunting_pack else 1.0,
        "dragon_roar": dragon_roar,
        "dragon_warrior": dragon_warrior,
        "mob_level": stats.get("mob_level", 63),
    }

    # Multiprocessing setup
    num_processes = mp.cpu_count()
    iterations_per_process = ceil(iterations / num_processes)
    seeds = [random.randint(0, 1_000_000) for _ in range(num_processes)]
    args_list = [(iterations_per_process, seeds[i], fight_kwargs) for i in range(num_processes)]

    # Run multiprocessing
    with mp.Pool(num_processes) as pool:
        chunk_results = pool.map(_worker, args_list)

    # Combine results
    final_results = {
        "results_total": [],
        "results_white_MH": [],
        "results_white_OH": [],
        "results_slam_MH": [],
        "results_slam_OH": [],
        "results_BT": [],
        "results_WW": [],
        "results_DR": [],
        "results_hs": [],
        "results_ambi": [],
        "result_proc_dmg": [],
        "results_avg_MH_dmg": [],
        "results_avg_OH_dmg": [],
        "results_deep_wounds_dps": [],
        "results_rend": [],
        "flurry_uptime_total": 0.0,
        "enrage_uptime_total": 0.0,
        "crusader_uptime_total": 0.0,
        "crusader_oh_uptime_total": 0.0,
        "Empyrian_Demolisher_uptime_total": 0.0,
        "death_wish_uptime_total": 0.0,
        "all_attack_counts": [],
        "iterations_total": 0
    }

    for chunk in chunk_results:
        for key in ["results_total", "results_white_MH", "results_white_OH", "results_slam_MH",
                    "results_slam_OH", "results_BT", "results_WW", "results_hs", "results_ambi",
                    "results_DR", "result_proc_dmg", "results_avg_MH_dmg", "results_avg_OH_dmg",
                    "results_deep_wounds_dps", "results_rend"]:
            final_results[key].extend(chunk[key])
        final_results["flurry_uptime_total"] += chunk["flurry_uptime_total"]
        final_results["enrage_uptime_total"] += chunk["enrage_uptime_total"]
        final_results["crusader_uptime_total"] += chunk["crusader_uptime_total"]
        final_results["crusader_oh_uptime_total"] += chunk["crusader_oh_uptime_total"]
        final_results["Empyrian_Demolisher_uptime_total"] += chunk["Empyrian_Demolisher_uptime_total"]
        final_results["death_wish_uptime_total"] += chunk["death_wish_uptime_total"]
        final_results["all_attack_counts"].extend(chunk["all_attack_counts"])
        final_results["iterations_total"] += chunk["iterations_chunk"]

    # Compute averages
    iters = final_results["iterations_total"]
    return {
        "mean_total_dps": sum(final_results["results_total"])/iters,
        "mean_white_MH_dps": sum(final_results["results_white_MH"])/iters,
        "mean_white_OH_dps": sum(final_results["results_white_OH"])/iters,
        "mean_slam_MH_dps": sum(final_results["results_slam_MH"])/iters,
        "mean_slam_OH_dps": sum(final_results["results_slam_OH"])/iters,
        "mean_BT_dps": sum(final_results["results_BT"])/iters,
        "mean_WW_dps": sum(final_results["results_WW"])/iters,
        "mean_DR_dps": sum(final_results["results_DR"])/iters,
        "mean_hs_dps": sum(final_results["results_hs"])/iters,
        "mean_ambi_dps": sum(final_results["results_ambi"])/iters,
        "mean_proc_dmg_dps": sum(final_results["result_proc_dmg"])/iters,
        "results_total": final_results["results_total"],
        "results_white_MH": final_results["results_white_MH"],
        "results_white_OH": final_results["results_white_OH"],
        "results_slam_MH": final_results["results_slam_MH"],
        "results_slam_OH": final_results["results_slam_OH"],
        "results_WW": final_results["results_WW"],
        "results_DR": final_results["results_DR"],
        "results_BT": final_results["results_BT"],
        "results_hs": final_results["results_hs"],
        "results_ambi": final_results["results_ambi"],
        "avg_flurry_uptime": final_results["flurry_uptime_total"]/iters,
        "avg_enrage_uptime": final_results["enrage_uptime_total"]/iters,
        "mean_avg_MH_dmg": sum(final_results["results_avg_MH_dmg"])/iters,
        "mean_avg_OH_dmg": sum(final_results["results_avg_OH_dmg"])/iters,
        "Deep Wounds DPS": sum(final_results["results_deep_wounds_dps"])/iters,
        "avg_crusader_uptime": final_results["crusader_uptime_total"]/iters,
        "avg_crusader_oh_uptime": final_results["crusader_oh_uptime_total"]/iters,
        "avg_Empyrian_Demolisher_uptime": final_results["Empyrian_Demolisher_uptime_total"]/iters,
        "all_attack_counts": final_results["all_attack_counts"],
        "avg_death_wish_uptime": final_results["death_wish_uptime_total"]/iters,
        "mean_Rend_dps": sum(final_results["results_rend"])/iters
    }
