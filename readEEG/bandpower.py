import time
from collections import deque, OrderedDict
from itertools import islice
from threading import Thread, Lock

import numpy as np
from pylsl import resolve_stream, StreamInlet, local_clock
from scipy.signal import periodogram


class bandpower:

    def __init__(self, data_segment):

        self.bands = OrderedDict([
            #('delta', [1, 3]),
            ('theta', [4, 7]),
            ('alpha', [8, 12])
            #('beta1', [13, 19]),
           # ('beta2', [20, 29])
        ])
        self.n_bands = len(self.bands.keys())
        self.data_segment = data_segment

        # get possible frequencies
        #data_segment = np.array(data_segment)[:, 0]
        f, _ = periodogram(data_segment, 125)

        # get mask for every single band and overall
        # self.freq_all_idx = (f >= 1) & (f < 29)
        #
        # self.freq_delta_idx = (f >= 1) & (f < 4)
        # self.freq_theta_idx = (f >= 4) & (f < 8)
        # self.freq_alpha_idx = (f >= 8) & (f < 13)
        # self.freq_beta1_idx = (f >= 13) & (f < 20)
        # self.freq_beta2_idx = (f >= 20) & (f < 29)

        #for only theta and alpha:
        self.freq_all_idx = ((f >= 4) & (f < 13))

        self.freq_theta_idx = (f >= 4) & (f < 8)
        self.freq_alpha_idx = (f >= 8) & (f < 13)

        # create list of masks
        self.mask_list = np.array(
            [self.freq_alpha_idx, self.freq_theta_idx])

        # lists for current cognitive load for every channel


    def calculate_bandpower(self, data, times, s_rate):
        channel_num = len(data[0])
        band_mat = []
        # for each channel
        for c in range(channel_num):

            data = np.array(data)
            f, power = periodogram(data[:, c], s_rate) # is doing FFM, f is mask and power the power for every frequence in channel c

            #create masks
            freq_all_idx = ((f >= 4) & (f < 13))
            freq_theta_idx = (f >= 4) & (f < 8)
            freq_alpha_idx = (f >= 8) & (f < 13)

            # create list of masks
            mask_list = np.array(
                [freq_theta_idx, freq_alpha_idx])


            rel_band = np.zeros(self.n_bands)
            for i in range(self.n_bands):
                rel_band[i] = (np.sum(power[mask_list[i]]) / np.sum(power[freq_all_idx])) # rel_band is a list of how much of every band is in channel c (if all bands taken, there are 5 values)
            #print("alpha, theta", rel_band)
            band_mat.append(rel_band) # list of rel_bands

        return band_mat

    def calculate_cl(self, band_mat, choose_channel):
        channel_num = len(band_mat)
        cl = np.zeros(channel_num)
        for c in range(channel_num):
            if c in choose_channel:
                #calculate cognitive load
                pass
        return cl, channel_num


