from pyhackrf2 import *
from pylab import *     # for plotting
import numpy as np

def mW_to_dBm(power):
    return np.around(10 * np.log10(power/1), 2)

def load_data_from_file(filename):
    new_freqs = []
    new_pxx = []
    with open(filename, "r") as file:
        data = file.readlines()
        for i in data:
            power, freq = i.split(",")
            new_pxx.append(float(power))
            new_freqs.append(float(freq))

    freqs = np.array(new_freqs, dtype=float64)
    pxx = np.array(new_pxx, dtype=float64)

    return pxx, freqs

def write_data_to_file(filename, pxx, freqs):
    with open(filename, "w") as file:
        buffer = ""
        for index, power in enumerate(pxx):
            buffer += str(power) + "," + str(freqs[index]) + "\n"
        file.write(buffer)
        file.close()

def measure(device_index = 1, sample_rate = 20e6, center_freq = 5780e6, sample_count = 1e6):
    hackrf_receiver = HackRF(device_index = device_index)

    hackrf_receiver.sample_rate = sample_rate
    hackrf_receiver.center_freq = center_freq

    samples = hackrf_receiver.read_samples(sample_count)

    pxx, freqs = psd(samples, NFFT=2048, Fs=hackrf_receiver.sample_rate/1e6, Fc=hackrf_receiver.center_freq/1e6)


    return samples, pxx, freqs


# use matplotlib to estimate and plot the PSD
#pxx, freqs = psd(samples, NFFT=2048, Fs=hackrf_receiver.sample_rate/1e6, Fc=hackrf_receiver.center_freq/1e6)

#xlabel('Frequency (MHz)')
#ylabel('Relative power (dB)')
#show()


#TODO change to true if using hardware, else keep false ot load from file a previous measurement
hardware_connected = False

if hardware_connected:
    samples, pxx, freqs = measure()
    write_data_to_file('results.csv', pxx, freqs)

pxx, freqs = load_data_from_file('results.csv')
    
#print(len(pxx))

select_count = 1000
#print("Max", max(pxx[:500]), "Min", min(pxx[:500]))
pxx_sample = pxx[:select_count]
freqs_sample = freqs[:select_count]

#max_index = np.argmax(pxx_sample)    
min_index = np.argmin(pxx_sample)
min_pxx_db = mW_to_dBm(pxx_sample[min_index])

#TODO use numpy instead of for loop
offset = 20 #db to offset from lowest value idk xd

for index, power in enumerate(pxx_sample):
    power_db = mW_to_dBm(power)
    if power_db > min_pxx_db + offset:
        print("Relative power of", power_db, "at freq", freqs_sample[index])


#print("max", pxx[max_index], freqs[max_index])

#print(pxx[max_index] - pxx[min_index])

#for value in pxx:
#    print(value)
if hardware_connected:

    psd(samples, NFFT=2048, Fs=20e6/1e6, Fc=5780e6/1e6)
    xlabel('Frequency (MHz)')
    ylabel('Relative power (dB)')
    show()
