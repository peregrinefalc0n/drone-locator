import dearpygui.dearpygui as dpg
import dearpygui.demo as demo
import dearpygui_map as dpg_map
from math import sin, cos
from src import esp32_controller
from src import signal_processor


top_area_height = 550
bottom_area_height = 350


sindatax = []
sindatay = []

hackrf_id = 1
device = None
sp = None

#device = esp32_controller.ESP32Controller()
#sp = signal_processor.SignalProcessor(id=hackrf_id)
#device.assign_signal_processor(signal_processor=sp)
#device.initialize()

for i in range(0, 500):
    sindatax.append(i / 1000)
    sindatay.append(0.5 + 0.5 * sin(50 * i / 1000))

def update_series():
    cosdatax = []
    cosdatay = []
    for i in range(0, 500):
        cosdatax.append(i / 1000)
        cosdatay.append(0.5 + 0.5 * cos(50 * i / 1000))
    dpg.set_value('series_tag', [cosdatax, cosdatay])
    dpg.set_item_label('series_tag', "0.5 + 0.5 * cos(x)")


def button_callback(sender, app_data, user_data):
    print(f"sender is: {sender}")
    print(f"app_data is: {app_data}")
    print(f"user_data is: {user_data}")


def set_hackrf_id(sender):
    global hackrf_id
    hackrf_id = dpg.get_value(sender)
    
    
def start_device():
    global hackrf_id
    global device
    global sp
    device = esp32_controller.ESP32Controller()
    sp = signal_processor.SignalProcessor(id=hackrf_id)
    device.assign_signal_processor(signal_processor=sp)
    device.initialize()

dpg.create_context()

dpg.create_viewport(title="Drone Locator GUI", width=1600, height=1000, resizable=False)
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
            height=top_area_height, width=400, no_scrollbar=True, no_scroll_with_mouse=True
        ):
            with dpg.group(label="start", horizontal=True):
                hackrf_id = dpg.add_input_int(tag="hackrf_id", label="HackRF ID", default_value=0, step=1, min_value=0, max_value=255, width=100, callback=set_hackrf_id)
                dpg.add_button(label="Initialize device", callback=start_device)
            
            dpg.add_button(label="Button 2")
            
            dpg.add_button(label="Button 3")
        with dpg.child_window(
            height=top_area_height,
            width=800,
            no_scrollbar=True,
            no_scroll_with_mouse=True,
            border=False,
        ):
            dpg_map.add_map_widget(
                width=800, height=top_area_height, center=(60.1641, 24.9402), zoom_level=14
            )

        with dpg.child_window(
            height=top_area_height,
            width=400,
            no_scrollbar=True,
            no_scroll_with_mouse=True,
        ):
            dpg.add_text("Top right area")

    with dpg.group(label="bottom_area", horizontal=True):

        with dpg.child_window(
            height=bottom_area_height, width=400, no_scrollbar=False, no_scroll_with_mouse=True
        ):
            with dpg.table(label="telemetry_table", header_row=True, borders_innerH=True, borders_innerV=True):

                dpg.add_table_column(label="Variable")
                dpg.add_table_column(label="Servo 1")
                dpg.add_table_column(label="Servo 2")

                with dpg.table_row(label="Temperature"):
                    dpg.add_text("Temperature")
                    dpg.add_text("36")
                    dpg.add_text("24")
                with dpg.table_row(label="Position"):
                    dpg.add_text("Position")
                    dpg.add_text("2400")
                    dpg.add_text("1024")

        with dpg.child_window(
            height=bottom_area_height,
            width=800,
            no_scrollbar=True,
            no_scroll_with_mouse=True,
            border=False
        ):
            dpg.add_button(label="Update Series", callback=update_series)
            # create plot
            with dpg.plot(label="Line Series", height=bottom_area_height, width=800):
                # optionally create legend
                dpg.add_plot_legend()

                # REQUIRED: create x and y axes
                dpg.add_plot_axis(dpg.mvXAxis, label="x")
                dpg.add_plot_axis(dpg.mvYAxis, label="y", tag="y_axis")

                # series belong to a y axis
                dpg.add_line_series(sindatax, sindatay, label="0.5 + 0.5 * sin(x)", parent="y_axis", tag="series_tag")
        with dpg.child_window(
            height=bottom_area_height,
            width=400,
            no_scrollbar=True,
            no_scroll_with_mouse=True,
        ):
            dpg.add_text("Bottom right area")

    with dpg.group(horizontal=True):
        dpg.add_button(label="Footer 1", width=175)
        dpg.add_text("Footer 2")
        dpg.add_button(label="Footer 3", width=175)
        dpg.add_text("Footer 4")

dpg.setup_dearpygui()
dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()
