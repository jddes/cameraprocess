""" This module contains a few helper functions for PyQt4 """
from PyQt5 import QtCore, QtGui, QtWidgets, uic
import time

rev_dict = lambda d : {v: k for k, v in d.items()} # not really qt-specific, but super helpful

def getChildWidgets(obj):
    """ Returns a dictionary containing one entry per Qt widget.
    Dict key is the attribute name, and value is the widget instance """
    return {n: w for n, w in obj.__dict__.items() if isinstance(w, QtWidgets.QWidget)}

def connect_signals_to_slots(obj):
    """ Iterates through the list of Qt Widgets that are children of obj,
    and connects every signal to a matching function of the object.
    The name of the function must exactly be equal to "children_signal",
    where "children" the name of the children,
    and "signal" is the name of the children's signal
    Ex, for a QPushButton obj.btnTest, the following connection will be made if possible:
    obj.btnTest.clicked.connect(obj.btnTest_clicked).

    Returns a textual list of the connections made, intended for debugging only """
    t1 = time.clock()

    # find all child Python widgets:
    child_widgets = getChildWidgets(obj)

    # Find all methods:
    all_attr = {n: getattr(obj, n) for n in dir(obj)}
    funcs = {n: f for n, f in all_attr.items() if not n.startswith("__") and callable(f)}

    connections_list = []
    for func_name, func in funcs.items():
        # we want to split for example "btnTest_Two_clicked" into "btnTest_Two" and "clicked"
        split_name = func_name.rsplit("_", 1)
        if len(split_name) <= 1:
            continue
        widget_name, signal_name = split_name[0], split_name[1]
        # check if we have a widget with the correct name:
        w = child_widgets.get(widget_name, None)
        if w is None:
            continue
        try:
            signal = getattr(w, signal_name)
        except AttributeError:
            print("connect_signals_to_slots(): warning, widget %s contains no signal named %s" % (widget_name, signal_name))
            continue
        # attempt the connection:
        signal.connect(func)

        connections_list.append("Connected %s.%s to %s" % (widget_name, signal_name, func_name))

    t2 = time.clock()
    # print("connect_signals_to_slots(): elapsed %f sec" % ((t2-t1)))
    return connections_list

def readFloatFromTextbox(textbox):
    try:
        str_from_textbox = str(textbox.text())
        if str_from_textbox == '':
            value = 0.
        else:
            value = float(eval(str_from_textbox))
    except:
        value = None
    return value