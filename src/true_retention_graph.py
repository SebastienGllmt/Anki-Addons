"""
Anki Addon: True Retention Graph

Shows you how well you've retained cards. Useful to know to adjust your card ease settings to avoid over-forgetting

Copyright: Sebastien Guillemot 2017 <https://github.com/SebastienGllmt>
Based off code for True Retention Graph (https://ankiweb.net/shared/info/808676221)

License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html
"""

import math

import anki.stats
from anki.hooks import wrap

# debug
import time
from aqt.utils import showInfo

class settings:
############### YOU MAY EDIT THESE SETTINGS ###############
    daily_minimum = 10  # minimum number of reviews in a day for the stats to be included
############# END USER CONFIGURABLE SETTINGS #############

_graph = anki.stats.CollectionStats._graph
_num_graphs = 0
todayStats_old = anki.stats.CollectionStats.todayStats
swapped = False
periods = [31, 365, float('inf')]


def _round_up_max(max_val):
  "Rounds up a maximum value."

  # Prevent zero values raising an error.  Rounds up to 10 at a minimum.
  max_val = max(10, max_val)

  e = int(math.log10(max_val))
  if e >= 2:
    e -= 1
  m = 10**e
  return math.ceil(float(max_val)/m)*m

def _round_up_min(min_val):
  if min_val >= 0:
    return min_val

  return - _round_up_max(-min_val)

def _plot(self, data, title, subtitle,
          color, labels, lines = False):
  global _num_graphs
  
  if not data:
    return ""

  max_yaxis = float('-inf')
  min_yaxis = float('inf')
  graph_data = []
  for i in range(len(data)):
    max_yaxis = max(max_yaxis, _round_up_max(max(y for x, y in data[i])))
    min_yaxis = min(min_yaxis, _round_up_min(min(y for x, y in data[i])))

    graph_data.append(dict(data=data[i], color=color[i], bars={'show': not lines}, lines={'show': lines}, label=labels[i], stack=-i))

  yaxes = [dict(min=min_yaxis, max=max_yaxis)]

  txt = self._title(_(title), _(subtitle))
  txt += _graph(
    self,
    id="trg-%s" % _num_graphs,
    data=graph_data,
    ylabel="Retention",
    timeTicks = False,
    conf=dict(
      xaxis=dict(max=0.5),
      yaxes=yaxes))

  _num_graphs += 1

  text_lines = []

  txt += self._lineTbl(text_lines)

  return txt

def _line_now(self, i, a, b, bold=True):
  colon = _(":")
  if bold:
    i.append(("<tr><td align=right>%s%s</td><td><b>%s</b></td></tr>") % (a,colon,b))
  else:
    i.append(("<tr><td align=right>%s%s</td><td>%s</td></tr>") % (a,colon,b))

def _lineTbl_now(self, i):
  return "<table>" + "".join(i) + "</table>"

def get_first_id(self):
  return self.col.db.first("select min(id) from revlog")[0]

def get_retention(self, lim, frm, min_ivl, max_ivl, to = ""):
  if to:
    _to = " and id < " + str(to)
  if lim:
    _to += " and "

  off = frm % (86400 * 1000)
  data = self.col.db.all("""
  select
  sum(case when ease = 1 and type == 1 and lastIvl > ? and lastIvl <= ? then 1 else 0 end), /* flunked */
  sum(case when ease > 1 and type == 1 and ivl > ? and ivl <= ? then 1 else 0 end), /* passed */
  cast(((? + id) / 86400 / 1000) as int) as `day`
  from revlog where id > ?""" + _to + lim + " group by day", min_ivl, max_ivl, min_ivl, max_ivl, -off, frm)

  munged = []
  last_day = 0
  for row in data:
    flunked, passed, day = row
    day = day or 0
    flunked = flunked or 0
    passed = passed or 0
    if flunked + passed < settings.daily_minimum:
      continue
    try:
      temp = "%0.1f" %(passed/float(passed+flunked)*100)
    except ZeroDivisionError:
      temp = "-1"

    for i in range(day - last_day - 1):
      munged.append([-1, 0, 0])

    last_day = day
    munged.append([temp, flunked, passed])

  return munged


def todayStats_new(self):
  global swapped
  if not swapped:
    anki.stats.CollectionStats.cardGraph = wrap(anki.stats.CollectionStats.cardGraph, new_progressGraphs, pos="around")
    swapped = True

  return todayStats_old(self)

def process_data(last_day, retentions):
  data = []
  for day in range(last_day, 0):
    retention = retentions[day][0]
    retention = float(retention)
    if retention >= 0: #61nine20
      data.append((day + 1, retention))
    else:
      if len(data) > 0:
        data.append((day + 1, data[-1][1]))
  return data

def new_progressGraphs(*args, **kwargs):
  now = time.time()
  self = args[0]

  last_day = -min(365 * 10, periods[self.type]) - 1
  last_day_t = (self.col.sched.dayCutoff + 86400 * last_day) * 1000
  
  #young
  retentions_young = get_retention(self, self._revlogLimit(), last_day_t, 0, 20, self.col.sched.dayCutoff * 1000)
  data_young = process_data(last_day, retentions_young)

  #mature
  retentions_mature = get_retention(self, self._revlogLimit(), last_day_t, 20, 65535, self.col.sched.dayCutoff * 1000)
  data_mature = process_data(last_day, retentions_mature)

  old = kwargs['_old']
  del kwargs['_old']

  result = old(*args, **kwargs)
  result += _plot(self,
          [data_young, data_mature],
          "True retention",
          "The percentage of correct reviews you had day per day, with days without reviews shown as a flat line.",
          color=["#7c7", "#070"],
          labels=[_("Young"), _("Mature")],
          lines = True)

  return result

anki.stats.CollectionStats.todayStats = todayStats_new
