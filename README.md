# Kosmos

An experimental image-to-MIDI tool for astronomical images.

Kosmos analyzes astronomical images, detects stars, dominant colors, and brightness, and converts this information into MIDI events that can be routed to a DAW such as Ableton Live. The generated MIDI can be used to control synthesizers and create music directly from the visual structure of an image.

---

## Features

- Detects and classifies small and large stars.
- Extracts dominant colors and reduces the image to a simplified color palette.
- Maps star position, size, color, and brightness to MIDI events.
- Creates virtual MIDI ports for seamless integration with a DAW.
- Allows image processing and detection parameters to be configured through a JSON file.
- Provides three dedicated MIDI outputs: **Stars**, **Bass**, and **Clock**.

---

## Requirements

- Python 3.11 or later
- macOS, Linux, or Windows
- `python-rtmidi` for virtual MIDI ports
- Ableton Live or any DAW that supports virtual MIDI ports

---

## Installation

1. Clone the repository:

```bash
git clone https://github.com/your-username/Kosmos.git
cd Kosmos
```

2. Create and activate a virtual environment:

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows**

```powershell
python -m venv .venv
.venv\Scripts\activate
```

3. Install the project dependencies:

```bash
pip install -r requirements.txt
```

---

## Configuration

Kosmos is configured through a JSON file. An example configuration is provided in `conf.json`.

### Key configuration options

| Parameter | Description |
|-----------|-------------|
| `star_detector.white_threshold.v` | HSV value threshold for bright pixels |
| `star_detector.white_threshold.s` | HSV saturation threshold for bright pixels |
| `star_detector.brightness_threshold` | Minimum brightness required to classify a star |
| `star_detector.small_stars.contrast` | Minimum contrast for detecting small stars |
| `tempo.bpm` | Tempo in beats per minute |
| `tempo.subdivision` | Beat subdivision |
| `instrument.bass_speed_beats` | Playback speed of bass notes |
| `instrument.bass_max_note_duration_beats` | Maximum duration of bass notes |
| `instrument.stars_speed_beats` | Playback speed of star notes |
| `images.saturation_boost` | Saturation applied before color extraction |
| `images.tolerance` | Color clustering tolerance |
| `images.blur` | Blur amount applied before processing |
| `instruments_name` | Names assigned to the MIDI outputs |

---

## Usage

Run the application by providing a configuration file and an input image:

```bash
python src/main.py conf.json path/to/space-image.jpg -o output
```

Where:

- `conf.json` is the configuration file.
- `path/to/space-image.jpg` is the input image.
- `-o output` specifies the directory where generated files and preview images are saved.

---

## Connecting to Ableton Live

1. On macOS, enable the **IAC Driver** in **Audio MIDI Setup**.
2. Create a MIDI track in Ableton Live.
3. Select one of the virtual MIDI ports created by Kosmos as the MIDI input.

Kosmos exposes the following virtual MIDI ports:

- `kosmos_stars`
- `kosmos_bass`
- `kosmos_clock`

---

## How It Works

1. Load the input RGB image.
2. Apply saturation enhancement and optional blur.
3. Group similar colors using a **Magic Wand–style** region-growing algorithm.
4. Detect and classify bright stars as either small or large.
5. Calculate each star's MIDI pitch, velocity, and stereo panning based on its position, color, and brightness.
6. Generate `note_on` and `note_off` MIDI messages for playback in the selected DAW.

---

## Customization

Kosmos is highly configurable. You can adjust both the image analysis and MIDI generation parameters to achieve different musical results.

For example, you can:

- Adjust brightness and saturation thresholds for different types of images.
- Modify `stars_speed_beats` to change playback speed.
- Rename MIDI outputs through `instruments_name` to better organize tracks in your DAW.
- Experiment with different astronomical images to generate unique musical patterns.

---

## Notes

- Kosmos generates MIDI signal from the visual structure of astronomical images.
- The current implementation focuses on **Stars** and **Bass**, but the architecture is designed for future expansion with additional instruments such as pads or leads.
- If you are using Ableton Live, make sure the virtual MIDI ports are available before starting the application.

---
