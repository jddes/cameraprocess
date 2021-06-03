
class linear_map():
    def __init__(self, scale, offset):
        """ scale and offset are the parameters of the linear map, defined as:
        display_value = scale * register_value + offset
        this is the "reg_to_display" map, and the "display_to_reg" map simply does the inverse """
        self.scale = scale
        self.offset = offset

        # make sure these functions are inverses
        assert( self.display_to_reg(self.reg_to_display( 1.)) == 1.)
        assert( self.display_to_reg(self.reg_to_display(10.)) == 10.)

    def reg_to_display(self, reg_value):
        return self.scale*reg_value + self.offset

    def display_to_reg(self, display_value):
        return (display_value - self.offset)/self.scale

class SUICamera():

    EXP_OFFSET = 28 # from manual, section 5.12: EXPPERIOD = (EXP + 28) / (PIXCLK:MAX) (seconds)
    PIXCLK_MAX = 20750000 # read back from the camera once
    BPP_DATASTREAM = 12 # Output data is scaled so that minimum ADC value maps to 0 and max maps to 2**BPP_DATASTREAM-1
    pixelsX = 640
    pixelsY = 512
    adc_gain_counts_per_Joule = 4.73e17 # ADC gain in counts per Joules

    def __init__(self):
        self.reply_buffer = ''

        self.registers = {k: None for k in ['EXP', 'FRAME:PERIOD']}
        self.reg_scaling = {
            'EXP':          linear_map(1, self.EXP_OFFSET),
            'FRAME:PERIOD': linear_map(1, 0),}

        for reg_name in self.registers:
            assert reg_name in self.reg_scaling

    def on_connected(self, writeSerialPort, readSerialPort):
        """ Called by ebus_reader after a connection is made to a camera.
        Sets a bunch of useful default values.
        writeSerialPort and readSerialPort must be functions that allow writing/reading the camera's serial port """
        self.writeSerialPort = writeSerialPort
        self.readSerialPort  = readSerialPort
        self.disableAutogain()
        self.enableTimestamps()
        self.readoutRegisters()

    def newSerialData(self, text):
        """ Updates our knowledge of register values if they appear in the serial communication data.
        Returns true if any of the registers has been updated """
        self.reply_buffer += text
        return self.splitSerialTextInLines()

    def splitSerialTextInLines(self):
        was_updated = False
        pos = self.reply_buffer.find('\r')
        while pos != -1:
            full_line = self.reply_buffer[:pos+1]
            was_updated = was_updated or self.parseSerialOutput(full_line)
            self.reply_buffer = self.reply_buffer[pos+1:]
            
            pos = self.reply_buffer.find('\r')

        return was_updated

    def parseSerialOutput(self, line):
        """ Called whenever the device replies one full line on its serial port.
        Will parse out relevant info and update the self.registers values.
        Returns True if any register value was updated as a result """
        was_updated = False
        for reg_name in self.registers.keys():
            header = reg_name + ' '
            if line.startswith(header):
                value = int(line[len(header):])
                self.registers[reg_name] = value
                was_updated = True
        return was_updated

    def disableAutogain(self):
        """ Turn off all AGC and 'enhancements' features, which ruin any chance at proper power calibration of the adc counts """
        self.writeSerialPort('ENH:ENABLE OFF\r')
        self.writeSerialPort('AGC:ENABLE OFF\r')

    def enableTimestamps(self):
        """ Enables the frame timestamps feature of the SUI camera.
        This feature replaces the first pixel of each line with the frame number from 0 to 4095.
        The datasheet actually says that it's only supposed to replace the first pixel at all,
        but the data suggests otherwise... """
        self.writeSerialPort('FRAME:STAMP ON\r')
        self.writeSerialPort('DIGITAL:SOURCE FSTAMP\r')

    def readoutRegisters(self):
        """ Requests the current value of all interesting registers from the camera """
        for reg_name in self.registers:
            self.writeSerialPort(reg_name + '?\r')

    def setRegister(self, reg_name, display_value):
        """ Scales and writes a single display_value to the camera """
        self._setRegister(reg_name, self.reg_scaling[reg_name].display_to_reg(display_value))

    def _setRegister(self, reg_name, reg_value):
        """ Writes a single raw register value to the camera """
        self.writeSerialPort(reg_name + ' %d\r' % int(reg_value))

    def setExposure(self, counts):
        self.setRegister('EXP', counts)

    def setFramePeriod(self, counts):
        self.setRegister('FRAME:PERIOD', counts)

    def getExposure(self):
        """ Returns the latest-known exposure duration """
        val_counts = self.reg_scaling['EXP'].reg_to_display(self.registers['EXP'])
        return (val_counts, self.countsToSeconds(val_counts))

    def getFramePeriod(self):
        """ Returns the latest-known frame duration """
        val_counts = self.reg_scaling['FRAME:PERIOD'].reg_to_display(self.registers['FRAME:PERIOD'])
        return (val_counts, self.countsToSeconds(val_counts))

    def countsToSeconds(self, EXP_adjusted):
        return float(EXP_adjusted)/self.PIXCLK_MAX

    def convertADCcountsToWatts(self, adc_counts):
        """ Converts a value in adc counts units to Watts """
        try:
            expo_counts, expo_time = self.getExposure()
            return adc_counts / (self.adc_gain_counts_per_Joule * expo_time)
        except:
            print('Warning: exposure time unknown. Incorrect scaling will result')
            return adc_counts # can't properly scale since we don't know the exposure time yet

    def setupWindowing(self, X1, Y1, X2, Y2):
        """ Applies constraints on the chosen resolution window,
        then sends the result via the camera's serial port.
        Returns a tuple containing (resolution_dict, X1, Y1, Y1, Y2),
        where resolution_dict are settings to be passed to the frame grabber ebus interface's openStream() function,
        and the rest of the values are after adjustment,
        or None if the values were grossely incorrect """
        make_even = lambda x : x + (x % 2)
        make_odd = lambda x : x + (1-(x % 2))
        X1 = max(0, X1)
        Y1 = max(0, Y1)
        X1 = make_even(X1)
        Y1 = make_even(Y1)
        X2 = make_odd(X2)
        Y2 = make_odd(Y2)
        X2 = min(X2, self.pixelsX-1)
        Y2 = min(Y2, self.pixelsY-1)

        resolution_dict = {
            "Width":       X2-X1+1,
            "Height":      Y2-Y1+1,
            "PixelFormat": "Mono12",
            "TestPattern": "Off",
            # "TestPattern": "iPORTTestPattern",
            "PixelBusDataValidEnabled": "1"
        }
        # Final sanity check:
        if (resolution_dict["Width"] > self.pixelsX or resolution_dict["Width"] < 0
            or resolution_dict["Height"] > self.pixelsY or resolution_dict["Height"] < 0):
            return None
        # Everything is good, send it out to the devices:
        str_cmd = 'WIN:RECT %d %d %d %d\r' % (X1, Y1, X2, Y2)
        self.writeSerialPort(str_cmd)
        return (resolution_dict, X1, Y1, X2, Y2)
