import os
import subprocess
import sys
from tkinter import Tk, filedialog
from dearpygui import dearpygui as dpg
from pydub import AudioSegment


ff_bin_dir = os.path.join(
    os.path.dirname(__file__), "redistributables", "ffmpeg", "bin"
)


FFMPEG_BIN = None
if sys.platform == "win32":
    FFMPEG_BIN = os.path.join(ff_bin_dir, "ffmpeg.exe")
elif sys.platform == "darwin":
    FFMPEG_BIN = os.path.join("ffmpeg")

# Fallback to system ffmpeg if bundled binary is missing
if FFMPEG_BIN and not os.path.isfile(FFMPEG_BIN):
    print(
        f"Bundled ffmpeg not found at {FFMPEG_BIN}, falling back to system ffmpeg on PATH."
    )
    FFMPEG_BIN = "ffmpeg"


def save_options():
    """Auto-save settings to options.json"""
    options = {
        "input_text": dpg.get_value("input_text"),
        "output_text": dpg.get_value("output_text"),
        "use_16bit": (
            dpg.get_value("use_16bit") if dpg.does_item_exist("use_16bit") else False
        ),
    }
    with open("options.json", "w") as f:
        import json

        json.dump(options, f)


def load_options():
    """Auto-load settings from options.json on startup"""
    try:
        with open("options.json", "r") as f:
            import json

            options = json.load(f)
            dpg.set_value("input_text", options.get("input_text", ""))
            dpg.set_value("output_text", options.get("output_text", ""))
            if dpg.does_item_exist("use_16bit"):
                dpg.set_value("use_16bit", options.get("use_16bit", False))
    except FileNotFoundError:
        pass


def save_sample(source_path, input_root, dest_root, use_16bit=False):
    """Convert source file to 16-bit, 44.1kHz WAV for Octatrack using ffmpeg directly."""

    if not os.path.isfile(source_path):
        raise FileNotFoundError(f"Source file not found: {source_path}")

    if FFMPEG_BIN is None:
        raise RuntimeError("FFMPEG_BIN is not set")

    rel = os.path.relpath(source_path, input_root)
    out_path = os.path.join(dest_root, os.path.splitext(rel)[0] + ".wav")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # ffmpeg command:
    # - overwrite
    # - input: source_path
    # - audio codec: 16-bit PCM
    # - sample rate: 44.1kHz
    # - channels: keep as is (or force 1/2 if you want)
    # choose output sample format by bit depth
    sample_fmt = "pcm_s16le" if use_16bit else "pcm_s24le"

    cmd = [
        FFMPEG_BIN,
        "-y",
        "-i",
        source_path,
        "-acodec",
        sample_fmt,
        "-ar",
        "44100",
        # If you want to force mono or stereo, uncomment one:
        # "-ac", "1",  # force mono
        # "-ac", "2",  # force stereo
        out_path,
    ]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=False,
    )

    if result.returncode != 0:
        # ffmpeg couldn’t decode or write it
        raise RuntimeError(
            f"ffmpeg failed for {source_path}:\n"
            f"RETURN CODE: {result.returncode}\n"
            f"STDERR:\n{result.stderr}"
        )


def count_input_files(input_path):
    """Count number of processable files (excluding Ableton .asd metadata)."""
    total = 0
    for root, dirs, files in os.walk(input_path):
        for file in files:
            if file.lower().endswith("asd"):
                continue
            total += 1
    return total


def traverse_and_convert(
    input_path, output_path, total_files=None, on_progress=None, use_16bit=False
):
    input_path = os.path.abspath(input_path)
    output_path = os.path.abspath(output_path)

    if not os.path.isdir(input_path):
        print(f"Input path not found: {input_path}")
        return

    # clear the output folder if it exists
    if os.path.exists(output_path):
        import shutil

        shutil.rmtree(output_path)

    # add name of the input folder to the output path
    input_path_name = os.path.basename(input_path.rstrip(os.sep))

    output_path = os.path.join(output_path, input_path_name)
    print(f"Saving samples to folder: {output_path}")
    processed_files = 0
    converted_files = 0
    failed_files = 0
    for root, dirs, files in os.walk(input_path):
        for file in files:
            if file.lower().endswith("asd"):
                # skip Ableton Live metadata files
                continue
            processed_files += 1
            source_path = os.path.join(root, file)
            try:
                save_sample(source_path, input_path, output_path, use_16bit=use_16bit)
                converted_files += 1
            except Exception as e:
                print(f"Skipping invalid file {source_path}: {e}")
                failed_files += 1
            # update progress if callback provided
            if on_progress is not None:
                try:
                    on_progress(
                        processed_files,
                        total_files or processed_files,
                        converted_files,
                        failed_files,
                    )
                finally:
                    try:
                        dpg.split_frame()
                    except Exception:
                        pass
    print(
        f"Conversion complete. Total files: {processed_files}, Converted: {converted_files}, Failed: {failed_files}"
    )


def convert_callback(sender, app_data, user_data):
    input_path = dpg.get_value("input_text")
    output_path = dpg.get_value("output_text")
    use_16bit = (
        dpg.get_value("use_16bit") if dpg.does_item_exist("use_16bit") else False
    )

    if not input_path or not os.path.exists(input_path):
        dpg.set_value("status_text", " Error: Invalid input path")
        return

    if not output_path:
        dpg.set_value("status_text", " Error: Please select output path")
        return

    # Pre-count files to set progress range
    total = count_input_files(input_path)
    if total == 0:
        dpg.set_value("status_text", " No files to convert in selected input folder")
        dpg.hide_item("progress_bar")
        return

    dpg.set_value("status_text", f" Converting... 0/{total}")
    dpg.show_item("progress_bar")
    dpg.set_value("progress_bar", 0.0)
    try:
        dpg.configure_item("progress_bar", overlay="0%  0/0")
    except Exception:
        pass

    print(f"Converting from \n\t{input_path} \nto \n\t{output_path}")

    def progress_update(done, total_files, converted, failed):
        ratio = max(0.0, min(1.0, (done / total_files) if total_files else 0.0))
        dpg.set_value("progress_bar", ratio)
        try:
            dpg.configure_item(
                "progress_bar", overlay=f"{int(ratio*100)}%  {done}/{total_files}"
            )
        except Exception:
            pass
        dpg.set_value(
            "status_text",
            f" Converting... {done}/{total_files} (ok:{converted}, failed:{failed})",
        )

    traverse_and_convert(
        input_path,
        output_path,
        total_files=total,
        on_progress=progress_update,
        use_16bit=use_16bit,
    )

    dpg.set_value("progress_bar", 1.0)
    try:
        dpg.configure_item("progress_bar", overlay=f"100%  {total}/{total}")
    except Exception:
        pass
    dpg.set_value("status_text", " Conversion complete!")


def input_folder_selected_callback(sender, app_data, user_data):
    """Open native folder dialog for input selection"""
    # Hide tkinter root window
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    # Get current value as initial directory
    current = dpg.get_value("input_text")
    initial_dir = current if current and os.path.exists(current) else None

    # Show native folder picker
    path = filedialog.askdirectory(title="Select Input Folder", initialdir=initial_dir)
    root.destroy()

    if path:
        dpg.set_value("input_text", path)
        save_options()  # Auto-save when folder is selected


def output_folder_selected_callback(sender, app_data, user_data):
    """Open native folder dialog for output selection"""
    # Hide tkinter root window
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    # Get current value as initial directory
    current = dpg.get_value("output_text")
    initial_dir = current if current and os.path.exists(current) else None

    # Show native folder picker
    path = filedialog.askdirectory(title="Select Output Folder", initialdir=initial_dir)
    root.destroy()

    if path:
        dpg.set_value("output_text", path)
        save_options()  # Auto-save when folder is selected


dpg.create_context()

# Setup theme
with dpg.theme() as global_theme:
    with dpg.theme_component(dpg.mvAll):
        dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (20, 20, 25))
        dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (40, 40, 50))
        dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (60, 60, 70))
        dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, (70, 70, 80))
        dpg.add_theme_color(dpg.mvThemeCol_Button, (60, 90, 180))
        dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (80, 110, 200))
        dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (50, 80, 160))
        dpg.add_theme_color(dpg.mvThemeCol_TitleBg, (30, 30, 40))
        dpg.add_theme_color(dpg.mvThemeCol_TitleBgActive, (40, 40, 50))
        dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 5)
        dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 20, 20)
        dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 10, 8)
        dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 10, 12)

dpg.bind_theme(global_theme)

dpg.create_viewport(title="Sample Converter", width=650, height=750)

with dpg.window(
    label="Sample Converter",
    tag="main_window",
    no_collapse=True,
    no_close=True,
    no_resize=True,
    no_move=True,
    no_title_bar=True,
):

    # Title Section
    dpg.add_text("Audio Sample Converter For Octatrack", tag="title_text")
    with dpg.theme() as title_theme:
        with dpg.theme_component(dpg.mvText):
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 0, 20)
    dpg.bind_item_theme("title_text", title_theme)

    dpg.add_text("Convert audio samples to 16-bit, 44.1kHz WAV format")
    dpg.add_spacer(height=10)
    dpg.add_separator()
    dpg.add_spacer(height=20)

    # Input Section
    with dpg.group(horizontal=False):
        dpg.add_text("Input Folder", color=(150, 200, 255))
        with dpg.group(horizontal=True):
            dpg.add_input_text(
                tag="input_text", width=480, hint="Select source folder..."
            )
            dpg.add_button(
                label="Browse",
                width=100,
                callback=input_folder_selected_callback,
            )

    dpg.add_spacer(height=15)

    # Output Section
    with dpg.group(horizontal=False):
        dpg.add_text("Output Folder", color=(150, 255, 200))
        with dpg.group(horizontal=True):
            dpg.add_input_text(
                tag="output_text",
                width=480,
                readonly=True,
                hint="Select destination folder...",
            )
            dpg.add_button(
                label="Browse",
                width=100,
                callback=output_folder_selected_callback,
            )

    dpg.add_spacer(height=25)
    dpg.add_separator()
    dpg.add_spacer(height=20)

    # Output Format Section
    with dpg.group(horizontal=True):
        dpg.add_checkbox(
            tag="use_16bit",
            label="Export 16-bit WAV (default is 24-bit)",
            default_value=False,
            callback=lambda s, a, u: save_options(),
        )

    # Convert Button
    with dpg.group(horizontal=True):
        dpg.add_button(
            label="Convert Samples", callback=convert_callback, width=300, height=45
        )
        with dpg.theme() as convert_button_theme:
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (80, 180, 80))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (100, 200, 100))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (60, 160, 60))
        dpg.bind_item_theme(dpg.last_item(), convert_button_theme)

    # Progress Bar
    dpg.add_spacer(height=15)
    dpg.add_progress_bar(tag="progress_bar", width=-1, show=False)

    # Status Section
    dpg.add_spacer(height=10)
    dpg.add_text("", tag="status_text", color=(200, 200, 200))


dpg.setup_dearpygui()
dpg.show_viewport()

# Set main window as primary (fills viewport)
dpg.set_primary_window("main_window", True)

# Auto-load saved settings on startup
load_options()
dpg.start_dearpygui()
dpg.destroy_context()
