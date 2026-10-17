# 2026-10-11: integer phases outside the original census.
# These stores commit a retained integer phase once per stock tick. The masked
# phases are used before the store and their copied UV values can safely repeat.
group player
count 16E978 | Celestial brush drawing 16C7E0: 896BEC is the 30-tick idle gap reset when a new stroke point is accepted, then sets flag8 on the last recorded point; pace elapsed idle time, preserving the point count and current-tick input sampling
group objects
count 22BFE6 | 22BF00: retained +1158 phase gains1 modulo512 each tick, adds phase/511 to both camera-facing UV coordinates; pace the phase while retaining current camera geometry
count 3368C3 | hm8f 3367E0: retained +1310 phase gains1 modulo512 and adds phase/511 to both camera-facing UV coordinates, as22BF00
count 5A7B36 | utd8 5A7A50: retained +115E phase gains1 modulo512 and adds phase/511 to both camera-facing UV coordinates; caller5A73B4 is the per-tick update
group actor
count 273778 | em2b 2736E0: retained byte+1440 gains1 modulo16 after choosing one of eight material UV frames (each shown twice); pace the flipbook, not the actor's other update work
count 2D8D97 | em8c update2D8BB0: retained byte+1234 gains1 modulo4 after3DE510 selects that frame for materials3..6; pace the flipbook while keeping motion and collisions current
group objects
count 2284C5 | 228370: retained +10E6 phase gains1 modulo8 while type892 is active; zero emits effect variant4, the other collision/state work still runs every tick
notyet 22848B 0x2284BA | 228370: the zero of the paced eight-tick emission phase is held between stock ticks; gate its compare itself so the emitter emits once, and the held path reaches only its own count row in the same group

# Manager elements count stock ticks through the existing actor row23D789.
# The installed fps byte is60 at both60 and120; dividing by it halves seconds.
group actor
stockfps 4B1FE2 0x4B1FF4 | script4B1D80: manager slot2 node+40 counts at30Hz through23D789; seconds divide by30 while actor pacing is on, retain the original fps byte when off
stockfps 4FBD8B 0x4FBD97 | script4FBCB0: manager slot3 node+40 counts at30Hz through23D789; seconds divide by30 while actor pacing is on, retain the original fps byte when off
stockfps 538422 0x538432 | script5381A0: manager slot1 node+40 counts at30Hz through23D789; seconds divide by30 while actor pacing is on, retain the original fps byte when off

# Stage callbacks run through4BA500/48BE20/48C120/48C280/135940 every tick.
group actor
count 4C5C2D | stage callback4C5900: B6D6DC elapsed count gains1 per callback; old count15 plays sound12, not an event tally
notyet 4C5C33 0x4C5C4B | callback4C5900: gate the old-count15 comparison itself so holding the paced counter cannot replay sound12; held path goes straight to the return
count 4C5FE1 | stage callback4C5E80: B6D6E4 elapsed count gains1 per callback; old count15 plays sound12, not an event tally
notyet 4C5FE7 0x4C5FFF | callback4C5E80: gate the old-count15 comparison itself so holding the paced counter cannot replay sound12; held path goes straight to the return

# B663D8 = cameraB661E0+1F8, decremented by the existing objects gate476030.
# Keep constant writers; normalize only the five fps-derived half-second waits.
group objects
stockfps 364CBE ("quake",0x364C96,0x364CD8) | quake duration B663D8 is floor(fps/30)*15; camera gate476030 already counts stock ticks, so read30 while objects pacing is on and preserve the original byte when off
stockfps 370026 ("quake",0x370021,0x370040) | quake duration B663D8 is floor(fps/30)*15; normalize the fps input with the same objects mask as camera gate476030
stockfps 3703FF ("quake",0x3703FA,0x37041B) | quake duration B663D8 is floor(fps/30)*15; normalize the fps input with the same objects mask as camera gate476030
stockfps 3C1DE8 ("quake",0x3C1E08,0x3C1E3C) | quake duration B663D8 is floor(fps/30)*15; normalize the fps input with the same objects mask as camera gate476030
stockfps 3C5FE6 ("quake",0x3C5FBD,0x3C6008) | quake duration B663D8 is floor(fps/30)*15; normalize the fps input with the same objects mask as camera gate476030
