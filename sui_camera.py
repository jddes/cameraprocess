
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

    def __init__(self):
        self.registers = {k: None for k in ['EXP', 'FRAME:PERIOD']}
        self.reg_scaling = {
            'EXP':          linear_map(1, self.EXP_OFFSET),
            'FRAME:PERIOD': linear_map(1, self.EXP_OFFSET),}

        for reg_name in self.registers:
            assert reg_name in self.reg_scaling

    def on_connected(self, ebus):
        """ Called by ebus_reader after a connection is made to a camera.
        Sets a bunch of useful default values.
        ebus must be a reference to the pyebus SDK wrapper """
        self.writeSerialPort = ebus.writeSerialPort
        self.readSerialPort  = ebus.readSerialPort
        self.disableAutogain()
        self.readoutRegisters()

    def newSerialData(self):
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

    def readoutRegisters(self):
        """ Requests the current value of all interesting registers from the camera """
        for reg_name in self.registers:
            self.writeSerialPort(reg_name + '?\r')

    def setRegister(self, reg_name, display_value):
        """ Scales and writes a single display_value to the camera """
        self._setRegister(reg_name, self.reg_scaling[reg_name].display_to_reg(display_value))

    def _setRegister(self, reg_name, reg_value):
        """ Writes a single raw register value to the camera """
        self.writeSerialPort(reg_name + '%d\r' % int(reg_value))

    def setExposure(self, counts):
        self.setRegister(self.reg_scaling['EXP'].display_to_reg(counts))

    def getExposure(self):
        """ Returns the latest-known exposure duration """
        val_counts = self.reg_scaling['EXP'].reg_to_diplay(self.registers['EXP'])
        return (val_counts, self.countsToSeconds(val_counts))

    def getFramePeriod(self):
        """ Returns the latest-known frame duration """
        val_counts = self.reg_scaling['FRAME:PERIOD'].reg_to_diplay(self.registers['FRAME:PERIOD'])
        return (val_counts, self.countsToSeconds(val_counts))

    def countsToSeconds(self, EXP_adjusted):
        return float(EXP_adjusted)/self.PIXCLK_MAX
