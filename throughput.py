#-*- coding: utf-8 -*-

#todo: predicted cards by 4AM
#todo: make tracking deck-specific (?)
#todo: save average to disk (?). Either that or algorithm to go back and simular batches
#todo: add page to stats
#todo: flame when you're bypassing expectation

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
    barcolor = '#603960'        #progress bar highlight color
    barbgcolor = '#BFBFBF'      #progress bar background color
    timebox = 5                 # size (in minutes) of a study batch to consider for throughput
    
    exponential_weight = 0.5 # decay for exponential weighted average
    goal_offset = 2 # how many more reviews than the exponential weighted average you hope to get this round
    initial_throughput_guess = 15 - goal_offset # initial goal when you just started studying
    points_by_card_type = [2,1,1] # get different amount of points based off if this card is (new, learning, due)
    
    penalize_idle = False  # If you got 0 points in batch, whether or not we should count it
    show_stats = True      #show stats as your studying
    keep_log = False        #log activity to file

    countdownBar = ProgressBar(
        textColor="black",
        bgColor="Green",
        fgColor="Limegreen",
        borderRadius=0,
        maxWidth="",
        orientationHV=Qt.Horizontal,
        invertTF=False,
        dockArea=Qt.BottomDockWidgetArea,
        pbStyle="",
        rangeMin=1,
        rangeMax=timebox*60,
        textVisible=True)

    pointBar = ProgressBar(
        textColor="white",
        bgColor="Darkslateblue",
        fgColor="Darkviolet",
        borderRadius=1,
        maxWidth="",
        orientationHV=Qt.Horizontal,
        invertTF=False,
        dockArea=Qt.BottomDockWidgetArea,
        pbStyle="",
        rangeMin=0,
        rangeMax=initial_throughput_guess,
        textVisible=True)
############# END USER CONFIGURABLE SETTINGS #############
progressBars = [settings.pointBar.progressBar, settings.countdownBar.progressBar]
for bar in progressBars:
    bar.hide()

__version__ = '1.0'

import os
import time

from anki.collection import _Collection
from anki.hooks import wrap, addHook, remHook, runHook
from anki.sched import Scheduler
from anki.utils import json
from aqt.reviewer import Reviewer
from aqt import mw

import Throughput.logging as logging
import Throughput.logging.handlers

try:
    import Progress_Bar
    Progress_Bar._dock = lambda x: None
    old_getMX = Progress_Bar.getMX
    Progress_Bar.getMX = lambda : 1
    Progress_Bar.progressBar, _ = Progress_Bar.pb()
    Progress_Bar.getMX = old_getMX
    Progress_Bar._renderBar = lambda x,y: None
    
    progressBars.append(Progress_Bar.progressBar)
except ImportError:
    pass

hasDocked = False
def _renderBar(state, oldState):
    global hasDocked
    if not hasDocked:
        ProgressBar.dock(progressBars)
        hasDocked = True
    for bar in progressBars:
        ProgressBar.renderBar(bar, state, oldState)

addHook("afterStateChange", _renderBar)

#settings.countdownBar.progressBar.show()
#settings.pointBar.progressBar.show()

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
        self.last_batch_time = time.time()
        self.previous_batches = [] # stored averages

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

    def throughout_stats(self):
        if settings.keep_log: 
            self.log.debug("Begin function")
        
        now = time.time()
        time_since_last_batch = int(now - self.last_batch_time)
        time_left = 60*settings.timebox - time_since_last_batch

        if time_left < 0:
            minutes = settings.timebox
            seconds = 0
            if self.batchPointCount > 0 or settings.penalize_idle:
                self.previous_batches.append(self.batchPointCount)
                if len(self.previous_batches) > 5:
                    self.previous_batches = self.previous_batches[1:6]
                self.batchPointCount = 0
            self.last_batch_time = now
        else:
            minutes = int(time_left / 60)
            seconds = time_left % 60

        string = "<font color='firebrick'>%s / %s</font> | <font color='darkorange'>%d:%02d</font>" % (self.batchPointCount, int(self.get_exponential_decay()) + settings.goal_offset, minutes, seconds)

        if settings.keep_log: 
            self.log.debug("End function returning: %s" %  string)
        return string

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

throughput = Main()

#Insert stats into UI
def my_remaining(x):
    if settings.keep_log: 
        throughput.log.debug("Begin function")
    
    ret = orig_remaining(x)
    
    if settings.show_stats:
        mini_stats = throughput.throughputTracker.throughout_stats()
        if mini_stats: 
            ret += " : %s" % (mini_stats)
    if settings.keep_log: 
        throughput.log.debug("End function returning: %s" %  ret)
    return ret

orig_remaining = Reviewer._remaining
Reviewer._remaining = my_remaining

curr_state = "question"
def set_state_as_question():
    global curr_state
    curr_state = "question"
    update_question_ui()
def set_state_as_answer():
    global curr_state
    curr_state = "answer"
    update_answer_ui()
addHook("showQuestion", set_state_as_question)
addHook("showAnswer", set_state_as_answer)

def update_question_ui():
    mw.reviewer.typeCorrect = True
    mw.reviewer._showAnswerButton()
    mw.reviewer.typeCorrect = False
def update_answer_ui():
    middle = mw.reviewer._answerButtons()
    if settings.show_stats:
        mini_stats = throughput.throughputTracker.throughout_stats()
        if mini_stats: 
            last_box = middle.rfind(r"</td>")
            if last_box != -1:
                middle = middle[:last_box] + (r"<td align=center><span class=nobold></span><br>%s</td>" % (mini_stats)) + middle[last_box+len(r"</td>"):]
                mw.reviewer.bottom.web.eval("showAnswer(%s);" % json.dumps(middle))

#based on Anki 2.0.45 aqt/main.py AnkiQt.onRefreshTimer
def onRefreshTimer():
    if settings.keep_log: 
        throughput.log.debug(curr_state + " " + mw.state)
    if curr_state == "question" and mw.state == "review":
        update_question_ui()

    if curr_state == "answer" and mw.state == "review":
        update_answer_ui()

#refresh page periodically
refreshTimer = mw.progress.timer(1000, onRefreshTimer, True)

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
