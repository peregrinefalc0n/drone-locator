from pyhackrf2 import HackRF
from matplotlib import pyplot

hackrf = HackRF()

hackrf.sample_rate = 20e6
hackrf.center_freq = 88.5e6

samples = hackrf.read_samples(2e6)

# use matplotlib to estimate and plot the PSD
pyplot.psd(samples, NFFT=1024, Fs=hackrf.sample_rate/1e6, Fc=hackrf.center_freq/1e6)
pyplot.xlabel('Frequency (MHz)')
pyplot.ylabel('Relative power (dB)')
pyplot.show()
