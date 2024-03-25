import time
import serial
import asyncio
import math
import platform


MODE = "serial"

if platform.system() == "Windows":
    SERIAL_PORT = "COM5"
elif platform.system() == "Linux":
    SERIAL_PORT = "/dev/ttyUSB0"
else:
    raise Exception("Unsupported platform")

GLOBAL_ACC = 100
GLOBAL_SPEED = 2000

CURRENT_POSITION_1 = 0
CURRENT_POSITION_2 = 0


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


#TODO turn the methods in this file to this class
class ESP32Controller:
    """Class for communicating with ESP32 over serial and controlling its connected servos. 
    By default, the serial port is set to COM5, baud rate to 115200 and timeout to 1 second."""	

    def __init__(self, serial_port = "COM5", baud_rate=115200, timeout=1):
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.esp32 = serial.Serial(self.serial_port, self.baud_rate, timeout=self.timeout)


def y_future_within_bounds(location):
    return 1000 <= location <= 2072


def inRange(actual, expected, range):
    return abs(actual - expected) <= range


def calculate_horizontal_sweepline_radii(lines = 6):
    """Calculate radii for horizontal sweep lines, so that they are evenly spaced out."""
    main_radius = 4096 // (math.pi * 2)
    division = 90 / lines
    radii = []
    for i in range(0, lines + 1):
        radius = main_radius * math.sin(math.radians(90 - (division * i)))
        radii.append(int(radius))
    return radii


def calculate_vertical_movement_distances(lines = 6):
    """Calculate vertical positions for a given number of lines, so that the lines are evenly spaced out vertically."""	
    y_positions = []
    for i in range(0, lines + 1):
        y = 1024 + i*(1024 // lines)
        y_positions.append(y)
    return y_positions


def calculate_circular_coordinates(center_x, center_y, radius, n):
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


def calculate_horizontal_distances(num_points=12, circumference=4092, start_angle=15):
    """Calculate num_points amount of horizontal distances from point 0 all the way to 4096. These distances are what the servos will move to."""
    distances = []
    angle_increment = 360 / num_points

    for i in range(num_points):
        angle_degrees = (start_angle + i * angle_increment) % 360
        distance = (angle_degrees / 360) * circumference
        distances.append((angle_degrees, int(distance)))
    return distances


def collectGarbage(esp32):
    print("Serial port opened.")
    time.sleep(1)
    response = esp32.readline().decode().strip()
    if len(response) > 0:
        print("Garbage:", response)


def servosReady(esp32):
    while True:
        horizontal  = get_position(esp32, 1)
        vertical    = get_position(esp32, 2)
        if horizontal == -1 or vertical == -1:
            print(f"Servo 1: {horizontal}, Servo 2: {vertical}. Retrying in 1 second.")
            time.sleep(1)
        else:
            return True


def center_servos():
    input(
        "First turn power switch off manually, then move servos by hand to center, finally press enter when done to calibrate."
    )

    with serial.Serial(SERIAL_PORT, 115200, timeout=1) as esp32:
        esp32.write((f"CALIBRATE,1" + "\n").encode())
        esp32.write((f"CALIBRATE,2" + "\n").encode())

        esp32.write((f"GET_POS,1" + "\n").encode())
        print(esp32.readline().decode().strip())
        esp32.write((f"GET_POS,2" + "\n").encode())
        print(esp32.readline().decode().strip())
        print("Servos calibrated.")


def get_position(esp32, servo_id):
    esp32.write((f"GET_POS,{servo_id}" + "\n").encode())
    location = int(esp32.readline().decode().split(",")[2])

    # Update global variables while we are at it
    match servo_id:
        case 1:
            global CURRENT_POSITION_1
            CURRENT_POSITION_1 = location
        case 2:
            global CURRENT_POSITION_2
            CURRENT_POSITION_2 = location

    # print(f"Servo {servo_id} is at position {location}.")
    return location

def get_telemetry(esp32, servo_id) -> dict:
    esp32.write((f"GET_TELEMETRY,{servo_id}" + "\n").encode())
    telemetry = esp32.readline().decode().split(",")
    #TELEMETRY,<servo_id>,<position>,<speed>,<load>,<voltage>,<temperature>,<move>,<current>
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
    return telemetry_data

def move_to(esp32, servo_id, expected_pos):
    # safeguard for y-axis
    if servo_id == 2:
        if not y_future_within_bounds(expected_pos):
            raise VerticalServoFutureOutOfBounds

    esp32.write(
        (f"MOVE,{servo_id},{expected_pos},{GLOBAL_SPEED},{GLOBAL_ACC}" + "\n").encode()
    )


def syncmove_to(esp32, servo_id1, servo_id2, expected_pos1, expected_pos2):
    # safeguard for y-axis
    if servo_id2 == 2:
        if not y_future_within_bounds(expected_pos2):
            raise VerticalServoFutureOutOfBounds
    esp32.write(
        (
            f"SYNC_MOVE,[{servo_id1},{servo_id2}],2,[{expected_pos1},{expected_pos2}],[{GLOBAL_SPEED},{GLOBAL_SPEED}],[{GLOBAL_ACC},{GLOBAL_ACC}]"
            + "\n"
        ).encode()
    )


def syncmove_distance(esp32, servo_id1, servo_id2, distance1, distance2):
    current_pos1 = get_position(esp32, servo_id1)
    current_pos2 = get_position(esp32, servo_id2)
    expected_pos1 = current_pos1 + distance1
    expected_pos2 = current_pos2 + distance2

    # safeguard for y-axis
    if servo_id2 == 2:
        if not y_future_within_bounds(distance2):
            raise VerticalServoFutureOutOfBounds

    esp32.write(
        (
            f"SYNC_MOVE,[{servo_id1},{servo_id2}],2,[{expected_pos1},{expected_pos2}],[{GLOBAL_SPEED},{GLOBAL_SPEED}],[{GLOBAL_ACC},{GLOBAL_ACC}]"
            + "\n"
        ).encode()
    )


def move_to_and_wait_for_complete(esp32, servo_id, expected_pos):

    move_to(esp32, servo_id, expected_pos)

    while True:
        current_pos = get_position(esp32, servo_id)
        if inRange(current_pos, expected_pos, 20):
            break


def move_distance_and_wait_for_complete(esp32, servo_id, distance):
    current_pos = get_position(esp32, servo_id)
    expected_pos = current_pos + distance
    move_to(esp32, servo_id, expected_pos)
    while True:
        current_pos = get_position(esp32, servo_id)
        if inRange(current_pos, expected_pos, 20):
            break


def scan_horizontal(
    esp32,
    sweeps,
    window_width,
    window_center,
    vertical_lines,
    horizontal_lines,
):

    window_radius = window_width // 2
    window_start = window_center - window_radius
    window_end = window_center + window_radius

    horizontal_step_size = window_width // horizontal_lines
    vertical_step_size = 1024 // vertical_lines

    move_to_and_wait_for_complete(esp32, 1, window_start)
    move_to_and_wait_for_complete(esp32, 2, 1024)

    for i in range(sweeps):
        print("=====================================")
        print(f"Sweep {i + 1}/{sweeps}")
        print("-------------------------------------")
        print("Window start:", window_start)
        print("Window end:", window_end)
        print("Horizontal step size:", horizontal_step_size)
        print("Vertical step size:", vertical_step_size)
        print("Window height:", 1024)
        print("Window width:", window_width)
        print("Current starting position 1:", get_position(esp32, 1))
        print("Current starting position 2:", get_position(esp32, 2))
        print("=====================================")
        x = 0

        for j in range(1, vertical_lines + 1, 2):
            move_to_and_wait_for_complete(esp32, 2, 1024 + (j - 1) * vertical_step_size)
            print("Vertical position:", get_position(esp32, 2))
            print("Horizontal position:", get_position(esp32, 1), "Performing scan.")
            perform_scan(esp32)

            points = horizontal_lines - x
            horizontal_step_size = window_width // points if points > 0 else 1
            for k in range(points):
                move_distance_and_wait_for_complete(esp32, 1, horizontal_step_size)
                print(
                    "Horizontal position:", get_position(esp32, 1), "Performing scan."
                )
                perform_scan(esp32)
            x += 1

            move_to_and_wait_for_complete(esp32, 2, 1024 + (j) * vertical_step_size)
            print("Vertical position:", get_position(esp32, 2))

            points = horizontal_lines - x
            horizontal_step_size = window_width // points if points > 0 else 1
            for k in range(points):
                move_distance_and_wait_for_complete(esp32, 1, -horizontal_step_size)
                print(
                    "Horizontal position:", get_position(esp32, 1), "Performing scan."
                )
                perform_scan(esp32)
            x += 1

    move_to_and_wait_for_complete(esp32, 1, window_start)
    move_to_and_wait_for_complete(esp32, 2, 1024)


def full_sweep_optimal(esp32):
    horizontal_lines = 6
    y_positions = calculate_vertical_movement_distances(horizontal_lines)
    point_array = [12,10,8,6,4,3,1]

    start_time = time.time()

    for i in range(len(y_positions)):
            #print(f"VERTICAL [{i}] Moving to y position {y_positions[i]}.")
            move_to_and_wait_for_complete(esp32, 2, y_positions[i])

            points = point_array[i]
            #circumference = 4096  #math.pi*2*x_radiuses[i]
            start_angle = 15 if (i % 2 == 0) else 0
            x_positions = calculate_horizontal_distances(points, 4096, start_angle)
            #print(x_positions)
            for x_position in x_positions if i % 2 == 0 else reversed(x_positions):
                move_to_and_wait_for_complete(esp32, 1, x_position[1])
                perform_scan(esp32, x_positions.index(x_position), x_position[0], x_position[1], y_positions[i])

    end_time = time.time()
    print(f"Full sweep time taken: {int(end_time - start_time)} seconds.")


def horizontal_only_sweep(esp32, number_of_points = 12):
    move_to_and_wait_for_complete(esp32, 2, 1024)
    x_positions = calculate_horizontal_distances(number_of_points, 4096, 0)
    
    reverse = False
    skip_first = False

    while True:
        for x_position in reversed(x_positions) if reverse else x_positions:
            if skip_first:
                skip_first = False
                continue
            move_to_and_wait_for_complete(esp32, 1, x_position[1])
            perform_scan(x_positions.index(x_position), x_position[0], x_position[1], 1024)
        reverse = not reverse
        skip_first = True


def perform_scan(esp32, n, angle, x, y):
    telemetry_1 = get_telemetry(esp32, 1)
    telemetry_2 = get_telemetry(esp32, 2)
    print(f"[{n}]Performing scan at x angle {angle} and x {x}, y {y}. Temp1 {telemetry_1['temperature']} Temp2 {telemetry_2['temperature']}.")
    if int(telemetry_1['temperature']) >= 50 or int(telemetry_2['temperature']) >= 50:
        raise ServoTemperatureTooHigh("Servo temperature too high.")
    time.sleep(0.2)


async def communicate():
    if MODE == "serial":
        first_run = True
        with serial.Serial(SERIAL_PORT, 115200, timeout=1) as esp32:
            while True:
                if first_run:
                    collectGarbage(esp32)
                    if servosReady(esp32):
                        print("Servos ready.")
                    first_run = False

                     # Reset and move to a safe forward position before doing stuff
                    move_to_and_wait_for_complete(esp32, 1, 2048)
                    move_to_and_wait_for_complete(esp32, 2, 1024)

                # do stuff here
                full_sweep_optimal(esp32)
                #horizontal_only_sweep(esp32, 32)
    else:
        print("Invalid mode selected. Please select either 'wifi' or 'serial'.")


if __name__ == "__main__":
    asyncio.run(communicate())
