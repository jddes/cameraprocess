from PyQt5 import QtCore, QtGui, QtWidgets, uic
import time
import sys

import numpy as np
import pyqtgraph as pg

class ScrollingPlot(QtWidgets.QWidget):

    def __init__(self, numPts=100, parent=None):
        """  """
        super().__init__(parent)

        # Set a few global PyQtGraph settings before creating plots:
        pg.setConfigOption('leftButtonPan', False)
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        pg.setConfigOption('antialias', True)

        self.updateXspan(numPts)

        # Load UI elements:
        self.setupUi()

    def setupUi(self):
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
        (penR, penG, penB) = colors_list[kColor % len(colors_list)]
        pen = QtGui.QPen(QtGui.QColor(penR*255, penG*255, penB*255))
        pen.setCosmetic(True)

        self.plt = pg.PlotWidget()
        self.plt.setTitle('Summed signal')
        # self.plt.setYRange(-60, 60)
        
        #self.plt.enableAxis(Qwt.QwtPlot.yRight)
        self.plt.setLabel('bottom', 'Frame # (scrolling center)')
        self.plt.setLabel('left', 'Value [counts]')
        self.curve = self.plt.getPlotItem().plot(pen=pen)

        vbox = QtWidgets.QVBoxLayout()
        vbox.addWidget(self.plt)
        self.setLayout(vbox)

    def updateXspan(self, numPts):
        self.numPts = numPts
        self.xdata = np.arange(self.numPts)
        self.ydata = np.empty(self.numPts)
        self.ydata.fill(np.nan)

        self.write_ptr = 0
        self.xdata[self.write_ptr] = 0.
        self.ydata[self.write_ptr] = 0.

    def newPoint(self, y):
        self.ydata[self.write_ptr] = y
        self.write_ptr = (self.write_ptr + 1) % self.numPts
        self.ydata[self.write_ptr] = np.nan

        self.curve.setData(self.xdata, self.ydata)

def main():
    app = QtWidgets.QApplication(sys.argv)
    gui = ScrollingPlot()
    gui.show()
    app.exec_()

if __name__ == '__main__':
    main()

