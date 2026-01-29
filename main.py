from gui.app import WarriorSimApp  # import the Tkinter GUI

if __name__ == "__main__":
    import multiprocessing as mp
    mp.freeze_support()   # REQUIRED on Windows

    app = WarriorSimApp()
    app.mainloop()

