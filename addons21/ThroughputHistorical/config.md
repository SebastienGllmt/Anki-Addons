# Historical Throughput

Adds a new graph to the statistics screen that shows you your historical throughput on Anki

Looks at how many cards you study in `batch_time` minutes and averages it in groups of `group_for_averaging`
Note: There must have been more than `threshold` reviews in `batch_time` minutes for it to count

Generate graphs for all card types (`learning`, `young` and `mature` ) by setting `add_all_graphs` to `true`.
