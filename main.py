from src import esp32_controller
from src import signal_processor

import dearpygui.dearpygui as dpg



if __name__ == "__main__":
    device = esp32_controller.ESP32Controller()
    sp = signal_processor.SignalProcessor(id=0)
    device.assign_signal_processor(signal_processor=sp)
    device.initialize()

    try:
        while True:
            device.horizontal_sweep_precise(show_graph=False, number_of_points=64, y_level=1050)
            for i,signal in enumerate(device.active_signals):
                print("Signal:", i, "Data:", signal.start_freq, signal.end_freq, signal.peak_power_db, signal.peak_freq)


    except KeyboardInterrupt:
        pass
