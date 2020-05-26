from instrumental.drivers.scopes import Scope
from instrumental.drivers import VisaMixin, SCPI_Facet, Facet
from pyvisa.constants import InterfaceType

import numpy as np
from ..util import visa_context
import visa


COMM_HEADER = {
    'CHDR LONG' : 'LONG',
    'CHDR SHORT': 'SHORT',
    'CHDR OFF'  : 'OFF',

    'LONG' : 'LONG',
    'SHORT': 'SHORT',
    'OFF'  : 'OFF',

    'COMM_HEADER LONG' : 'LONG',
    'COMM_HEADER SHORT': 'SHORT',
    'COMM_HEADER OFF'  : 'OFF'
}


TRIG_MODE = {
    'AUTO'   : 'AUTO',
    'NORM'   : 'NORM',
    'SINGLE' : 'SINGLE',
    'STOP'   : 'STOP',

    'TRMD AUTO'   : 'AUTO',
    'TRMD NORM'   : 'NORM',
    'TRMD SINGLE' : 'SINGLE',
    'TRMD STOP'   : 'STOP',

    'TRIG_MODE AUTO'   : 'AUTO',
    'TRIG_MODE NORM'   : 'NORM',
    'TRIG_MODE SINGLE' : 'SINGLE',
    'TRIG_MODE STOP'   : 'STOP'
}

COMM_FORMAT_DATA_TYPE = {
    'BYTE' : 'DEF9,BYTE,BIN',
    'WORD' : 'DEF9,WORD,BIN',

    'DEF9,BYTE,BIN' : 'BYTE',
    'DEF9,WORD,BIN' : 'WORD',

    'CFMT DEF9,BYTE,BIN' : 'BYTE',
    'CFMT DEF9,WORD,BIN' : 'WORD',

    'COMM_FORMAT DEF9,BYTE,BIN' : 'BYTE',
    'COMM_FORMAT DEF9,WORD,BIN' : 'WORD'
}

class AcquisitionChannel(VisaMixin):
    id = 0
    name = ''
    def _initialize(self, **settings):
        self.id = 0
        self.name = 0
        print(settings)

    def waveform(self):
        msg = self.name + ':WF? ALL'
        print(msg)
        reply = super().query(msg)
        print('Reply len:', len(reply))
        #print('Reply len:', len(reply))

RESOLUTION = {
    '8bits' : 8,
    '12bits' : 12
}

ANALOGUE_CHANNELS = {
    '4' : ('C1', 'C2', 'C3', 'C4')
}


def convert_comm_header(msg):
    comm_header = 'SHORT'
    msg = msg.strip().upper()
    try:
        comm_header = COMM_HEADER[msg]
    except:
        print(msg, ' is unsupported COMM HEADER. Please, provide one of the following values:', {v for _,v in COMM_HEADER.items()})
        print('COMM HEADER is set to', comm_header)

    return comm_header

def convert_trig_mode(msg):
    trig_mode = 'SINGLE'
    msg = msg.strip().upper()
    try:
        trig_mode = TRIG_MODE[msg]
    except:
        print(msg, ' is unsupported TRIG MODE. Please, provide one of the following values:', {v for _,v in TRIG_MODE.items()})
        print('TRIG MODE is set to', trig_mode)

    return trig_mode

def convert_comm_format_data_type(msg):
    data_type = 'BYTE'
    msg = msg.strip().upper()
    try:
        data_type = COMM_FORMAT_DATA_TYPE[msg]
    except:
        print(msg, ' is unsupported COMM FORMAT DATA TYPE. Please, provide one of the following values:', {v for _,v in COMM_FORMAT_DATA_TYPE.items()})
        print('COMM FORMAT DATA TYPE is set to', data_type)

    return data_type

#This function takes a message from an oscilloscope (typically *IDN? reply), and
#takes the end of the message as the message termination.
def infer_termination(msg_str):
    if msg_str.endswith('\r\n'):
        return '\r\n'
    elif msg_str.endswith('\r'):
        return '\r'
    elif msg_str.endswith('\n'):
        return '\n'
    return None






class LeCroyScope(Scope, VisaMixin):

    model = ''
    channels = list()
    resolution = 0

    analogue_waveform_parameters = dict()

    """
    A base class for LeCroy Scopes
    """
    def _initialize(self):

        if self.resource.interface_type == InterfaceType.usb or self.resource.interface_type == InterfaceType.tcpip:

            #self.model will read the oscilloscope name and then compare with the name defined in the class
            if (self.model != self._INST_VISA_INFO_[1]):
                print('ERROR: read oscilloscope model is {} while expecting {}'.format(self.model,self._INST_VISA_INFO_[1]))
                pass

            #for each oscilloscope name there shall be a pre-defined list of channels
            if (self._INST_VISA_INFO_[2] is None):
                print('ERROR: channels are not defined for this scope:', self.model)
                pass

            self.resolution = self._INST_VISA_INFO_[2]
            self.channels = self._INST_VISA_INFO_[3]

            print('Connected to:', self.resource)
            print('Device model:', self.model)
            print('Analogue channels:', self.channels)
            print('Resolution:', self.resolution)

            msg = self.query('*IDN?')
            self._rsrc.read_termination = infer_termination(msg)

            #Get all the analogue waveform parameters for future use
            self.analogue_waveform_parameters = self.get_all_waveparams('C1', verbose=False).keys()

            print('Accessible analogue waveform parameters:', self.analogue_waveform_parameters)
        else:
            pass


    def clear_sweeps(self):
        """The CLEAR_SWEEPS command restarts the cumulative processing
        functions: summed or continuous average, extrema, FFT power average,
        histogram, pluse parameter statistics, Pass/Fail counters, and persistence"""
        self.write('CLSW')

    def arm_acquisition(self):
        """The ARM_ACQUISITION command arms the scope and forces a
        single acquisition if it is already armed."""
        self.write('ARM')

    def stop_acquisition(self):
        """The STOP command immediately stops the acquisition of a signal. If
        the trigger mode is AUTO or NORM, STOP places the oscilloscope in
        Stopped trigger mode to prevent further acquisition."""
        self.write('STOP')

    def force_trigger(self):
        """Causes the instrument to make one acquisition."""
        self.write('FRTR')

    def read_template(self):

        with self.resource.ignore_warning(visa.constants.VI_SUCCESS_MAX_CNT),\
             visa_context(self.resource, timeout=10000, read_termination=None,
                          end_input=visa.constants.SerialTermination.none):

            visalib = self.resource.visalib
            session = self.resource.session
            # NB: Must take slice of bytes returned by visalib.read,
            # to keep from autoconverting to int
            self.write('TMPL?')

            #Define the header length depending on the communication format
            reply, status = visalib.read(session, 30000)

            print('TEMPLATE reply:', reply.decode("utf-8"))
            print('Status:', status)


    def get_all_waveparams(self, channel_name, verbose=False):
        if channel_name not in self.channels:
            print(channel_name, ' is not in the list of accepted channels ', self.channels)
            pass

        with self.resource.ignore_warning(visa.constants.VI_SUCCESS_MAX_CNT),\
             visa_context(self.resource, timeout=10000, read_termination=None,
                          end_input=visa.constants.SerialTermination.none):

            visalib = self.resource.visalib
            session = self.resource.session
            # NB: Must take slice of bytes returned by visalib.read,
            # to keep from autoconverting to int
            msg = channel_name + ":INSP? 'WAVEDESC'"
            if verbose:
                print(msg)

            self.write(msg)

            reply, status = visalib.read(session, 30000)
            reply = reply.decode('utf-8')
            list_parameters = reply.split('"')[1].split('\r\n')

            #print('TEMPLATE reply:', list_parameters)
            param_dict = {}
            for param in list_parameters:
                if verbose:
                    print(param)

                try:
                    tag, value = param.split(':')
                    param_dict[tag.strip()] = value.strip()
                except:
                    if verbose:
                        print('No <tag : value> for this entry')
        if verbose:
            print(param_dict)

        return param_dict


    def get_waveparam(self, channel_name, param, verbose=False):
        channel_name = channel_name.strip().upper()
        if channel_name not in self.channels:
            print(channel_name, ' is not in the list of accepted channels ', self.channels)
            pass

        param = param.strip().upper()
        if param not in self.analogue_waveform_parameters:
            print(param, ' is not in the list of accepted channel parameters', self.analogue_waveform_parameters)
            pass

        msg = channel_name + ":INSP? '" + param + "'"
        if verbose:
            print(msg)

        reply = self.query(msg)
        if verbose:
            print(reply)

        value = None

        try:
            value = reply.split('"')[1].split(':')[1].strip()
            if verbose:
                print(value)
        except:
            print('Could not decode the reply', reply)

        return value






    def inr_query(self):
        """The INR? query reads and clears the contents of the INternal state
        change Register (INR). The INR register records the completion of various internal
        operations and state transitions."""
        """
        15 Reserved for future use
        14 Probe was changed
        13 Trigger is ready
        12 Pass/Fail test detected desired outcome
        11 Reserved
        10 Reserved
        9  Reserved
        8  Reserved
        7  A floppy or hard disk exchange has been detected
        6  Floppy or hard disk has become full in AutoStore Fill mode
        5  Reserved for LeCroy use
        4  A segment of a sequence waveform has been acquired in acquisition memory but not yet read out into the main memory
        3  A time-out has occurred in a data block transfer
        2  A return to the local state is detected
        1  A screen dump has terminated
        0  A new signal has been acquired in acquisition memory and read out into the main memory
        """
        print(self.query('INR?'))

    def alst_query(self):
        """The ALL_STATUS? query reads and clears the contents of all status registers:
        STB, ESR, INR, DDR, CMR, EXR and URR except for the MAV bit (bit 6) of the STB
        register. For an interpretation of the contents of each register, refer to the
        appropriate status retister.
        """
        print(self.query('ALST?'))

    def message(self):
        self.query('MSG HELLO')

    def print_comm_format(self):
        msg = 'CFMT?'
        reply = self.query(msg)
        print(reply)

    def print_seq(self):
        msg = 'SEQ?'
        reply = self.query(msg)
        print(reply)

    def get_waveform(self, channel_name, verbose = False):

        if channel_name not in self.channels:
            print(channel_name, ' is not in the list of accepted channels ', self.channels)
            pass

        #Check the header format to properly decode the header
        header = self.comm_header

        #Get the data type. For 12 bit oscilloscope use WORD only
        data_type = self.comm_format_data_type

        if self.resolution == 12 and data_type == 'BYTE':
            print('WARNING: Waveform data type:', data_type, 'is less than oscilloscope resolution', self.resolution)
            self.print_comm_format()
            print('WARNING: One sample is one byte only, while the effective resolution is higher')
            print('WARNING: Changing the data type to WORD')
            self.comm_format_data_type = 'WORD'
            self.print_comm_format()

        #This code is taken fro tektronix.py driver
        with self.resource.ignore_warning(visa.constants.VI_SUCCESS_MAX_CNT),\
             visa_context(self.resource, timeout=10000, read_termination=None,
                          end_input=visa.constants.SerialTermination.none):

            visalib = self.resource.visalib
            session = self.resource.session
            # NB: Must take slice of bytes returned by visalib.read,
            # to keep from autoconverting to int
            msg = channel_name + ':WF? DAT1'
            self.write(msg)

            #Define the header length depending on the communication format
            header_len = 16

            if header == 'SHORT':
                header_len = header_len + 6
            elif header == 'LONG':
                header_len = header_len + 12
            else:
                print('ERROR: Wrong COMM_HEADER format')
                pass

            header, status = visalib.read(session, header_len)

            try:
                num_bytes = int(header[-9:])
            except:
                print('ERROR: number of bytes in the header is wrong')
                print('Header', header)

            #Create a bytearray to keep the trace
            buf = bytearray(num_bytes)
            cursor = 0
            while cursor < num_bytes:
                raw_bin, _ = visalib.read(session, num_bytes-cursor)
                buf[cursor:cursor+len(raw_bin)] = raw_bin
                cursor += len(raw_bin)

        self.resource.read()  # Eat termination

        if verbose:
            print('Trace header', header)
            print('Num bytes initial', num_bytes)
            print('Num bytes read (with overhead)', cursor)
            print('Status', status)

        num_points = int(num_bytes // 2)

        raw_data_y = None
        if self.comm_format_data_type == 'WORD':
            raw_data_y = np.frombuffer(buf, dtype='<i2', count=num_points)
        else:
            raw_data_y = np.frombuffer(buf, dtype='<i1', count=num_points)

        if verbose:
            print('Raw trace shape', raw_data_y.shape)

        return raw_data_y



    @property
    def model(self):
        _, model, _, _ = self.query('*IDN?').split(',')
        return model

    comm_format_data_type = SCPI_Facet('CFMT', convert=convert_comm_format_data_type, doc = 'Selects the format for sending waveform data.')
    comm_header = SCPI_Facet('CHDR', convert=convert_comm_header, doc = 'Controls formating of query responses.')
    trig_mode   = SCPI_Facet('TRMD', convert=convert_trig_mode, doc = 'Command specifing the trigger mode.')

    #template = SCPI_Facet('TMPL', readonly=True, doc='Description of the various logical entities making up a complete waveform.')

class Waverunner625Zi(LeCroyScope):

    _INST_PARAMS_ = ['visa_address']
    _INST_VISA_INFO_ = ('LeCroy', 'WR625ZI')

#Code for this oscilloscope is based on documentation:
#MAUI Oscilloscopes Remote Control and Automation Manual, April 2019
#Part 5 and Part 6
class Wavepro404HD(LeCroyScope):

    _INST_PARAMS_ = ['visa_address']
    _INST_VISA_INFO_ = ('LeCroy', 'WP404HD', RESOLUTION['12bits'], ANALOGUE_CHANNELS['4'])
