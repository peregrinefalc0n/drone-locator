class SignalDict:
    """Class that represents a dictionary of signals"""
    def __init__(self):
        self.signals = dict()
    
    def add(self, signal):
        self.signals[signal.channel] = signal
    
    def get_all(self):
        return self.signals
    
    def get(self, channel):
        return self.signals[channel]

