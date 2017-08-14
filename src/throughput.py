#-*- coding: utf-8 -*-

#todo: show number of cards you can cover until 4AM (or whatever time you set Anki to consider new day)
#todo: make tracking deck-specific (?)
#      initialize bars when you look at a collection instead of globally (or iterate over all decks?)
#todo: save average to disk (?). Either that or algorithm to go back and simular batches
#todo: add page to stats

#todo: fix flame in non-fullscreen mode
#todo: make flame gif (?)

"""
Anki Add-on: Throughput Monitor

Tried to predict your throughput as you study.
Hopes to encourage you to improve your throughput

Copyright: Sebastien Guillemot 2017 <https://github.com/SebastienGllmt>
Based off code by Glutanimate 2017 <https://glutanimate.com/>

License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html
"""

import Throughput
from Throughput.bar import ProgressBar
from aqt.qt import *

class settings:
    ############### YOU MAY EDIT THESE SETTINGS ###############
    
    keep_log = False        #log activity to file

    ### FLAME SETTINGS ###
    show_flame = True
    flame_height = 100 # height in pixels (width is automatically adjusted to maintain aspect ratio)

    ### PROGRESS BAR SETTINGS ###

    timebox = 5*60              # size (in seconds) of a study batch to consider for throughput

    # Point bar settings
    penalize_idle = False  # If you got 0 points in batch, whether or not we should count it
    exponential_weight = 0.5 # decay for exponential weighted average
    goal_offset = 2 # how many more reviews than the exponential weighted average you hope to get this round
    initial_throughput_guess = 15 - goal_offset # initial goal when you just started studying
    points_by_card_type = [3,1,1] # get different amount of points based off if this card is (new, learning, due)

    # area where the bars will appear. Uncomment the one you want to 
    # note: Qt.LeftDockWidgetArea and Qt.RightDockWidgetArea are not well supported
    #bar_area = Qt.TopDockWidgetArea
    bar_area = Qt.BottomDockWidgetArea
    
    #format: (show until we reach this percentage left in countdown, background color, foreground color)
    countdown_colors = [(0.50, "#006400", "#008000"), (0.10, "#B8860B", "#DAA520"), (0.00, "#8B0000", "#B22222")]
    invert_timer = False
    countdown_timer_as_percentage = False # whether or not to display the time left in batch or just the % time passed
    countdownBar = ProgressBar(
        textColor="white",
        bgColor=countdown_colors[0][2] if invert_timer else countdown_colors[0][1],
        fgColor=countdown_colors[0][1] if invert_timer else countdown_colors[0][2],
        borderRadius=0,
        maxWidth="",
        orientationHV=Qt.Horizontal if bar_area == Qt.TopDockWidgetArea or bar_area == Qt.BottomDockWidgetArea else Qt.Vertical,
        invertTF=not invert_timer,
        dockArea=bar_area,
        pbStyle=None,
        rangeMin=0,
        rangeMax=timebox*1000, #use milliseconds
        textVisible=True)

    points_as_percentage = True
    points_as_number = True
    pointBar = ProgressBar(
        textColor="white",
        bgColor="Darkslateblue",
        fgColor="Darkviolet",
        borderRadius=0,
        maxWidth="",
        orientationHV=Qt.Horizontal if bar_area == Qt.TopDockWidgetArea or bar_area == Qt.BottomDockWidgetArea else Qt.Vertical,
        invertTF=False,
        dockArea=bar_area,
        pbStyle=None,
        rangeMin=0,
        rangeMax=initial_throughput_guess,
        textVisible=True)
############# END USER CONFIGURABLE SETTINGS #############
progressBars = [settings.pointBar.progressBar, settings.countdownBar.progressBar]

__version__ = '1.0'

import os
import time

from anki.collection import _Collection
from anki.hooks import wrap, addHook, remHook, runHook
from anki.sched import Scheduler
from anki.utils import json
from aqt.reviewer import Reviewer
from aqt import mw

from Throughput.stopwatch import Stopwatch
import Throughput.logging as logging
import Throughput.logging.handlers

fire_file = os.path.join(mw.pm.addonFolder(), 'Throughput', 'img', 'fire.png')

_flameLabel = None

def getFlame(parent=None):
    global _flameLabel

    myImage = QImage()
    myImage.load(fire_file)

    aw = parent or mw.app.activeWindow() or mw
    myLabel = QLabel(aw)

    originalPixMap = QPixmap.fromImage(myImage)
    newPixMap = originalPixMap.scaledToHeight(settings.flame_height)
    myLabel.setPixmap(newPixMap)

    #myLabel.setFrameStyle(QFrame.Panel)
    myLabel.setLineWidth(2)
    #myLabel.setWindowFlags(Qt.ToolTip)
    vdiff = settings.flame_height + 128 # 128 add to account for the review bar at the bottom of the window
    myLabel.setMargin(10)
    myLabel.move(QPoint(0, aw.height() - vdiff))
    
    # set that the image can be shrunk if window is also shrunk
    #myLabel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
    # scale the image to fit the size of the label
    myLabel.adjustSize()
    myLabel.show()

    _flameLabel = myLabel

# add compatability with the Progress Bar plugin
try:
    import Progress_Bar
    Progress_Bar._dock = lambda x: None
    old_getMX = Progress_Bar.getMX
    Progress_Bar.getMX = lambda : 1
    
    Progress_Bar.progressBar, _ = Progress_Bar.pb()
    Progress_Bar.progressBar.setOrientation(Qt.Horizontal if settings.bar_area == Qt.TopDockWidgetArea or settings.bar_area == Qt.BottomDockWidgetArea else Qt.Vertical)
    Progress_Bar.progressBar.dockArea = settings.bar_area
    Progress_Bar.getMX = old_getMX
    
    progressBars.append(Progress_Bar.progressBar)
except ImportError:
    pass

# add all the progress bars to the UI
hasDocked = False
def dockProgressBars(state, oldState):
    global hasDocked
    if not hasDocked:
        ProgressBar.dock(progressBars, settings.bar_area)
        hasDocked = True
    for bar in progressBars:
        ProgressBar.renderBar(bar, state, oldState)
addHook("afterStateChange", dockProgressBars)

def setupLog(obj, name):
    obj.log = logging.getLogger(name)
    obj.log.setLevel(logging.DEBUG)
        
    logName = os.path.join(os.path.dirname(os.path.realpath(__file__)), name + '.log')
    fh = logging.handlers.RotatingFileHandler(logName, maxBytes=1e7, backupCount=5)
    fmt = logging.Formatter('%(asctime)s [%(threadName)14s:%(filename)18s:%(lineno)5s - %(funcName)30s()] %(levelname)8s: %(message)s')
    fh.setFormatter(fmt)
    obj.log.addHandler(fh)

class Main(object):
    
    def __init__(self):
        setupLog(self, "Throughput")
        self.throughputTracker = ThroughputTracker()
    
class ThroughputTracker(object):

    def __init__(self):
        setupLog(self, "ThroughputTracker")
        self.batchPointCount = 0
        self.previous_batches = [] # stored averages
        self.stopwatch = Stopwatch()
        self.countdownColorIndex = 0

    def get_exponential_decay(self):
        if len(self.previous_batches) == 0:
            return settings.initial_throughput_guess
        return self.get_exponential_decay_i(len(self.previous_batches)-1)

    def get_exponential_decay_i(self, i):
        if i == 0:
            return self.previous_batches[i]

        node = settings.exponential_weight * self.previous_batches[i]
        node += (1-settings.exponential_weight) * self.get_exponential_decay_i(i-1)
        return node

    def updateTime(self):
        time_left = settings.timebox - self.stopwatch.get_time()
        if settings.keep_log: 
            self.log.debug("timeleft: " + str(time_left))
        if time_left < 0:
            #update batch point history
            if self.batchPointCount > 0 or settings.penalize_idle:
                self.previous_batches.append(self.batchPointCount)
                if len(self.previous_batches) > 5:
                    self.previous_batches = self.previous_batches[1:6]
                self.batchPointCount = 0
            pointbar_max = self.get_exponential_decay()
                
            self.stopwatch.reset()
            self.stopwatch.start()

            # readjust bars
            self.setPointFormat(0, pointbar_max)
            self.setCountdownFormat(0)
        
        else:
            self.setCountdownFormat(self.stopwatch.get_time())

    def setCountdownFormat(self, curr_time):
        perc_left = 1 - (curr_time / settings.timebox)
        if settings.invert_timer:
            if settings.countdown_timer_as_percentage:
                self.setCountdownFormatPerc(curr_time, 100*(1-perc_left))
            else:
                minutes = int(curr_time / 60)
                seconds = int(curr_time % 60)
                self.setCountdownFormatTime(curr_time, minutes, seconds)
        else:
            if settings.countdown_timer_as_percentage:
                self.setCountdownFormatPerc(curr_time, 100*perc_left)
            else:
                minutes = int(((settings.timebox) - curr_time) / 60)
                seconds = int(((settings.timebox) - curr_time) % 60)
                self.setCountdownFormatTime(curr_time, minutes, seconds)

        for i, color in enumerate(settings.countdown_colors):
            if perc_left > color[0]:
                #if we're already at this color, don't recolor
                if i == self.countdownColorIndex:
                    break

                self.countdownColorIndex = i
                settings.countdownBar.recolor(bgColor=color[2], fgColor=color[1])
                break

    def setCountdownFormatPerc(self, curr, perc):
        settings.countdownBar.setValue(int(curr*1000), str(perc) + "%")

    def setCountdownFormatTime(self, curr, minutes, seconds):
        settings.countdownBar.setValue(int(curr*1000), "%d:%02d" % (minutes, seconds))

    def setPointFormat(self, curr, maximum):
        maximum += settings.goal_offset
        if settings.points_as_percentage:
            if settings.points_as_number:
                point_format = "%d / %d (%d%%)" % (curr, maximum, int(100*curr/maximum))
            else:
                point_format = "%d%%" % (int(100*curr/maximum))
        else:
            if settings.points_as_number:
                point_format = "%d / %d" % (curr, maximum)
            else:
                point_format = " "

        settings.pointBar.progressBar.setMaximum(maximum)
        # setting value larger than maximum can cause some bugs
        if curr > maximum:
            settings.pointBar.setValue(maximum, point_format)
        else:
            settings.pointBar.setValue(curr, point_format)
        

        if settings.show_flame:
            global _flameLabel
            if self.batchPointCount >= maximum and _flameLabel == None:
                getFlame()
            if self.batchPointCount < maximum and _flameLabel != None:
                _flameLabel.deleteLater()
                _flameLabel = None
		
    def adjustPointCount(self, card, increment):
        if card.type >= 0 and card.type < len(settings.points_by_card_type):
            base_point = settings.points_by_card_type[card.type]
        else:
            # this shouldn't happen unless the user has a different addon that messes with card types and didn't change the config for this addon
            base_point = 1

        if increment:
            self.batchPointCount += base_point
        else:
            self.batchPointCount -= base_point
            # this can happen if you undo cards that were part of a previous batch
            if self.batchPointCount < 0:
                self.batchPointCount = 0

        pointbar_max = self.get_exponential_decay()
        self.setPointFormat(self.batchPointCount, pointbar_max)

throughput = Main()

#initialize bars
def initializeProgressBars(state, oldState):
    if state == "overview":
        throughput.throughputTracker.setPointFormat(throughput.throughputTracker.batchPointCount, throughput.throughputTracker.get_exponential_decay())
        throughput.throughputTracker.setCountdownFormat(throughput.throughputTracker.stopwatch.get_time())
addHook("afterStateChange", initializeProgressBars)


# based on Anki 2.0.45 aqt/main.py AnkiQt.onRefreshTimer
def onRefreshTimer():
    if settings.keep_log: 
        throughput.log.debug(mw.state)
    if throughput.throughputTracker.stopwatch.is_running():
        throughput.throughputTracker.updateTime()

# refresh page periodically
refreshTimer = mw.progress.timer(100, onRefreshTimer, True)

### check when user answers something
def updateThroughputOnAnswer(x, card, ease):
    throughput.throughputTracker.adjustPointCount(card, increment=True)
Scheduler.answerCard = wrap(Scheduler.answerCard, updateThroughputOnAnswer, "before")

# check for undos and remove points based off of it
def updateThroughputOnUndo(x, _old):
    cardid = _old(x)
    if cardid:
        card = mw.col.getCard(cardid)
        throughput.throughputTracker.adjustPointCount(card, increment=False)
        
_Collection.undo = wrap(_Collection.undo, updateThroughputOnUndo, "around")

# stop the stopwatch when we exit reviews
def pauseTimerOnReviewExit(state, oldState):
    if settings.keep_log: 
        throughput.log.debug("state: " + state)
    if state in ["question", "answer", "review"]:
        throughput.throughputTracker.stopwatch.start()
    else:
        throughput.throughputTracker.stopwatch.stop()
    
addHook("afterStateChange", pauseTimerOnReviewExit)