import math
import dearpygui.dearpygui as dpg
import dearpygui.demo as demo
import dearpygui_map as dpg_map
from math import sin, cos
from src import esp32_controller
from src import signal_processor
from src.data_structs import ChannelDict
import time
import threading
import queue
import logging
import datetime


def gui_query_thread_method():
    while True:
        global hackrf_id, sp, ready_to_query, telemetry_data_1, telemetry_data_2, device_center_frequency_from_gui, device_sample_rate_from_gui, device_sample_count_from_gui, device_amplifier, currently_scanning, device, inbound_data_queue, device_vga_gain_from_gui

        command = outbound_command_queue.get(block=True, timeout=None)
        # print(f"Command received: {command}")

        if command == "start_device":
            device = esp32_controller.ESP32Controller()
            database = ChannelDict()
            sp = signal_processor.SignalProcessor(id=hackrf_id, database=database)
            device.assign_signal_processor(signal_processor=sp)
            device.initialize()
            device_center_frequency_from_gui = device.sp.hackrf.center_freq
            device_sample_rate_from_gui = device.sp.hackrf.sample_rate
            device_sample_count_from_gui = device.sp.sample_count
            device_amplifier = device.sp.hackrf.amplifier_on
            device_vga_gain_from_gui = device.sp.hackrf.vga_gain
            inbound_data_queue = device.return_queue

            ready_to_query = True
            dpg.enable_item("start_full_scan_button")
            dpg.enable_item("stop_scan_button")
            dpg.enable_item("toggle_amplifier_button")
            dpg.enable_item("move_antenna_front_button")
            dpg.enable_item("perform_single_scan_button")
            dpg.enable_item("start_horizontal_scan_button")
            dpg.enable_item("continuously_scan_button")
            dpg.enable_item("update_parameters_button")
            dpg.enable_item("start_section_scan_button")

        if command == "stop_device":
            device.stop()

        if command == "get_telemetry":
            if currently_scanning:
                continue
            else:
                telemetry_data_1 = device.get_telemetry(1)
                telemetry_data_2 = device.get_telemetry(2)

        if command == "perform_full_scan":
            currently_scanning = True
            try:
                device_thread = threading.Thread(
                    target=perform_full_scan_method, daemon=True
                )
                device_thread.start()
            except esp32_controller.stopEverything:
                # print("Device was stopped")
                device_thread = None
                currently_scanning = False

        if command == "perform_horizontal_scan":
            currently_scanning = True
            try:
                device_thread = threading.Thread(
                    target=perform_horizontal_scan_method, daemon=True
                )
                device_thread.start()
            except esp32_controller.stopEverything:
                # print("Device was stopped")
                currently_scanning = False
                device_thread = None
                
        if command == "perform_section_scan":
            currently_scanning = True
            try:
                device_thread = threading.Thread(
                    target=perform_section_scan_method, daemon=True
                )
                device_thread.start()
            except esp32_controller.stopEverything:
                # print("Device was stopped")
                currently_scanning = False
                device_thread = None
            

        if command == "move_antenna_front":
            device.go_to_forward()

        if command == "perform_single_scan":
            device.perform_scan()

        if command == "continuously_scan":
            currently_scanning = True
            try:
                device_thread = threading.Thread(
                    target=perform_continuous_scan_method, daemon=True
                )
                device_thread.start()
            except esp32_controller.stopEverything:
                # print("Device was stopped")
                currently_scanning = False
                device_thread = None


def perform_horizontal_scan_method():
    global inbound_data_queue, currently_scanning, horizontal_scan_points, horizontal_scan_elevation
    inbound_data_queue = device.return_queue
    try:
        device.horizontal_sweep_precise(
            number_of_points=horizontal_scan_points, y_level=horizontal_scan_elevation
        )
        currently_scanning = False
    except esp32_controller.stopEverything:
        # print("Device was stopped")
        currently_scanning = False

def perform_section_scan_method():
    global inbound_data_queue, currently_scanning, section_scan_points, section_scan_elevation, section_scan_start, section_scan_end
    inbound_data_queue = device.return_queue
    try:
        device.horizontal_section_sweep_precise(section_start=int(section_scan_start), section_end=int(section_scan_end),   
            number_of_points=section_scan_points, y_level=section_scan_elevation
        )
        currently_scanning = False
    except esp32_controller.stopEverything:
        # print("Device was stopped")
        currently_scanning = False

def perform_full_scan_method():
    global inbound_data_queue, currently_scanning
    inbound_data_queue = device.return_queue
    try:
        device.full_sweep_optimal()
        currently_scanning = False
    except esp32_controller.stopEverything:
        # print("Device was stopped")
        currently_scanning = False


def perform_continuous_scan_method():
    global inbound_data_queue, currently_scanning
    inbound_data_queue = device.return_queue
    try:
        device.continuously_scan()
    except esp32_controller.stopEverything:
        # print("Device was stopped")
        currently_scanning = False


def import_data_thread_method():
    while True:
        global inbound_data_queue, graph_data, telemetry_data_1, telemetry_data_2

        if not ready_to_query:
            continue

        data = inbound_data_queue.get(block=True, timeout=None)
        # print("Data gotten:", len(data), len(data[0]), len(data[1]), len(data[2]), len(data[3]))
        # print("Raw:", len(data[1][0]), len(data[1][1]))
        # print(data[1][0][0:5])
        # print(data[1][1][0:5])

        if data is None:
            continue

        signals = data[0]
        raw_data = data[1]
        # print(len(raw_data))
        telem1 = data[2]
        telem2 = data[3]
        graph_data = raw_data

        if telem1 is not None and type(telem1) is dict:
            telemetry_data_1 = telem1
        if telem2 is not None and type(telem2) is dict:
            telemetry_data_2 = telem2

        text = ""
        for signal in signals:
            text += f"{signal.channel if signal.channel != None else '?'} | {round(signal.peak_freq, 4)} MHz | {signal.peak_power_db} dBm\n"
            logger.info(signal.to_log_string())
        add_to_console_table(text)



def button_callback(sender, app_data, user_data):
    global device, horizontal_scan_points, device_sample_rate_from_gui, device_center_frequency_from_gui, horizontal_scan_elevation, device_vga_gain_from_gui, section_scan_points, section_scan_elevation, section_scan_end, section_scan_start
    # print(f"sender is: {sender}")
    # print(f"app_data is: {app_data}")
    # print(f"user_data is: {user_data}")
    if sender == "initialize_button":
        start_device()
    elif sender == "start_full_scan_button":
        outbound_command_queue.put("perform_full_scan")
        # dpg.disable_item("start_full_scan_button")
    elif sender == "start_horizontal_scan_button":
        # update global variables
        horizontal_scan_points = dpg.get_value("horizontal_scan_points")
        horizontal_scan_elevation = dpg.get_value("horizontal_scan_elevation")
        # dpg.disable_item("perform_horizontal_scan_button")
        outbound_command_queue.put("perform_horizontal_scan")
    elif sender == "start_section_scan_button":
        # update global variables
        section_scan_points = dpg.get_value("section_scan_points")
        section_scan_elevation = dpg.get_value("section_scan_elevation")
        section_scan_start = dpg.get_value("section_scan_start")
        section_scan_end = dpg.get_value("section_scan_end")
        # dpg.disable_item("perform_horizontal_scan_button")
        outbound_command_queue.put("perform_section_scan")
    
    elif sender == "stop_scan_button":
        outbound_command_queue.put("stop_device")
        # dpg.enable_item("perform_horizontal_scan_button")
        # dpg.enable_item("start_full_scan_button")
    elif sender == "toggle_amplifier_button":
        device.sp.set_amplifier(not device.sp.hackrf.amplifier_on)
        # print(f"Amplifier is now: {device.sp.hackrf.amplifier_on}")
        dpg.set_value(
            "amplifier_status",
            f"Amplifier is {'on' if device.sp.hackrf.amplifier_on else 'off'}",
        )
    elif sender == "move_antenna_front_button":
        outbound_command_queue.put("move_antenna_front")
    elif sender == "perform_single_scan_button":
        outbound_command_queue.put("perform_single_scan")
    elif sender == "continuously_scan_button":
        outbound_command_queue.put("continuously_scan")
    elif sender == "update_parameters_button":
        device.sp.hackrf.sample_rate = device_sample_rate_from_gui
        device.sp.hackrf.center_freq = device_center_frequency_from_gui
        device.sp.sample_count = device_sample_count_from_gui
        device.sp.hackrf.vga_gain = device_vga_gain_from_gui


def set_hackrf_id(sender):
    global hackrf_id
    hackrf_id = int(dpg.get_value(sender))


def start_device():
    outbound_command_queue.put("start_device")
    dpg.disable_item("initialize_button")


def update_series():
    global graph_data
    if graph_data is None:
        return
    if len(graph_data[0]) == 0 or len(graph_data[1]) == 0:
        return

    x = [signal_processor.mW_to_dBm(v) for v in graph_data[0]]
    y = [v for v in graph_data[1]]

    if remove_dc_spike:
        # find the average of the y values
        x_avg = sum(x[0:1000]) / 1000
        # replace DC spike with average value
        x = [
            x_avg if i in range(1012, 1036) else val
            for i, val in enumerate(x)
        ]

    dpg.set_value("series_tag", [y, x])
    
    if device.sp.db_offset_in_use is not None or device.sp.db_offset_in_use != 0.0:
        dpg.set_value("level_of_interest_line", [y, [device.sp.db_offset_in_use for i in range(len(y))]])

    dpg.fit_axis_data("y_axis")
    dpg.fit_axis_data("x_axis")


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
    if len(message) == 0:
        return
    message = f'{time.strftime("%H:%M:%S")}] \n{message}'
    dpg.add_text(message, parent="console_window")
    if dpg.get_y_scroll_max("console_window") > 0:
        dpg.set_y_scroll("console_window", dpg.get_y_scroll_max("console_window"))


def calc_compass_antenna_pos(offset):

    # x_0,y_0 --- x_max,y_0
    #  |            |
    #  |            |
    #  |            |
    # x_0,y_max --- x_max,y_max

    # Heading goes from 0 to 4096
    # 2048 is north

    x_0 = 200
    y_0 = 100
    x_max = 600
    y_max = 500
    center_x = (x_max - x_0) / 2
    center_y = (y_max - y_0) / 2
    # Method must draw arrow from center of circle towards the edge of the circle

    if telemetry_data_1 is None:
        return

    heading = int(telemetry_data_1.get("position"))

    if heading is None:
        return

    offset += 90
    # convert offset of degrees to radians
    offset = offset * 2 * math.pi / 360

    # convert heading to angle in radians
    angle = heading * 2 * math.pi / 4096
    angle += offset
    # find coordinates of the arrows tip on the circles edge (radius = 200) by using the angle
    x = ((x_max + x_0) / 2) + 200 * math.cos(angle)
    y = ((y_max + y_0) / 2) + 200 * math.sin(angle)
    return (x, y)


def draw_signals_on_compass():
    """Method to draw short lines according to the strength of the signal on the outside of the compass ring. The length of the line is propertional to signal's strength. Each signal gets its own color."""
    # get starting point of signal line (point on the circle)
    global device

    if device.active_signals is None or len(device.active_signals) == 0:
        return

    for i, signal in enumerate(device.active_signals):
        # get the signal's direction and strength
        sid = signal.id
        signal_direction = signal.x
        signal_strength = signal.peak_power_db
        signal_id = f"signal_strength_line_{sid}"
        
        if not signal_processor.calculate_signal_channel(signal):
            continue
            
        # offset adjustment (add 90 degrees to the position of each signal line)
        offset = 1024

        # calculate the length of the signals line (Signals strength is in dBm, ranging from -60 to 15. We must convert that to a value between 0 and 50 pixels.)
        length = 50 * (signal_strength + 60) // 75

        # calculate starting points of the signal line on the compass circle
        x_start = 400 + 200 * math.cos((signal_direction + offset) * 2 * math.pi / 4096)
        y_start = 300 + 200 * math.sin((signal_direction + offset) * 2 * math.pi / 4096)

        # calculate the end point of the line (it is at max 20pixels length)
        x_end = x_start + length * math.cos(
            (signal_direction + offset) * 2 * math.pi / 4096
        )
        y_end = y_start + length * math.sin(
            (signal_direction + offset) * 2 * math.pi / 4096
        )

        # find the max points where the signal could go (for the end dot)
        x_max = x_start + 50 * math.cos(
            (signal_direction + offset) * 2 * math.pi / 4096
        )
        y_max = y_start + 50 * math.sin(
            (signal_direction + offset) * 2 * math.pi / 4096
        )

        # pick a color
        signal_color = color_list[i]

        if dpg.does_item_exist(f"{signal_id}_line"):
            dpg.delete_item(f"{signal_id}_line")
            dpg.delete_item(f"{signal_id}_text")
            dpg.delete_item(f"{signal_id}_circle")
        # write signal's strength as a number
        dpg.draw_text(
            pos=(x_max, y_max),
            text=f"{round(signal_strength, 3)}",
            tag=f"{signal_id}_text",
            color=signal_color,
            size=18,
            parent="compass_drawlist",
        )
        # draw the signals strength line
        dpg.draw_line(
            p1=(x_start, y_start),
            p2=(x_end, y_end),
            tag=f"{signal_id}_line",
            color=signal_color,
            thickness=2,
            parent="compass_drawlist",
        )
        # draw a point at the max possible signal length
        dpg.draw_circle(
            (x_max, y_max),
            2,
            tag=f"{signal_id}_circle",
            color=signal_color,
            thickness=2,
            parent="compass_drawlist",
        )
        # else:
        # dpg.set_value(signal_id, ((x_start, y_start), (x_end, y_end)))
        # dpg.set_value(signal_id+"text", (x_end, y_end), f"{round(signal_strength, 3)}")
        # dpg.set_value(signal_id+"circle", (x_max, y_max))

        #TODO
        #remove old signal history lines
        #if (len(signal.position_history) > 2):
        #    for i, sweep in enumerate(signal.position_history):
        #        for j, position in enumerate(sweep):
        #            if dpg.does_item_exist(f"signal_history_line_{sid}_{i}_{j}"):
        #                dpg.delete_item(f"signal_history_line_{sid}_{i}_{j}")

        # global telemetry_data_1
        # for this signal, also draw the last two sweeps worth of positions
        #print(len(signal.position_history), signal.position_history)      
        for i, sweep in enumerate(signal.position_history):
            for j, position in enumerate(sweep):
                x_start = 400 + 200 * math.cos(
                    (position[0] + offset) * 2 * math.pi / 4096
                )
                y_start = 300 + 200 * math.sin(
                    (position[0] + offset) * 2 * math.pi / 4096
                )
                length_h = 50 * (position[2] + 60) // 75

                x_end = x_start + length_h * math.cos(
                    (position[0] + offset) * 2 * math.pi / 4096
                )
                y_end = y_start + length_h * math.sin(
                    (position[0] + offset) * 2 * math.pi / 4096
                )

                if not dpg.does_item_exist(f"signal_history_line_{sid}_{i}_{j}"):
                    dpg.draw_line(
                        p1=(x_start, y_start),
                        p2=(x_end, y_end),
                        tag=f"signal_history_line_{sid}_{i}_{j}",
                        color=signal_color,
                        thickness=1,
                        parent="compass_drawlist",
                    )


def update_signals_table():

    for signal in device.active_signals:
        sid = "signal_" + str(signal.id)
        if dpg.does_item_exist(sid):
            dpg.delete_item(sid)
        with dpg.table_row(
            parent="signals_table",
            tag=sid,
        ):
            dpg.add_text(signal.channel)
            dpg.add_text(signal.x)
            dpg.add_text(signal.y)
            dpg.add_text(signal.start_freq)
            dpg.add_text(signal.end_freq)
            dpg.add_text(signal.peak_power_db)
            dpg.add_text(signal.peak_freq)

            # signal.y,
            # signal.start_freq,
            # signal.end_freq,
            # signal.peak_power_db,
            # signal.peak_freq,


def update_compass():

    try:
        dpg.delete_item("compass_15")
        dpg.delete_item("compass_0")
        dpg.delete_item("compass_-15")
    except:
        pass

    dpg.draw_line(
        p1=calc_compass_antenna_pos(15),
        p2=(400, 300),
        color=(0, 255, 0, 255),
        thickness=2,
        parent="compass_drawlist",
        tag="compass_15",
    )
    dpg.draw_line(
        p1=calc_compass_antenna_pos(0),
        p2=(400, 300),
        color=(0, 255, 0, 255),
        thickness=4,
        parent="compass_drawlist",
        tag="compass_0",
    )
    dpg.draw_line(
        p1=calc_compass_antenna_pos(-15),
        p2=(400, 300),
        color=(0, 255, 0, 255),
        thickness=2,
        parent="compass_drawlist",
        tag="compass_-15",
    )


def gui():
    dpg.create_context()
    dpg.create_viewport(
        title="Drone Locator GUI", width=1600, height=1000, resizable=False
    )
    with dpg.window(
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
                with dpg.group(horizontal=True):
                    dpg.add_button(
                        tag="initialize_button",
                        label="Initialize Device",
                        callback=button_callback,
                    )
                    dpg.add_input_int(
                        label="HackRF ID",
                        default_value=0,
                        min_value=0,
                        min_clamped=True,
                        max_value=255,
                        width=100,
                        callback=set_hackrf_id,
                    )

                dpg.add_spacer(height=15)

                dpg.add_button(
                    tag="move_antenna_front_button",
                    label="Move antenna to front",
                    enabled=False,
                    callback=button_callback,
                    width=175,
                )
                
                with dpg.group(horizontal=True):

                    dpg.add_button(
                        tag="start_full_scan_button",
                        label="Start Full Scan",
                        callback=button_callback,
                        enabled=False,
                        width=175,
                    )
                    dpg.add_input_int(
                        tag="full_scan_horizontal_points",
                        label="x",
                        default_value=32,
                        min_value=2,
                        max_value=4096,
                        width=80,
                        min_clamped=True,
                        max_clamped=True,
                    )
                    dpg.add_input_int(
                        tag="full_scan_vertical_points",
                        label="y",
                        default_value=4,
                        min_value=4,
                        max_value=100,
                        width=80,
                        min_clamped=True,
                        max_clamped=True,
                    )

                with dpg.group(horizontal=True):
                    dpg.add_button(
                        tag="start_horizontal_scan_button",
                        label="Start Horizontal Scan",
                        enabled=False,
                        callback=button_callback,
                        width=175,
                    )
                    # dpg.add_spacer(width=0)
                    dpg.add_input_int(
                        tag="horizontal_scan_points",
                        label="x",
                        default_value=360,
                        min_value=1,
                        max_value=4096,
                        width=80,
                        min_clamped=True,
                        max_clamped=True,
                    )
                    # dpg.add_spacer(width=0)
                    dpg.add_input_int(
                        tag="horizontal_scan_elevation",
                        label="h",
                        default_value=1024,
                        min_value=700,
                        max_value=2048,
                        width=80,
                        min_clamped=True,
                        max_clamped=True,
                    )
                
                with dpg.group(horizontal=False):
                    with dpg.group(horizontal=True):
                        dpg.add_button(
                            tag="start_section_scan_button",
                            label="Start Section Scan",
                            enabled=False,
                            callback=button_callback,
                            width=175,
                        )
                        # dpg.add_spacer(width=0)
                        dpg.add_input_int(
                            tag="section_scan_points",
                            label="x",
                            default_value=360,
                            min_value=1,
                            max_value=4096,
                            width=80,
                            min_clamped=True,
                            max_clamped=True,
                        )
                        # dpg.add_spacer(width=0)
                        dpg.add_input_int(
                            tag="section_scan_elevation",
                            label="h",
                            default_value=1024,
                            min_value=700,
                            max_value=2048,
                            width=80,
                            min_clamped=True,
                            max_clamped=True,
                        )
                    with dpg.group(horizontal=True):
                    #two integer inputs between 0 and 4096 that describe the section that will be scanned
                        
                        dpg.add_input_int(
                            tag="section_scan_start",
                            label="Section start",
                            default_value=1024,
                            min_value=0,
                            max_value=4096,
                            width=80,
                            min_clamped=True,
                            max_clamped=True,
                        )
                        
                        dpg.add_spacer(width=15)
                        
                        dpg.add_input_int(
                            tag="section_scan_end",
                            label="Section end",
                            default_value=3072,
                            min_value=0,
                            max_value=4096,
                            width=80,
                            min_clamped=True,
                            max_clamped=True,
                        )         

                dpg.add_button(
                    tag="perform_single_scan_button",
                    label="Perform single scan at current position",
                    enabled=False,
                    callback=button_callback,
                    width=300,
                )

                dpg.add_button(
                    tag="continuously_scan_button",
                    label="Continuously scan at current position",
                    enabled=False,
                    callback=button_callback,
                    width=300,
                )

                dpg.add_spacer(height=15)

                dpg.add_button(
                    tag="stop_scan_button",
                    label="Stop Scan",
                    enabled=False,
                    callback=button_callback,
                )

                dpg.add_spacer(height=15)

                with dpg.group(horizontal=True):
                    dpg.add_button(
                        tag="toggle_amplifier_button",
                        enabled=False,
                        label="Toggle Amplifier",
                        callback=button_callback,
                        width=150,
                    )

                    # dpg.add_spacer(width=18)

                    dpg.add_text(
                        tag="amplifier_status", default_value="Amplifier is off"
                    )

                # add inputs for :   device_center_frequency_from_gui
                #                   device_sample_rate_from_gui
                #                   device_sample_count_from_gui
                dpg.add_input_int(
                    label="Center frequency (MHz)",
                    tag="center_frequency_input",
                    default_value=5772,
                    min_value=5718,
                    max_value=5840,
                    step=1,
                    width=150,
                    min_clamped=True,
                    max_clamped=True,
                )
                dpg.add_input_int(
                    label="Sample rate",
                    tag="sample_rate_input",
                    default_value=20,
                    min_value=1,
                    step=1,
                    max_value=20,
                    width=150,
                    min_clamped=True,
                    max_clamped=True,
                )
                dpg.add_input_int(
                    label="Sample count",
                    tag="sample_count_input",
                    default_value=1000000,
                    min_value=1000,
                    max_value=10000000,
                    width=150,
                    step=1_000,
                    min_clamped=True,
                    max_clamped=True,
                )
                dpg.add_input_int(
                    label="VGA Gain",
                    tag="vga_gain_input",
                    default_value=16,
                    min_value=0,
                    max_value=62,
                    width=150,
                    step=2,
                    min_clamped=True,
                    max_clamped=True,
                )

                dpg.add_button(
                    tag="update_parameters_button",
                    label="Update Parameters",
                    callback=button_callback,
                    enabled=False,
                    width=150,
                )

            # dpg_map.add_map_widget(
            #        width=800,
            #        height=top_area_height,
            #        center=(60.1641, 24.9402),
            #        zoom_level=14,
            #    )
            with dpg.drawlist(
                width=800, height=top_area_height, tag="compass_drawlist"
            ):
                # dpg.draw_rectangle((200, 100), (600, 500), color=(255, 0, 0, 255), thickness=2, parent="compass_drawlist")
                dpg.draw_arrow(
                    (400, 80),
                    (400, 300),
                    color=(255, 255, 255, 255),
                    thickness=4,
                    parent="compass_drawlist",
                )  # 0
                dpg.draw_circle(
                    (400, 300),
                    200,
                    color=(255, 255, 255, 255),
                    thickness=2,
                    parent="compass_drawlist",
                )  # 1
                # dpg.draw_text(
                #    (410, 60),
                #    "Forward",
                #    color=(255, 255, 255, 255),
                #    size=30,
                #    parent="compass_drawlist",
                # )  # 2

                dpg.draw_line(
                    p1=calc_compass_antenna_pos(15),
                    p2=(400, 300),
                    color=(0, 255, 0, 255),
                    thickness=2,
                    parent="compass_drawlist",
                )
                dpg.draw_line(
                    p1=calc_compass_antenna_pos(0),
                    p2=(400, 300),
                    color=(0, 255, 0, 255),
                    thickness=4,
                    parent="compass_drawlist",
                )
                dpg.draw_line(
                    p1=calc_compass_antenna_pos(-15),
                    p2=(400, 300),
                    color=(0, 255, 0, 255),
                    thickness=2,
                    parent="compass_drawlist",
                )

            with dpg.child_window(
                height=top_area_height,
                width=370,
                no_scrollbar=True,
                no_scroll_with_mouse=True,
            ):
                dpg.add_text("Table of discovered signals")
                with dpg.table(
                    tag="signals_table", borders_innerH=True, borders_innerV=True
                ):
                    dpg.add_table_column(label="Signal ID")
                    dpg.add_table_column(label="X")
                    dpg.add_table_column(label="Y")
                    dpg.add_table_column(label="Start Frequency")
                    dpg.add_table_column(label="End Frequency")
                    dpg.add_table_column(label="Peak Power")
                    dpg.add_table_column(label="Peak Frequency")

        with dpg.group(label="bottom_area", horizontal=True):

            with dpg.child_window(
                height=bottom_area_height,
                width=400,
                no_scrollbar=False,
                no_scroll_with_mouse=True,
            ):
                # dpg.add_button(
                #    label="Update Telemetry", callback=update_telemetry_table
                # )
                dpg.add_text("Telemetry Table")
                dpg.add_spacer(height=5)
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
                # dpg.add_button(label="Update Series", callback=update_series)
                # create plot
                with dpg.plot(
                    label="Last Scan Output",
                    height=bottom_area_height,
                    width=800,
                ):
                    # optionally create legend
                    dpg.add_plot_legend()

                    # REQUIRED: create x and y axes
                    dpg.add_plot_axis(
                        dpg.mvXAxis, label="Frequency (MHz)", tag="x_axis"
                    )
                    dpg.add_plot_axis(
                        dpg.mvYAxis,
                        label="Signal Strength (dBm)",
                        tag="y_axis",
                        log_scale=False,
                    )

                    # series belong to a y axis
                    dpg.add_line_series(
                        [i for i in range(2048)],
                        [0.0 for i in range(2048)],
                        label="HackRF Data",
                        parent="y_axis",
                        tag="series_tag",
                    )
                    #draw a horizontal line
                    
                    dpg.add_line_series([i for i in range(2048)],
                        [-52 for i in range(2048)], tag="level_of_interest_line", label="LOI", parent="y_axis")

            with dpg.child_window(
                height=bottom_area_height,
                width=370,
                no_scrollbar=False,
                no_scroll_with_mouse=False,
                tag="console_window",
            ):
                dpg.add_text("Console log", tag="console_row_1")

        with dpg.group(horizontal=True):
            dpg.add_button(label="Footer 1", width=175)
            dpg.add_text("Footer 2")
            dpg.add_button(label="Footer 3", width=175)
            dpg.add_text("Footer 4")

    dpg.setup_dearpygui()
    dpg.show_viewport()
    first_run = True
    fast_loop_timer = slow_loop_timer = time.time()
    # update telemetry table every second from the global variables
    while dpg.is_dearpygui_running():
        if first_run:
            first_run = False
            gui_query_thread = threading.Thread(
                target=gui_query_thread_method, daemon=True
            )

            import_data_thread = threading.Thread(
                target=import_data_thread_method, daemon=True
            )
            import_data_thread.start()
            gui_query_thread.start()

        current_time = time.time()
        if ready_to_query:
            # Thito do all the time
            update_global_variables()
            # Things to do every second
            if current_time > slow_loop_timer + 0.5:
                # Request data
                outbound_command_queue.put("get_telemetry")
                slow_loop_timer = time.time()

            if current_time > fast_loop_timer + (1 / 60):  # 60 fps
                # Update series
                update_global_variables()
                update_series()
                update_compass()
                update_telemetry_table()
                update_signals_table()
                draw_signals_on_compass()
                fast_loop_timer = time.time()

        dpg.render_dearpygui_frame()

    dpg.destroy_context()


def update_global_variables():
    global telemetry_data_1, telemetry_data_2, device_center_frequency_from_gui, device_sample_rate_from_gui, device_sample_count_from_gui, device_vga_gain_from_gui
    telemetry_data_1 = device.TELEMETRY_1
    telemetry_data_2 = device.TELEMETRY_2
    device_center_frequency_from_gui = float(
        dpg.get_value("center_frequency_input")
    ) * float(1.0e6)
    device_sample_rate_from_gui = float(dpg.get_value("sample_rate_input")) * float(
        1.0e6
    )
    device_sample_count_from_gui = float(dpg.get_value("sample_count_input"))
    device_vga_gain_from_gui = int(dpg.get_value("vga_gain_input"))

def create_logger():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file_path = f'data/signals_log_{timestamp}.log'
    handler = logging.FileHandler(log_file_path)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

# Gui layout constants
top_area_height = 550
bottom_area_height = 385

# Device constants
hackrf_id = 0
device = None
sp = None

device_center_frequency_from_gui = 0.0
device_sample_rate_from_gui = 0.0
device_sample_count_from_gui = 0.0
device_amplifier = False
device_vga_gain_from_gui = 0

ready_to_query = False
currently_scanning = False
horizontal_scan_points = 0
horizontal_scan_elevation = 0
section_scan_elevation = 0
section_scan_points = 0
section_scan_start = 1024
section_scan_end = 3072

telemetry_data_1 = None
telemetry_data_2 = None
graph_data = None
remove_dc_spike = True

# make a list of colors for the signals to be drawn (32 colors, adjacent colors are as different as possible, not white or black)
# TODO might need more than 32 colors but for now this will do
color_list = [
    (255, 0, 0, 255),
    (255, 255, 0, 255),
    (0, 255, 0, 255),
    (0, 255, 255, 255),
    (0, 0, 255, 255),
    (255, 0, 255, 255),
    (128, 0, 0, 255),
    (128, 128, 0, 255),
    (0, 128, 0, 255),
    (0, 128, 128, 255),
    (0, 0, 128, 255),
    (128, 0, 128, 255),
    (255, 128, 0, 255),
    (128, 255, 0, 255),
    (0, 255, 128, 255),
    (0, 128, 255, 255),
    (128, 0, 255, 255),
    (255, 0, 128, 255),
    (255, 128, 128, 255),
    (128, 255, 128, 255),
    (128, 128, 255, 255),
    (255, 255, 128, 255),
    (255, 128, 255, 255),
    (128, 255, 255, 255),
    (192, 0, 0, 255),
    (192, 192, 0, 255),
    (0, 192, 0, 255),
    (0, 192, 192, 255),
    (0, 0, 192, 255),
    (192, 0, 192, 255),
    (255, 192, 0, 255),
    (192, 255, 0, 255),
    (0, 255, 192, 255),
    (0, 192, 255, 255),
    (192, 0, 255, 255),
    (255, 0, 192, 255),
    (255, 192, 192, 255),
    (192, 255, 192, 255),
    (192, 192, 255, 255),
    (255, 255, 192, 255),
    (255, 192, 255, 255),
    (192, 255, 255, 255)
]
    

outbound_command_queue = queue.Queue()
inbound_data_queue = queue.Queue()


# device = esp32_controller.ESP32Controller()
# sp = signal_processor.SignalProcessor(id=hackrf_id)
# device.assign_signal_processor(signal_processor=sp)
# device.initialize()

if __name__ == "__main__":
    logger = create_logger()
    gui()