import dearpygui.dearpygui as dpg
import dearpygui.demo as demo
import dearpygui_map as dpg_map
from math import sin, cos
from src import esp32_controller
from src import signal_processor
import time
import threading
import queue


def gui_query_thread_method():
    while True:
        global hackrf_id, sp, ready_to_query, telemetry_data_1, telemetry_data_2, device_center_frequency_from_gui, device_sample_rate_from_gui, device_sample_count_from_gui, device_amplifier, currently_scanning, device, inbound_data_queue

        command = outbound_command_queue.get(block=True, timeout=None)
        # print(f"Command received: {command}")

        if command == "start_device":
            device = esp32_controller.ESP32Controller()
            sp = signal_processor.SignalProcessor(id=hackrf_id)
            device.assign_signal_processor(signal_processor=sp)
            device.initialize()
            device_center_frequency_from_gui = device.sp.center_freq
            device_sample_rate_from_gui = device.sp.sample_rate
            device_sample_count_from_gui = device.sp.sample_count
            device_amplifier = device.sp.aplifier_on
            inbound_data_queue = device.return_queue

            ready_to_query = True

        if command == "stop_device":
            device.stop()

        if command == "get_telemetry":
            if currently_scanning:
                continue
            telemetry_data_1 = device.get_telemetry(1)
            telemetry_data_2 = device.get_telemetry(2)

        if command == "set_frequency":
            device.sp.center_freq = device_center_frequency_from_gui

        if command == "toggle_amplifier":
            device.sp = not device.sp.aplifier_on

        if command == "set_sample_rate":
            device.sp.sample_rate = device_sample_rate_from_gui

        if command == "set_sample_count":
            device.sp.sample_count = device_sample_count_from_gui

        if command == "perform_full_scan":

            def perform_full_scan_method():
                global inbound_data_queue, currently_scanning
                inbound_data_queue = device.return_queue
                try:
                    device.full_sweep_optimal()
                except esp32_controller.stopEverything:
                    print("Device was stopped")
                    currently_scanning = False
            
            currently_scanning = True
            try:
                device_thread = threading.Thread(target=perform_full_scan_method)
                device_thread.daemon = True
                device_thread.start()
            except esp32_controller.stopEverything:
                print("Device was stopped")
                currently_scanning = False


def import_data_thread_method():
    while True:
        global inbound_data_queue, graph_data, telemetry_data_1, telemetry_data_2

        if not ready_to_query:
            continue
        
        data = inbound_data_queue.get(block=True, timeout=None)
        print("Data gotten:", len(data), len(data[0]), len(data[1]), len(data[2]), len(data[3]))
        print("Raw:", len(data[1][0]), len(data[1][1]))
        print(data[1][0][0:5])
        print(data[1][1][0:5])

        if data is None:
            continue
        
        signals = data[0]
        raw_data = data[1]
        print(len(raw_data))
        telem1 = data[2]
        telem2 = data[3]
        graph_data = raw_data

        if telem1 is not None and type(telem1) is dict:
            telemetry_data_1 = telem1
        if telem2 is not None and type(telem2) is dict:
            telemetry_data_2 = telem2


        text = f"Signals: {signals}" if len(signals) >= 1 else "No signals found"
        add_to_console_table(text)


def button_callback(sender, app_data, user_data):
    print(f"sender is: {sender}")
    print(f"app_data is: {app_data}")
    print(f"user_data is: {user_data}")
    if sender == "initialize_button_pressed":
        start_device()
    if sender == "start_full_scan_pressed":
        outbound_command_queue.put("perform_full_scan")
    if sender == "stop_scan_pressed":
        outbound_command_queue.put("stop_device")


def set_hackrf_id(sender):
    global hackrf_id
    hackrf_id = int(dpg.get_value(sender))


def start_device():
    outbound_command_queue.put("start_device")


def update_series():
    global graph_data
    if graph_data is None:
        return
    if len(graph_data[0]) == 0 or len(graph_data[1]) == 0:
        return
    x = [v for v in graph_data[0]]
    y = [v for v in graph_data[1]]
    dpg.set_value("series_tag", [y, x])
    dpg.set_item_label("series_tag", "Current Scan Data")


def update_telemetry_table():
    global telemetry_data_1, telemetry_data_2

    if telemetry_data_1 is None or telemetry_data_2 is None:
        return

    dpg.set_value("pos_1", telemetry_data_1["position"])
    dpg.set_value("pos_2", telemetry_data_2["position"])
    dpg.set_value("speed_1", telemetry_data_1["speed"])
    dpg.set_value("speed_2", telemetry_data_2["speed"])
    dpg.set_value("load_1", telemetry_data_1["load"])
    dpg.set_value("load_2", telemetry_data_2["load"])
    dpg.set_value(
        "voltage_1",
        f'{telemetry_data_1["voltage"][:-1]}.{telemetry_data_1["voltage"][-1]} V',
    )
    dpg.set_value(
        "voltage_2",
        f'{telemetry_data_2["voltage"][:-1]}.{telemetry_data_2["voltage"][-1]} V',
    )
    dpg.set_value("temperature_1", f'{telemetry_data_1["temperature"]} °C')
    dpg.set_value("temperature_2", f'{telemetry_data_2["temperature"]} °C')


def add_to_console_table(message):
    message = f'{time.strftime("%H:%M:%S")}] - {message}'
    dpg.set_value("console_row_1", dpg.get_value("console_row_1") + f"\n{message}")




def gui():
    dpg.create_context()
    dpg.create_viewport(
        title="Drone Locator GUI", width=1600, height=1000, resizable=False
    )
    with dpg.window(
        label="Dear PyGui Demo",
        width=1600,
        height=1000,
        pos=(0, 0),
        tag="__demo_id",
        no_collapse=True,
        no_move=True,
        no_resize=True,
        no_title_bar=True,
        no_close=True,
        no_scroll_with_mouse=True,
        no_scrollbar=True,
    ):
        with dpg.menu_bar():
            dpg.add_menu(label="Menu")
            dpg.add_menu(label="About")
        with dpg.group(label="top_area", horizontal=True):
            with dpg.child_window(
                height=top_area_height,
                width=400,
                no_scrollbar=True,
                no_scroll_with_mouse=True,
            ):
                dpg.add_input_int(
                    label="HackRF ID",
                    default_value=0,
                    step=1,
                    min_value=0,
                    max_value=255,
                    width=100,
                    callback=set_hackrf_id,
                )
                dpg.add_button(
                    tag="initialize_button_pressed",
                    label="Initialize Device",
                    callback=button_callback,
                )

                dpg.add_button(
                    tag="start_full_scan_pressed",
                    label="Start Full Scan",
                    callback=button_callback,
                )

                dpg.add_button(
                    tag="stop_scan_pressed", label="Stop Scan", callback=button_callback
                )
            with dpg.child_window(
                height=top_area_height,
                width=800,
                no_scrollbar=True,
                no_scroll_with_mouse=True,
                border=False,
            ):
                dpg_map.add_map_widget(
                    width=800,
                    height=top_area_height,
                    center=(60.1641, 24.9402),
                    zoom_level=14,
                )

            with dpg.child_window(
                height=top_area_height,
                width=370,
                no_scrollbar=True,
                no_scroll_with_mouse=True,
            ):
                dpg.add_text("Top right area")

        with dpg.group(label="bottom_area", horizontal=True):

            with dpg.child_window(
                height=bottom_area_height,
                width=400,
                no_scrollbar=False,
                no_scroll_with_mouse=True,
            ):
                dpg.add_button(
                    label="Update Telemetry", callback=update_telemetry_table
                )
                with dpg.table(
                    label="telemetry_table",
                    header_row=True,
                    borders_innerH=True,
                    borders_innerV=True,
                ):
                    dpg.add_table_column(label="Variable")
                    dpg.add_table_column(label="Servo 1")
                    dpg.add_table_column(label="Servo 2")

                    with dpg.table_row():
                        dpg.add_text("Position")
                        dpg.add_text(tag="pos_1", default_value="-1")
                        dpg.add_text(tag="pos_2", default_value="-1")

                    with dpg.table_row():
                        dpg.add_text("Speed")
                        dpg.add_text(tag="speed_1", default_value="-1")
                        dpg.add_text(tag="speed_2", default_value="-1")

                    with dpg.table_row():
                        dpg.add_text("Load")
                        dpg.add_text(tag="load_1", default_value="-1")
                        dpg.add_text(tag="load_2", default_value="-1")

                    with dpg.table_row():
                        dpg.add_text("Voltage")
                        dpg.add_text(tag="voltage_1", default_value="-1 V")
                        dpg.add_text(tag="voltage_2", default_value="-1 V")

                    with dpg.table_row():
                        dpg.add_text("Temperature")
                        dpg.add_text(tag="temperature_1", default_value="-1 °C")
                        dpg.add_text(tag="temperature_2", default_value="-1 °C")

            with dpg.child_window(
                height=bottom_area_height,
                width=800,
                no_scrollbar=True,
                no_scroll_with_mouse=True,
                border=False,
            ):
                dpg.add_button(label="Update Series", callback=update_series)
                # create plot
                with dpg.plot(
                    label="Last Scan Output", height=bottom_area_height, width=800,
                ):
                    # optionally create legend
                    dpg.add_plot_legend()

                    # REQUIRED: create x and y axes
                    dpg.add_plot_axis(dpg.mvXAxis, label="Frequency (Hz)")
                    dpg.add_plot_axis(dpg.mvYAxis, label="Signal Strength (dBm)", tag="y_axis", log_scale=True, lock_max=True, lock_min=True)

                    # series belong to a y axis
                    dpg.add_line_series(
                        [1.0,2.0,3.0],
                        [1.0,1.0,1.0],
                        label="0.5 + 0.5 * sin(x)",
                        parent="y_axis",
                        tag="series_tag",
                        
                    )
                    
            with dpg.child_window(
                height=bottom_area_height,
                width=370,
                no_scrollbar=False,
                no_scroll_with_mouse=False,
            ):
                dpg.add_text("Bottom right area", tag="console_row_1")

        with dpg.group(horizontal=True):
            dpg.add_button(label="Footer 1", width=175)
            dpg.add_text("Footer 2")
            dpg.add_button(label="Footer 3", width=175)
            dpg.add_text("Footer 4")

    dpg.setup_dearpygui()
    dpg.show_viewport()
    first_run = True
    last_time = time.time()
    # update telemetry table every second from the global variables
    while dpg.is_dearpygui_running():
        if first_run:
            first_run = False
            gui_query_thread = threading.Thread(target=gui_query_thread_method)
            gui_query_thread.daemon = True

            import_data_thread = threading.Thread(target=import_data_thread_method)
            import_data_thread.daemon = True
            import_data_thread.start()
            gui_query_thread.start()

        current_time = time.time()
        if ready_to_query:
            # Things to do every second
            if current_time > last_time + 0.5:
                # Request data
                if not currently_scanning:
                    outbound_command_queue.put("get_telemetry")
                # Update telemetry table
                update_telemetry_table()
                last_time = current_time

            if current_time > last_time + 0.1:
                # Update series
                update_series()

        dpg.render_dearpygui_frame()

    dpg.destroy_context()



# Gui stuff
top_area_height = 550
bottom_area_height = 350

# Device stuff
hackrf_id = 0
device = None
sp = None

device_center_frequency_from_gui = 0
device_sample_rate_from_gui = 0
device_sample_count_from_gui = 0
device_amplifier = False


ready_to_query = False
currently_scanning = False

# Variables
telemetry_data_1 = None
telemetry_data_2 = None
graph_data = None

outbound_command_queue = queue.Queue()
inbound_data_queue = queue.Queue()


# device = esp32_controller.ESP32Controller()
# sp = signal_processor.SignalProcessor(id=hackrf_id)
# device.assign_signal_processor(signal_processor=sp)
# device.initialize()

gui()