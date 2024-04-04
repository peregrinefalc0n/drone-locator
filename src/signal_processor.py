from pyhackrf2 import HackRF
import numpy as np
from matplotlib.pyplot import psd
from . import objects

id = 0

channel_freq_range_list = {
    "A": [
        [5850, 5880],
        [5830, 5860],
        [5810, 5840],
        [5790, 5820],
        [5770, 5800],
        [5750, 5780],
        [5730, 5760],
        [5710, 5740],
    ],
    "B": [
        [5718, 5748],
        [5737, 5767],
        [5756, 5786],
        [5775, 5805],
        [5794, 5824],
        [5813, 5843],
        [5832, 5862],
        [5851, 5881],
    ],
    "E": [
        [5690, 5720],
        [5670, 5700],
        [5650, 5680],
        [5630, 5660],
        [5870, 5900],
        [5890, 5920],
        [5910, 5940],
        [5930, 5960],
    ],
    "F": [
        [5725, 5755],
        [5745, 5775],
        [5765, 5795],
        [5785, 5815],
        [5805, 5835],
        [5825, 5855],
        [5845, 5875],
        [5865, 5895],
    ],
    "R": [
        [5643, 5673],
        [5679, 5709],
        [5716, 5746],
        [5753, 5783],
        [5790, 5820],
        [5827, 5857],
        [5864, 5894],
        [5901, 5931],
    ],
    "D": [
        [5347, 5377],
        [5384, 5414],
        [5421, 5451],
        [5458, 5488],
        [5495, 5525],
        [5532, 5562],
        [5569, 5599],
        [5606, 5636],
    ],
    "U": [
        [5300, 5330],
        [5323, 5353],
        [5341, 5371],
        [5359, 5389],
        [5377, 5407],
        [5395, 5425],
        [5413, 5443],
        [5431, 5461],
    ],
    "O": [
        [5459, 5489],
        [5477, 5507],
        [5495, 5525],
        [5513, 5543],
        [5531, 5561],
        [5549, 5579],
        [5567, 5597],
        [5585, 5615],
    ],
    "L": [
        [5318, 5348],
        [5358, 5388],
        [5398, 5428],
        [5438, 5468],
        [5478, 5508],
        [5518, 5548],
        [5558, 5588],
        [5598, 5628],
    ],
    "H": [
        [5638, 5668],
        [5678, 5708],
        [5718, 5748],
        [5758, 5788],
        [5798, 5828],
        [5838, 5868],
        [5878, 5908],
        [5918, 5948],
    ],
}

channel_center_freq_list = {
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


class SignalProcessor:
    """Class that processes signals. It takes a HackRF device id, sample rate, sample count, center frequency and amplifier state as arguments. \n
    Method get_signals returns a list of signals that are above the noise floor by the given offset in dBm. \n
    """

    def __init__(self, id, sample_rate=20e6, sample_count=1e6, center_freq=5772e6):
        self.device_id = id
        self.sample_count = sample_count
        self.fft_count = 2048
        self.manual_offset_in_use = False
        self.manual_offset_value = 10
        self.db_offset_in_use = 0.0

        self.hackrf = HackRF(device_index=self.device_id)
        self.hackrf.sample_rate = sample_rate
        self.hackrf.center_freq = center_freq

    def set_amplifier(self, state):
        """Sets the amplifier state to the provided state."""
        self.hackrf.amplifier_on = state

    def mW_to_dBm(self, power):
        """Converts power in mW to dBm"""
        return round(10 * np.log10(power / 1), 2)

    def __measure(self):
        """Measures the samples and returns them"""
        samples = self.hackrf.read_samples(self.sample_count)
        return samples

    def __process(self):
        """Processes the samples and returns a list of signals that are above the noise floor by the given offset in dBm, and the raw data."""
        pxx, freqs = psd(
            self.__measure(),
            NFFT=self.fft_count,
            Fs=self.hackrf.sample_rate / 1e6,
            Fc=self.hackrf.center_freq / 1e6,
            return_line=False,
        )
        raw_data = [pxx, freqs]

        level_of_interest_db = 0.0
        level_of_interest_db_max = -35.0
        level_of_interest_db_min = -55.0

        # Set the level of interest to the minimum power + offset
        if self.manual_offset_in_use:
            level_of_interest_db = self.manual_offset_value
            self.db_offset_in_use = level_of_interest_db
        else:
            select_count = (self.fft_count // 2) - 24
            # Take the first half of samples to avoid the DC spike
            pxx_sample = pxx[:select_count]
            freqs_sample = freqs[:select_count]

            # Find the minimum power in the sample to which we add the average power to get the level of interest
            min_index = np.argmin(pxx_sample)
            avg_pxx_db = self.mW_to_dBm(np.average(pxx_sample))  # avg value
            min_pxx_db = self.mW_to_dBm(pxx_sample[min_index])  # min value
            level_of_interest_db = min_pxx_db + 4 * (abs(min_pxx_db) - abs(avg_pxx_db))
            # print(min_pxx_db, avg_pxx_db, level_of_interest_db, self.db_offset_in_use)

        # Limit the level of interest to the max and min values
        if level_of_interest_db < level_of_interest_db_min:
            level_of_interest_db = level_of_interest_db_min
        elif level_of_interest_db > level_of_interest_db_max:
            level_of_interest_db = level_of_interest_db_max

        # reset the sample arrays to max size again
        freqs_sample = freqs
        pxx_sample = pxx
        self.db_offset_in_use = level_of_interest_db

        # Find the signals that are above the noise floor by the given offset
        signals_list = list()
        index = 0
        while index < len(pxx_sample):
            # skip DC spike
            if index == 1000:
                index = 1048
            power_db = self.mW_to_dBm(pxx_sample[index])
            if power_db >= level_of_interest_db:
                temp_signal = objects(
                    freqs_sample[index],
                    freqs_sample[index],
                    power_db,
                    freqs_sample[index],
                )
                power_db = self.mW_to_dBm(pxx_sample[index])
                while (power_db >= level_of_interest_db) and (index < len(pxx_sample)):
                    power_db = self.mW_to_dBm(pxx_sample[index])
                    temp_signal.end_freq = freqs_sample[index]
                    if power_db > temp_signal.peak_power_db:
                        temp_signal.peak_power_db = power_db
                        temp_signal.peak_freq = freqs_sample[index]
                    index += 1
                signals_list.append(temp_signal)
            index += 1

        return (signals_list, raw_data)

    def get_signals(self):
        """Returns a list of signals that are above the lowest signal by the given offset in dBm. \n
        The signals are represented as Signal objects. \n
        The raw data is also returned. \n
        """
        return self.__process()


def mW_to_dBm(value):
    """Converts power in mW to dBm"""
    return round(10 * np.log10(value / 1), 2)


def calculate_signal_channel(signal:objects):
    """Updates the signals' channels based on the signals' peak frequencies. \n
    If no channel is a direct fit, assigns potential channels to signals based on their peak frequencies. \n
    """
    # if signals peak freq is exactly a channel center freq, assign the channel to that signal
    for channel, center_freq_list in channel_center_freq_list.items():
        if round(signal.peak_freq) in center_freq_list:
            signal.channel = channel + str(
                center_freq_list.index(round(signal.peak_freq))
            )
            break

    if signal.channel is not None:
        return True

    # assign potential channels to signals based on their peak freq
    for channel, freq_range_list in channel_freq_range_list.items():
        for freq_range in freq_range_list:
            if signal.peak_freq >= freq_range[0] and signal.peak_freq <= freq_range[1]:
                signal.potential_channels.append(
                    channel + str(freq_range_list.index(freq_range))
                )
                break

    if signal.channel is None:
        signal.channel = "Unknown"
        return False
    return True


if __name__ == "__main__":
    print("This is a module file. Run gui.py instead.")
