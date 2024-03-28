from pyhackrf2 import HackRF
import numpy as np
from matplotlib.pyplot import psd, xlabel, ylabel, show

class Signal:
    """Class that represents a signal"""
    def __init__(self, start_freq, end_freq, peak_power_db, peak_freq):
        self.start_freq = start_freq
        self.end_freq = end_freq
        self.peak_power_db = peak_power_db
        self.peak_freq = peak_freq
        self.bandwidth = end_freq - start_freq
        self.center_freq = (end_freq + start_freq) / 2

class SignalProcessor:
    """ Class that processes signals. It takes a HackRF device id, sample rate, sample count, center frequency and amplifier state as arguments. \n
        Method get_signals returns a list of signals that are above the noise floor by the given offset in dBm. \n"""
    def __init__(self, id, sample_rate=20e6, sample_count=1e6, center_freq=5780e6, aplifier_on=False):
        self.device_id = id
        self.sample_rate = sample_rate
        self.sample_count = sample_count
        self.center_freq = center_freq
        self.aplifier_on = aplifier_on

        self.hackrf = HackRF(device_index=self.device_id)
        self.hackrf.sample_rate = self.sample_rate
        self.hackrf.center_freq = self.center_freq
        self.hackrf.amplifier_on = self.aplifier_on


    def __mW_to_dBm(self, power):
        """Converts power in mW to dBm"""
        return np.around(10 * np.log10(power/1), 2)
    
    def __measure(self):
        """Measures the samples and returns them"""
        samples = self.hackrf.read_samples(self.sample_count)
        return samples
    
    def __process(self, offset = 10, show_graph = False) -> list:
        """Processes the samples and returns a list of signals that are above the noise floor by the given offset in dBm"""
        pxx, freqs, line = psd(self.__measure(), NFFT=2048, Fs=self.hackrf.sample_rate/1e6, Fc=self.hackrf.center_freq/1e6, return_line=True)

        if show_graph:
            xlabel('Frequency (MHz)')
            ylabel('Relative power (dB)')
            show()

        #Take the first 1000 samples to avoid the DC spike (essentially taking less than half of our samples (we had 2048 of them))
        select_count = 1000
        pxx_sample = pxx[:select_count]
        freqs_sample = freqs[:select_count]

        #Find the minimum power in the sample to see where the noise floor is
        min_index = np.argmin(pxx_sample)
        min_pxx_db = self.__mW_to_dBm(pxx_sample[min_index])
        
        #TODO find a more elegant or dynamic solution instead of hardcoding the offset value from lowest recorded power value
        
        #reset the sample arrays to max size again
        freqs_sample = freqs
        pxx_sample = pxx
        
        #Find the signals that are above the noise floor by the given offset
        signals_list = list()
        index = 0
        while index < len(pxx_sample):
            #skip DC spike
            if index == 1000:
                index = 1048
            power_db = self.__mW_to_dBm(pxx_sample[index])
            if power_db >= min_pxx_db + offset:
                temp_signal = Signal(freqs_sample[index], freqs_sample[index], power_db, freqs_sample[index])
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

        return signals_list

    def get_signals(self, offset = 10, show_graph = False):
        """Returns a list of signals that are above the lowest signal by the given offset in dBm. \n
        If show_graph is set to True, a graph of the power spectral density is shown (blocking). \n"""
        return self.__process(offset, show_graph)

if __name__ == "__main__":
    signal_processor = SignalProcessor(id=1)
    for signal in signal_processor.get_signals(show_graph=True):
        print("Signal from", signal.start_freq, "to", signal.end_freq, "with peak power of", signal.peak_power_db, " at freq ", signal.peak_freq)
