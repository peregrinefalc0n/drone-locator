import csv

import matplotlib.pyplot as plt

def plot_data(filename):
    # Initialize lists to hold the data
    horizontal_angles = []
    vertical_angles = []

    # Read data from CSV file
    with open(filename, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            horizontal_angles.append(float(row[' ch_horizontal_angle']))
            vertical_angles.append(float(row[' ch_vertical_angle']))

    # Plotting
    plt.figure(figsize=(10, 6))

    # Plot all points
    plt.scatter(horizontal_angles, vertical_angles, label='Points', marker='o', color='blue')

    # Include the origin point
    plt.scatter(0, 0, color='red', label='Origin (0, 0)', marker='x')

    # Labels and Title
    plt.xlabel('Horizontal Angle Deviation')
    plt.ylabel('Vertical Angle Deviation')
    plt.title('Off-Axis Deviation')
    plt.legend()
    plt.grid(True)

    # Show plot
    plt.show()

def plot_data_two_horizontals(filename):
    # Initialize lists to hold the data
    first_point_horizontal_angles = []
    first_point_vertical_angles = []
    second_point_horizontal_angles = []
    second_point_vertical_angles = []

    with open(filename, 'r') as file:
        reader = csv.DictReader(file)
        for i, row in enumerate(reader):
            if i < 10:
                first_point_horizontal_angles.append(float(row[' ch_horizontal_angle']))
                first_point_vertical_angles.append(float(row[' ch_vertical_angle']))
            if i >= 10:
                second_point_horizontal_angles.append(float(row[' ch_horizontal_angle']))
                second_point_vertical_angles.append(float(row[' ch_vertical_angle']))
    
    # Calculate the average of the first 10 measurements and the average of the second 10 measurements to get the average position of first and second point
    first_point_horizontal_avg = sum(first_point_horizontal_angles) / len(first_point_horizontal_angles)
    first_point_vertical_avg = sum(first_point_vertical_angles) / len(first_point_vertical_angles)
    second_point_horizontal_avg = sum(second_point_horizontal_angles) / len(second_point_horizontal_angles)
    second_point_vertical_avg = sum(second_point_vertical_angles) / len(second_point_vertical_angles)

    # Plotting
    plt.figure(figsize=(10, 6))

    # Plot all points
    plt.scatter(first_point_horizontal_angles, first_point_vertical_angles, label='P1 measurements', marker='o', color='blue')
    plt.scatter(second_point_horizontal_angles, second_point_vertical_angles, label='P2 measurements', marker='o', color='red')

    # Include the center point
    plt.scatter(0, 0, color='green', label='Center (0, 0)', marker='+')
    
    # Include the average point
    plt.scatter(first_point_horizontal_avg, first_point_vertical_avg, color='blue', label='P1 Average', marker='x')
    plt.scatter(second_point_horizontal_avg, second_point_vertical_avg, color='red', label='P2 Average', marker='x')


    #Calculate the angle between the P1 and the P2 average points
    angle_p1 = round(((int(first_point_horizontal_avg) - 2048) / 2048 * 180), ndigits=3)
    angle_p2 = round(((int(second_point_horizontal_avg) - 2048) / 2048 * 180), ndigits=3)
    angle_between_p1_p2 = round(abs(angle_p2) + abs(angle_p1), ndigits=3)


    # Labels and Title
    plt.xlabel('Horizontal Axis')
    plt.ylabel('Vertical Axis')
    plt.title(f'Error Analysis. Angle P1 <-> P2: {angle_between_p1_p2}°')
    plt.legend()
    plt.grid(True)


    # Show plot
    plt.show()


if __name__ == "__main__":
    #plot_data("TESTS/TEST_time16_44_22_n50_distance5_power25.csv") # 50 points bad (-20ish)
    #plot_data("TESTS/TEST_time18_33_51_n100_distance5_power25.csv") # 100 points also bad result but all on left side (-20ish)
    plot_data("TESTS/TEST_time18_45_01_n120_distance5_power25.csv") # 120 points great result
