# Reviewer Notes: Closing-Velocity Feature

*(Antigravity Review Notes)*

I agree completely with the data-directed approach and your recommendation to run **(a) the closing-velocity feature** first. It is surgical, it directly targets the POMDP observability hole revealed by the ~5x death-rate skew, and it cleanly avoids confounding observability with the decision-quantization issue.

If Claude is going to implement this, here are my architectural recommendations to ensure it's done smoothly:

## 1. The Driver Implementation (`game/chrome_driver.py`)
To compute the `Δx/frame` closing velocity, the driver needs state across frames. 
- **Recommendation:** Add a `_prev_obstacles_x` dictionary or list to `DinoDriver`. 
- **The Edge Case:** When an obstacle appears for the very first time on screen, there is no `prev_x` to compute `Δx`. 
- **The Fix:** Default the closing velocity to the current game `speed`. Since the bird offset is tiny (±0.8), using the base speed for a single frame is a safe and robust fallback.

## 2. The Sim Implementation (`game/dino_env.py`)
The simulator already has perfect knowledge of the bird's `speed_offset`. 
- **Recommendation:** Do not bother tracking `prev_x` in the simulator. Simply compute closing velocity as `self.speed + ob.speed_offset` for birds (and `self.speed` for cacti). This is computationally cheaper and perfectly mimics the discrete calculation the driver will do.
- **Feature Array Update:** Increment `N_FEATURES` to 28. Normalize the new closing velocity features (e.g., `(cv - 6.0) / 7.0`, mimicking the speed normalization) and append them right after the `cadence` feature (at indices 20 and 21).

## 3. Configuration (`config.py`)
- **Recommendation:** Update `DQN_CONFIG["network_layers"]` from `[26, 128, 64]` to `[28, 128, 64]`.
- **Note for older checkpoints:** Remind Claude that loading older models like the July 7 champion will now require passing `--layers 26,256,128` explicitly since the default config is moving to 28 features.

## Summary
Proceed with option (a). It's the most rigorous next step. If it resolves the bird skew but endurance doesn't lift globally, we can confidently move on to the poll-rate experiment (c) knowing observability is no longer the bottleneck.
