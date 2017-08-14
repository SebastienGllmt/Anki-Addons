"""
Class for managing a QTProgressBar

Copyright: Sebastien Guillemot 2017 <https://github.com/SebastienGllmt>
Based off code by Glutanimate 2017 <https://glutanimate.com/>

License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html
"""

from aqt.qt import *
from aqt import mw

class ProgressBar:

    def __init__(self,
        textColor,
        bgColor,
        fgColor,
        borderRadius,
        maxWidth, # ex: 5px
        orientationHV,
        invertTF,
        dockArea,
        pbStyle,
        rangeMin,
        rangeMax,
        textVisible):

        """Initialize and set parameters for progress bar, adding it to the dock."""
        self.progressBar = QProgressBar()
        self.progressBar.setRange(rangeMin, rangeMax)
        self.progressBar.setTextVisible(textVisible)
        self.progressBar.setInvertedAppearance(invertTF)
        self.progressBar.setOrientation(orientationHV)
        self.progressBar.hide()

        self.maxWidth = maxWidth
        self.borderRadius = borderRadius
        self.textColor = textColor
        self.bgColor = bgColor
        self.fgColor = fgColor
        
        self.recolor(textColor, bgColor, fgColor, borderRadius, maxWidth, pbStyle)
            
    def recolor(self,
                textColor=None,
                bgColor=None, 
                fgColor=None, 
                borderRadius=None, 
                maxWidth=None, 
                pbStyle=None):
        
        if textColor == None:
            textColor = self.textColor
        if bgColor == None:
            bgColor = self.bgColor
        if fgColor == None:
            fgColor = self.fgColor
        if maxWidth == None:
            maxWidth = self.maxWidth
        if borderRadius == None:
            borderRadius = self.borderRadius

        if pbStyle == None:
            if maxWidth:
                if orientationHV == Qt.Horizontal:
                    restrictSize = "max-height: %s;" % maxWidth
                else:
                    restrictSize = "max-width: %s;" % maxWidth
            else:
                restrictSize = ""
            
            self.progressBar.setStyleSheet(
            '''
                QProgressBar
            {
                text-align:center;
                color:%s;
                background-color: %s;
                border-radius: %dpx;
                %s
            }
                QProgressBar::chunk
            {
                background-color: %s;
                margin: 0px;
                border-radius: %dpx;
            }
            ''' % (textColor, bgColor, borderRadius, restrictSize, fgColor, borderRadius))
        else:
            pbdStyle = QStyleFactory.create("%s" % (pbStyle))
            self.progressBar.setStyle(pbdStyle)
            
            palette = QPalette()
            palette.setColor(QPalette.Base, QColor(bgColor))
            palette.setColor(QPalette.Highlight, QColor(fgColor))
            palette.setColor(QPalette.Button, QColor(bgColor))
            palette.setColor(QPalette.WindowText, QColor(textColor))
            palette.setColor(QPalette.Window, QColor(bgColor))
            self.progressBar.setPalette(palette)
        
        

    @staticmethod
    def dock(barList, dockArea):
        """Dock for the progress bar. Giving it a blank title bar,
        making sure to set focus back to the reviewer."""

        if len(barList) == 0:
            return

        mw.setDockNestingEnabled(True)
        prevWidget = None
        dockWidgets = [QDockWidget() for _ in barList]
        widgets = [QWidget() for _ in barList]
        for i, bar in enumerate(barList):
            dock = dockWidgets[i]
            tWidget = widgets[i]
            dock.setObjectName("pbDock_" + str(i))
            dock.setWidget(bar)
            dock.setTitleBarWidget( tWidget )
            mw.addDockWidget(dockArea, dock)
            if prevWidget == None:
                prevWidget = dock
            else:
                # Moves second dock widget on top of first dock widget
                if dockArea == Qt.TopDockWidgetArea or dockArea == Qt.BottomDockWidgetArea:
                    stack_method = Qt.Vertical
                if dockArea == Qt.LeftDockWidgetArea or dockArea == Qt.RightDockWidgetArea:
                    stack_method = Qt.Horizontal
                mw.splitDockWidget(prevWidget, dock, stack_method)
                prevWidget = dock
        mw.web.setFocus()

    def setValue(self, val, text=None):
        self.progressBar.hide()
        self.progressBar.setValue(val)
        if text:
            self.progressBar.setFormat(text)
        self.progressBar.show()

    @staticmethod
    def renderBar(bar, state, show_states):
        if state in ["question", "answer", "review", "overview"]:
            bar.show()
        else:
            bar.hide()