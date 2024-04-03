from pyhackrf2 import HackRF
import numpy as np
from matplotlib.pyplot import psd, xlabel, ylabel, show

id = 0

channel_list = {
    "A": [5865, 5845, 5825, 5805, 5785, 5765, 5745, 5725],
    "B": [5733, 5752, 5771, 5790, 5809, 5828, 5847, 5866],
    "E": [5705, 5685, 5665, 5645, 5885, 5905, 5925, 5945],
    "F": [5740, 5760, 5780, 5800, 5820, 5840, 5860, 5880],
    "R": [5658, 5695, 5732, 5769, 5806, 5843, 5880, 5917],
    "D": [5362, 5399, 5436, 5473, 5510, 5547, 5584, 5621],
    "U": [5325, 5348, 5366, 5384, 5402, 5420, 5438, 5456],
    "O": [5474, 5492, 5510, 5528, 5546, 5564, 5582, 5600],
    "L": [5333, 5373, 5413, 5453, 5493, 5533, 5573, 5613],
    "H": [5653, 5693, 5733, 5773, 5813, 5853, 5893, 5933],
}


class Signal:
    """Class that represents a signal"""

    def __init__(self, start_freq, end_freq, peak_power_db, peak_freq):
        self.id = self.new_id()
        self.start_freq = start_freq
        self.end_freq = end_freq
        self.peak_power_db = peak_power_db
        self.peak_freq = peak_freq
        self.bandwidth = end_freq - start_freq
        self.center_freq = (end_freq + start_freq) / 2
        self.x = None
        self.y = None

        # List of lists where each inner list is a sweep's worth of signals positions tuples (x, y, strength_in_dbm)
        # inner list index is the sweep id/number
        self.position_history = list(list())
        self.sweep_id = 0

    def to_string(self):
        return f"Signal: {self.start_freq} - {self.end_freq} MHz, {self.peak_power_db} dBm, {self.peak_freq} MHz, position: {self.x}, {self.y}"

    def new_id(self):
        global id
        id += 1
        return id

    def inc_sweep_id(self):
        self.sweep_id += 1

    def update_sweep_list(self):
        while len(self.position_history) < self.sweep_id + 1:
            self.position_history.append(list())


class SignalProcessor:
    """Class that processes signals. It takes a HackRF device id, sample rate, sample count, center frequency and amplifier state as arguments. \n
    Method get_signals returns a list of signals that are above the noise floor by the given offset in dBm. \n
    """

    def __init__(self, id, sample_rate=20e6, sample_count=1e6, center_freq=5780e6):
        self.device_id = id
        self.sample_count = sample_count
        # self.sample_rate = sample_rate
        # self.center_freq = center_freq
        # self.amplifier_on = amplifier_on

        self.hackrf = HackRF(device_index=self.device_id)
        self.hackrf.sample_rate = sample_rate
        self.hackrf.center_freq = center_freq

    def set_amplifier(self, state):
        """Sets the amplifier state to the provided state."""
        self.hackrf.amplifier_on = state

    def __mW_to_dBm(self, power):
        """Converts power in mW to dBm"""
        return np.around(10 * np.log10(power / 1), 2)

    def __measure(self):
        """Measures the samples and returns them"""
        samples = self.hackrf.read_samples(self.sample_count)
        return samples

    def __process(self, offset=10, show_graph=False):
        """Processes the samples and returns a list of signals that are above the noise floor by the given offset in dBm, and the raw data."""
        pxx, freqs = psd(
            self.__measure(),
            NFFT=2048,
            Fs=self.hackrf.sample_rate / 1e6,
            Fc=self.hackrf.center_freq / 1e6,
            return_line=False,
        )
        raw_data = [pxx, freqs]

        if show_graph:
            xlabel("Frequency (MHz)")
            ylabel("Relative power (dB)")
            show()

        # Take the first 1000 samples to avoid the DC spike (essentially taking less than half of our samples (we had 2048 of them))
        select_count = 1000
        pxx_sample = pxx[:select_count]
        freqs_sample = freqs[:select_count]

        # Find the minimum power in the sample to see where the noise floor is
        min_index = np.argmin(pxx_sample)
        min_pxx_db = self.__mW_to_dBm(pxx_sample[min_index])

        # TODO find a more elegant or dynamic solution instead of hardcoding the offset value from lowest recorded power value

        # reset the sample arrays to max size again
        freqs_sample = freqs
        pxx_sample = pxx

        # Find the signals that are above the noise floor by the given offset
        signals_list = list()
        index = 0
        while index < len(pxx_sample):
            # skip DC spike
            if index == 1000:
                index = 1048
            power_db = self.__mW_to_dBm(pxx_sample[index])
            if power_db >= min_pxx_db + offset:
                temp_signal = Signal(
                    freqs_sample[index],
                    freqs_sample[index],
                    power_db,
                    freqs_sample[index],
                )
                power_db = self.__mW_to_dBm(pxx_sample[index])
                while (power_db >= min_pxx_db + offset) and (index < len(pxx_sample)):
                    power_db = self.__mW_to_dBm(pxx_sample[index])
                    temp_signal.end_freq = freqs_sample[index]
                    if power_db > temp_signal.peak_power_db:
                        temp_signal.peak_power_db = power_db
                        temp_signal.peak_freq = freqs_sample[index]
                    index += 1
                signals_list.append(temp_signal)
            index += 1

        return (signals_list, raw_data)

    def get_signals(self, offset=10, show_graph=False):
        """Returns a list of signals that are above the lowest signal by the given offset in dBm. \n
        If show_graph is set to True, a graph of the power spectral density is shown (blocking). \n
        """
        return self.__process(offset, show_graph)


if __name__ == "__main__":
    print("This is a module file. Run gui.py instead.")
