# -*- coding: utf-8 -*-
"""
Anki Add-on: Studyahead Audio

Exports the next N new cards as an audio file so you can listen to them while doing something else
The goal is that when you actually study these cards, you will memorize them faster

            (c) SebastienGllmt 2017 <https://github.com/SebastienGllmt/>

License: GNU AGPLv3 or later <https://www.gnu.org/licenses/agpl.html>
"""

# todo: Add some visual indication that it's running...
# todo: Create UI
# todo: add error if ffmpeg is not on your computer and in path

import os.path
import codecs

from aqt import mw
from aqt.qt import *
from aqt.utils import showInfo

from anki.utils import call, namedtmp, ids2str

def get_card_audio(num_cards, field_names, model_ids):
    'get (up to) /num_cards/ next new cards. Looks for fields /fieldNames/ in the cards'

    if mw.col == None or mw.col.decks.active() == None:
        return None

    curr_deck = mw.col.decks.active()
    data = mw.col.db.all("""
        SELECT Notes.mid, Notes.flds, Notes.mid
        FROM (Cards INNER JOIN NOTES ON Cards.nid=Notes.id) 
        WHERE Notes.mid in %s and Cards.type=0 and Cards.did in %s
        GROUP BY Notes.id 
        ORDER BY Cards.due 
        limit ?""" % (ids2str(model_ids), ids2str(curr_deck)), num_cards)

    model_field_map = dict()
    audio_files = []
    for row in data:
        if row[0] in model_field_map:
            field_map = model_field_map[row[0]]
        else:
            model = mw.col.models.get(row[0])
            field_map = mw.col.models.fieldMap(model)
            model_field_map[row[0]] = field_map
        
        for name in field_names:
            if name in field_map:
                field_data = row[1].split(chr(0x1f))
                audio_field = field_data[field_map[name][0]]
                # note: an audio field could contain multiple audio files.
                # search for all [filename] inside field
                
                matches = mw.col.media.filesInStr(row[0], audio_field)
                audio_files.extend(matches)
                break
    
    return audio_files

def export_audio(output_folder, field_names, model_ids, cards_per_batch, num_batches, num_loops, include_separator):
    "Save all audio files into one large audio file"
    audio_files = get_card_audio(cards_per_batch*num_batches, field_names, model_ids)

    # get files on machine
    audio_files = [os.path.join(mw.col.media.dir(), field) for field in audio_files]

    for batch_id in range(num_batches):
        audio_files_in_batch = audio_files[batch_id*cards_per_batch:(batch_id+1)*cards_per_batch]
        output_file = os.path.join(output_folder,"batch%d.mp3" % batch_id)
        audio_list_tmp_file = namedtmp("studyahead_audio_list.txt")

        separator_audio = os.path.join(mw.pm.addonFolder(), 'Studyahead_Audio', 'file_seperator.mp3')
        with codecs.open(audio_list_tmp_file, "w", "utf-8") as f:
            for i, audio_file in enumerate(audio_files_in_batch):
                for j in range(num_loops):
                    f.write("file '%s'\n" % os.path.relpath(audio_file, os.path.dirname(audio_list_tmp_file)).replace("\\","/"))
                if i < len(audio_files_in_batch)-1 and include_separator:
                    f.write("file '%s'\n" % os.path.relpath(separator_audio, os.path.dirname(audio_list_tmp_file)).replace("\\","/"))

        output_command = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", audio_list_tmp_file.replace("\\","/"), "-vcodec", "copy", output_file]
        with open(namedtmp("studyahead_audio_log.txt"), "w") as log:
            call(output_command, wait=True, stdout=log, stderr=log)

def open_settings_ui():
    "Open UI for selecting the settings"
    # TODO: make the UI
    out_dir = "C:/Users/Sebas/Desktop/test"
    export_audio(out_dir, ["Audio"], [1484037039341],10,3,3, True)
    showInfo("Audio exported to {}".format(out_dir))

#Add a pull-down menu item	
action = QAction("Studyahead Audio", mw)
action.triggered.connect(open_settings_ui)
mw.form.menuTools.addAction(action)
