from src import esp32_controller
from src import signal_processor
import os, time

import dearpygui.dearpygui as dpg

from testplot import plot_data, plot_data_two_horizontals

if __name__ == "__main__":
    device = esp32_controller.ESP32Controller()
    sp = signal_processor.SignalProcessor(id=0)
    device.assign_signal_processor(signal_processor=sp)
    device.initialize()

    try:
        p = input("Enter power: ")
        d = input("Enter distance: ")
        #n = input("Enter number of points: ")
        n = 180
        t = time.strftime("%H_%M_%S")
        filename = f'TESTS_MAIN/TEST_time{t}_npoints{n}_distance{d}_power{p}.csv'
        
        os.makedirs("TESTS_MAIN", exist_ok=True)
        f = open(filename, "w")
        
        
        input("Press enter to start test!")
        
        print(f"START OF TEST WITH POWER: {p}mw, DISTANCE: {d}m, NUMBER OF POINTS: {n}, resolution: {90/n}°")
        
        #5760 - 5810 is best for antenna
        #A5 sits at 5785 and with a 20hmz bandwidth it goes from 5775 to 5795 thus is in the middle of the best range for our directional antenna
        #center is thus 5785mhz or 5.785ghz
        
        
        #Set the frequency to 5.785ghz, enable amp and set lna 0 vga 16
        device.sp.hackrf.center_freq = 5780e6
        device.sp.hackrf.lna_gain = 16 #was 8 at best test so far
        device.sp.hackrf.vga_gain = 32 #TODO maybe revert back to 16 (32 was best so far)
        
        
        #change sample count from 1e6 to more (or less)
        device.sp.hackrf._sample_count = 5e5
        #5e5 is half of 1e6
        
        device.sp.hackrf.amplifier_on = True
        device.sp.set_amplifier(True)
                
        #run the test of five vertical sweeps and five horizontal sweeps
        device.section_TEST_TWO_POINTS(power=p, distance=d, number_of_points=int(n), show_graph=False, file=f)
        
        print("END OF TEST")
        
        plot_data_two_horizontals(filename)

    except KeyboardInterrupt:
        pass
