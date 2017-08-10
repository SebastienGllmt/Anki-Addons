#-*- coding: utf-8 -*-

#todo: make undo reduce count by one (unless it makes it go negative)
#todo: predicted cards by 4AM
#todo: make tracking deck-specific
#todo: save average to disk
#todo: score based off ease
#todo: erase progress bar code
#todo: add page to stats
#todo: points per card type (?)
#todo: option for idle = no penalty
#todo: flame when you're bypassing expectation
"""
Anki Add-on: Throughput Tracker

Tried to predict your throughput as you study.
Hopes to encourage you to improve your throughput

Copyright: Sebastien Guillemot 2017
License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html
"""

# Please don't edit this if you don't know what you're doing.

import os
import time

from anki.hooks import wrap, addHook
from anki.sched import Scheduler
from anki.utils import json
from aqt.reviewer import Reviewer
from aqt import mw

import Throughput
import Throughput.logging as logging
import Throughput.logging.handlers

log = Throughput.logging.Logger

def setupLog(obj, name):
    obj.log = logging.getLogger(name)
    obj.log.setLevel(logging.DEBUG)
        
    logName = os.path.join(os.path.dirname(os.path.realpath(__file__)), name + '.log')
    fh = logging.handlers.RotatingFileHandler(logName, maxBytes=1e6, backupCount=5)
    fmt = logging.Formatter('%(asctime)s [%(threadName)14s:%(filename)18s:%(lineno)5s - %(funcName)30s()] %(levelname)8s: %(message)s')
    fh.setFormatter(fmt)
    obj.log.addHandler(fh)

class settings: #tiny class for holding settings
    ############### YOU MAY EDIT THESE SETTINGS ###############
    step = 1                    #this is how many points each tick of the progress bar represents
    barcolor = '#603960'        #progress bar highlight color
    barbgcolor = '#BFBFBF'      #progress bar background color
    timebox = 5                 # size (in minutes) of a study batch to consider for throughput
    
    tries_eq = 2                #this many wrong answers gives us one point
    matured_eq = 2              #this many matured cards gives us one point
    learned_eq = 2              #this many newly learned cards gives us one point
    
    show_mini_stats = True      #Show Habitica HP, XP, and MP %s next to prog bar
    keep_log = False            #log activity to file
############# END USER CONFIGURABLE SETTINGS #############

class Main(object):
    
    def __init__(self):
        setupLog(self, "Throughput")
        self.progbar = ""
        self.throughputTracker = ThroughputTracker()
    
    #Make progress bar
    def make_progbar(self, cur_score):
        if settings.keep_log: 
            self.log.debug("Begin function")
        if settings.keep_log: 
            self.log.debug("Current score for progress bar: %s out of %s" % (cur_score, settings.timebox))
        
        #length of progress bar excluding increased rate after threshold
        real_length = int(settings.timebox / settings.step)
        
        #length of shaded bar excluding threshold trickery
        real_point_length = int(cur_score / settings.step) % real_length #total real bar length
        
        #shaded bar should not be larger than whole prog bar
        bar = min(real_length, real_point_length) #length of shaded bar
        self.progbar = '<font color="%s">' % settings.barcolor
        #full bar for each tick
        for _ in range(bar):
            self.progbar += "&#9608;"
        self.progbar += '</font>'
        points_left = int(real_length) - int(bar)
        self.progbar += '<font color="%s">' % settings.barbgcolor
        for _ in range(points_left):
            self.progbar += "&#9608"
        self.progbar += '</font>'
        if settings.keep_log: 
            self.log.debug("End function returning: %s" %  self.progbar)
    
class ThroughputTracker(object):

    def __init__(self):
        setupLog(self, "ThroughputTracker")
        self.responseCount = 0
        self.last_batch_time = time.time()
        self.previous_batches = [] # stored averages
        self.exponential_weight = 0.5 # decay for exponential weighted average
        self.goal_offset = 5 # how many more reviews than the exponential weighted average you hope to get this round

    def get_exponential_decay(self):
        if len(self.previous_batches) == 0:
            return 0
        return self.get_exponential_decay_i(len(self.previous_batches)-1)

    def get_exponential_decay_i(self, i):
        if i == 0:
            return self.previous_batches[i]

        node = self.exponential_weight * self.previous_batches[i]
        node += (1-self.exponential_weight) * self.get_exponential_decay_i(i-1)
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
            if self.responseCount > 0:
                self.previous_batches.append(self.responseCount)
                if len(self.previous_batches) > 5:
                    self.previous_batches = self.previous_batches[1:6]
                self.responseCount = 0
            self.last_batch_time = now
        else:
            minutes = int(time_left / 60)
            seconds = time_left % 60

        string = "<font color='firebrick'>%s / %s</font> | <font color='darkorange'>%d:%02d</font>" % (self.responseCount, int(self.get_exponential_decay()) + self.goal_offset, minutes, seconds)

        if settings.keep_log: 
            self.log.debug("End function returning: %s" %  string)
        return string

    def incrementResponseCount(self, card, ease):
        self.responseCount += 1

throughput = Main()

#Insert progress bar into bottom review stats
#       along with database scoring
def my_remaining(x):
    if settings.keep_log: 
        throughput.log.debug("Begin function")
    
    ret = orig_remaining(x)
    
    if settings.show_mini_stats:
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
    if settings.show_mini_stats:
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

def updateThroughputOnAnswer(x, card, ease):
    throughput.throughputTracker.incrementResponseCount(card, ease)

# check when user answers something
Scheduler.answerCard = wrap(Scheduler.answerCard, updateThroughputOnAnswer)