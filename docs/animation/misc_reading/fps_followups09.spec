# 2026-10-11: the chain effects' relaxation (esp10, esp31): spring chains integrated once a
# tick, the swinging bones' problem (1BA350). Velocities are displacements per stock tick, so
# a tick's share of a step is: spring and force pushes x s (dst on the factor a Scale or
# operator* takes in xmm2; scaledadd on a force's +=), damping k^s (root), the integration
# p += s x v (scaledadd), and a relaxation toward the previous point 1 - (1 - r)^s (blendr).
# The length constraints that follow are geometry, right at any rate. At 120 every chain
# swung, sagged and settled four times as fast.
#
# esp10 1A20A0 (slot 1), once its grow-in (+308 to +30C, counted at 1A214D) is done:
#   v[i] += (p[i+1] - p[i]) x k (+320), then back from the tail v[i] += (p[i-1] - p[i]) x k;
#   for each point but the head: v.y += g (+31C), v *= d (+324), p += v, p += (p[i-1] - p) x r
#   (+32C); then the span limit +314 and the head at its owner (18C980) or attach point.
group effect
dst 1A2269 scale:1A2279 | esp10 1A20A0: the forward spring push v[i] += (p[i+1] - p[i]) x +320 a tick (Scale's factor): s of it
dst 1A22E9 scale:1A22F9 | esp10 1A20A0: the backward spring push v[i] += (p[i-1] - p[i]) x +320 a tick: s of it
pre 1A2366 | esp10 1A20A0: v.y += g (+31C, in xmm0) a tick: s of it
root 1A237B | esp10 1A20A0: v *= +324 a tick (the damping Scale takes): +324^s
scaledadd 1A23A3 | esp10 1A20A0: p += v a tick (cVec::operator+=): p += s x v
blendr 1A23CC | esp10 1A20A0: p += (p[i-1] - p) x +32C a tick, the relaxation toward the previous point (operator*'s factor): 1 - (1 - r)^s
# esp31 1AA210 (slot 1): its sway phase +338 is paced already (1AA23D); the sway vector
# (sin(phase) x +324 in x and z) and the force +300 (through the owner's rotation) are made
# afresh each tick. From the tail: v[i] += (p[i-1] - p[i]) x k (+31C); from the head: the span
# limit +318 on each segment, v[i+1] -= d x k x 0.1 and v[i] += d x k; then for each point but
# the head: p += sway x w (w 1, x 0.97 a point, for the first +334 points), v += force,
# v *= +320, p += v.
dst 1AA3AA scale:1AA3BC | esp31 1AA210: the spring push from the tail v[i] += (p[i-1] - p[i]) x +31C a tick: s of it
dst 1AA4C7 scale:1AA4D8 | esp31 1AA210: the segment's push back v[i+1] -= d x +31C x 0.1 a tick (operator*'s factor): s of it
dst 1AA502 scale:1AA514 | esp31 1AA210: the segment's push v[i] += d x +31C a tick: s of it
dst 1AA57B scale:1AA589 | esp31 1AA210: the sway displacement p += sway x w a tick (operator*'s factor, a copy of w in xmm2; w itself kept): s of it
scaledadd 1AA5C1 | esp31 1AA210: v += force (+300 through the owner's rotation) a tick: v += s x force
root 1AA5CE | esp31 1AA210: v *= +320 a tick (the damping Scale takes): +320^s
scaledadd 1AA5F6 | esp31 1AA210: p += v a tick (cVec::operator+=): p += s x v
