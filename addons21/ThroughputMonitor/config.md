# Throughput Monitor

Tries to gamify Anki by breaking your study session into batches of time (ex: 5 minutes) through a countdown bar.

Using these batches, we

1) Show a rolling average of how much you study in the given batch
2) Shows how many cards you've studied in the current batch compared to your average
3) If you surpass the rolling average, a flame will appear to show you that you're on fire!

We use this to also show how long it will take to complete your review at your current pace.

## Settings

### Countdown bar settings

- `timebox` size (in seconds) of a study batches to consider for

- `countdown_colors` color of the bar as the countdown gets closer to 0
- `invert_timer` decides if countdown bar fills from left->right or right->left
- `countdown_timer_as_percentage` whether or not to display the time left in batch or just the % time passed

### Study time left settings

- `include_all_study_time_for_day` whether to include the entire day's worth of study in the bar or just the current review

- `show_time_till_end` show the exact time until you finish all cards

### Point bar settings

- `penalize_idle` if you got 0 points in batch, whether or not we should count it
- `exponential_weight` decay for exponential weighted average
- `goal_offset`how many more reviews than the exponential weighted average you hope to get this round
- `initial_throughput_guess` initial goal when you just started on a deck with no prior study history
- `bonus_points_by_card_type` get different amount of points based off if this card is (new, learning, due, relearn)

- `number_batches_to_keep` number of batches to use to calculate moving average
- `threshold_for_batch` how many answers needed in a batches to be considered for the moving average

- `points_as_percentage` whether or not to show % towards reaching moving average in batch
- `points_as_number` whether or not to show how many points you have in the current batch

- `show_flame` whether or not to show a flame when doing better than average
- `flame_height` height in pixels of the fire (width is automatically adjusted to maintain aspect ratio)
