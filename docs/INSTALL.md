# Installation

## Project Setting

### Download Project from GitHub

- URL: [AWS_Client](https://github.com/Carima-SSY/AWS_Client)

### Install Python Package (Python version: 3.12.8)

1. Open the terminal.
2. Navigate to the version folder you're setting up (`src/v1/` or `src/v2/`) — that's where `requirements.txt` is located.
3. Run the following command.

   ```bash
   pip install -r requirements.txt
   ```

   > `picamera2`/`picamera` are only for Raspberry Pi CSI camera support and are marked with an environment condition in `requirements.txt`, so `pip` automatically skips them on non-Raspberry-Pi machines (Mac/Windows/x86 Linux) — no manual edit needed. `lib/cam_manager.py` falls back to OpenCV when they're unavailable. On an actual Raspberry Pi, `picamera2` may still fail to install via pip because it needs `libcamera` system bindings — in that case install it with `sudo apt install -y python3-picamera2` instead.

# Build

## Make Execution File (Program)

PyInstaller is already included in `requirements.txt`, so no separate install step is needed here.

1. Run the following command from the version folder (`src/v1/` or `src/v2/`).

   ```bash
   pyinstaller --onefile AWSClientApp.py
   ```

### Confirm Result

- Check for the executable program located at `dist/AWSClientApp.exe` (Windows) or `dist/AWSClientApp` (Linux/Raspberry Pi).
- On a Raspberry Pi, enter the following command to make it executable.

  ```bash
  chmod +x dist/AWSClientApp
  ```
