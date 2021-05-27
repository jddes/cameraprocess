from PyQt5 import QtCore, QtGui, QtWidgets, uic
import time
import sys

class SerialWidget(QtWidgets.QWidget):

    def __init__(self, parent=None):
        """  """
        super().__init__(parent)

        # Load UI elements:
        self.setupUi()

    def setupUi(self):
        vbox = QtWidgets.QVBoxLayout()
        self.editPrompt = QtWidgets.QLineEdit()
        self.editConsole = QtWidgets.QPlainTextEdit()
        vbox.addWidget(self.editPrompt)
        vbox.addWidget(self.editConsole)

        # create a mono-spaced font:
        font = QtGui.QFont("Monospace")
        font.setStyleHint(QtGui.QFont.TypeWriter)
        self.editPrompt.setFont(font)
        self.editConsole.setFont(font)

        self.editPrompt.returnPressed.connect(self.editPrompt_returnPressed)

        self.setLayout(vbox)
        self.setWindowTitle('eBUS Serial Console')

    def editPrompt_returnPressed(self):
        newtext = 'Sent: ' + self.editPrompt.text()
        self.editConsole.appendPlainText(repr(newtext))

def main():
    app = QtWidgets.QApplication(sys.argv)
    gui = SerialWidget()
    gui.show()
    app.exec_()

if __name__ == '__main__':
    main()

