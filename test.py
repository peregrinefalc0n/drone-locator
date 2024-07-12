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
        
        #5760 - 5810 is best for antenna
        #A5 sits at 5785 and with a 20hmz bandwidth it goes from 5775 to 5795 thus is in the middle of the best range for our directional antenna
        #center is thus 5785mhz or 5.785ghz
        
        
        device.section_TEST(power=p, distance=d, number_of_points=int(n), show_graph=False)
        
        print("END OF TEST")

    except KeyboardInterrupt:
        pass
