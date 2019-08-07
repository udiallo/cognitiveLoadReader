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

        self.cl_min = 0 # cognitive load baseline value
        self.cl_max = 0 # cognitive load max value
        self.threshold = 0
        self.threshold_calculated = False

        self.do_pretest = True  # if true, pretest with sequences of numbers is done before skills lab


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


    def cl_index(self, segment_powers, alpha_channel, theta_channel): # calculate cognitive load index

        segment_powers = np.array(segment_powers)
        theta = segment_powers[theta_channel, 0]  # mat -> second values rows, third values columns
        alpha = segment_powers[alpha_channel, 1]  # currently over all channels

        cli_all_channel = theta / alpha # calculate cognitive load

        if len(cli_all_channel) > 1:
            cli_mean_of_channel = np.mean(cli_all_channel)
        else:
            cli_mean_of_channel = cli_all_channel
        return cli_mean_of_channel, cli_all_channel


    def plot_cli(self, cli_list):
        plt.plot(cli_list)
        plt.show()

    def send_hint(self, cli_list):
        # send hint, if mean of last cli values is under threshold

        threshold = 4 # hard coded threshold
        num_of_last_values = 10 # num of last cli values to calculate mean
        if (do_pretest): # if pretest flag is true, threshold is taken from pretest, otherwise is hard coded
            threshold = lsl.threshold

        cli_last_values = cli_list[-num_of_last_values:-1] # == cli_list[len(cli_list)-4 : len(cli_list)-1]
        if (len(cli_last_values) >= 2):
            cli_mean = np.mean(cli_last_values)
            print("mean of last cli values: ", cli_mean)

            if (cli_mean > threshold): # check if cli_mean is bigger than threshold
                print("Show hint!!!")

                requests.post("http://localhost:25080", json.dumps({'hint': 1})) # sends 1 to server, which means "show hint"

    def calculate_cl_min(self, cli_list): # calculates the mean value of cognitive load while subject is just looking at fixation cross (baseline)
        num_last_values = 30 # num of last values which are taken into account
        cli_list = cli_list[-num_last_values:-1]
        cli_list = np.asarray(cli_list)
        min_value = np.mean(cli_list) #
        self.cl_min = min_value

    def calculate_cl_max(self, cli_list): # calculate max cognitive load by taking highest value
        num_last_values = 40
        cli_list = cli_list[-num_last_values:-1]
        cli_list = np.asarray(cli_list)
        max_value = max(cli_list)
        self.cl_max = max_value

    def calculate_threshold(self): # calculate threshold by taking certain amount of max cognitive load value
        self.threshold = 0.9 * self.cl_max

    def start_task2(self): # send text and sequences to server
        requests.post("http://localhost:25080",
                      json.dumps({'canvasText': "Please remember the sequence of sequence and speak it out loud, when the sequence disappear"}))
        time.sleep(5)

        requests.post("http://localhost:25080",
                      json.dumps({'sequence': ["392", "5346",  "28975", "640901", "8475132", "10738295", "923717562", "28461053042"]}))


    def end_task2(self):

        requests.post("http://localhost:25080",
                      json.dumps({'canvasText': "Thank you"}))
        #time.sleep(4)




if __name__ == '__main__':
    #start receiver
    lsl = Lsl_receiver()
    lsl.auto_resolve()
    lsl.start_recording()

    requests.post("http://localhost:25080",
          json.dumps({'reset': True}))

    alpha_channel = [11]#, 2]  # choose channel of interest for alpha_band
    theta_channel = [15]#, 3]  # choose channel of interest for theta_band

    ###########################
    # do pretest for calculating threshold #
    ###########################
    if lsl.do_pretest:  # check flag


        requests.post("http://localhost:25080",
                      json.dumps({'canvasText': "Please look at the fixation-cross for the next seconds"}))
        time.sleep(3)
        requests.post("http://localhost:25080",
                      json.dumps({'showFixationPoint': True}))



        try:
            time.sleep(1)
            data, _ = lsl.cut_segment(local_clock(), 1)
            band = bandpower(data_segment=data)
            cli_list = []
            counter = 0
            time_stop_task1 = 34 # amount of seconds until task 1 is finished
            time_stop_task2 = 110 # amount of seconds until task 2 is finished
            time_after_task2 = 120 # time after task 2 until threshold is calculated
            try:
                while not lsl.threshold_calculated:
                    time.sleep(1)  # time.sleep, otherwise CPU will be 100% used

                    if counter == time_stop_task1:
                        lsl.calculate_cl_min(cli_list)
                        cli_list = []
                        lsl.start_task2()

                    if counter == time_stop_task2:
                        lsl.end_task2()

                    if counter == time_after_task2:
                        lsl.calculate_cl_max(cli_list)
                        lsl.calculate_threshold()
                        lsl.threshold_calculated = True

                    # data contains for 1 second 125 arrays with each 8 values (for every channel)
                    data, times = lsl.cut_segment(local_clock() - 5.5, 5)  # current time minus x seconds for an interval of y (Second argument)
                    segment_powers = band.calculate_bandpower(data, times, 125)

                    #band_mat.append(segment_powers)  # band_mat == band powers

                    cli, _ = lsl.cl_index(segment_powers, alpha_channel, theta_channel) # get cli (cognitive load index)

                    cli_list.append(cli)

                    lsl.plot_cli(cli_list)  # plots always new cli value
                    counter+=1
                    print(counter)


            except KeyboardInterrupt:
                pass


        except KeyboardInterrupt:
            lsl.stop_recording()

            print("Done.")




    requests.post("http://localhost:25080",
                  json.dumps({'canvasText': "You can start with the skillslab task now!"}))

    print("cl_threshold: " + str(lsl.threshold))
    print("cl_min: " + str(lsl.cl_min))
    print("cl_max: " + str(lsl.cl_max))

    time.sleep(3)

    requests.post("http://localhost:25080",
                  json.dumps({'finishedPreparation': True}))


    ###########################################
    # start of measurement during skills lab #
    ###########################################
    try:
        time.sleep(1)
        data, _ = lsl.cut_segment(local_clock(), 1)
        band = bandpower(data_segment=data)
        band_mat = []
        cli_list = []

        try:
            while True:
                time.sleep(1) #time.sleep, otherwise CPU will be 100% used
                # data contains for 1 second 125 arrays with each 8 values (for every channel)
                data, times = lsl.cut_segment(local_clock()-5.5, 5) #current time minus x seconds for an interval of y (Second argument)
                segment_powers = band.calculate_bandpower(data, times, 125)

                #band_mat.append(segment_powers) # band_mat == band powers

                cli, _ = lsl.cl_index(segment_powers, alpha_channel, theta_channel)  # could also give cli_all_channel, which is an array of cli for every channel

                cli_list.append(cli)

                lsl.send_hint(cli_list) # check if hint should be displayed

                #lsl.plot_cli(cli_list)



                lsl.plot_cli(cli_list) # plot list of cli for channel chan

        except KeyboardInterrupt:
            pass

    except KeyboardInterrupt:
        lsl.stop_recording()

        print("Done.")


