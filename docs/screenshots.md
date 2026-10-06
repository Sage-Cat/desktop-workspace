# README screenshots

Both images are native, full-desktop captures from GNOME Shell 46 on Wayland,
1920 × 1200 at scale 1. They were captured on 2026-10-06 without image editing.

- `hud-and-desktop.png`: the real Login HUD renders example ready-stage telemetry over four running applications.
- `desktop-apps.png`: the same desktop after dismissing the HUD: Alacritty with three tmux tabs, Chrome with two local example pages, VS Code and Nemo opening an example project.

The capture used a disposable compositor, session bus, application profiles and
tmux socket. No personal profiles, credentials or conversation data were used.
Window identities and geometry were checked before capture; the HUD held no
modal input grab. PNG metadata contains only the capture software and time.

These are UI demonstrations. Actual restoration and shutdown/boot results are
recorded in [validation](validation.md). [Provenance](images/provenance.json)
records the HUD revision, source digests and image checksums.
