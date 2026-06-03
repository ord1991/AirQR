## 2025-05-15 - [OpenCV Status Overlay & GUI Closure]
**Learning:** In headless or CLI-first tools that open GUI windows (like OpenCV), users tend to focus exclusively on the graphical window. Lack of status feedback in the GUI and failure to respond to the window's close (X) button are major friction points.
**Action:** Always provide a status overlay and a "Quit" hint in the primary GUI window, and implement GUI-native window closure detection alongside keyboard-based exit.
