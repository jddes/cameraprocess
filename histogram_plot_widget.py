from PyQt5 import QtCore, QtGui, QtWidgets, uic
import time
import sys

import numpy as np
import pyqtgraph as pg

# Set a few global PyQtGraph settings before creating plots:
pg.setConfigOption('leftButtonPan', False)
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')
pg.setConfigOption('antialias', False)

class HistogramPlotWidget(pg.PlotWidget):

    def __init__(self, parent=None):
        """  """
        super().__init__(parent)

        # Load UI elements:
        self.setupUi()

    def setupUi(self):
        # self.setTitle('Histogram')
        self.setWindowTitle('Histogram')

        # list of RGB tuples defining the colors (same colorset as matlab)
        colors_list = [(     0,    0.4470,    0.7410),
                       (0.8500,    0.3250,    0.0980),
                       (0.9290,    0.6940,    0.1250),
                       (0.4940,    0.1840,    0.5560),
                       (0.4660,    0.6740,    0.1880),
                       (0.3010,    0.7450,    0.9330),
                       (0.6350,    0.0780,    0.1840)]

        # create our pen:
        kColor = 0
        color_tuple = colors_list[kColor % len(colors_list)]
        color = QtGui.QColor(*(int(c*255) for c in color_tuple))
        self.brush = QtGui.QBrush(color)

        self.setLabel('bottom', 'log10(ADC value/max value)')
        self.setLabel('left', 'log10(Counts)')

    def createCurveItem(self, x, y):
        self.curve = pg.PlotCurveItem(x, y, stepMode="center", fillLevel=0.5, brush=self.brush)
        self.addItem(self.curve)
        
    def updateData(self, data):
        t1 = time.perf_counter()
        bins = np.logspace(np.log10(1.0/2**16), np.log10(1.0), 1000)
        # soooo slow.... 28 ms!
        # y, x = np.histogram(data.astype(np.float64)/2**16, bins)
        # y = np.random.rand(1000)
        # x = np.r_[bins, bins[-1]]

        if not hasattr(self, 'curve'):
            self.createCurveItem(x, y+0.5)
        else:
            t2 = time.perf_counter()
            self.curve.setData(np.log10(x), np.log10(y+0.5)) # the 0.5 offset is to avoid a divide by 0
            t3 = time.perf_counter()
            # pyqtgraph can't do log mode, at least with this data...
            # self.setLogMode(y=True)
            # self.setXRange(0, np.log10(2**16))
            self.setXRange(np.log10(bins[0]), np.log10(bins[-1]))
            t4 = time.perf_counter()
            print(t2-t1, t3-t2, t4-t3)

def main():
    app = QtWidgets.QApplication(sys.argv)
    gui = HistogramPlotWidget()
    gui.updateData(2**13 + 2**12*np.random.randn(500*500))
    gui.updateData(2**13 + 2**12*np.random.randn(500*500))
    gui.show()
    app.exec_()

if __name__ == '__main__':
    main()

