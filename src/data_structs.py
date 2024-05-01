signal_id = 0
sweep_id = 0


class ID_gen:
    def new_signal_id():
        """Returns a new unique id for signals"""
        global signal_id
        signal_id += 1
        return signal_id

    def new_sweep_id():
        """Returns a new unique id for sweeps"""
        global sweep_id
        sweep_id += 1
        return sweep_id

    def current_signal_id():
        """Returns the current signal id"""
        return signal_id

    def current_sweep_id():
        """Returns the current sweep id"""
        return sweep_id


class Signal:
    """Class that represents a signal"""

    def __init__(self, start_freq = None, end_freq = None, peak_power_db = None, peak_freq = None):
        self.id = ID_gen.new_signal_id()
        self.start_freq = start_freq
        self.end_freq = end_freq
        self.bandwidth = None
        self.center_freq = None
        self.is_of_interest = False

        self.peak_power_db = peak_power_db
        self.peak_freq = peak_freq
        self.peak_x = None
        self.peak_y = None

        self.channel_name = None
        self.position_history = PositionHistory()

    def log_string(self):
        return f"ID {self.id}, Signal: {self.start_freq} MHz - {self.end_freq} MHz, Peak {self.peak_power_db} dBm at {self.peak_freq} MHz, Position: {self.x} x, {self.y} y, Channel {'False' if self.channel_name is None else 'True'}: {self.channel_name}"

    def csv_string(self):
        return f"{self.start_freq},{self.end_freq},{self.bandwidth},{self.peak_power_db},{self.peak_freq},{self.x},{self.y},{self.channel_name}"

    def csv_header(self):
        return "Start Frequency,End Frequency,Bandwidth,Peak Power (dBm),Peak Frequency,Position X,Position Y,Channel Name"


class Position:
    """Class that represents a historical position"""

    def __init__(self, x, y, peak_power_db=None, peak_freq=None):
        self.x = x
        self.y = y
        self.peak_power_db = None
        self.peak_freq = None
        self.is_of_interest = False
        self.sweep_id = ID_gen.current_sweep_id()


class PositionHistory:
    """Class that represents a list of historical of positions for a signal"""

    def __init__(self):
        self.positions = list()

    def add(self, position: Position):
        self.positions.append(position)

    def get_all(self):
        return self.positions

class Sweep:
    """Class that represents a single sweep in a scan"""

    def __init__(self):
        self.sweep_id = None


class Scanner:
    """Class that represents a scanner that performs sweeps and updates channel/signals"""

    def __init__(self):
        self.sweeps = list()
        

class Channel:
    """Class that represents a channel"""

    def __init__(
        self, name: str, center_freq: float, start_freq: float, end_freq: float
    ):
        self.name = name
        self.center_freq = center_freq
        self.start_freq = start_freq
        self.end_freq = end_freq
        self.signal = None
    
    def get_signal(self : Signal):
        return self.signal


class ChannelDict:
    """Class that represents a list of channels (currently only channels A1-A8) where there is a signal on each channel"""

    def __init__(self):
        self.channels = list()

        channel_a_ranges = [
            [5850, 5880],
            [5830, 5860],
            [5810, 5840],
            [5790, 5820],
            [5770, 5800],
            [5750, 5780],
            [5730, 5760],
            [5710, 5740],
        ]
        channel_a_centers = [5865, 5845, 5825, 5805, 5785, 5765, 5745, 5725]

        for i in range(1, 9):
            self.channels.append(
                Channel(
                    f"A{i}",
                    channel_a_centers[i],
                    channel_a_ranges[i][0],
                    channel_a_ranges[i][1],
                )
            )
    
    def get_all(self):
        return self.channels
