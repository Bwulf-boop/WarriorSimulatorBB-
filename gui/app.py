import tkinter as tk
from tkinter import ttk, messagebox
import threading
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from simulator.core import run_simulation  


class WarriorSimApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("WoW BB Warrior Simulator")
        self.geometry("900x1000")

        # ---------- Main Container ----------
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, padx=12, pady=12)

        # ---------- Frames ----------
        self.left_frame = ttk.LabelFrame(container, text="Character Stats")
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        self.right_frame = ttk.LabelFrame(container, text="Simulation Settings")
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 12))

        self.bottom_frame = ttk.LabelFrame(container, text="Results & Histogram")
        self.bottom_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(12, 0))

        # ---------- Bottom frame: results left, plot right ----------
        self.results_frame = ttk.Frame(self.bottom_frame)
        self.results_frame.pack(side="left", fill="y", padx=(5,10), pady=5)

        self.plot_frame = ttk.Frame(self.bottom_frame)
        self.plot_frame.pack(side="right", fill="both", expand=True, padx=(10,5), pady=5)

        self.show_attacks_button = ttk.Button(self.results_frame, text="Show Attack Counts", command=self._show_attack_counts)
        self.show_attacks_button.pack(pady=5)

        # Allow resizing
        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=1)
        container.grid_rowconfigure(1, weight=1)  # bottom frame expands

        # ---------- Variables ----------
        self.stats = {
            "strength": tk.DoubleVar(value=403),
            "Agility": tk.DoubleVar(value=121),
            "attack_power": tk.DoubleVar(value=1455),
            "crit": tk.DoubleVar(value=30.42),
            "hit": tk.DoubleVar(value=8),
            "Your_Armor": tk.DoubleVar(value=4234),
            "Boss_armor": tk.DoubleVar(value=4644),
            "armor_penetration": tk.DoubleVar(value=78),
            "min_dmg": tk.DoubleVar(value=97),
            "max_dmg": tk.DoubleVar(value=157),
            "oh_min_dmg": tk.DoubleVar(value=100),
            "oh_max_dmg": tk.DoubleVar(value=157),
            "haste": tk.DoubleVar(value=0),
            "wf": tk.DoubleVar(value=0),
        }
        # Add new cost variables
        self.BT_cost = tk.DoubleVar(value=20.0)
        self.slam_cost = tk.DoubleVar(value=15.0)
        self.HS_cost = tk.DoubleVar(value=15.0)
        self.ww_cost = tk.DoubleVar(value=25.0)
        self.mh_speed = tk.DoubleVar(value=2.6)
        self.oh_speed = tk.DoubleVar(value=2.7)
        self.fight_length = tk.DoubleVar(value=60.0)
        self.iterations = tk.IntVar(value=1000)
        self.dual_wield = tk.BooleanVar(value=True)
        self.multi = tk.DoubleVar(value=1.0)
        self.battering_ram = tk.BooleanVar(value=True)
        self.tank_dummy = tk.BooleanVar(value=False)
        self.ambi_ME = tk.BooleanVar(value=True)
        self.skull_cracker = tk.BooleanVar(value=True)
        self.kings = tk.BooleanVar(value=False)
        self.str_earth = tk.BooleanVar(value=False)
        self.bashguuder = tk.BooleanVar(value=False)
        self.sunders = tk.BooleanVar(value=False)
        self.faeri = tk.BooleanVar(value=False)
        self.shamanistic_rage = tk.BooleanVar(value=False)
        self.outrage = tk.BooleanVar(value=False)
        self.icon = tk.BooleanVar(value=False)
        self.trauma = tk.BooleanVar(value=False)
        self.HoJ = tk.BooleanVar(value=False)
        self.bloodlust_time = tk.DoubleVar(value=61.0)
        self.bloodfury_time = tk.DoubleVar(value=61.0)


        # Weapon Proc Options
        self.MH_PROC_OPTIONS = ["Crusader", "Flurry Axe", "Empyrian Demolisher", "Wound"]
        self.OH_PROC_OPTIONS = ["Crusader_OH","Flurry Axe", "Rend Garg","Empyrian Demolisher", "Wound"]

        # Track checkbox selections
        self.MH_proc_vars = {proc: tk.IntVar(value=0) for proc in self.MH_PROC_OPTIONS}
        self.OH_proc_vars = {proc: tk.IntVar(value=0) for proc in self.OH_PROC_OPTIONS}
        

        # ---------- Build UI ----------
        self._create_stats_input(self.left_frame)
        self._create_settings_input(self.right_frame)
        self._create_results(self.bottom_frame)  # uses self.results_frame

        # ---------- Matplotlib Canvas ----------
        self.figure = plt.Figure(figsize=(6,3))
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.plot_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    # ---------- Stats Input ----------
    def _create_stats_input(self, frame):
        for stat, var in self.stats.items():
            row = ttk.Frame(frame)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=stat.replace("_", " ").title(), width=20).pack(side="left")
            ttk.Entry(row, textvariable=var, width=10).pack(side="left")

    # ---------- Simulation Settings ----------
    def _create_settings_input(self, frame):
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="MH Speed").pack(side="left")
        ttk.Entry(row, textvariable=self.mh_speed, width=10).pack(side="left")
        ttk.Label(row, text="OH Speed").pack(side="left")
        ttk.Entry(row, textvariable=self.oh_speed, width=10).pack(side="left")

        row = ttk.Frame(frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Fight Length (s)").pack(side="left")
        ttk.Entry(row, textvariable=self.fight_length, width=10).pack(side="left")
        ttk.Label(row, text="Iterations").pack(side="left")
        ttk.Entry(row, textvariable=self.iterations, width=10).pack(side="left")

        row = ttk.Frame(frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Damage Multiplier").pack(side="left")
        ttk.Entry(row, textvariable=self.multi, width=10).pack(side="left")
        # ---------- Checkbox Grid ----------
        checkbox_frame = ttk.Frame(frame)
        checkbox_frame.pack(fill="x", pady=6)
        
        ttk.Checkbutton(checkbox_frame, text="Dual Wield", variable=self.dual_wield)\
            .grid(row=0, column=0, sticky="w", pady=2)
        ttk.Checkbutton(checkbox_frame, text="Battering Ram", variable=self.battering_ram)\
            .grid(row=1, column=0, sticky="w", pady=2)
        ttk.Checkbutton(checkbox_frame, text="Outrage", variable=self.outrage)\
            .grid(row=2, column=0, sticky="w", pady=2)
        ttk.Checkbutton(checkbox_frame, text="Ambi ME", variable=self.ambi_ME)\
            .grid(row=3, column=0, sticky="w", pady=2)
        ttk.Checkbutton(checkbox_frame, text="Skull Cracker", variable=self.skull_cracker)\
            .grid(row=4, column=0, sticky="w", pady=2)
        
        ttk.Checkbutton(checkbox_frame, text="Kings", variable=self.kings)\
            .grid(row=0, column=1, sticky="w", pady=2, padx=(20, 0))
        ttk.Checkbutton(checkbox_frame, text="Strength of Earth", variable=self.str_earth)\
            .grid(row=1, column=1, sticky="w", pady=2, padx=(20, 0))
        ttk.Checkbutton(checkbox_frame, text="Shamanistic Rage", variable=self.shamanistic_rage)\
            .grid(row=2, column=1, sticky="w", pady=2, padx=(20, 0))
        ttk.Checkbutton(checkbox_frame, text="Sunders", variable=self.sunders)\
            .grid(row=3, column=1, sticky="w", pady=2, padx=(20, 0))
        ttk.Checkbutton(checkbox_frame, text="Faeri Fire", variable=self.faeri)\
            .grid(row=4, column=1, sticky="w", pady=2, padx=(20, 0))
        ttk.Checkbutton(checkbox_frame, text="Bashguuder", variable=self.bashguuder)\
            .grid(row=0, column=2, sticky="w", pady=2, padx=(20, 0))
        ttk.Checkbutton(checkbox_frame, text="Icon", variable=self.icon)\
            .grid(row=1, column=2, sticky="w", pady=2, padx=(20, 0))
        ttk.Checkbutton(checkbox_frame, text="Trauma", variable=self.trauma)\
            .grid(row=2, column=2, sticky="w", pady=2, padx=(20, 0))
        ttk.Checkbutton(checkbox_frame, text="HoJ", variable=self.HoJ)\
            .grid(row=3, column=2, sticky="w", pady=2, padx=(20, 0))
        

        

        ttk.Checkbutton(checkbox_frame, text="Tank dummy", variable=self.tank_dummy)\
            .grid(row=5, column=0, sticky="w", pady=2)
        
        self.run_button = ttk.Button(frame, text="Run Simulation", command=self._run_simulation_thread)
        self.run_button.pack(pady=10)
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="BT Cost").pack(side="left")
        ttk.Entry(row, textvariable=self.BT_cost, width=10).pack(side="left")

        ttk.Label(row, text="Slam Cost").pack(side="left")
        ttk.Entry(row, textvariable=self.slam_cost, width=10).pack(side="left")

        ttk.Label(row, text="WW Cost").pack(side="left")
        ttk.Entry(row, textvariable=self.ww_cost, width=10).pack(side="left")

        ttk.Label(row, text="HS Cost").pack(side="left")
        ttk.Entry(row, textvariable=self.HS_cost, width=10).pack(side="left")

        row = ttk.Frame(frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Bloodlust Time (s)").pack(side="left")
        ttk.Entry(row, textvariable=self.bloodlust_time, width=10).pack(side="left")
        ttk.Label(row, text="Bloodfury Time (s)").pack(side="left")
        ttk.Entry(row, textvariable=self.bloodfury_time, width=10).pack(side="left")

         # ---------- Main Hand Procs ----------
        mh_frame = ttk.LabelFrame(frame, text="Main Hand Procs")
        mh_frame.pack(fill="x", pady=4)
        for proc, var in self.MH_proc_vars.items():
            ttk.Checkbutton(mh_frame, text=proc, variable=var).pack(side="left", padx=5)

        # ---------- Off-Hand Procs ----------
        oh_frame = ttk.LabelFrame(frame, text="Off-Hand Procs")
        oh_frame.pack(fill="x", pady=4)
        for proc, var in self.OH_proc_vars.items():
            ttk.Checkbutton(oh_frame, text=proc, variable=var).pack(side="left", padx=5)
       

    # ---------- Results Labels ----------
    def _create_results(self, frame):
        parent = self.results_frame
        self.mean_label = ttk.Label(parent, text="Mean DPS: -")
        self.white_MH_label = ttk.Label(parent, text="White MH DPS: -")
        self.white_OH_label = ttk.Label(parent, text="White OH DPS: -")
        self.hs_label = ttk.Label(parent, text="Heroic Strike DPS: -")
        self.slam_MH_label = ttk.Label(parent, text="Slam MH DPS: -")
        self.slam_OH_label = ttk.Label(parent, text="Slam OH DPS: -")
        self.WW_label = ttk.Label(parent, text="WW DPS: -")
        self.BT_label = ttk.Label(parent, text="BT DPS: -")
        self.ambi_label = ttk.Label(parent, text="Ambi Hit DPS: -")
        self.flurry_label = ttk.Label(parent, text="Flurry uptime: -")
        self.enrage_label = ttk.Label(parent, text="Enrage uptime: -")
        self.crusader_label = ttk.Label(parent, text="Crusader uptime: -")
        self.crusader_oh_label = ttk.Label(parent, text="Crusader oh uptime: -")
        self.Empyrian_Demolisher_label = ttk.Label(parent, text="Empyrian Demolisher uptime: -")
        self.dw_label = ttk.Label(parent, text="Deep Wounds DPS: -")
        self.rend_label = ttk.Label(parent, text="Rend Garg DPS: -")
        self.dmg_proc_label = ttk.Label(parent, text="DMG Proc DPS: -")


        self.dwish_label = ttk.Label(parent, text="Death Wish uptime: -")
        self.dwish_label.pack(anchor="w")

        self.avg_mh_var = tk.StringVar(value="-")
        self.avg_oh_var = tk.StringVar(value="-")
        self.avg_MH_label = ttk.Label(parent, text="Avg MH Damage:")
        self.avg_MH_value = ttk.Label(parent, textvariable=self.avg_mh_var)
        self.avg_OH_label = ttk.Label(parent, text="Avg OH Damage:")
        self.avg_OH_value = ttk.Label(parent, textvariable=self.avg_oh_var)

        for lbl in [self.mean_label, self.white_MH_label, self.white_OH_label, self.hs_label,
                    self.slam_MH_label, self.slam_OH_label, self.WW_label, self.BT_label, self.ambi_label,
                    self.flurry_label, self.enrage_label, self.crusader_label, self.crusader_oh_label, self.Empyrian_Demolisher_label,
                    self.dw_label, self.rend_label,self.dmg_proc_label,
                    self.avg_MH_label, self.avg_MH_value, self.avg_OH_label, self.avg_OH_value]:
            lbl.pack(anchor="w", pady=1)

    # ---------- Simulation Methods ----------
    def _run_simulation_thread(self):
        thread = threading.Thread(target=self._run_simulation)
        thread.start()

    def _run_simulation(self):
        self.run_button.config(state="disabled")
        try:
            stats = {k: v.get() for k, v in self.stats.items()}

            selected_MH_procs = [proc for proc, var in self.MH_proc_vars.items() if var.get() == 1]
            selected_OH_procs = [proc for proc, var in self.OH_proc_vars.items() if var.get() == 1]

            stats["MH_procs"] = selected_MH_procs
            stats["OH_procs"] = selected_OH_procs
            stats["icon"] = self.icon.get()
            stats["trauma"] = self.trauma.get()
            stats["HoJ"] = self.HoJ.get()
            stats["bloodlust_time"] = self.bloodlust_time.get()
            stats["bloodfury_time"] = self.bloodfury_time.get()

            result = run_simulation(
                iterations=self.iterations.get(),
                mh_speed=self.mh_speed.get(),
                oh_speed=self.oh_speed.get(),
                fight_length=self.fight_length.get(),
                stats=stats,
                dual_wield=self.dual_wield.get(),
                multi=self.multi.get(),
                battering_ram=self.battering_ram.get(),
                tank_dummy = self.tank_dummy.get(),
                ambi_ME=self.ambi_ME.get(),
                skull_cracker=self.skull_cracker.get(),
                kings = self.kings.get(),
                str_earth = self.str_earth.get(),
                shamanistic_rage = self.shamanistic_rage.get(),
                faeri = self.faeri.get(),
                sunders = self.sunders.get(),
                bashguuder = self.bashguuder.get(),
                icon = self.icon.get(),
                trauma = self.trauma.get(),
                HoJ = self.HoJ.get(),
                outrage = self.outrage.get(),
                BT_COST=self.BT_cost.get(),
                slam_COST=self.slam_cost.get(),
                ww_COST=self.ww_cost.get(),
                HS_COST=self.HS_cost.get()
            )
            self._show_results(result)
            self.last_result = result

            
        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            self.run_button.config(state="normal")

    def _show_results(self, result):
        self.mean_label.config(text=f"Mean DPS: {result['mean_total_dps']:.1f}")
        self.white_MH_label.config(text=f"White MH DPS: {result['mean_white_MH_dps']:.1f}")
        self.white_OH_label.config(text=f"White OH DPS: {result['mean_white_OH_dps']:.1f}")
        self.slam_MH_label.config(text=f"Slam MH DPS: {result['mean_slam_MH_dps']:.1f}")
        self.slam_OH_label.config(text=f"Slam OH DPS: {result['mean_slam_OH_dps']:.1f}")
        self.ambi_label.config(text=f"AMbi Hit DPS: {result['mean_ambi_dps']:.1f}")
        self.hs_label.config(text=f"Heroic Strike DPS: {result['mean_hs_dps']:.1f}")
        self.WW_label.config(text=f"WW DPS: {result['mean_WW_dps']:.1f}")
        self.BT_label.config(text=f"BT DPS: {result['mean_BT_dps']:.1f}")
        self.flurry_label.config(text=f"Flurry uptime: {result['avg_flurry_uptime']*100:.1f}%")
        self.enrage_label.config(text=f"Enrage uptime: {result['avg_enrage_uptime']*100:.1f}%")
        self.crusader_label.config(text=f"Crusader uptime: {result['avg_crusader_uptime']*100:.1f}%")
        self.crusader_oh_label.config(text=f"Crusader OH uptime: {result['avg_crusader_oh_uptime']*100:.1f}%")
        self.Empyrian_Demolisher_label.config(text=f"Empyrian Demolisher uptime: {result['avg_Empyrian_Demolisher_uptime']*100:.1f}%")
        self.avg_mh_var.set(f"{result.get('mean_avg_MH_dmg', 0):.1f}")
        self.avg_oh_var.set(f"{result.get('mean_avg_OH_dmg', 0):.1f}")
        self.dw_label.config(text=f"Deep Wounds DPS: {result.get('Deep Wounds DPS', 0):.1f}")
        self.dwish_label.config(text=f"Death Wish uptime: {result['avg_death_wish_uptime']*100:.1f}%")
        self.rend_label.config(text=f"Rend Garg DPS: {result.get('mean_Rend_dps', 0):.1f}")                             
        self.dmg_proc_label.config(text=f"DMG Proc DPS: {result.get('mean_proc_dmg_dps', 0):.1f}")                             
        



        self.ax.clear()
        self.ax.hist(result['results_total'], bins=30, color='skyblue', edgecolor='black')
        self.ax.set_title("Total DPS Distribution")
        self.ax.set_xlabel("DPS")
        self.ax.set_ylabel("Frequency")
        self.canvas.draw()

    def _show_attack_counts(self):
       try:
           # Check if last simulation result exists
           if not hasattr(self, "last_result"):
               messagebox.showinfo("Info", "Run a simulation first!")
               return
    
           counts_text = ""
           # Iterate over fights
           for i, fight_counts in enumerate(self.last_result['all_attack_counts']):
               counts_text += f"Fight {i+1}:\n"
               for atk, val in fight_counts.items():
                   counts_text += f"  {atk}: Hits={val['hits']}, Crits={val['crits']}, Misses={val['misses']}\n"
               counts_text += "\n"
    
           # Show in a scrollable window
           win = tk.Toplevel(self)
           win.title("All Attack Counts")
           text = tk.Text(win, width=60, height=30)
           text.pack(side="left", fill="both", expand=True)
           scrollbar = ttk.Scrollbar(win, command=text.yview)
           scrollbar.pack(side="right", fill="y")
           text.configure(yscrollcommand=scrollbar.set)
           text.insert("1.0", counts_text)
           text.config(state="disabled")
    
       except Exception as e:
           messagebox.showerror("Error", str(e))





if __name__ == "__main__":
    app = WarriorSimApp()
    app.mainloop()
