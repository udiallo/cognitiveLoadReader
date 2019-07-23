import sys
import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

"""
EEG script sends True or False (Brain loaded or not)
This script decides if hint (and which kind of hint) should be shown
Does not show hint in the first 10 seconds of new task
"""

# minimum number of seconds since process beginning after which the first hint can be shown
min_process_seconds_1 = 10
# minimum number of seconds since first hint after which the second hint can be shown
min_process_seconds_2 = 10

#time between each number on the canvas in preparation phase in seconds
seconds_between_numbers = 2.5

"""
Colors for printing to terminal
"""
class PrintColors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    ENDC = '\033[0m'


class S(BaseHTTPRequestHandler):

    """
    0 = keep current hinting status
    1 = normal/first hint
    2 = special/second hint
    """
    _hint = 0
    
    _show_fixation_point = True
    
    _canvas_text = ""
    
    # format: [(time_between_symbols, time_after_sequence, [symbol1, symbol2, symbol3, ...])]
    _sequences = []
    
    _finished_preparation = False

    _process_timestamp = datetime.now()

    @property
    def hint(self):
        return type(self)._hint

    @hint.setter
    def hint(self, val):
        type(self)._hint = val
        
    @property
    def show_fixation_point(self):
        return type(self)._show_fixation_point
        
    @show_fixation_point.setter
    def show_fixation_point(self, val):
        type(self)._show_fixation_point = val
        
    @property
    def canvas_text(self):
        return type(self)._canvas_text
        
    @canvas_text.setter
    def canvas_text(self, val):
        type(self)._canvas_text = val
        
    @property
    def sequences(self):
        return type(self)._sequences
        
    @sequences.setter
    def sequences(self, val):
        type(self)._sequences = val

    @property
    def finished_preparation(self):
        return type(self)._finished_preparation

    @finished_preparation.setter
    def finished_preparation(self, val):
        type(self)._finished_preparation = val

    @property
    def process_timestamp(self):
        return type(self)._process_timestamp

    @process_timestamp.setter
    def process_timestamp(self, val):
        type(self)._process_timestamp = val

    def _set_headers(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
    
    """
    Disables request logging
    """
    def log_message(self, format, *args):
        return
     
    """
    Handles GET Requests from Unreal Engine (one per second)
    Returns if hint should be shown
    """
    def do_GET(self):
        # for debugging
        time = datetime.now()
        time = time.strftime("%H:%M:%S")
        
        self._set_headers()
        
        # Next sequence. If none left, sequence is empty.
        sequence = []
        if len(self.sequences) > 0:
            sequence = self.sequences.pop(0)
        
        response_dict = { \
                'hint': self.hint, \
                'showFixationPoint': self.show_fixation_point, \
                'canvasText': self.canvas_text, \
                'sequence': sequence, \
                'finishedPreparation': self.finished_preparation \
                }
        
        json_response = json.dumps(response_dict)

        self.wfile.write(json_response.encode())
        print(PrintColors.ENDC + "[{}] GET , returning: {}".format(time, json_response) + PrintColors.ENDC, flush=True)
        
    def do_HEAD(self):
        self._set_headers()
        
    """
    Handles POST Requests from EEG Script (Cognitive Load value) and from Unreal Engine (Start of new process)
    """
    def do_POST(self):
        # for debugging
        time = datetime.now()
        time = time.strftime("%H:%M:%S")
        
        content_length = int(self.headers["Content-Length"]) # gets data size
        post_string = self.rfile.read(content_length).decode('utf8') # gets data itself
        data = json.loads(post_string)
        
        self._set_headers()
        
        # print("[{}] POST, received:  {} \t Content Length: {}".format(time, data, content_length), flush=True)
        print(PrintColors.OKGREEN + "[{}] POST, received:  {}".format(time, data) + PrintColors.ENDC, flush=True)

        # from EEG script
        if 'hint' in data:
            # check if Cognitive Load threshold reached
            if data['hint']:
                if self.hint == 0:  # no hint shown yet
                    if (datetime.now() - self.process_timestamp).seconds > min_process_seconds_1:
                        # enough time has passed in process
                        self.hint = 1  # show first hint
                elif self.hint == 1:  # first hint shown already
                    if (datetime.now() - self.process_timestamp).seconds \
                            > min_process_seconds_1 + min_process_seconds_2:  # enough time has passed after first hint
                        self.hint = 2  # show second hint

            else:
                self.hint = 0

        # from Unreal Engine, new Task
        if 'process' in data:
            self.hint = 0  # show no hint again
            self.process_timestamp = datetime.now()  # reset process beginning timestamp
            
        if 'showFixationPoint' in data:
            self.show_fixation_point = data['showFixationPoint']
            if self.show_fixation_point:
                self.canvas_text = ""
            
        if 'canvasText' in data:
            self.canvas_text = data['canvasText']
            self.show_fixation_point = False
            
        if 'sequences' in data:
            self.sequences = data['sequences']
            self.show_fixation_point = True
            self.canvas_text = ""
        
        if 'finishedPreparation' in data:
            self.finished_preparation = data['finishedPreparation']
            
        if 'reset' in data:
            if data['reset'] == True:
                self.hint = 0
                self.show_fixation_point = True
                self.canvas_text = ""
                self.finished_preparation = False
                self.process_timestamp = datetime.now()
                


def run(server_class=HTTPServer, handler_class=S, port=25080):
    server_address = ("localhost", port)
    httpd = server_class(server_address, handler_class)
    print(PrintColors.HEADER + "Starting httpd on " + server_address[0] + ":" + str(server_address[1]) + PrintColors.ENDC, flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    from sys import argv
    if len(argv) == 2:
        run(port=int(argv[1]))
    else:
        run()
