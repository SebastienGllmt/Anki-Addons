#-*- coding: utf-8 -*-

#todo: show number of cards you can cover until 4AM (or whatever time you set Anki to consider new day) (?)
#todo: button to reset batch  (?)

"""
Anki Add-on: Throughput Monitor

Tried to predict your throughput as you study.
Hopes to encourage you to improve your throughput

Copyright: Sebastien Guillemot 2017 <https://github.com/SebastienGllmt>
Based off code by Glutanimate 2017 <https://glutanimate.com/>

License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html
"""

import os
import time

from anki.collection import _Collection
from anki.hooks import wrap, addHook, remHook, runHook

from anki.sched import Scheduler as sched1
from anki.schedv2 import Scheduler as sched2
from anki import version as anki_version

from anki.utils import json, ids2str

from aqt.reviewer import Reviewer
from aqt import mw
from aqt.qt import *

from .ThroughputMonitor.bar import ProgressBar
from .ThroughputMonitor.stopwatch import Stopwatch

settings = mw.addonManager.getConfig(__name__)

hasDeckDueList = anki_version.startswith("2.0.") or (
    anki_version.startswith("2.1.") and int(anki_version.split(".")[-1]) < 28
)

# area where the bars will appear.
# too unstable to provide as a user setting
# only Qt.TopDockWidgetArea works well
bar_area = Qt.TopDockWidgetArea

adjusted_initial_guess = settings['initial_throughput_guess'] - settings['goal_offset'] 

addon_path = os.path.dirname(__file__)
fire_file = os.path.join(addon_path, 'img', 'fire.png')
_flameLabel = None

def getFlame(parent=None):
    global _flameLabel

    myImage = QImage()
    myImage.load(fire_file)

    aw = parent or mw.app.activeWindow() or mw
    myLabel = QLabel(aw)

    originalPixMap = QPixmap.fromImage(myImage)
    newPixMap = originalPixMap.scaledToHeight(settings['flame_height'])
    myLabel.setPixmap(newPixMap)

    #myLabel.setFrameStyle(QFrame.Panel)
    myLabel.setLineWidth(2)
    #myLabel.setWindowFlags(Qt.ToolTip)
    vdiff = settings['flame_height'] + 128 # 128 add to account for the review bar at the bottom of the window
    myLabel.setMargin(10)
    myLabel.move(QPoint(0, aw.height() - vdiff))
    
    # set that the image can be shrunk if window is also shrunk
    #myLabel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
    # scale the image to fit the size of the label
    myLabel.adjustSize()
    myLabel.show()

    _flameLabel = myLabel

class ProgressBarHolder(object):
    def __init__(self):
        self.batchCountdownBar = ProgressBar(
            textColor="white",
            bgColor=settings['countdown_colors'][0]['fg_color'] if settings['invert_timer'] else settings['countdown_colors'][0]['bg_color'],
            fgColor=settings['countdown_colors'][0]['bg_color'] if settings['invert_timer'] else settings['countdown_colors'][0]['fg_color'],
            borderRadius=0,
            maxWidth="",
            orientationHV=Qt.Horizontal if bar_area == Qt.TopDockWidgetArea or bar_area == Qt.BottomDockWidgetArea else Qt.Vertical,
            invertTF=not settings['invert_timer'],
            dockArea=bar_area,
            pbStyle=None,
            rangeMin=0,
            rangeMax=settings['timebox']*1000, #use milliseconds
            textVisible=True)

        self.studyTimeLeftBar = ProgressBar(
            textColor="white",
            bgColor="#584cbf",
            fgColor="#4539d1",
            borderRadius=0,
            maxWidth="",
            orientationHV=Qt.Horizontal if bar_area == Qt.TopDockWidgetArea or bar_area == Qt.BottomDockWidgetArea else Qt.Vertical,
            invertTF=False,
            dockArea=bar_area,
            pbStyle=None,
            rangeMin=0,
            rangeMax=0,
            textVisible=True)

        self.pointBar = ProgressBar(
            textColor="white",
            bgColor="#582A72",
            fgColor="#862ab8",
            borderRadius=0,
            maxWidth="",
            orientationHV=Qt.Horizontal if bar_area == Qt.TopDockWidgetArea or bar_area == Qt.BottomDockWidgetArea else Qt.Vertical,
            invertTF=False,
            dockArea=bar_area,
            pbStyle=None,
            rangeMin=0,
            rangeMax=adjusted_initial_guess,
            textVisible=True)

        if settings['show_time_till_end']:
            self.progress_bars = [self.batchCountdownBar.progressBar, self.studyTimeLeftBar.progressBar, self.pointBar.progressBar]
        else:
            self.progress_bars = [self.batchCountdownBar.progressBar, self.pointBar.progressBar]

bar_holder = None

class ThroughputTracker(object):

    def __init__(self):
        self.batchPointCount = [0,0] # [raw_points, with_bonus_points]
        self.previous_batches = [] # stored averages in format [[raw_points, with_bonus_points], ...]
        self.batchStopwatch = Stopwatch()
        self.studyTimeStopwatch = Stopwatch()
        self.currentAnswerStopwatch = Stopwatch()
        self.dailyStudyTime = 0
        self.countdownColorIndex = 0
        self.cardsLeftSnapshot = 0

    def update(self):
        time_left = settings['timebox'] - self.batchStopwatch.get_time()

        if time_left < 0:
            #update batch point history
            if self.batchPointCount[0] > 0 or settings['penalize_idle']:
                self.previous_batches.append([float(self.batchPointCount[0]), float(self.batchPointCount[1])])
                if len(self.previous_batches) > settings['number_batches_to_keep']:
                    self.previous_batches = self.previous_batches[1:1+settings['number_batches_to_keep']]
                self.batchPointCount = [0,0]
            throughput = self.get_exponential_decay()

            self.batchStopwatch.reset()
            self.batchStopwatch.start()

            # readjust bars
            self.setPointFormat([0,0], throughput)
            self.setCountdownFormat(0)

        else:
            self.setCountdownFormat(self.batchStopwatch.get_time())
            throughput = self.get_exponential_decay()

        if settings['show_time_till_end']:
            self.setStudyTimeLeftFormat(throughput[0])

    ### TIME LEFT BAR

    def setStudyTimeLeftFormat(self, predicted_throughput):
        if not settings['show_time_till_end']:
            return

        # get time left until we complete all our reviews assuming current pace
        if self.cardsLeftSnapshot == 0 or predicted_throughput == 0:
            time_string = ""
            seconds_left = 0
        else:
            timebox_left = self.cardsLeftSnapshot / float(predicted_throughput)
            seconds_left = timebox_left * settings['timebox']
	
        granularity = 1000 # setValue can only take an int as the first argument. Multiplying everything gives us finer granularity on the value of the bar
        bar_holder.studyTimeLeftBar.progressBar.setMaximum(((seconds_left + self.studyTimeStopwatch.get_time())*granularity) + self.dailyStudyTime)

        if seconds_left < self.currentAnswerStopwatch.get_time():
            time_string = "~0"
            bar_holder.studyTimeLeftBar.setValue(0, time_string)
            return

        if seconds_left >= 24*60*60:
            time_string = ">1d"
        else:
            time_string = time.strftime('%H:%M:%S', time.gmtime(int(seconds_left) - int(self.currentAnswerStopwatch.get_time())))

        bar_holder.studyTimeLeftBar.setValue((seconds_left*granularity) - self.currentAnswerStopwatch.get_time(), time_string)
        
    ### POINT BAR

    def get_exponential_decay(self):
        if len(self.previous_batches) == 0:
            return [adjusted_initial_guess, adjusted_initial_guess]
        return self.get_exponential_decay_i(len(self.previous_batches)-1)

    def get_exponential_decay_i(self, i):
        if i == 0:
            return [self.previous_batches[i][0], self.previous_batches[i][1]]

        node = [settings['exponential_weight'] * self.previous_batches[i][0],
                settings['exponential_weight'] * self.previous_batches[i][1]]

        next_node = self.get_exponential_decay_i(i-1)

        node[0] += (1-settings['exponential_weight']) * next_node[0]
        node[1] += (1-settings['exponential_weight']) * next_node[1]
        
        return node

    def setPointFormat(self, curr, maximum):
        curr = curr[1]
        maximum = int(maximum[1])
        maximum += settings['goal_offset']
        if settings['points_as_percentage']:
            if settings['points_as_number']:
                point_format = "%d / %d (%d%%)" % (curr, maximum, int(100*curr/maximum))
            else:
                point_format = "%d%%" % (int(100*curr/maximum))
        else:
            if settings['points_as_number']:
                point_format = "%d / %d" % (curr, maximum)
            else:
                point_format = " "

        bar_holder.pointBar.progressBar.setMaximum(maximum)
        # setting value larger than maximum can cause some bugs
        if curr > maximum:
            bar_holder.pointBar.setValue(maximum, point_format)
        else:
            bar_holder.pointBar.setValue(curr, point_format)

        if settings['show_flame']:
            global _flameLabel
            if self.batchPointCount[1] >= maximum and _flameLabel == None:
                getFlame()
            if self.batchPointCount[1] < maximum and _flameLabel != None:
                old_flame = _flameLabel
                _flameLabel = None
                try:
                    old_flame.deleteLater()
                except:
                    # already deleted as parent window closed
                    pass

    def adjustPointCount(self, card, increment):
        if card.type >= 0 and card.type < len(settings['bonus_points_by_card_type']):
            bonus_point = settings['bonus_points_by_card_type'][card.type]
        else:
            # this shouldn't happen unless the user has a different addon that messes with card types and didn't change the config for this addon
            bonus_point = 0

        if increment:
            self.batchPointCount[0] += 1
            self.batchPointCount[1] += 1 + bonus_point
        else:
            self.batchPointCount[0] -= 1
            self.batchPointCount[1] -= (1 + bonus_point)
            # this can happen if you undo cards that were part of a previous batch
            if self.batchPointCount[0] < 0:
                self.batchPointCount[0] = 0
            if self.batchPointCount[1] < 0:
                self.batchPointCount[1] = 0

        pointbar_max = self.get_exponential_decay()
        self.setPointFormat(self.batchPointCount, pointbar_max)

    ### COUNTDOWN BAR

    def setCountdownFormat(self, curr_time, force_recolor=False):
        perc_left = 1 - (curr_time / settings['timebox'])
        if settings['invert_timer']:
            if settings['countdown_timer_as_percentage']:
                self.setCountdownFormatPerc(curr_time, 100*(1-perc_left))
            else:
                minutes = int(curr_time / 60)
                seconds = int(curr_time % 60)
                self.setCountdownFormatTime(curr_time, minutes, seconds)
        else:
            if settings['countdown_timer_as_percentage']:
                self.setCountdownFormatPerc(curr_time, 100*perc_left)
            else:
                minutes = int(((settings['timebox']) - curr_time) / 60)
                seconds = int(((settings['timebox']) - curr_time) % 60)
                self.setCountdownFormatTime(curr_time, minutes, seconds)

        for i, color in enumerate(settings['countdown_colors']):
            if perc_left > color['until']:
                #if we're already at this color, don't recolor
                if i == self.countdownColorIndex and force_recolor==False:
                    break

                self.countdownColorIndex = i
                bar_holder.batchCountdownBar.recolor(bgColor=color['fg_color'], fgColor=color['bg_color'])
                break

    def setCountdownFormatPerc(self, curr, perc):
        bar_holder.batchCountdownBar.setValue(int(curr*1000), str(perc) + "%")

    def setCountdownFormatTime(self, curr, minutes, seconds):
        bar_holder.batchCountdownBar.setValue(int(curr*1000), "%d:%02d" % (minutes, seconds))

def _getNumCardsLeft():
    """ Get the number of new / lrn / rev cards you have left for the day """
    if not settings['show_time_till_end']:
        return 0

    active_decks = mw.col.decks.active()
    if len(active_decks) == 0:
        return 0

    rev = lrn = nu = 0

    left = 0

    if hasDeckDueList:
        # get number of cards
        for tree in [deck for deck in mw.col.sched.deckDueList() if deck[1] in active_decks]:
            rev += tree[2]
            lrn += tree[3]
            nu += tree[4]
            left += nu+lrn+rev
    else:
        for node in [node for node in mw.col.sched.deck_due_tree().children if node.deck_id in active_decks]:
            rev += node.review_count
            lrn += node.learn_count
            nu += node.new_count
            left += nu+lrn+rev

    return left

deck_map = dict()
def GetStateForCol(repaintFormat=False):
    global bar_holder

    if bar_holder == None:
        bar_holder = ProgressBarHolder()
        ProgressBar.dock(bar_holder.progress_bars, bar_area)
        for bar in bar_holder.progress_bars:
            bar.hide()
    
    if mw.col == None:
        return None

    curr_deck = mw.col.decks.selected()
    if curr_deck in deck_map:
        throughput_tracker = deck_map[curr_deck]
    else:
        throughput_tracker = ThroughputTracker()
        throughput_tracker.previous_batches = _getPredictedThroughputForDeck(mw.col.decks.active())
        deck_map[curr_deck] = throughput_tracker

    throughput_tracker.cardsLeftSnapshot = _getNumCardsLeft()

    if repaintFormat:
        throughput_tracker.dailyStudyTime = getDailyStudyTime(mw.col.decks.active())
        throughput = throughput_tracker.get_exponential_decay()
        throughput_tracker.setStudyTimeLeftFormat(throughput[0])
        throughput_tracker.setPointFormat(throughput_tracker.batchPointCount, throughput)
        throughput_tracker.setCountdownFormat(throughput_tracker.batchStopwatch.get_time(), force_recolor=True)

    return throughput_tracker

def _getPredictedThroughputForDeck(curr_deck):
    """ For our initial guess of the user throughput, look back at historical data for the deck"""

    # limit the revlogs to only the ones in the selected deck
    limit = ("cid in (select id from cards where did in %s)" % ids2str(curr_deck))
    data = mw.col.db.all("""
        SELECT id, type
        FROM revlog 
        WHERE """ + limit + """
        ORDER BY id DESC limit 1000 """)

    if not data:
        return []

    munged = []
    last_batch = data[0][0]
    batch_size = [0 for i in range(len(settings['bonus_points_by_card_type'])+1)]

    for row in data:
        revtime, typ = row
        if revtime < last_batch - settings['timebox'] * 1000:
            if sum(batch_size) >= settings['threshold_for_batch']:
                munged.append(batch_size)
            batch_size = [0 for i in range(len(settings['bonus_points_by_card_type'])+1)]
            last_batch = revtime
            if len(munged) >= settings['number_batches_to_keep']:
                break

        if typ < len(settings['bonus_points_by_card_type']):
            batch_size[typ] += 1
        else:
            batch_size[len(batch_size)-1] += 1
    # put in any leftover elements
    if sum(batch_size) > 0 and sum(batch_size) >= settings['threshold_for_batch']:
        munged.append(batch_size)

    result = []
    for batch in munged:
        bonus_points =  [batch[i]*settings['bonus_points_by_card_type'][i] for i in range(len(settings['bonus_points_by_card_type']))]
        result.append([sum(batch), sum(batch)+sum(bonus_points)])

    return result

def getDailyStudyTime(curr_deck):
    """ Get how much time we've studied so far today on the current deck"""

    # limit the revlogs to only the ones in the selected deck
    one_day = 86400
    cutoff = (mw.col.sched.dayCutoff - one_day)*1000
    limit = ("cid in (select id from cards where did in %s) " % ids2str(curr_deck))
    data = mw.col.db.list("""
        SELECT time
        FROM revlog 
        WHERE id > %d AND %s
        ORDER BY id DESC limit 1000 """ % (cutoff, limit))

    return sum(data)

#initialize bars
def renderProgressBars(state, oldState):
    if bar_holder == None:
        return

    if state in ["question", "answer", "review", "overview"]:
        if oldState not in ["question", "answer", "review", "overview"]:
            throughput_tracker = GetStateForCol(repaintFormat=True)
            if throughput_tracker == None:
                return

            throughput_tracker.dailyStudyTime = getDailyStudyTime(mw.col.decks.active())
            for bar in bar_holder.progress_bars:
                bar.show()
    else:
        global _flameLabel
        if _flameLabel != None:
            old_flame = _flameLabel
            _flameLabel = None
            try:
                old_flame.deleteLater()
            except:
                # already deleted as parent window closed
                pass
        for bar in bar_holder.progress_bars:
            bar.hide()
addHook("afterStateChange", renderProgressBars)

# based on Anki 2.0.45 aqt/main.py AnkiQt.onRefreshTimer
def onRefreshTimer():
    if mw.state not in ["question", "answer", "review"]:
        return

    throughput_tracker = GetStateForCol()
    if throughput_tracker == None:
        return

    if throughput_tracker.batchStopwatch.is_running():
        throughput_tracker.update()
# refresh page periodically
refreshTimer = mw.progress.timer(100, onRefreshTimer, True)

### check when user answers something
def updateThroughputOnAnswer(x, card, ease):
    throughput_tracker = GetStateForCol()
    if throughput_tracker == None:
        return

    throughput_tracker.cardsLeftSnapshot = _getNumCardsLeft()
    throughput_tracker.currentAnswerStopwatch.reset()
    throughput_tracker.currentAnswerStopwatch.start()
    throughput_tracker.adjustPointCount(card, increment=True)
sched1.answerCard = wrap(sched1.answerCard, updateThroughputOnAnswer, "before")
sched2.answerCard = wrap(sched2.answerCard, updateThroughputOnAnswer, "before")

# check for undos and remove points based off of it
def updateThroughputOnUndo(x, _old):
    cardid = _old(x)
    if cardid:
        card = mw.col.getCard(cardid)
        throughput_tracker = GetStateForCol()
        if throughput_tracker == None:
            return cardid

        throughput_tracker.cardsLeftSnapshot = _getNumCardsLeft()

        throughput_tracker.adjustPointCount(card, increment=False)
    return cardid
_Collection.undo = wrap(_Collection.undo, updateThroughputOnUndo, "around")

# stop the stopwatch when we exit reviews
def pauseTimerOnReviewExit(state, oldState):
    throughput_tracker = GetStateForCol()
    if throughput_tracker == None:
        return

    if state in ["question", "answer", "review"]:
        throughput_tracker.batchStopwatch.start()
        throughput_tracker.studyTimeStopwatch.start()
        throughput_tracker.currentAnswerStopwatch.start()
    else:
        throughput_tracker.batchStopwatch.stop()
        throughput_tracker.studyTimeStopwatch.reset()
        throughput_tracker.currentAnswerStopwatch.reset()
addHook("afterStateChange", pauseTimerOnReviewExit)
