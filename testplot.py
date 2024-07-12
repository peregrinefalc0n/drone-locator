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
    
if __name__ == "__main__":
    #plot_data("TESTS/TEST_time16_44_22_n50_distance5_power25.csv") # 50 points bad (-20ish)
    #plot_data("TESTS/TEST_time18_33_51_n100_distance5_power25.csv") # 100 points also bad result but all on left side (-20ish)
    plot_data("TESTS/TEST_time18_45_01_n120_distance5_power25.csv") # 120 points great result
