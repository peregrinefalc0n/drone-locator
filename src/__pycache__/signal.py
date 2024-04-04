class Signal:
    """Class that represents a signal"""

    def __init__(self, start_freq, end_freq, peak_power_db, peak_freq):
        self.start_freq = start_freq
        self.end_freq = end_freq
        self.peak_power_db = peak_power_db
        self.peak_freq = peak_freq

        self.bandwidth = end_freq - start_freq
        self.center_freq = (end_freq + start_freq) / 2

        self.x = None
        self.y = None
        self.channel = None
        self.potential_channels = list()

        # List of lists where each inner list is a sweep's worth of signals positions tuples (x, y, strength_in_dbm)
        # inner list index is the sweep id/number
        self.position_history = list()
        self.sweep_number = 0

    def to_string(self):
        return f"Signal: {self.start_freq} - {self.end_freq} MHz, {self.peak_power_db} dBm, {self.peak_freq} MHz, position: {self.x}, {self.y}"

    def new_id(self):
        global id
        id += 1
        return id

    def update_sweep_list(self):
        while len(self.position_history) < self.sweep_id + 1:
            self.position_history.append(list())

    def inc_sweep_id(self):
        self.sweep_id += 1
