import time
import serial
import asyncio
import math


MODE = "serial"
SERIAL_PORT = "COM5"

GLOBAL_ACC = 100
GLOBAL_SPEED = 4000

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
    """Calculate num_points amount of horizontal distances from point 0 all the way to 4096"""
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
    return False


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


def sweep_horizontal_optimal(esp32, horizontal_lines = 6):
    #move to default position
    #calculate y positions
    y_positions = calculate_vertical_movement_distances(horizontal_lines)
    #calculate each horizontal layers path radius
    x_radiuses = calculate_horizontal_sweepline_radii(horizontal_lines)

    point_array = [12,10,8,8,6,4,1]

    start_time = time.time()

    for i in range(len(y_positions)):
            move_to_and_wait_for_complete(esp32, 2, y_positions[i])

            points = point_array[i]
            circumference = 4096  #math.pi*2*x_radiuses[i]
            start_angle = (15 * 1) if (i % 2 == 0) else (15 * 0)
            if points == 1:
                start_angle = 0
            x_positions = calculate_horizontal_distances(points, circumference,start_angle)
            print(x_positions)
            for x_position in x_positions if i % 2 == 0 else reversed(x_positions):
                move_to_and_wait_for_complete(esp32, 1, x_position[1])
                time.sleep(0.1)

                #perform_scan(x_position[0], x_position[1], y_positions[i])

    end_time = time.time()

    print(f"Full sweep time taken: {int(end_time - start_time)} seconds.")
    #scan completed
    #move to default position



def perform_scan(angle, x, y):
    print(f"Performing scan at x angle {angle} and x {x}, y {y}.")
    for i in range(1, 4):
        print("Scanning" + i * ".")
        time.sleep(0.1)


async def communicate():
    if MODE == "serial":
        first_run = True
        with serial.Serial(SERIAL_PORT, 115200, timeout=1) as esp32:
            while True:
                if first_run:
                    first_run = collectGarbage(esp32)

                # Reset and move to a safe forward position before doing stuff
                move_to_and_wait_for_complete(esp32, 1, 2048)
                move_to_and_wait_for_complete(esp32, 2, 1024)

                # do stuff here
                sweep_horizontal_optimal(esp32)
    else:
        print("Invalid mode selected. Please select either 'wifi' or 'serial'.")


if __name__ == "__main__":
    asyncio.run(communicate())
