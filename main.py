import esp32_controller
import dearpygui.dearpygui as dpg

if __name__ == "__main__":
    device = esp32_controller.ESP32Controller()
    device.connect()
    device.initialize()


    try:
        while True:
            device.horizontal_sweep(show_graph=True, number_of_points=32, y_level=1024)
    except KeyboardInterrupt:
        pass
