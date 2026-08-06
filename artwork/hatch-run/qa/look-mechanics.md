# Godette look-direction mechanics

Godette is a humanoid character. Her planted feet, lower-body scale, and baseline
are the registration anchors. Gaze begins with her blue irises and pupils, then
the eyelids and brows, with only restrained support from the chin, neck, and
upper torso. Her skull and face proportions must not warp.

The twin hair buns and plain worn backpack are rigid identity features. They
follow the head and torso through believable overlap and strap occlusion; they
must not detach, deform into aiming devices, acquire logos, or become props.

Cardinal semantics:

- `000 up`: eyes and irises point to the top edge; brows and eyelids reinforce
  the gaze; the chin and head may lift subtly.
- `090 screen-right`: pupils, nose, face plane, and cheek/bun occlusion make the
  viewer's right edge unmistakable.
- `180 down`: eyes and irises point to the bottom edge; the chin tucks slightly
  and a little more hair/top plane may be visible.
- `270 screen-left`: the exact semantic inverse of `090`, aimed at the viewer's
  left edge.

For every 22.5-degree step, use a similar visual increment. Keep feet and the
baseline fixed, the head center within roughly two pixels after registration,
and the shoulders within roughly one pixel. Avoid sudden flips, pose jumps, or
whole-sprite rotation. The transition from `337.5` back to `000` must be as
continuous as every other neighboring pair.
