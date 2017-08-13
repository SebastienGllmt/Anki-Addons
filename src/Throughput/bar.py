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

        pbdStyle = QStyleFactory.create("%s" % (pbStyle)) # Don't touch.

        """Initialize and set parameters for progress bar, adding it to the dock."""
        self.progressBar = QProgressBar()
        self.progressBar.setRange(rangeMin, rangeMax)
        self.progressBar.setTextVisible(textVisible)
        self.progressBar.setInvertedAppearance(invertTF)
        self.progressBar.setOrientation(orientationHV)
        self.progressBar.hide()
        
        palette = QPalette()
        palette.setColor(QPalette.Base, QColor(bgColor))
        palette.setColor(QPalette.Highlight, QColor(fgColor))
        palette.setColor(QPalette.Button, QColor(bgColor))
        palette.setColor(QPalette.WindowText, QColor(textColor))
        palette.setColor(QPalette.Window, QColor(bgColor))

        if maxWidth:
            if orientationHV == Qt.Horizontal:
                restrictSize = "max-height: %s;" % maxWidth
            else:
                restrictSize = "max-width: %s;" % maxWidth
        else:
            restrictSize = ""

        if pbdStyle == None:
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
            self.progressBar.setStyle(pbdStyle)
            self.progressBar.setPalette(palette)


    @staticmethod
    def dock(barList):
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
            mw.addDockWidget(Qt.TopDockWidgetArea, dock)
            if prevWidget == None:
                prevWidget = dock
            else:
                # Moves second dock widget on top of first dock widget
                mw.splitDockWidget(prevWidget, dock, Qt.Vertical)
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