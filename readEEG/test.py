from scipy import signal
import matplotlib.pyplot as plt
import numpy as np

fs = 10e3
N = 1e5
amp = 2*np.sqrt(2)
freq = 1234.0
noise_power = 0.001 * fs / 2
time = np.arange(N) / fs
x = amp*np.sin(2*np.pi*freq*time)
x += np.random.normal(scale=np.sqrt(noise_power), size=time.shape)


f, Pxx_den = signal.periodogram(x, fs)


f = open("data_from_cut_segment.txt", "r")
print(f.readline())




print("x")
print(x)
print("fs")
print(fs)
print("f")
print(f)
print(f.size)
print("Pxx_den")
print(Pxx_den.size)

plt.semilogy(f, Pxx_den)
plt.xlabel('frequency [Hz]')
plt.ylabel('PSD [V**2/Hz]')
plt.show()


f.close()