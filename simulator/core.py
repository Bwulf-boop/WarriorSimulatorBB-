import random
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
        self.total_uptime = 0.0      # <--- add this
        self.last_update_time = 0.0  # <--- add this

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
        self.last_update_time = current_time


        self.active = True
        self.end_time = current_time + self.duration
        self.last_trigger_time = current_time

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
            self.total_uptime += current_time - self.last_update_time

        if self.active and current_time >= self.end_time:
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
# Single fight simulation
# -------------------------
def _run_single_fight(mh_speed, oh_speed, total_ap, strength, agility, crit, hit,
                      min_dmg, max_dmg, oh_min_dmg, oh_max_dmg,
                      dual_wield,battering_ram, ambi_ME,skull_cracker, fight_length, armor, armor_penetration, haste, wf, tank_dummy, BT_COST=30.0, slam_COST=15.0, ww_COST=25.0, HS_COST=15,
                      mob_level=63, multi=1.0,
                      MH_procs=None,
                      OH_procs=None,
                      kings=False, str_earth=False, shamanistic_rage = False,bashguuder=False, faeri=False,sunders=False,outrage=False,icon=False,trauma=False,HoJ=False,
                      bloodlust_time=10.0, bloodfury_time=10,
                      ):
    time = 0.0
    total_damage = 0.0
    proc_damage_count = 0.0
    proc_dmg = 0.0
    white_MH_damage = 0.0
    white_OH_damage = 0.0
    hs_damage = 0.0
    WW_damage = 0.0
    BT_damage = 0.0
    slam_damage_MH = 0.0
    slam_damage_OH = 0.0
    event_id = 0
    queue = PriorityQueue()
    slam_lockout_until = 0.0
    total_ambi = 0
    impwield = 1.25
    Starting_rage=0.0
    base_crit=crit
    base_crit-=agility/20/100
    current_total_ap = total_ap
    
    mob_level=mob_level or 63
    if armor is None:
        armor = 4644
    if bashguuder:
        armor-=668
    if sunders:
        armor*=0.8
    if faeri:
        armor*=0.95
        
    if armor_penetration is None:
        armor_penetration = 0.0
    if battering_ram: armor_penetration+=0.025

    if outrage:
        enrage_multi=1.1*1.05
    else:
        enrage_multi=1.1




    # -------------------------
    # Rage and GCD
    # -------------------------
    HS_queue = 0
    DW_COST= 10.0
    HS_COST = HS_COST
    slam_COST = slam_COST
    ww_COST = ww_COST
    WW_CD_UP = 0
    BT_COST = BT_COST
    BT_CD_UP = 0
    gcd = 1.5
    gcd_delay = 0.05
    slam_proc = 0
    FLURRY_MULT = 1.25
    flurry_hits_remaining = 0
    flurry_time = 0.0
    last_event_time = 0.0
    proced_haste=0.0
    base_multi = multi
    multi_oh = multi
   

    # -------------------------
    #Damage Multis
    # -------------------------
    PVE_PWR=1.2475
    SMF = 1.05

    # -------------------------
    # Deep wounds
    # -------------------------
    deep_wounds = DeepWounds()
    rend_bleed = RendBleed(duration=30.0, tick_interval=3.0)

    # -------------------------
    # Enrage tracker
    # -------------------------
    enrage = EnrageTracker(duration=5.0)

    # -------------------------
    #Buff tracker
    # -------------------------
    onhit_buffs = BuffTracker()
    death_wish = DeathWish()
    bloodlust = Bloodlust(duration=40.0, haste_bonus=0.3)  # 40s buff, 30% haste
    bloodfury = Bloodfury(duration=15.0, ap_bonus=242, onhit_buffs=onhit_buffs)

    # -------------------------
    # Attack tracking
    # -------------------------
    attack_counts = {k: 0 for k in ["MH","OH","HS","SLAM_MH","SLAM_OH","WW","BT"]}
    crit_counts = {k: 0 for k in ["MH_CRIT","OH_CRIT","HS_CRIT","SLAM_MH_CRIT","SLAM_OH_CRIT","WW_CRIT","BT_CRIT"]}
    miss_counts = {k: 0 for k in ["MH_MISS","OH_MISS","HS_MISS","SLAM_MH_MISS","SLAM_OH_MISS","WW_MISS","BT_MISS"]}


    def next_id():
        nonlocal event_id
        event_id += 1
        return event_id
    
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

    
    ambidextrous = Ambidextrous(duration=8.0, max_stacks=3, per_stack=0.05)
    
    # -------------------------
    # Set procs for MH/OH and extra attacks
    # -------------------------
    # Ensure defaults
    if MH_procs is None:
        MH_procs = ["Crusader"]
    if OH_procs is None:
        OH_procs = ["Crusader_OH"]
    MH_PROCS = set(MH_procs)
    OH_PROCS = set(OH_procs)
    MH_EXTRA_PROCS = set(MH_procs)
    if icon:
        MH_PROCS.add("icon")
        OH_PROCS.add("icon")
        MH_EXTRA_PROCS.add("icon")
    if HoJ:
        MH_PROCS.add("HoJ")
        OH_PROCS.add("HoJ")
        MH_EXTRA_PROCS.add("HoJ")
    # -------------------------
    # On hit proc handler def
    # -------------------------
    def handle_procs(triggered, time):
        dmg=0.0
        for proc in triggered:
            # Instant extra MH swing procs (Flurry Axe, Wound, Rend)
            if proc.get("mh_extra_hit"):
                queue.put((time, next_id(), "Extra_Attack",{ "source_proc": proc["name"]}))

            if proc["name"] == "Rend Garg":
                rend_bleed.trigger(time, current_total_ap, multi, trauma)

            if proc.get("ap_based"):
                dmg = proc.get("base_damage", 0) + current_total_ap * proc["ap_multiplier"] * proc.get("weapon_multiplier", 1.0)
                DR = _calc_dr(armor, armor_penetration, mob_level)
                dmg*=(1-DR)
                if random.random()<crit:
                    deep_wounds.trigger(time, mh_base_avg)
                    dmg*=2
            
            if proc.get("magic_based"):
                dmg = proc.get("base_damage", 0) + current_total_ap * proc["ap_multiplier"] * proc.get("weapon_multiplier", 1.0)
                dmg/= multi
                dmg*=1.2475
                if random.random()<crit:
                    dmg*=1.5
          

        return dmg * multi


    # Schedule first events
    
    queue.put((0, next_id(), "MH_SWING",False))
    queue.put((0.1, next_id(), "GCD", False))
    if tank_dummy:queue.put((0.05, next_id(), "Tank_dummy",False))

    if dual_wield:
        queue.put((0.18, next_id(), "OH_SWING",False))
    
    rage=Starting_rage

    while not queue.empty():
        time, _, event, extra_attack = queue.get()
        active_mods = onhit_buffs.update(time)

        # Update flurry,enrage, dw , ambi uptime
        delta = time - last_event_time
        if flurry_hits_remaining > 0:
            flurry_time += delta
        enrage.update(time)
        ambidextrous.update(time)
        death_wish.update(time)
        last_event_time = time

        if time > fight_length:
            break

        # Apply deep wounds and dots damage
        deep_wounds.update(time)
        rend_bleed.update(time)

        #Bloodlust
        if time >= bloodlust_time and time >= bloodlust.next_available:
            bloodlust.trigger(time)
        bloodlust.update(time)

        # Bloodfury activation
        if time >= bloodfury_time and not bloodfury.active and (time - bloodfury.last_trigger_time >= bloodfury.cooldown): 
            bloodfury.trigger(time)
        # Update its state every event
        bloodfury.update(time)


       # STR -> AP convertion with buffs before event
        crit=base_crit
        crit += active_mods.get("crit", 0.0)
        if bloodfury.active:
            current_total_ap += bloodfury.get_bonus_ap()
        if kings and str_earth:
            current_total_ap = total_ap + (strength + active_mods.get("strength", 0)+88*1.2 )* 2*1.1
            crit+=((agility+88)*1.1/20/100)
        elif kings:
            current_total_ap = total_ap + (strength + active_mods.get("strength", 0) )* 2*1.1
            crit+=((agility)/20/100)
        elif str_earth:
            current_total_ap = total_ap + (strength + active_mods.get("strength", 0)+88*1.2 )* 2
            crit+=((agility+88)/20/100)

        else:
            current_total_ap = total_ap + (strength + active_mods.get("strength", 0) )* 2
            crit+=((agility)/20/100)
        
        if shamanistic_rage: current_total_ap*=1.1
        #Calc haste before event
        proced_haste=haste + active_mods.get("haste", 0)
        current_haste = FLURRY_MULT*proced_haste*wf if flurry_hits_remaining > 0 else (proced_haste * wf)
        current_haste *= 1 + bloodlust.get_bonus_haste()

        # Mh base dmg each start for wounds calc
      
        if trauma:mh_base_avg = ((min_dmg + max_dmg)/2 + current_total_ap / 14 * mh_speed)*multi/1.247*1.3 #Trauma RendBleed
        else: mh_base_avg = ((min_dmg + max_dmg)/2 + current_total_ap / 14 * mh_speed)*multi/1.2475 #No PVE POWER
        if trauma: oh_base_avg = ((oh_min_dmg + oh_max_dmg)/2 + current_total_ap / 14 * oh_speed)*multi_oh/1.2475*1.3
        else:  oh_base_avg = ((oh_min_dmg + oh_max_dmg)/2 + current_total_ap / 14 * oh_speed)*multi_oh/1.2475 #No PVE POWER


        #Collects uptime for all on hit proc buffs
        buff_uptimes = {name: onhit_buffs.get_uptime(name, fight_length) for name in onhit_buffs.uptime.keys()}

        # -------------------------
        # Set Damage Multi on each event
        # -------------------------
        multi = base_multi
        if enrage.active:
            multi *= enrage_multi
        if death_wish.active:
            multi *= 1.20
        multi *= PVE_PWR
        multi *= SMF
        multi_oh = multi 
        multi_oh*=0.5* impwield*ambidextrous.get_multiplier() #Ambi and OH penalty
    


        # Queue HS if enough rage
        if rage >= HS_COST and not extra_attack:
            HS_queue = 1
        
        # -------------------------
        # MAIN EVENTS
        # -------------------------
        if event == "MH_SWING":
            swing_speed = mh_speed / current_haste
            if not extra_attack and flurry_hits_remaining > 0:
                flurry_hits_remaining -= 1
            if time < slam_lockout_until:
                queue.put((slam_lockout_until, next_id(), event, False))

                continue
            if HS_queue == 1 and not extra_attack and rage>= HS_COST:
                HS_queue = 0
                was_crit = False
                # Heroic Strike
                hs_base = random.randint(int(min_dmg), int(max_dmg)) + 201 + current_total_ap /14 * mh_speed
                triggered = resolve_on_hit_procs(time, mh_speed, procs_to_check=MH_PROCS)
                apply_on_hit_procs(triggered, time, onhit_buffs, total_ap=total_ap)
                proc_dmg = handle_procs(triggered, time) or 0.0
                proc_damage_count += proc_dmg
                total_damage += proc_dmg 
                DR = _calc_dr(armor, armor_penetration, mob_level)
                hs_dmg_val = hs_base * (1 - DR)
                hs_crit = random.random() < (crit + 0.15)
                if hs_crit: 
                    hs_dmg_val *= 2.2
                    deep_wounds.trigger(time, mh_base_avg)
                    rage+=10
                    if rage>100: rage=100
                    flurry_hits_remaining = 3
                hs_dmg_val *=multi
                hs_damage += hs_dmg_val
                total_damage += hs_dmg_val
                rage -= HS_COST
                if random.random() < (0.2): slam_proc=1
                HS_queue = 0
                attack_counts["HS"] += 1
                next_time=time + swing_speed
                if hs_crit: crit_counts["HS_CRIT"] += 1
                if ambi_ME:
                    ambi_dmg = random.randint(int(oh_min_dmg), int(oh_max_dmg)) + (current_total_ap  / 14 * oh_speed)
                    ambi_dmg*=multi_oh*0.75
                    ambi_dmg *= (1 - DR)
                    ambi_crit = random.random() < crit
                    if ambi_crit: 
                        ambi_dmg*=2
                        deep_wounds.trigger(time, oh_base_avg)
                        flurry_hits_remaining = 3
                    total_damage += ambi_dmg
                    total_ambi+= ambi_dmg
                    ambidextrous.trigger(time)
                if next_time <= fight_length:
                    queue.put((next_time, next_id(), "MH_SWING", False))
            else:
                # White swing

                dmg, was_crit, was_miss = _resolve_swing(min_dmg, max_dmg, current_total_ap, crit, hit, dual_wield, armor, armor_penetration, 
                                                         HS_queue, mh_speed, mob_level, multi=multi)
                total_damage += dmg
                white_MH_damage += dmg
                attack_counts["MH"] += 1
                if was_crit: crit_counts["MH_CRIT"] += 1
                if was_miss == 0:
                    triggered = resolve_on_hit_procs(time,mh_speed, procs_to_check=MH_PROCS)
                    apply_on_hit_procs(triggered, time, onhit_buffs, total_ap=total_ap)
                    proc_dmg = handle_procs(triggered, time) or 0.0
                    proc_damage_count+=proc_dmg
                    total_damage += proc_dmg
                       
                else: miss_counts["MH_MISS"] += 1

                rage += _generate_rage_classic(dmg, mh_speed, offhand=False, is_crit=was_crit)
                if rage > 100.0: rage = 100.0
                if was_crit: 
                    flurry_hits_remaining = 3
                    deep_wounds.trigger(time, mh_base_avg)  # trigger DW on crit
                next_time = time + swing_speed
                if next_time <= fight_length:
                        queue.put((next_time, next_id(), "MH_SWING", False))

        elif event== "Extra_Attack":
            if flurry_hits_remaining > 0:
                flurry_hits_remaining -= 1 
            dmg, was_crit, was_miss = _resolve_swing(min_dmg, max_dmg, current_total_ap, crit, hit, dual_wield, armor, armor_penetration, 
                                                         HS_queue, mh_speed, mob_level, multi=multi)
            total_damage += dmg
            white_MH_damage += dmg
            attack_counts["MH"] += 1
            if was_crit: crit_counts["MH_CRIT"] += 1
            if was_miss == 0:
                procs = MH_EXTRA_PROCS.copy()
                payload = extra_attack if isinstance(extra_attack, dict) else {}
                source_proc = payload.get("source_proc")
                procs.discard(source_proc)
                triggered = resolve_on_hit_procs(time,mh_speed, procs_to_check=procs)
                apply_on_hit_procs(triggered, time, onhit_buffs, total_ap=total_ap)
                proc_dmg = handle_procs(triggered, time) or 0.0
                total_damage += proc_dmg 
                proc_damage_count+=proc_dmg     

            else: miss_counts["MH_MISS"] += 1

            rage += _generate_rage_classic(dmg, mh_speed, offhand=False, is_crit=was_crit)
            if rage > 100.0: rage = 100.0
            if was_crit: 
                flurry_hits_remaining = 3
                deep_wounds.trigger(time, mh_base_avg)  # trigger DW on crit

        elif event == "OH_SWING" and dual_wield:
            was_crit = False
            if flurry_hits_remaining > 0:
                flurry_hits_remaining -= 1
            if time < slam_lockout_until:
                queue.put((slam_lockout_until, next_id(), event, False))
                continue
            dmg, was_crit, was_miss = _resolve_swing(oh_min_dmg, oh_max_dmg, current_total_ap , crit, hit, dual_wield, armor, armor_penetration,
                                                     HS_queue, oh_speed, mob_level, multi=multi_oh)

            total_damage += dmg
            white_OH_damage += dmg
            attack_counts["OH"] += 1
            if was_crit: 
                crit_counts["OH_CRIT"] += 1
                deep_wounds.trigger(time, oh_base_avg)  # trigger DW on crit
            if was_miss==0:
                triggered = resolve_on_hit_procs(time, oh_speed, procs_to_check=OH_PROCS)
                apply_on_hit_procs(triggered, time, onhit_buffs, total_ap=current_total_ap)
                proc_dmg = handle_procs(triggered, time) or 0.0
                proc_damage_count+=proc_dmg
                total_damage += proc_dmg
            else: miss_counts["OH_MISS"] += 1

            rage += _generate_rage_classic(dmg, oh_speed, offhand=True, is_crit=was_crit)
            if rage > 100.0: rage = 100.0
            if was_crit: flurry_hits_remaining = 3

            next_time = time + oh_speed / current_haste
            if next_time <= fight_length:
                queue.put((next_time, next_id(), "OH_SWING", False))


        # -------------------------
        # GCD: Slam / WW / BT
        # -------------------------
        elif event == "GCD":
            used_gcd = False
            was_crit = False
            was_miss=0

            if not used_gcd and death_wish.can_cast(time) and rage>=DW_COST:
                death_wish.cast(time)
                used_gcd = True 
            # Slam
            elif rage >= slam_COST and slam_proc==1:
                slam_proc=0
                dmg, crit_flag,proc_flag = _resolve_slam(min_dmg, max_dmg, current_total_ap , crit, hit, armor, armor_penetration, mh_speed,False, mob_level=63, multi=multi)
                #undending fury multi
                dmg*=1.1
                total_damage += dmg
                slam_damage_MH += dmg
                attack_counts["SLAM_MH"] += 1
                
                if crit_flag: 
                    crit_counts["SLAM_MH_CRIT"] += 1
                    deep_wounds.trigger(time, mh_base_avg)  # trigger DW on crit
                    flurry_hits_remaining = 3

                if was_miss == 0:
                    triggered = resolve_on_hit_procs(time, mh_speed, procs_to_check=MH_PROCS)  # get triggered procs
                    apply_on_hit_procs(triggered, time, onhit_buffs, total_ap=total_ap)
                    proc_dmg = handle_procs(triggered, time) or 0.0
                    proc_damage_count+=proc_dmg  # calculate total proc damage
                    total_damage += proc_dmg
                if was_miss == 0 and battering_ram:
                    triggered = resolve_on_hit_procs(time, mh_speed, procs_to_check=MH_PROCS)  # get triggered procs
                    proc_dmg  = apply_on_hit_procs(triggered, time, onhit_buffs, total_ap=total_ap)  or 0.0  # calculate proc damage
                    handle_procs(triggered, time)  # apply buffs like Crusader
                    proc_damage_count+=proc_dmg
                    total_damage += proc_dmg  
                if was_miss== 0 and skull_cracker: death_wish.next_available = max(time, death_wish.next_available - 2.0)


                if proc_flag:
                    enrage.trigger(time)
                    slam_proc=1

                # Offhand Slam
                dmg, crit_flag, proc_flag = _resolve_slam(oh_min_dmg, oh_max_dmg, current_total_ap , crit, hit, armor, armor_penetration, oh_speed, True,mob_level=63, multi=multi_oh)
                #undending fury multi
                dmg*=1.1
                if proc_flag:
                    enrage.trigger(time)
                total_damage += dmg
                slam_damage_OH += dmg
                attack_counts["SLAM_OH"] += 1
                if was_miss == 0:
                    triggered = resolve_on_hit_procs(time, mh_speed, procs_to_check=OH_PROCS)  # get triggered procs
                    apply_on_hit_procs(triggered, time, onhit_buffs, total_ap=total_ap)
                    proc_dmg = handle_procs(triggered, time) or 0.0
                    proc_damage_count+=proc_dmg  # calculate proc damage
                    total_damage += proc_dmg 
                if was_miss == 0 and battering_ram:
                    triggered = resolve_on_hit_procs(time, mh_speed, procs_to_check=MH_PROCS)  # get triggered procs
                    apply_on_hit_procs(triggered, time, onhit_buffs, total_ap=total_ap)
                    proc_dmg = handle_procs(triggered, time) or 0.0
                    total_damage += proc_dmg
                    proc_damage_count+=proc_dmg  # calculate proc damage
                if was_miss== 0 and skull_cracker: death_wish.next_available = max(time, death_wish.next_available - 2.0)
                if crit_flag: 
                    crit_counts["SLAM_OH_CRIT"] += 1
                    deep_wounds.trigger(time, oh_base_avg)  # trigger DW on crit
                    flurry_hits_remaining = 3
                if proc_flag:
                    enrage.trigger(time)
                    slam_proc=1
                
     
                rage -= slam_COST
                used_gcd = True

                # -----------------
                # Bloodthirst
                # -----------------
            elif rage >= BT_COST and time >= BT_CD_UP:
                bt_base = total_ap * 0.5
                DR = _calc_dr(armor, armor_penetration, mob_level)
                dmg = bt_base * (1 - DR) * multi
                #undending fury
                dmg*=1.1
                crit_flag = random.random() < crit
                if crit_flag:
                    dmg *= 2.2
                    crit_counts["BT_CRIT"] += 1
                    deep_wounds.trigger(time, mh_base_avg)
                    flurry_hits_remaining = 3
                total_damage += dmg
                BT_damage += dmg
                attack_counts["BT"] += 1
                triggered = resolve_on_hit_procs(time, mh_speed, procs_to_check=MH_PROCS)
                apply_on_hit_procs(triggered, time, onhit_buffs, total_ap=current_total_ap)
                proc_dmg = handle_procs(triggered, time) or 0.0
                proc_damage_count+=proc_dmg
                total_damage += proc_dmg
                if random.random() < (0.2): slam_proc=1
                rage -= BT_COST
                BT_CD_UP = time + 6.0
                used_gcd = True

            elif rage >= ww_COST and time >= WW_CD_UP:
                ww_base = random.randint(int(min_dmg), int(max_dmg)) + current_total_ap  / 14 * 2.4
                DR = _calc_dr(armor, armor_penetration, mob_level)
                #undending fury multi
                ww_base*=1.1                
                dmg = ww_base * (1 - DR) * multi

                crit_flag = random.random() < crit
                if crit_flag:
                    dmg *= 2.2
                    crit_counts["WW_CRIT"] += 1
                    deep_wounds.trigger(time, mh_base_avg)
                    flurry_hits_remaining = 3

                ww_base = random.randint(int(oh_min_dmg), int(oh_max_dmg)) + current_total_ap  / 14 * 2.4
                #undending fury multi
                ww_base*=1.1
                dmg += ww_base * (1 - DR) * multi_oh
                crit_flag = random.random() < crit
                if crit_flag:
                    dmg *= 2
                    crit_counts["WW_CRIT"] += 1
                    deep_wounds.trigger(time, oh_base_avg)
                    flurry_hits_remaining = 3

                total_damage += dmg
                WW_damage += dmg
                attack_counts["WW"] += 1
                if random.random() < (0.2): slam_proc=1
                if random.random() < (0.2): slam_proc=1
                triggered = resolve_on_hit_procs(time, mh_speed, procs_to_check=MH_PROCS)
                apply_on_hit_procs(triggered, time, onhit_buffs, total_ap=current_total_ap)
                proc_dmg = handle_procs(triggered, time) or 0.0
                proc_damage_count+=proc_dmg
                total_damage += proc_dmg
                triggered = resolve_on_hit_procs(time, mh_speed, procs_to_check=OH_PROCS) 
                apply_on_hit_procs(triggered, time, onhit_buffs, total_ap=current_total_ap)
                proc_dmg = handle_procs(triggered, time) or 0.0
                proc_damage_count+=proc_dmg
                total_damage += proc_dmg

                rage -= ww_COST
                WW_CD_UP = time + 8.0
                used_gcd = True
              # Hard cast slam  
            elif rage >= slam_COST:
                slam_cast_time = 1.5
                slam_lockout_until = time + slam_cast_time
                dmg, crit_flag, proc_flag= _resolve_slam(min_dmg, max_dmg, current_total_ap , crit, hit, armor, armor_penetration, mh_speed, False, mob_level=63, multi=multi)
                #undending fury multi
                dmg*=1.1           
                total_damage += dmg
                slam_damage_MH += dmg
                if proc_flag:
                    enrage.trigger(time)
                attack_counts["SLAM_MH"] += 1
                if was_miss == 0:
                    triggered = resolve_on_hit_procs(time, mh_speed, procs_to_check=MH_PROCS)  # get triggered procs
                    apply_on_hit_procs(triggered, time, onhit_buffs, total_ap=total_ap)
                    proc_dmg = handle_procs(triggered, time) or 0.0
                    total_damage += proc_dmg
                    proc_damage_count +=proc_dmg
                if was_miss == 0 and battering_ram:
                    triggered = resolve_on_hit_procs(time, mh_speed, procs_to_check=MH_PROCS)  # get triggered procs
                    apply_on_hit_procs(triggered, time, onhit_buffs, total_ap=total_ap)
                    proc_dmg = handle_procs(triggered, time) or 0.0
                    total_damage += proc_dmg
                    proc_damage_count +=proc_dmg
                if was_miss== 0 and skull_cracker: death_wish.next_available = max(time, death_wish.next_available - 2.0)
                if crit_flag: 
                    crit_counts["SLAM_MH_CRIT"] += 1
                    deep_wounds.trigger(time, mh_base_avg)  # trigger DW on crit
                    flurry_hits_remaining = 3
                if was_miss== 0 and skull_cracker: death_wish.next_available = max(time, death_wish.next_available - 2.0)
                if proc_flag:
                    enrage.trigger(time)
                    slam_proc=1
        
                # Offhand Slam
                dmg, crit_flag, proc_flag = _resolve_slam(oh_min_dmg, oh_max_dmg, current_total_ap , crit, hit, armor, armor_penetration, oh_speed, True, mob_level=63, multi=multi_oh)
                #undending fury multi
                dmg*=1.1  
                total_damage += dmg
                slam_damage_OH += dmg

                if proc_flag:
                    enrage.trigger(time)
                attack_counts["SLAM_OH"] += 1
                if was_miss == 0:
                    triggered = resolve_on_hit_procs(time, mh_speed, procs_to_check=OH_PROCS)  # get triggered procs
                    apply_on_hit_procs(triggered, time, onhit_buffs, total_ap=total_ap)
                    proc_dmg = handle_procs(triggered, time) or 0.0
                    total_damage += proc_dmg
                    proc_damage_count +=proc_dmg
                if was_miss == 0 and battering_ram:
                    triggered = resolve_on_hit_procs(time, mh_speed, procs_to_check=MH_PROCS)  # get triggered procs
                    apply_on_hit_procs(triggered, time, onhit_buffs, total_ap=total_ap)
                    proc_dmg = handle_procs(triggered, time) or 0.0
                    total_damage += proc_dmg 
                    proc_damage_count +=proc_dmg
                if was_miss== 0 and skull_cracker: death_wish.next_available = max(time, death_wish.next_available - 2.0)
                if crit_flag: 
                    crit_counts["SLAM_OH_CRIT"] += 1
                    deep_wounds.trigger(time, oh_base_avg)  # trigger DW on crit
                    flurry_hits_remaining = 3
                if was_miss== 0 and skull_cracker: death_wish.next_available = max(time, death_wish.next_available - 2.0)
                if proc_flag:
                    enrage.trigger(time)
                    slam_proc=1                
          
                rage -= slam_COST
                used_gcd = True

            if used_gcd:
                    next_time = time + gcd + gcd_delay
                    if next_time <= fight_length:
                        queue.put((next_time, next_id(), "GCD",False))
            else:
                next_time = time+0.02
                if next_time <= fight_length:
                    queue.put((next_time, next_id(), "GCD", False))


        elif event== "Tank_dummy":
            rage+=60
            if rage>100: rage=100
            next_time = time+1.5
            if next_time <= fight_length:
                queue.put((next_time, next_id(), "Tank_dummy", False))

    # -------------------------
    # Final averages
    # -------------------------
    avg_MH_dmg = white_MH_damage / max(attack_counts["MH"], 1)
    avg_OH_dmg = white_OH_damage / max(attack_counts["OH"], 1)

    # -------------------------
    # Last update for all buffs 
    # -------------------------
    onhit_buffs.update(fight_length)

    # Track On hit buff uptime
    crusader_uptime = onhit_buffs.get_uptime("Crusader", fight_length)
    crusader_oh_uptime = onhit_buffs.get_uptime("Crusader_OH", fight_length)
    Empyrian_Demolisher_uptime = onhit_buffs.get_uptime("Empyrian Demolisher", fight_length)

    return {
        "slam_MH_dps": slam_damage_MH / fight_length,
        "slam_OH_dps": slam_damage_OH / fight_length,
        "white_MH_dps": white_MH_damage / fight_length,
        "white_OH_dps": white_OH_damage / fight_length,
        "avg_MH_dmg": avg_MH_dmg,
        "avg_OH_dmg": avg_OH_dmg,
        "hs_dps": hs_damage / fight_length,
        "WW_dps": WW_damage / fight_length,
        "BT_dps": BT_damage / fight_length,
        "Ambi_dps": total_ambi / fight_length,
        "all_attack_counts": [
            {
                atk: {
                    "hits": attack_counts[atk],
                    "crits": crit_counts[f"{atk}_CRIT"],
                    "misses": miss_counts[f"{atk}_MISS"]
                }
                for atk in attack_counts
            }
        ],
        "flurry_uptime": flurry_time / fight_length,
        "enrage_uptime": enrage.total_uptime / fight_length,
        "total_dps": (total_damage + deep_wounds.total_damage+rend_bleed.total_damage) / fight_length,
        "deep_wounds_dps": deep_wounds.total_damage / fight_length,
        "crusader_uptime": crusader_uptime,
        "crusader_oh_uptime": crusader_oh_uptime,
        "Empyrian_Demolisher_uptime": Empyrian_Demolisher_uptime,
        "death_wish_uptime": death_wish.total_uptime / fight_length,
        "Rend_dps": rend_bleed.total_damage / fight_length,
        "Proc_dmg_dps": proc_damage_count / fight_length,
    }


# -------------------------
# Swing, Slam resolution
# -------------------------
def _resolve_swing(min_dmg, max_dmg, current_total_ap, crit, hit, dual_wield, armor, armor_penetration,
                   HS_queue, base_speed, mob_level=63, multi=1.0, forced_crit=None):
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
                  mob_level=63, multi=1.0, forced_crit=None):
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
    f = 4 if offhand and is_crit else 2 if offhand else 14 if is_crit else 7
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
# Run Simulation
# -------------------------

def run_simulation(iterations=1000, mh_speed=2.6, oh_speed=2.7,
                   fight_length=60.0, stats=None, dual_wield=True, battering_ram = True, ambi_ME=True, skull_cracker=True, tank_dummy = False,
                   kings=False, str_earth=False,shamanistic_rage=False, outrage=False,
                   bashguuder=False, faeri=False,sunders=False, icon=False,trauma=False,HoJ=False,
                   multi=1.0, BT_COST=30.0, slam_COST=15.0, ww_COST=25.0, HS_COST=15.0):
    """
    Run multiple iterations of the warrior simulation.
    Returns a dict with all mean DPS values and per-fight results.
    """
    if stats is None:
        stats = {}
    strength = stats.get("strength", 0)
    agility = stats.get("Agility", 121)
    attack_power = stats.get("attack_power", 2800)
    crit = stats.get("crit", 31)/100 - 0.048
    hit = stats.get("hit", 8)/100
    your_armor=stats.get("Your_Armor", 4000)
    armor = stats.get("boss_armor", 4644)
    armor_penetration = stats.get("armor_penetration", 10)/5/100
    min_dmg = stats.get("min_dmg", 96)
    max_dmg = stats.get("max_dmg", 152)
    oh_min_dmg = stats.get("oh_min_dmg", 100)
    oh_max_dmg = stats.get("oh_max_dmg", 157)
    haste =stats.get("haste",0)
    wf =stats.get("wf",0)
    haste = 1 + haste / 1000  # 10 -> 0.01 -> 1.01
    wf = 1 + wf / 1000
    ap_from_armor=your_armor/102*3
    all_attack_counts = []
    base_ap=60*3-20
    extra_str = stats.get("Add_Str", 0)
    extra_agi = stats.get("Add_Agi", 0)
    extra_ap = stats.get("Add_Ap", 0)
    extra_crit = stats.get("Add_Crit", 0)/100
    
    #Calculate Base stats from Char sheet input, needed for buff interaction
    Gear_AP=attack_power - base_ap - strength * 2 - ap_from_armor

    
    total_ap = Gear_AP  + ap_from_armor + base_ap + extra_ap

    strength += extra_str*1.2
    agility = agility + extra_agi
    crit = crit + extra_crit
    # Lists to collect per-fight values
    results_total = []
    results_white_MH = []
    results_white_OH = []
    results_slam_MH = []
    results_slam_OH = []
    results_BT = []
    results_WW = []
    results_hs = []
    results_avg_MH_dmg = []
    results_avg_OH_dmg = []
    flurry_uptime_total = 0.0
    enrage_uptime_total = 0.0
    crusader_uptime_total = 0.0
    crusader_oh_uptime_total = 0.0
    Empyrian_Demolisher_uptime_total = 0.0 
    death_wish_uptime_total = 0.0
    results_deep_wounds_dps = []
    results_ambi = []
    results_rend=[]
    result_proc_dmg=[]

    for _ in range(iterations):
        fight = _run_single_fight(
            mh_speed=mh_speed,
            oh_speed=oh_speed,
            strength=strength,
            agility=agility,
            total_ap=total_ap,
            crit=crit,
            hit=hit,
            min_dmg=min_dmg,
            max_dmg=max_dmg,
            oh_min_dmg=oh_min_dmg,
            oh_max_dmg=oh_max_dmg,
            dual_wield=dual_wield,
            battering_ram=battering_ram,
            ambi_ME=ambi_ME,
            tank_dummy = tank_dummy,
            skull_cracker=skull_cracker,
            kings=kings,
            outrage=outrage,
            bashguuder=bashguuder, 
            faeri=faeri,
            sunders=sunders,
            str_earth =  str_earth,
            shamanistic_rage = shamanistic_rage,
            fight_length=fight_length,
            armor=armor,
            armor_penetration=armor_penetration,
            haste=haste,
            wf=wf,
            BT_COST=BT_COST,
            slam_COST=slam_COST,
            ww_COST=ww_COST,
            HS_COST=HS_COST,
            multi=multi,
            icon=icon,       
            trauma=trauma,
            HoJ=HoJ,
            MH_procs=stats.get("MH_procs"), 
            OH_procs=stats.get("OH_procs"),
            bloodlust_time=stats.get("bloodlust_time", 10.0),
            bloodfury_time=stats.get("bloodfury_time", 10.0)
    )
        results_total.append(fight["total_dps"])
        results_white_MH.append(fight["white_MH_dps"])
        results_white_OH.append(fight["white_OH_dps"])
        results_slam_MH.append(fight["slam_MH_dps"])
        results_slam_OH.append(fight["slam_OH_dps"])
        results_BT.append(fight["BT_dps"])
        results_WW.append(fight["WW_dps"])
        results_hs.append(fight["hs_dps"])
        results_ambi.append(fight["Ambi_dps"])
        result_proc_dmg.append(fight["Proc_dmg_dps"])
        results_avg_MH_dmg.append(fight["avg_MH_dmg"])
        results_avg_OH_dmg.append(fight["avg_OH_dmg"])
        flurry_uptime_total += fight["flurry_uptime"]
        enrage_uptime_total += fight["enrage_uptime"]
        results_deep_wounds_dps.append(fight["deep_wounds_dps"])
        crusader_uptime_total += fight["crusader_uptime"]
        crusader_oh_uptime_total += fight["crusader_oh_uptime"]
        Empyrian_Demolisher_uptime_total += fight["Empyrian_Demolisher_uptime"]
        all_attack_counts.append(fight["all_attack_counts"][0])
        death_wish_uptime_total += fight["death_wish_uptime"]
        results_rend.append(fight["Rend_dps"])


    return {
        "mean_total_dps": sum(results_total)/iterations,
        "mean_white_MH_dps": sum(results_white_MH)/iterations,
        "mean_white_OH_dps": sum(results_white_OH)/iterations,
        "mean_slam_MH_dps": sum(results_slam_MH)/iterations,
        "mean_slam_OH_dps": sum(results_slam_OH)/iterations,
        "mean_BT_dps": sum(results_BT)/iterations,
        "mean_WW_dps": sum(results_WW)/iterations,
        "mean_hs_dps": sum(results_hs)/iterations,
        "mean_ambi_dps": sum(results_ambi)/iterations,
        "mean_proc_dmg_dps": sum(result_proc_dmg)/iterations,
        "results_total": results_total,
        "results_white_MH": results_white_MH,
        "results_white_OH": results_white_OH,
        "results_slam_MH": results_slam_MH,
        "results_slam_OH": results_slam_OH,
        "results_WW": results_WW,
        "results_BT": results_BT,
        "results_hs": results_hs,
        "results_ambi": results_ambi,
        "avg_flurry_uptime": flurry_uptime_total/iterations,
        "avg_enrage_uptime": enrage_uptime_total/iterations,
        "mean_avg_MH_dmg": sum(results_avg_MH_dmg)/iterations,
        "mean_avg_OH_dmg": sum(results_avg_OH_dmg)/iterations,
        "Deep Wounds DPS": sum(results_deep_wounds_dps)/iterations,
        "avg_crusader_uptime": crusader_uptime_total/iterations,
        "avg_crusader_oh_uptime": crusader_oh_uptime_total/iterations,
        "avg_Empyrian_Demolisher_uptime": Empyrian_Demolisher_uptime_total/iterations,
        "all_attack_counts": all_attack_counts,
        "avg_death_wish_uptime": death_wish_uptime_total / iterations,
        "mean_Rend_dps": sum(results_rend) / iterations
       
    }

