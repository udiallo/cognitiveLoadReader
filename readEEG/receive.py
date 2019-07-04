import time
from collections import deque, OrderedDict
from itertools import islice
from threading import Thread, Lock

import numpy as np
from pylsl import resolve_stream, StreamInlet, local_clock
from scipy.signal import periodogram

from bandpower import bandpower
import matplotlib.pyplot as plt

import json, requests

class Lsl_receiver:

    def __init__(self):
        self.inlet = None
        self.stream = None
        self.data_buffer = deque(maxlen=125*5) #efficient implemented list object, thread safe, 256*5 == 5 seconds (with sampling rate 256)
        self.time_buffer = deque(maxlen=125*5) #buffer for timestemps
        self.offset = 0.0
        self.recording = False
        self.collection_thread = Thread(target=self.grab_data)
        self.lock = Lock() # lock buffer so that only one process is working on it


    def auto_resolve(self):
        streams = resolve_stream() # get all current streams
        for stream in streams:
            print(stream)
            if stream.name() == "obci_eeg1": #looking for stream with name ...
                self.stream = stream
                print("Found stream!!!!!!!")

        if self.stream is None:
            print("No stream found")
            return False

        self.inlet = StreamInlet(self.stream) #inlet for handeling data from stream
        print("Sampling rate:", self.inlet.info().nominal_srate())

        self.offset = self.inlet.time_correction(timeout=3)

    def grab_data(self):
        while self.recording:
            data, times = self.inlet.pull_chunk(timeout=0.0) # data contains sample (e.g. 16 values for 16 channels), if CPU to slow, data can contain more than one sample (list of lists == chunks)

            if data: #if more than 0 elements is in data
                #print(data)
                # f = open("eeg_eyes_closed.txt", "a")
                # np.savetxt(f, data)
                # f.write("\n")
                # f.close()

                with self.lock: # use lock to protect buffer from other processes
                    self.data_buffer.extend(data) # extend: puts data into data_buffer
                    self.time_buffer.extend(np.array(times) + self.offset)

            time.sleep(0.0001) #wait so CPU is not crashing

    def cut_segment(self, timestamp, segment_size_in_sec): #timestamp we are interested in, second argument: segment_size
        data_segment = None
        time_segment = None
        with self.lock:
            diffs = np.abs([timestamp-ts for ts in self.time_buffer])  # create list of differences from timestamp
            index = int(diffs.argmin()) #index of timestamp with smallest difference
            segment_size = int(self.inlet.info().nominal_srate() * segment_size_in_sec)


            #print("index of timestamp with smallest difference: ", index)
            #print("current segment_size: ", segment_size)
            #print("length of data_buffer: ", len(self.data_buffer))
            #sanity checks: segment_size not bigger than buffer_size, index+segment_length not bigger than buffer

            data_segment = list(islice(self.data_buffer, index, index + segment_size))
            time_segment = list(islice(self.time_buffer, index, index + segment_size))

        return data_segment, time_segment




    def start_recording(self):
        self.recording = True
        self.collection_thread.daemon = True #automatic ending if main is finished
        self.collection_thread.start()

    def stop_recording(self):
        self.recording = False
        self.collection_thread.join() #clean up threads


    def cl_index(self, segment_powers, alpha_channel, theta_channel):
        # alpha_channel, theta_channel -> choosing channel of interest for each band

        segment_powers = np.array(segment_powers)
        theta = segment_powers[theta_channel, 0]  # mat -> second values rows, third values columns
        alpha = segment_powers[alpha_channel, 1]  # currently over all channels

        cli = theta / alpha # calculate cognitive load


        return cli


    def plot_cli(self, cli_list):
        plt.plot(cli_list)
        plt.show()

    def send_hint(self, cli_list):
        # send hint, if mean of last three cli values is under threshold

        threshold = 0.6
        num_of_last_values = 10

        cli_last_values = cli_list[-num_of_last_values:-1] # == cli_list[len(cli_list)-4 : len(cli_list)-1]
        if (len(cli_last_values) >= 2):
            cli_mean = np.mean(cli_last_values)
            print("mean of last cli values: ", cli_mean)

            if (cli_mean < threshold):
                print("Show hint!!!")

                requests.post("http://localhost:25080", json.dumps({'hint': 1}))






if __name__ == '__main__':
    lsl = Lsl_receiver()
    lsl.auto_resolve()
    lsl.start_recording()



    try:
        time.sleep(1)
        data, _ = lsl.cut_segment(local_clock(), 1)
        band = bandpower(data_segment=data)
        band_mat = []
        cli_list = []
        alpha_channel = [0, 1] # choose channel of interest for alpha_band
        theta_channel = [0, 1] # choose channel of interest for theta_band
        try:
            while True:
                time.sleep(1) #time.sleep, otherwise CPU will be 100% used
                # data contains for 1 second 125 arrays with each 8 values (for every channel)
                data, times = lsl.cut_segment(local_clock()-5.5, 1) #current time minus x seconds for an interval of y (Second argument)
                segment_powers = band.calculate_bandpower(data, times, 125)

                band_mat.append(segment_powers) # band_mat == band powers

                cli = lsl.cl_index(segment_powers, alpha_channel, theta_channel)

                cli_list.append(cli)

                lsl.send_hint(cli_list)

                lsl.plot_cli(cli_list) # plot list of cli for channel chan

        except KeyboardInterrupt:
            pass




        ###later: wait for trigger, than start lsl.cut_segment with argument which could be passed from unreal?
        ### So, in main, while loop is waiting for input?


    except KeyboardInterrupt:
        lsl.stop_recording()

        print("Done.")


# plug in dongle, turn on cyton, start "sudo python openbci_lsl.py /dev/ttyUSB0 --stream" in OpenBCI_LSL directory
# then /start for streaming, /stop and /exit