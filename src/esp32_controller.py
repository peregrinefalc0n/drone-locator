import time
import serial
import math
import platform
from src import signal_processor
import queue

# The custom command structure when interfacing with esp32 over serial (usb)
# No returns:
# MOVE,<servo_id>,<position>,<speed>,<acceleration>
# CALIBRATE,<servo_id>
# SYNC_MOVE, [<servo_id1>,<servo_id2>], <servo_count>, [<servo_position1>,<servo_position2>], [<servo_speed1>,<servo_speed2>], [<servo_acc1>,<servo_acc2>]
# With returns:
# GET_POS,<servo_id>        ---> POSITION,<servo_id>,<position>
# GET_TELEMETRY,<servo_id>  ---> TELEMETRY,<servo_id>,<position>,<speed>,<load>,<voltage>,<temperature>,<move>,<current>

# Specification of PRO 12T helical antenna:
# Bandwidth: 5640-5945 MHz
# Beam width:  30 degrees with highest gain, 50-60 at close range
# Gain: 14 dBi
# Reflector diameter: 45mm
# Cable length: ~6cm
# Antenna conductor: 1,2mm pure enameled copper wire
# Turns: 12
# Polarisation: RHCP or LHCP
# vSWR: lower than 1.2
# Maximum power input: 50W
# Connector: SMA or RP-SMA
# Weight of antenna: ~27g

# Servo specifications:
# Horizontal coordinate range: 0 - 4096
# Vertical coordinate range: 1024 horizontal(safety range 1000) - 2048 up(safety range 2072)
# Speed: 0 - 4000
# Acceleration: 0 - alot


class VerticalServoFutureOutOfBounds(Exception):
    """Raised if the vertical servo would potentially be moved out of bounds."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class ServoTemperatureTooHigh(Exception):
    """Raised if the servo temperature is too high."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class stopEverything(Exception):
    """Raised if the user wants to stop everything."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class ESP32Controller:
    """Class for communicating with ESP32 and controlling the connected servos."""

    def __init__(
        self,
        communication_method="serial",
        serial_port=None,
        baud_rate: int = 115200,
        timeout=1,
    ):
        self.communication_method = communication_method
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.stop_everything = False
        self.return_queue = queue.Queue()
        self.active_signals = []  # x,y,start_freq,end_freq,peak_freq,peak_power_db

        self.GLOBAL_ACC = 100
        self.GLOBAL_SPEED = 2000
        self.CURRENT_POSITION_1 = 0
        self.CURRENT_POSITION_2 = 0
        self.TELEMETRY_1 = None
        self.TELEMETRY_2 = None

        if serial_port == None:
            if platform.system() == "Windows":
                self.serial_port = "COM5"
            elif platform.system() == "Linux":
                self.serial_port = "/dev/ttyUSB0"
            else:
                raise Exception("Unsupported platform")
        else:
            raise Exception(
                "Serial port can't be automatically detected. Please specify the serial port parameter."
            )

        # Initialize the signal processor
        self.sp = None

    def stop(self):
        """Stop everything."""
        self.stop_everything = True

    def assign_signal_processor(
        self, signal_processor: signal_processor.SignalProcessor
    ):
        """Assign a signal processor to the ESP32 controller."""
        self.sp = signal_processor

    def __y_future_within_bounds(self, location: int) -> bool:
        """Check if the future y-axis location is within the bounds of the vertical servo safe operation. \n
        These values should be edited if servo movement range is expanded or reduced on the physical device.
        """
        return 1000 <= location <= 2072

    def __inRange(self, actual, expected, range):
        """Check if the actual value is within the expected value with a given range."""
        return abs(actual - expected) <= range

    # Unused
    def __calculate_horizontal_sweepline_radii(self, lines=6):
        """Calculate radii for horizontal sweep lines, so that they are evenly spaced out."""
        main_radius = 4096 // (math.pi * 2)
        division = 90 / lines
        radii = []
        for i in range(0, lines + 1):
            radius = main_radius * math.sin(math.radians(90 - (division * i)))
            radii.append(int(radius))
        return radii

    def __calculate_vertical_movement_distances(self, n):
        """Returns a list of y-axis positions for the vertical servo to move to.\n
        The returned values are evenly spaced out between 1024 and 2048."""

        y_positions = []
        for i in range(0, n + 1):
            y = 1024 + i * (1024 // n)
            y_positions.append(y)
        return y_positions

    # Unused (for now)
    def calculate_circular_coordinates(self, center_x, center_y, radius, n):
        """Calculate n evenly spaced out coordinates in a circle around center_x and center_y coordinates."""
        coordinates = []
        for i in range(n):
            angle_radians = math.radians(360 * i / n)
            x = int(center_x + radius * math.cos(angle_radians))
            y = int(center_y + radius * math.sin(angle_radians))

            # y-axis squishing
            if y > 2072:
                y = 2048
            if y < 1000:
                y = 1024

            # x-axis squishing
            if x > 4096:
                x = 4096
            if x < 0:
                x = 0

            coordinates.append((x, y))
        return coordinates

    def __calculate_horizontal_distances(
        self, num_points=12, circumference=4092, start_angle=0
    ):
        """Calculate num_points amount of horizontal distances from point 0 all the way to 4096. These distances are what the servos will move to."""
        distances = []
        angle_increment = 360 / num_points

        for i in range(num_points):
            angle_degrees = (start_angle + i * angle_increment) % 360
            distance = (angle_degrees / 360) * circumference
            distances.append((angle_degrees, int(distance)))
        return distances

    def __collectGarbage(self):
        print("Serial port opened.")
        time.sleep(1)
        response = self.esp32.readline().decode().strip()
        if len(response) > 0:
            print("Garbage:", response)

    def __servosReady(self) -> bool:
        """Returns true when servos are ready to be used."""
        while True:
            horizontal = self.__get_position(1)
            vertical = self.__get_position(2)
            if horizontal == -1 or vertical == -1:
                print(
                    f"Servo 1: {horizontal}, Servo 2: {vertical}. Retrying in 1 second."
                )
                time.sleep(1)
            else:
                return True

    def __center_servos(self):
        """Center the servos manually by moving them to the middle position."""
        input(
            "First turn power switch off manually, then move servos by hand to center, finally press enter when done to calibrate."
        )

        self.esp32.write((f"CALIBRATE,1" + "\n").encode())
        self.esp32.write((f"CALIBRATE,2" + "\n").encode())

        if (
            self.__get_position(self.esp32, 1) == 2048
            and self.__get_position(self.esp32, 2) == 2048
        ):
            print(
                f"Servos calibrated. Servo 1 at {self.CURRENT_POSITION_1}, Servo 2 at {self.CURRENT_POSITION_2}."
            )
        else:
            print("Servos not calibrated. Please try again.")
            self.__center_servos()

    def __get_position(self, servo_id) -> int:
        """Get the current position of the servo with the specified id."""
        self.esp32.write((f"GET_POS,{servo_id}" + "\n").encode())
        location = int(self.esp32.readline().decode().split(",")[2])

        # Update global variables while we are at it
        match servo_id:
            case 1:
                self.CURRENT_POSITION_1 = location
            case 2:
                self.CURRENT_POSITION_2 = location
        return location

    def get_telemetry(self, servo_id: int) -> dict[str, int]:
        self.esp32.write((f"GET_TELEMETRY,{servo_id}" + "\n").encode())
        # TELEMETRY,<servo_id>,<position>,<speed>,<load>,<voltage>,<temperature>,<move>,<current>
        telemetry = self.esp32.readline().decode().split(",")
        if (
            telemetry is not None
            and "TELEMETRY" in telemetry[0]
            and int(telemetry[1]) == servo_id
        ):
            telemetry_data = {
                "servo_id": telemetry[1],
                "position": telemetry[2],
                "speed": telemetry[3],
                "load": telemetry[4],
                "voltage": telemetry[5],
                "temperature": telemetry[6],
                "move": telemetry[7],
                "current": telemetry[8],
            }
            if servo_id == 1:
                self.TELEMETRY_1 = telemetry_data
            elif servo_id == 2:
                self.TELEMETRY_2 = telemetry_data
        else:
            return None
        # print(telemetry_data)
        return telemetry_data

    def move_both(self, servo_id1, servo_id2, expected_pos1, expected_pos2):
        """Move two servos to the specified positions."""
        self.__move_to(servo_id1, expected_pos1)
        self.__move_to(servo_id2, expected_pos2)

        while True:
            if self.__inRange(
                self.__get_position(servo_id1), expected_pos1, 10
            ) and self.__inRange(self.__get_position(servo_id2), expected_pos2, 10):
                return

    def __move_to(self, servo_id: int, expected_pos: int):
        """Move the servo with the specified id to the expected position."""
        if self.stop_everything:
            self.stop_everything = False
            raise stopEverything("User stopped everything.")

        # safeguard for y-axis
        if servo_id == 2:
            if not self.__y_future_within_bounds(expected_pos):
                raise VerticalServoFutureOutOfBounds(
                    "Vertical servo future position out of bounds."
                )

        self.esp32.write(
            (
                f"MOVE,{servo_id},{expected_pos},{self.GLOBAL_SPEED},{self.GLOBAL_ACC}"
                + "\n"
            ).encode()
        )

    def __syncmove_to(self, servo_id1, servo_id2, expected_pos1, expected_pos2):
        """Move two servos to the desired positions at the same time synchronously."""
        if self.stop_everything:
            self.stop_everything = False
            raise stopEverything("User stopped everything.")

        # safeguard for y-axis
        if servo_id2 == 2:
            if not self.__y_future_within_bounds(expected_pos2):
                raise VerticalServoFutureOutOfBounds(
                    "Vertical servo future posiion out of bounds."
                )

        self.esp32.write(
            (
                f"SYNC_MOVE,[{servo_id1},{servo_id2}],2,[{expected_pos1},{expected_pos2}],[{self.GLOBAL_SPEED},{self.GLOBAL_SPEED}],[{self.GLOBAL_ACC},{self.GLOBAL_ACC}]"
                + "\n"
            ).encode()
        )

    def __syncmove_distance(self, servo_id1, servo_id2, distance1, distance2):
        """Move two servos by the specified distances at the same time synchronously."""
        current_pos1 = self.__get_position(servo_id1)
        current_pos2 = self.__get_position(servo_id2)
        expected_pos1 = current_pos1 + distance1
        expected_pos2 = current_pos2 + distance2

        # safeguard for y-axis
        if servo_id2 == 2:
            if not self.__y_future_within_bounds(expected_pos2):
                raise VerticalServoFutureOutOfBounds

        self.esp32.write(
            (
                f"SYNC_MOVE,[{servo_id1},{servo_id2}],2,[{expected_pos1},{expected_pos2}],[{self.GLOBAL_SPEED},{self.GLOBAL_SPEED}],[{self.GLOBAL_ACC},{self.GLOBAL_ACC}]"
                + "\n"
            ).encode()
        )

    def __move_to_and_wait_for_complete(self, servo_id, expected_pos):
        """Move the servo to the expected position and wait for the movement to complete."""

        self.__move_to(servo_id, expected_pos)
        while True:
            current_pos = self.__get_position(servo_id)
            if self.__inRange(current_pos, expected_pos, 20):
                break

    def __move_distance_and_wait_for_complete(self, servo_id, distance):
        """Move the servo by the specified distance and wait for the movement to complete."""
        current_pos = self.__get_position(servo_id)
        expected_pos = current_pos + distance
        self.__move_to(servo_id, expected_pos)
        while True:
            current_pos = self.__get_position(servo_id)
            if self.__inRange(current_pos, expected_pos, 20):
                break

    def full_sweep_optimal(self, show_graph=False):
        """Perform a full sweep of the whole servo movement range in an optimal way."""
        y_positions = self.__calculate_vertical_movement_distances(6)
        point_array = [12, 12, 10, 8, 6, 4, 1]

        for i in range(len(y_positions)):
            self.__move_to_and_wait_for_complete(2, y_positions[i])
            points = point_array[i]
            start_angle = 0
            x_positions = self.__calculate_horizontal_distances(
                points, 4096, start_angle
            )
            for x_position in x_positions if i % 2 == 0 else reversed(x_positions):
                self.__move_to_and_wait_for_complete(1, x_position[1])
                self.perform_scan(offset=10, show_graph=show_graph)
                # self.return_queue.put((signals, raw_data, telem1, telem2), block=False, timeout=0)
                # print(len(signals), len(raw_data), len(telem1), len(telem2))

    def horizontal_sweep(self, show_graph=False, number_of_points=12, y_level=1024):
        """Perform a horizontal sweep scan at y_level with the specified number of points."""
        self.__move_to_and_wait_for_complete(servo_id=2, expected_pos=y_level)
        x_positions = self.__calculate_horizontal_distances(number_of_points, 4096, 0)

        reverse = False
        skip_first = False
        while True:
            for x_position in reversed(x_positions) if reverse else x_positions:
                if skip_first:
                    skip_first = False
                    continue
                self.__move_to_and_wait_for_complete(1, x_position[1])
                scan_data = self.perform_scan(offset=10, show_graph=show_graph)
                # self.return_queue.put((signals, raw_data, telem1, telem2), block=False, timeout=0)
                # print(len(signals), len(raw_data), len(telem1), len(telem2))

            reverse = not reverse
            skip_first = True

    def horizontal_sweep_precise(
        self, show_graph=False, number_of_points=12, y_level=1024
    ):
        """Perform a horizontal sweep scan at y_level with the specified number of points."""
        self.__move_to_and_wait_for_complete(servo_id=2, expected_pos=y_level)
        x_positions = self.__calculate_horizontal_distances(number_of_points, 4096, 0)

        reverse = False
        skip_first = False
        if True: #remove this
            current_run_signals = []
            for x_position in reversed(x_positions) if reverse else x_positions:
                if skip_first:
                    skip_first = False
                    continue
                self.__move_to_and_wait_for_complete(1, x_position[1])
                scan_data = self.perform_scan(offset=10, show_graph=show_graph)
                # x,y,start_freq,end_freq,peak_freq,peak_power_db
                x = self.CURRENT_POSITION_1
                y = self.CURRENT_POSITION_2
                # start_freq = scan_data[0][0].start_freq
                # end_freq = scan_data[0][0].end_freq
                # peak_freq = scan_data[0][0].peak_freq
                # peak_power_db = scan_data[0][0].peak_power_db

                if len(scan_data[0]) > 0:  # if we got signals on this scan
                    for signal in scan_data[0]:
                        print("Found signals:", len(scan_data[0]))
                        if len(self.active_signals) == 0:
                            signal.x = x
                            signal.y = y
                            self.active_signals.append(signal)
                            print("!active signals == 0! Added completely new signal to active signals", signal.to_string())
                        
                        
                        # check if signal is already in active signals, if it is, update it
                        this_signal_is_new = True
                        for index, existing_signal in enumerate(self.active_signals):
                            if (
                                self.__inRange(
                                    signal.peak_freq,
                                    existing_signal.peak_freq,
                                    0.1,
                                )
                                and self.__inRange(
                                    signal.start_freq,
                                    existing_signal.start_freq,
                                    1,
                                )
                                and self.__inRange(
                                    signal.end_freq,
                                    existing_signal.end_freq,
                                    0.1
                                )
                                # and self.__inRange(x, existing_signal.x, 10)
                                # and self.__inRange(y, existing_signal.y, 10)
                            ):
                                # found existing signal, update it
                                this_signal_is_new = False
                                (
                                    x_return,
                                    y_return,
                                    signal_frequency_return,
                                    signal_power_return,
                                ) = self.find_strongest_point_of_signal(
                                    x_position[1],
                                    y_level,
                                    signal.peak_freq,
                                    signal.peak_power_db,
                                    signal.start_freq,
                                    signal.end_freq,
                                )
                                if signal_power_return > existing_signal.peak_power_db:
                                    print("Found a stronger signal position: ", x_return, y_return)
                                    # update existing signal with new data
                                    existing_signal.x = x_return
                                    existing_signal.y = y_return
                                    existing_signal.peak_freq = signal_frequency_return
                                    existing_signal.peak_power_db = signal_power_return
                                    existing_signal.start_freq = signal.start_freq
                                    existing_signal.end_freq = signal.end_freq
                                    # x,y,signal
                                    break
                        if this_signal_is_new:
                            signal.x = x
                            signal.y = y
                            self.active_signals.append(signal)
                            print("Added new signal to active signals", signal.to_string())
                        
                                        
                # self.return_queue.put((signals, raw_data, telem1, telem2), block=False, timeout=0)
                # print(len(signals), len(raw_data), len(telem1), len(telem2))

            reverse = not reverse
            skip_first = True

    def find_strongest_point_of_signal(
        self,
        prev_x,
        prev_y,
        prev_signal_frequency,
        prev_signal_power,
        prev_signal_start_freq,
        prev_signal_end_freq,
    ):
        """Finds the strongest point of a signal by moving the device to the location of the signal and scanning again. If a stronger signal is found, it moves to that location and scans again. This process is repeated until no stronger signal is found."""
        x_return = prev_x
        y_return = prev_y
        signal_frequency_return = prev_signal_frequency
        signal_power_return = prev_signal_power

        locations = self.calculate_circular_coordinates(prev_x, prev_y, 25, 8)

        location_data = list()
        for location in locations:
            #print(location)
            self.move_both(1, 2, location[0], location[1])
            location_data.append([location, self.perform_scan()])

        new_strongest_signal_power = None
        new_strongest_signal_freq = None

        for scan in location_data:
            signals = scan[1][0]
            if len(signals) > 0:
                for signal in signals:
                    if prev_signal_start_freq < signal.peak_freq < prev_signal_end_freq:
                        if signal.peak_power_db > prev_signal_power:
                            new_strongest_signal_power = signal.peak_power_db
                            new_strongest_signal_freq = signal.peak_freq
                            new_strongest_signal_x = self.__get_position(1)
                            new_strongest_signal_y = self.__get_position(2)

        # If we found a stronger signal, we move to that location and scan again to find the strongest point of the signal
        if new_strongest_signal_power is not None:
            return self.find_strongest_point_of_signal(
                prev_x=new_strongest_signal_x,
                prev_y=new_strongest_signal_y,
                prev_signal_frequency=new_strongest_signal_freq,
                prev_signal_power=new_strongest_signal_power,
                prev_signal_start_freq=prev_signal_start_freq,
                prev_signal_end_freq=prev_signal_end_freq,
            )
        else:
            return x_return, y_return, signal_frequency_return, signal_power_return

    def go_to_forward(self):
        self.__move_to(1, 2048)
        self.__move_to(2, 1024)
        # self.__syncmove_to(1, 2, 2048, 1024)

    def perform_scan(
        self, offset=10, show_graph=False
    ) -> tuple[list[signal_processor.Signal], list, dict[str, int], dict[str, int]]:
        """Perform a scan at the current servo positions. \n
        Returns any signals found + servo telemetry."""
        telemetry_1 = self.get_telemetry(1)
        telemetry_2 = self.get_telemetry(2)
        # print("=====================================")
        # print(
        #    f'[INFO] Performing scan at x {telemetry_1["position"]}, y {telemetry_2["position"]}. Temp1 {telemetry_1["temperature"]} Temp2 {telemetry_2["temperature"]}.'
        # )
        # if int(telemetry_1['temperature']) >= 50 or int(telemetry_2['temperature']) >= 50:
        #    raise ServoTemperatureTooHigh("Servo temperature too high.")
        signals, raw_data = self.sp.get_signals(offset, show_graph)
        # print("Signals found: ", len(signals))
        # for i, signal in enumerate(signals):
        # print(
        # f"[{i}] Signal from",
        # signal.start_freq,
        # "to",
        # signal.end_freq,
        # "with peak power of",
        # signal.peak_power_db,
        #  " at freq ",
        #   signal.peak_freq,
        # )
        # print("=====================================")
        self.return_queue.put(
            (signals, raw_data, telemetry_1, telemetry_2), block=False, timeout=0
        )
        return (signals, raw_data, telemetry_1, telemetry_2)

    def initialize(self):
        """Initialize the ESP32 controller and connect to the device."""
        if self.sp == None:
            raise Exception(
                "Signal processor not assigned. Please assign a signal processor before initializing."
            )
        """Connect to the ESP32 device and initialize the servos."""
        if self.communication_method == "serial":
            self.esp32 = serial.Serial(
                self.serial_port, self.baud_rate, timeout=self.timeout
            )
        elif self.communication_method == "wifi":
            raise Exception("Wifi communication not yet supported :(")
        else:
            raise Exception(
                "Invalid communication method. Please select either 'serial' or 'wifi'."
            )
        print("[INFO] Connected to ESP32.")

        self.__collectGarbage()
        if self.__servosReady():
            print("[INFO] Servos ready.")


if __name__ == "__main__":
    print("This is a module file. Run gui.py instead.")
