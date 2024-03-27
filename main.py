from src import esp32_controller
from src import signal_processor

import dearpygui.dearpygui as dpg

if __name__ == "__main__":
    device = esp32_controller.ESP32Controller()
    sp = signal_processor.SignalProcessor(id=1)
    device.assign_signal_processor(signal_processor=sp)
    device.initialize()

    try:
        while True:
            device.horizontal_sweep(show_graph=True, number_of_points=32, y_level=1024)
    except KeyboardInterrupt:
        pass
