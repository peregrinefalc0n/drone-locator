from pyhackrf2 import HackRF
import numpy as np
from matplotlib.pyplot import psd
from data_structs import *

class SignalProcessor:
    """Class that processes signals. It takes a HackRF device id, sample rate, sample count, center frequency and amplifier state as arguments. \n
    It updates the ChannelDict chdict. \n
    """

    def __init__(self, id, database : ChannelDict, sample_rate=20e6, sample_count=1e6, center_freq=5772e6):
        self.device_id = id
        self.database = database
        self.sample_count = sample_count
        self.fft_count = 2048
        self.manual_offset_in_use = False
        self.manual_offset_value = 10
        self.db_offset_in_use = 0.0
        self.id_provider = ID_gen()

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

    def __process(self, x, y):
        """Processes the samples and updates channels."""
        pxx, freqs = psd(
            self.__measure(),
            NFFT=self.fft_count,
            Fs=self.hackrf.sample_rate / 1e6,
            Fc=self.hackrf.center_freq / 1e6,
            return_line=False,
        )
        raw_data = [pxx, freqs]

        level_of_interest_db = 0.0
        level_of_interest_db_max = -30.0
        level_of_interest_db_min = -50.0

        # Set the level of interest to the minimum power + offset
        if self.manual_offset_in_use:
            level_of_interest_db = self.manual_offset_value
            self.db_offset_in_use = level_of_interest_db
        else:
            select_count = (
                self.fft_count // 2
            ) - 12  # so for example with 2048 samples we ignore the middle 24 samples (12 from each side) to avoid the DC spike
            # Take the first half of samples to avoid the DC spike
            pxx_sample = pxx[:select_count].extend(pxx[select_count:])
            freqs_sample = freqs[:select_count].extend(freqs[select_count:])

            # Find the minimum power in the sample to which we add the average power to get the level of interest
            min_index = np.argmin(pxx_sample)
            median_pxx_db = self.mW_to_dBm(np.median(pxx_sample))  # median value
            min_pxx_db = self.mW_to_dBm(pxx_sample[min_index])  # min value
            level_of_interest_db = min_pxx_db + 2 * abs(
                abs(min_pxx_db) - abs(median_pxx_db)
            )
            freqs_sample = freqs
            pxx_sample = pxx
            self.db_offset_in_use = level_of_interest_db

        # Limit the level of interest to between the hardcoded max and min values
        if level_of_interest_db < level_of_interest_db_min:
            level_of_interest_db = level_of_interest_db_min
        elif level_of_interest_db > level_of_interest_db_max:
            level_of_interest_db = level_of_interest_db_max

        index = 0
        for channel in self.database.channels:
            if channel.start_freq > freqs_sample[-1] or channel.end_freq < freqs_sample[0]:
                continue
            
            current_start_freq = channel.start_freq
            current_end_freq = channel.end_freq
            current_signal = channel.get_signal()
            
            if current_signal is None:
                current_signal = Signal()
                channel.signal = current_signal
            
            temp_historical_pos = Position(x, y)
            
            while current_start_freq <= freqs_sample[index] and freqs_sample[index] <= current_end_freq:
                if index >= len(pxx_sample):
                    break
                
                #skip dc spike
                if index == 1012:
                    index = 1036
                
                power_db = self.mW_to_dBm(pxx_sample[index])                
                if power_db >= temp_historical_pos.peak_power_db:
                    temp_historical_pos.peak_power_db = power_db
                    temp_historical_pos.peak_freq = freqs_sample[index]
                    temp_historical_pos.sweep_id = self.id_provider.current_sweep_id()
                
                if power_db >= level_of_interest_db:
                    if freqs_sample[index] < current_signal.start_freq:
                        current_signal.start_freq = freqs_sample[index]
                    if freqs_sample[index] > current_signal.end_freq:
                        current_signal.end_freq = freqs_sample[index]
                    
                index += 1
            
            if temp_historical_pos.peak_power_db >= level_of_interest_db:
                temp_historical_pos.is_of_interest = True
                current_signal.is_of_interest = True
            
            if temp_historical_pos.peak_power_db >= current_signal.peak_power_db:
                current_signal.peak_power_db = temp_historical_pos.peak_power_db
                current_signal.peak_freq = temp_historical_pos.peak_freq
                current_signal.peak_x = x
                current_signal.peak_y = y
            
            current_signal.position_history.add(temp_historical_pos)

        return raw_data


       
    def get_signals(self, x, y, offset=None):
        """Returns a list of signals that are above the lowest signal by the given offset in dBm. \n
        The signals are represented as Signal objects. \n
        The raw data is also returned. \n
        """
        if offset is not None:
            self.manual_offset_in_use = True
            self.manual_offset_value = offset
        
        return self.__process(x, y)


def mW_to_dBm(value):
    """Converts power in mW to dBm"""
    return round(10 * np.log10(value / 1), 2)


def calculate_signal_channel(signal: Signal):
    """Updates the signals' channels based on the signals' peak frequencies. \n
    If no channel is a direct fit, assigns potential channels to signals based on their peak frequencies. \n
    """
    # if signals peak freq is exactly a channel center freq, assign the channel to that signal
    for channel, frequencies in channel_center_freq_list.items():
        for i, freq in enumerate(frequencies):
            if int(signal.peak_freq) == freq:
                signal.channel = f"{channel}{i+1}"
                return True

    # assign potential channels to signals based on their peak freq
    for channel, frequencies in channel_freq_range_list.items():
        for i, freq_range in enumerate(frequencies):
            if signal.peak_freq >= freq_range[0] and signal.peak_freq <= freq_range[1]:
                signal.potential_channels.append(f"{channel}{i+1}")

    if signal.channel is None or len(signal.potential_channels) == 0:
        signal.channel = "Unclear"
        return False

    return True


if __name__ == "__main__":
    print("This is a module file. Run gui.py instead.")
