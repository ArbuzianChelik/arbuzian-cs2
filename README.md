# 🍉 ARBUZIAN CS2

Python-based external cheat for Counter-Strike 2
Semi-working / educational project. Use at your own risk.
⚠️ Disclaimer

This project is for educational purposes only.

    ❌ No VAC bypass — and there never will be one.

    ✅ Use only on your own local server or in offline mode with bots.

    🚫 The author is not responsible for any bans or damage caused by using this software.

By using this software you agree that you are solely responsible for your actions.
✨ Features
🎯 Aimbot

    Smooth Aimbot with adjustable FOV, smoothing, and humanization.

    Hitbox selection — Head, Neck, Chest, Stomach.

    Target priority — closest to crosshair (FOV), lowest HP, or distance.

    Visibility check — aims only at visible enemies.

    RCS (Recoil Control System) — compensates recoil while spraying.

🔫 Silent Aim

    Silent Aim — snaps bullets to targets without moving your view.

    360° Aim — works even for enemies behind you (world-angle based).

    Silent FOV and hold duration adjustable.

    Visibility filter for silent aim.

👁 Visuals (ESP)

    Player ESP: Box, Corner Box, Skeleton, Health bar, Name, Distance, Weapon, Tracer, Fill.

    Bomb ESP — shows planted C4.

    Radar Hack — reveals enemies on radar.

    No Flash — disables flashbang effect.

    FOV Circle — visualizes aimbot FOV.

🦘 Movement

    Bunnyhop (Bhop) — auto-jump with +jump force flag.

    Auto Strafe — key-based or velocity-based strafe to gain speed mid-air.

    Supports both simple key strafe and rage-style autofly.

💥 Anti-Aim

    Spinbot — Spin, Jitter, or Random modes with adjustable speed and range.

    Desync — fake body yaw (Left / Right / Random).

    Optional hotkey for spinbot.

🖱 Triggerbot

    Automatically fires when an enemy is in your crosshair.

    Adjustable delay (ms).

🛠 Requirements

    Windows 10/11 (x64)

    Python 3.8+

    Counter-Strike 2 running in windowed or fullscreen windowed mode (borderless).

    Run as Administrator (required to read/write game memory).

Python packages

pip install customtkinter

(tkinter is included with standard Python on Windows.)

🚀 Installation & Usage

    Clone the repository:

    git clone https://github.com/ArbuzianChelik/arbuzian-cs2.git
    cd arbuzian-cs2

    Install dependencies:

    pip install customtkinter

    (If requirements.txt is missing, just pip install customtkinter.)

    Launch CS2 and join a local server (or offline with bots).

    Run the cheat:
    
    python main.py

    Open the menu — press INSERT.

        The overlay will appear on top of the game.

        The menu is draggable and always-on-top.

    Configure features via the sidebar:

        Aimbot, Anti-Aim, Movement, Visuals.

        Save/Load configs with the buttons at the bottom.

    Exit — press END (emergency kill switch) or close the overlay window.
