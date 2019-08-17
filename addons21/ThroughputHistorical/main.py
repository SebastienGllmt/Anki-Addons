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

    add_all_graphs = False # whether to generate a graph for every card type or only a single "Cumulative" graph

    # how many studies have to have occurred in a batch for it to be considered
    # this is because otherwise studying just one card randomly during your free time severely impacts the graph
    threshold = 5
############# END USER CONFIGURABLE SETTINGS #############

import math
import itertools

import anki.stats
from anki import version
from anki.hooks import wrap

# debug
import time
from aqt.utils import showInfo
from anki.lang import _

###
#  Setup our new graph
###

periods = [30, 365, float('inf')]

def new_progressGraphs(*args, **kwargs):
    self = args[0]

    start_not_used, num_buckets, bucket_size_days = self.get_start_end_chunk()

    if num_buckets:
        last_day = -(num_buckets * bucket_size_days) - 1
    else:
        # arbitrary day way in the past (to make sure it covers full deck life)
        # todo: replace by calculation of # days since Anki launched
        last_day = -(365 * 20) - 1

    last_day_t = (self.col.sched.dayCutoff + 24*60*60 * last_day) * 1000
    raw_data = get_data(self, self._revlogLimit(), last_day_t, self.col.sched.dayCutoff * 1000)
    
    retentions = [get_retention(self, raw_data, filter_none)]
    if settings.add_all_graphs:
        retentions.append(get_retention(self, raw_data, filter_for_young))
        retentions.append(get_retention(self, raw_data, filter_for_mature))
        retentions.append(get_retention(self, raw_data, filter_for_new))

    graph_data = []
    for i in range(len(retentions)):
        data = []
        for j, day in enumerate(range(-len(retentions[i]), 0)):
            data.append((day+1, retentions[i][len(retentions[i])-j-1]))
        graph_data.append(data)

    old = kwargs['_old']
    del kwargs['_old']

    result = old(*args, **kwargs)

    colors=["#880", "#7c7", "#070","#00F"]
    labels=[_("Cumulative"), _("Young"), _("Mature"),_("Learn")]
    for i in range(len(graph_data)):
        result += _plot(self,
                        graph_data[i],
                        "Historical Throughput",
                        """Looks at how many cards you study in %d minutes and averages it in groups of %d
                        <br>Note: There must have been more than %d reviews in %d minutes for it to count"""
                        % (settings.batch_time, settings.group_for_averaging, settings.threshold, settings.batch_time),
                        colors[i],
                        labels[i],
                        bucket_size_days,
                        lines = True)

    return result

###
#  Data filters
###

def filter_for_mature(ivl, typ):
    if typ == 0:
        return False
    if ivl <= 20:
        return False
    return True
def filter_for_young(ivl, typ):
    if typ == 0:
        return False
    if ivl <= 20:
        return True
    return False
def filter_for_new(ivl, typ):
    return typ == 0
def filter_none(ivl, typ):
    return True

###
#  Calculate data for our graph
###

def get_data(self, lim, frm, to):
    # limit the revlogs to only the ones in the selected deck
    if lim:
        lim = " and " + lim
    data = self.col.db.all("""
        SELECT id, ivl, type
        FROM revlog 
        WHERE id >= ? and id < ?""" + lim + """
        ORDER BY id DESC""",
        frm, to)
    
    return data

def get_retention(self, data, rev_filter):
    
    if not data:
        return []

    ### First create all the batches ###
    munged = []
    last_batch = data[0][0]
    batch_size = 0

    for row in data:
        revtime, ivl, typ = row
        if not rev_filter(ivl, typ):
            continue
        if revtime >= last_batch - settings.batch_time * 60 * 1000:
            batch_size += 1
        else:
            if batch_size >= settings.threshold:
                munged.append(batch_size)
            last_batch = revtime
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
          color, label, bucket_size_days, lines = False):
    global _num_graphs

    if not data:
        return ""

    max_yaxis = _round_up_max(max(y for x, y in data))
    max_xaxis = len(data)

    graph_data = [dict(data=data, color=color, bars={'show': not lines}, lines={'show': lines}, label=label)]

    yaxes = [dict(min=0, max=max_yaxis)]
    xaxes = [dict(min=0, max=max_xaxis)]

    txt = self._title(_(title), _(subtitle))

    # can only disable x-axis labels after this PR https://github.com/dae/anki/pull/323
    canDisableXAxis = moreRecentThan(2, 1, 15)
    txt += _graph(
        self,
        id="throughput-%s" % _num_graphs,
        data=graph_data,
        xunit=None if canDisableXAxis else bucket_size_days,
        ylabel="Reviews in Batch",
        conf=dict(
            xaxis=xaxes,
            yaxes=yaxes))

    _num_graphs += 1

    text_lines = []

    txt += self._lineTbl(text_lines)

    return txt

def moreRecentThan(major, minor, patch):
    # really really basic test for semantic versioning.
    try:
        parts = version.split(".")
        if major < int(parts[0]):
            return True
        if minor < int(parts[1]):
            return True
        # patch often has a suffix
        # ex: 2.1.5beta2
        patchNum = ''.join(itertools.takewhile(str.isdigit, parts[2]))
        if patch < int(patchNum):
            return True

        return False
    except:
        # don't know if this format will be followed in future Anki versions
        # so if parsing fails, just return True
        return True


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
