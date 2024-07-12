from src import esp32_controller
from src import signal_processor

import dearpygui.dearpygui as dpg



if __name__ == "__main__":
    device = esp32_controller.ESP32Controller()
    sp = signal_processor.SignalProcessor(id=0)
    device.assign_signal_processor(signal_processor=sp)
    device.initialize()

    try:
        p = input("Enter power: ")
        d = input("Enter distance: ")
        n = input("Enter number of points: ")
        
        print(f"START OF TEST WITH POWER: {p}mw, DISTANCE: {d}m, NUMBER OF POINTS: {n}")
        
        device.section_TEST(power=p, distance=d, number_of_points=int(n), show_graph=False)
        
        print("END OF TEST")

    except KeyboardInterrupt:
        pass
