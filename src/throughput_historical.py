"""
Anki Addon: Historical Throughput

Measures your historical throughput using a graph

Copyright: Sebastien Guillemot 2017 <https://github.com/SebastienGllmt>
Based off code for True Retention Graph (https://ankiweb.net/shared/info/808676221)

License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html
"""

class settings:
############### YOU MAY EDIT THESE SETTINGS ###############
    batch_time = 5            # the number of minutes for a batch of studies
    group_for_averaging = 5   # the number of batches to average together

    # how many studies have to have occured in a batch for it to be considered
    # this is because otherwise studying just one card randomly during your free time severly impacts the graph
    threshold = 5
############# END USER CONFIGURABLE SETTINGS #############

import math

import anki.stats
from anki.hooks import wrap

# debug
import time
from aqt.utils import showInfo

###
#  Setup our new graph
###

periods = [30, 365, float('inf')]
def new_progressGraphs(*args, **kwargs):
    self = args[0]

    last_day = -min(365 * 10, periods[self.type]) - 1
    last_day_t = (self.col.sched.dayCutoff + 24*60*60 * last_day) * 1000
    retentions = get_retention(self, self._revlogLimit(), last_day_t, self.col.sched.dayCutoff * 1000)

    data = []
    for i, day in enumerate(range(-len(retentions), 0)):
        data.append((day+1, retentions[len(retentions)-i-1]))

    old = kwargs['_old']
    del kwargs['_old']

    result = old(*args, **kwargs)
    result += _plot(self,
                    data,
                    "Historical Throughput",
                    """Looks at how many cards you study in %d minutes and averages it in groups of %d
                    <br>Note: There must have been more than %d reviews in %d minutes for it to count"""
                     % (settings.batch_time, settings.group_for_averaging, settings.threshold, settings.batch_time),
                    color="#880",
                    lines = True)

    return result

###
#  Calculate data for our graph
###

def get_retention(self, lim, frm, to):
    # limit the revlogs to only the ones in the selected deck
    if lim:
        lim = " and " + lim
    data = self.col.db.all("""
        SELECT id 
        FROM revlog 
        WHERE id >= ? and id < ?""" + lim + """
        ORDER BY id DESC""",
        frm, to)

    if not data:
        return []

    ### First create all the batches ###
    munged = []
    last_batch = data[0][0]
    batch_size = 0

    for row in data:
        if row[0] >= last_batch - settings.batch_time * 60 * 1000:
            batch_size += 1
        else:
            if batch_size >= settings.threshold:
                munged.append(batch_size)
            last_batch = row[0]
            batch_size = 1
    # put in any leftover elements
    if batch_size > 0:
        munged.append(batch_size)

    ### Now average the batches ###

    shrunk_data = []
    i = 0
    while len(munged) > i + settings.group_for_averaging:
        average = 0
        for j in range(i,i+settings.group_for_averaging):
            average += munged[j]
        shrunk_data.append(average / settings.group_for_averaging)
        i += settings.group_for_averaging
    # put in any leftover elements
    if i < len(munged):
        average = 0
        for j in range(i,len(munged)):
            average += munged[j]
        shrunk_data.append(average / (len(munged)-i))
        i += settings.group_for_averaging

    return shrunk_data

###
#  Render our new graph
###

_graph = anki.stats.CollectionStats._graph
_num_graphs = 0

def _round_up_max(max_val):
    "Rounds up to the nearest power of 10"

    # Prevent zero values raising an error.  Rounds up to 10 at a minimum.
    max_val = max(10, max_val)

    e = int(math.log10(max_val))
    if e >= 2:
        e -= 1
    m = 10**e
    return math.ceil(float(max_val)/m)*m

def _plot(self, data, title, subtitle,
          color="#f00", lines = False):
    global _num_graphs
    if not data:
        return ""

    txt = self._title(_(title), _(subtitle))

    graph_data = [dict(data=data, color=color, bars={'show': not lines}, lines={'show': lines})]

    max_yaxis = _round_up_max(max(y for x, y in data))
    yaxes = [dict(min=0, max=max_yaxis)]
    xaxes = [dict(min=0, max=len(data))]

    txt += _graph(
        self,
        id="throughput-%s" % _num_graphs,
        data=graph_data,
        ylabel="Reviews in Batch",
        timeTicks=False,
        conf=dict(
            xaxis=xaxes,
            yaxes=yaxes))

    _num_graphs += 1

    text_lines = []

    txt += self._lineTbl(text_lines)

    return txt

###
#  Swap in our new graph ###
###

todayStats_old = anki.stats.CollectionStats.todayStats
swapped = False
def todayStats_new(self):
    global swapped
    if not swapped:
        anki.stats.CollectionStats.cardGraph = wrap(anki.stats.CollectionStats.cardGraph, new_progressGraphs, pos="around")
        swapped = True

    return todayStats_old(self)
anki.stats.CollectionStats.todayStats = todayStats_new
