-- tests/radial_bearing/sim.lua
-- 4-pole radial magnetic bearing regression simulation.
-- Ref: https://www.femm.info/wiki/RadialMagneticBearing
--
-- Geometry is reconstructed from brgmodel.fem (FEMM wiki).
-- Problem is planar, units in inches, depth = 1.6 in.
-- Circuits: i1=6A (right), i2=12A (top), i3=6A (left), i4=0A (bottom).
--
-- Accepts /lua-var=outdir=Z:\path\to\outputdir
-- (FEMM lowercases all /lua-var values, so outdir must be a lowercase path)
-- Optionally /lua-var=interactive=1 to skip quit() and leave the window open.
-- Writes:
--   outdir/sim.fem        — problem definition
--   outdir/sim.ans        — solution (created automatically by FEMM)
--   outdir/results.txt    — key=value scalar results for test runner

if outdir == nil then outdir = "z:\\tmp\\femm_test_radial_bearing" end
if interactive == nil then interactive = "0" end

newdocument(0)
mi_probdef(0, "inches", "planar", 1e-8, 1.6, 30)

-- ── Materials ─────────────────────────────────────────────────────────────
mi_addmaterial("Air", 1, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0)

-- M-19 Silicon Steel with nonlinear B-H curve from brgmodel.fem
mi_addmaterial("M-19 Steel", 4416, 4416, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0)
mi_addbhpoint("M-19 Steel",    0,       0)
mi_addbhpoint("M-19 Steel",    0.3,     39.78875)
mi_addbhpoint("M-19 Steel",    0.8,     79.5775)
mi_addbhpoint("M-19 Steel",    1.12,   159.155)
mi_addbhpoint("M-19 Steel",    1.32,   318.31)
mi_addbhpoint("M-19 Steel",    1.46,   795.775)
mi_addbhpoint("M-19 Steel",    1.54,  1591.55)
mi_addbhpoint("M-19 Steel",    1.61875, 3376.667)
mi_addbhpoint("M-19 Steel",    1.74,  7957.75)
mi_addbhpoint("M-19 Steel",    1.87, 15915.5)
mi_addbhpoint("M-19 Steel",    1.99, 31831)
mi_addbhpoint("M-19 Steel",    2.045964, 55102.04)
mi_addbhpoint("M-19 Steel",    2.08, 79577.5)

-- 18 AWG stranded wire (LamType=3, wire diam = 1.024 mm)
mi_addmaterial("18 AWG", 1, 1, 0, 0, 58, 0, 0, 1, 3, 0, 0, 1, 1.0239652968433499)

-- ── Boundary conditions ───────────────────────────────────────────────────
mi_addboundprop("A=0", 0, 0, 0, 0, 0, 0, 0, 0, 0)

-- ── Circuits ──────────────────────────────────────────────────────────────
mi_addcircprop("i1",  6, 1)
mi_addcircprop("i2", 12, 1)
mi_addcircprop("i3",  6, 1)
mi_addcircprop("i4",  0, 1)

-- ── Geometry: nodes ───────────────────────────────────────────────────────
-- 102 nodes from brgmodel.fem (0-indexed in original file)
mi_addnode(0.92388, -0.382683)
mi_addnode(-0.92388, 0.382683)
mi_addnode(1.020017, -0.202894)
mi_addnode(0.864729, -0.577793)
mi_addnode(0.864728, 0.577793)
mi_addnode(1.020016, 0.202894)
mi_addnode(0.202894, 1.020017)
mi_addnode(0.577793, 0.864729)
mi_addnode(-0.577793, 0.864728)
mi_addnode(-0.202894, 1.020016)
mi_addnode(-0.202894, -1.020017)
mi_addnode(-0.577793, -0.864729)
mi_addnode(0.577793, -0.864728)
mi_addnode(0.202894, -1.020016)
mi_addnode(-0.864728, -0.577793)
mi_addnode(-1.020016, -0.202894)
mi_addnode(-1.020017, 0.202894)
mi_addnode(-0.864729, 0.577793)
mi_addnode(1.915871, -0.573969)
mi_addnode(1.760582, -0.948868)
mi_addnode(1.760582, 0.948868)
mi_addnode(1.91587, 0.573969)
mi_addnode(0.573969, 1.915871)
mi_addnode(0.948868, 1.760582)
mi_addnode(-0.948868, 1.760582)
mi_addnode(-0.573969, 1.91587)
mi_addnode(-1.915871, 0.573969)
mi_addnode(-1.760582, 0.948868)
mi_addnode(-1.760582, -0.948868)
mi_addnode(-1.91587, -0.573969)
mi_addnode(-0.573969, -1.915871)
mi_addnode(-0.948868, -1.760582)
mi_addnode(0.948868, -1.760582)
mi_addnode(0.573969, -1.91587)
mi_addnode(2.217311, -0.91844)
mi_addnode(-2.217311, 0.91844)
mi_addnode(0.554328, -0.22961)
mi_addnode(-0.554328, 0.22961)
mi_addnode(1.346191, -0.016415)
mi_addnode(0.963508, -0.940294)
mi_addnode(1.900519, -0.246025)
mi_addnode(1.517835, -1.169904)
mi_addnode(1.232494, -0.290905)
mi_addnode(1.077205, -0.665804)
mi_addnode(1.786821, -0.520515)
mi_addnode(1.631533, -0.895414)
mi_addnode(0.963508, 0.940294)
mi_addnode(1.517835, 1.169904)
mi_addnode(1.346191, 0.016414)
mi_addnode(1.900519, 0.246024)
mi_addnode(1.077205, 0.665804)
mi_addnode(1.232493, 0.290905)
mi_addnode(1.631533, 0.895414)
mi_addnode(1.786821, 0.520515)
mi_addnode(0.016415, 1.346191)
mi_addnode(0.246025, 1.900519)
mi_addnode(0.940294, 0.963508)
mi_addnode(1.169904, 1.517835)
mi_addnode(0.290905, 1.232494)
mi_addnode(0.665804, 1.077205)
mi_addnode(0.520515, 1.786821)
mi_addnode(0.895414, 1.631533)
mi_addnode(-0.940294, 0.963508)
mi_addnode(-1.169904, 1.517835)
mi_addnode(-0.016414, 1.346191)
mi_addnode(-0.246024, 1.900519)
mi_addnode(-0.665804, 1.077205)
mi_addnode(-0.290905, 1.232493)
mi_addnode(-0.895414, 1.631533)
mi_addnode(-0.520515, 1.786821)
mi_addnode(-1.346191, 0.016415)
mi_addnode(-1.900519, 0.246025)
mi_addnode(-0.963508, 0.940294)
mi_addnode(-1.517835, 1.169904)
mi_addnode(-1.232494, 0.290905)
mi_addnode(-1.077205, 0.665804)
mi_addnode(-1.786821, 0.520515)
mi_addnode(-1.631533, 0.895414)
mi_addnode(-0.963508, -0.940294)
mi_addnode(-1.517835, -1.169904)
mi_addnode(-1.346191, -0.016414)
mi_addnode(-1.900519, -0.246024)
mi_addnode(-1.077205, -0.665804)
mi_addnode(-1.232493, -0.290905)
mi_addnode(-1.631533, -0.895414)
mi_addnode(-1.786821, -0.520515)
mi_addnode(-0.016415, -1.346191)
mi_addnode(-0.246025, -1.900519)
mi_addnode(-0.940294, -0.963508)
mi_addnode(-1.169904, -1.517835)
mi_addnode(-0.290905, -1.232494)
mi_addnode(-0.665804, -1.077205)
mi_addnode(-0.520515, -1.786821)
mi_addnode(-0.895414, -1.631533)
mi_addnode(0.940294, -0.963508)
mi_addnode(1.169904, -1.517835)
mi_addnode(0.016414, -1.346191)
mi_addnode(0.246024, -1.900519)
mi_addnode(0.665804, -1.077205)
mi_addnode(0.290905, -1.232493)
mi_addnode(0.895414, -1.631533)
mi_addnode(0.520515, -1.786821)

-- ── Geometry: line segments ───────────────────────────────────────────────
-- 96 line segments from brgmodel.fem
mi_addsegment(0.864728, 0.577793, 1.077205, 0.665804)
mi_addsegment(1.077205, 0.665804, 1.631533, 0.895414)
mi_addsegment(1.631533, 0.895414, 1.760582, 0.948868)
mi_addsegment(1.020016, 0.202894, 1.232493, 0.290905)
mi_addsegment(1.232493, 0.290905, 1.786821, 0.520515)
mi_addsegment(1.786821, 0.520515, 1.91587, 0.573969)
mi_addsegment(0.202894, 1.020017, 0.290905, 1.232494)
mi_addsegment(0.290905, 1.232494, 0.520515, 1.786821)
mi_addsegment(0.520515, 1.786821, 0.573969, 1.915871)
mi_addsegment(0.577793, 0.864729, 0.665804, 1.077205)
mi_addsegment(0.665804, 1.077205, 0.895414, 1.631533)
mi_addsegment(0.895414, 1.631533, 0.948868, 1.760582)
mi_addsegment(-0.577793, 0.864728, -0.665804, 1.077205)
mi_addsegment(-0.665804, 1.077205, -0.895414, 1.631533)
mi_addsegment(-0.895414, 1.631533, -0.948868, 1.760582)
mi_addsegment(-0.202894, 1.020016, -0.290905, 1.232493)
mi_addsegment(-0.290905, 1.232493, -0.520515, 1.786821)
mi_addsegment(-0.520515, 1.786821, -0.573969, 1.91587)
mi_addsegment(-1.020017, 0.202894, -1.232494, 0.290905)
mi_addsegment(-1.232494, 0.290905, -1.786821, 0.520515)
mi_addsegment(-1.786821, 0.520515, -1.915871, 0.573969)
mi_addsegment(-0.864729, 0.577793, -1.077205, 0.665804)
mi_addsegment(-1.077205, 0.665804, -1.631533, 0.895414)
mi_addsegment(-1.631533, 0.895414, -1.760582, 0.948868)
mi_addsegment(-0.864728, -0.577793, -1.077205, -0.665804)
mi_addsegment(-1.077205, -0.665804, -1.631533, -0.895414)
mi_addsegment(-1.631533, -0.895414, -1.760582, -0.948868)
mi_addsegment(-1.020016, -0.202894, -1.232493, -0.290905)
mi_addsegment(-1.232493, -0.290905, -1.786821, -0.520515)
mi_addsegment(-1.786821, -0.520515, -1.91587, -0.573969)
mi_addsegment(-0.202894, -1.020017, -0.290905, -1.232494)
mi_addsegment(-0.290905, -1.232494, -0.520515, -1.786821)
mi_addsegment(-0.520515, -1.786821, -0.573969, -1.915871)
mi_addsegment(-0.577793, -0.864729, -0.665804, -1.077205)
mi_addsegment(-0.665804, -1.077205, -0.895414, -1.631533)
mi_addsegment(-0.895414, -1.631533, -0.948868, -1.760582)
mi_addsegment(0.577793, -0.864728, 0.665804, -1.077205)
mi_addsegment(0.665804, -1.077205, 0.895414, -1.631533)
mi_addsegment(0.895414, -1.631533, 0.948868, -1.760582)
mi_addsegment(0.202894, -1.020016, 0.290905, -1.232493)
mi_addsegment(0.290905, -1.232493, 0.520515, -1.786821)
mi_addsegment(0.520515, -1.786821, 0.573969, -1.91587)
mi_addsegment(1.020017, -0.202894, 1.232494, -0.290905)
mi_addsegment(0.864729, -0.577793, 1.077205, -0.665804)
mi_addsegment(1.346191, -0.016415, 1.900519, -0.246025)
mi_addsegment(0.963508, -0.940294, 1.517835, -1.169904)
mi_addsegment(1.232494, -0.290905, 1.786821, -0.520515)
mi_addsegment(1.077205, -0.665804, 1.631533, -0.895414)
mi_addsegment(1.346191, -0.016415, 1.232494, -0.290905)
mi_addsegment(1.077205, -0.665804, 0.963508, -0.940294)
mi_addsegment(1.786821, -0.520515, 1.915871, -0.573969)
mi_addsegment(1.631533, -0.895414, 1.760582, -0.948868)
mi_addsegment(1.900519, -0.246025, 1.786821, -0.520515)
mi_addsegment(1.631533, -0.895414, 1.517835, -1.169904)
mi_addsegment(0.963508, 0.940294, 1.517835, 1.169904)
mi_addsegment(1.346191, 0.016414, 1.900519, 0.246024)
mi_addsegment(0.963508, 0.940294, 1.077205, 0.665804)
mi_addsegment(1.232493, 0.290905, 1.346191, 0.016414)
mi_addsegment(1.517835, 1.169904, 1.631533, 0.895414)
mi_addsegment(1.786821, 0.520515, 1.900519, 0.246024)
mi_addsegment(0.016415, 1.346191, 0.246025, 1.900519)
mi_addsegment(0.940294, 0.963508, 1.169904, 1.517835)
mi_addsegment(0.016415, 1.346191, 0.290905, 1.232494)
mi_addsegment(0.665804, 1.077205, 0.940294, 0.963508)
mi_addsegment(0.246025, 1.900519, 0.520515, 1.786821)
mi_addsegment(0.895414, 1.631533, 1.169904, 1.517835)
mi_addsegment(-0.940294, 0.963508, -1.169904, 1.517835)
mi_addsegment(-0.016414, 1.346191, -0.246024, 1.900519)
mi_addsegment(-0.940294, 0.963508, -0.665804, 1.077205)
mi_addsegment(-0.290905, 1.232493, -0.016414, 1.346191)
mi_addsegment(-1.169904, 1.517835, -0.895414, 1.631533)
mi_addsegment(-0.520515, 1.786821, -0.246024, 1.900519)
mi_addsegment(-1.346191, 0.016415, -1.900519, 0.246025)
mi_addsegment(-0.963508, 0.940294, -1.517835, 1.169904)
mi_addsegment(-1.346191, 0.016415, -1.232494, 0.290905)
mi_addsegment(-1.077205, 0.665804, -0.963508, 0.940294)
mi_addsegment(-1.900519, 0.246025, -1.786821, 0.520515)
mi_addsegment(-1.631533, 0.895414, -1.517835, 1.169904)
mi_addsegment(-0.963508, -0.940294, -1.517835, -1.169904)
mi_addsegment(-1.346191, -0.016414, -1.900519, -0.246024)
mi_addsegment(-0.963508, -0.940294, -1.077205, -0.665804)
mi_addsegment(-1.232493, -0.290905, -1.346191, -0.016414)
mi_addsegment(-1.517835, -1.169904, -1.631533, -0.895414)
mi_addsegment(-1.786821, -0.520515, -1.900519, -0.246024)
mi_addsegment(-0.016415, -1.346191, -0.246025, -1.900519)
mi_addsegment(-0.940294, -0.963508, -1.169904, -1.517835)
mi_addsegment(-0.016415, -1.346191, -0.290905, -1.232494)
mi_addsegment(-0.665804, -1.077205, -0.940294, -0.963508)
mi_addsegment(-0.246025, -1.900519, -0.520515, -1.786821)
mi_addsegment(-0.895414, -1.631533, -1.169904, -1.517835)
mi_addsegment(0.940294, -0.963508, 1.169904, -1.517835)
mi_addsegment(0.016414, -1.346191, 0.246024, -1.900519)
mi_addsegment(0.940294, -0.963508, 0.665804, -1.077205)
mi_addsegment(0.290905, -1.232493, 0.016414, -1.346191)
mi_addsegment(1.169904, -1.517835, 0.895414, -1.631533)
mi_addsegment(0.520515, -1.786821, 0.246024, -1.900519)

-- ── Geometry: arc segments ────────────────────────────────────────────────
-- 22 arc segments from brgmodel.fem
-- Rotor outer surface: two 180° arcs forming a complete circle at r=1.0 in
mi_addarc(0.92388, -0.382683, -0.92388, 0.382683, 180.0, 2.5)
mi_addarc(-0.92388, 0.382683, 0.92388, -0.382683, 180.0, 2.5)
-- Stator bore arcs: 8 arcs of 22.5° defining the pole face boundaries at r≈1.04 in
mi_addarc(1.020016, 0.202894, 0.864728, 0.577793, 22.5, 2.5)
mi_addarc(0.577793, 0.864729, 0.202894, 1.020017, 22.5, 2.5)
mi_addarc(-0.202894, 1.020016, -0.577793, 0.864728, 22.5, 2.5)
mi_addarc(-1.020016, -0.202894, -0.864728, -0.577793, 22.5, 2.5)
mi_addarc(-0.577793, -0.864729, -0.202894, -1.020017, 22.5, 2.5)
mi_addarc(0.202894, -1.020016, 0.577793, -0.864728, 22.5, 2.5)
mi_addarc(0.864729, -0.577793, 1.020017, -0.202894, 22.5, 2.5)
mi_addarc(-0.864729, 0.577793, -1.020017, 0.202894, 22.5, 2.5)
-- Outer stator face arcs: 8 arcs of 33.355° at r≈2.0 in
mi_addarc(-1.915871, 0.573969, -1.91587, -0.573969, 33.355001, 2.5)
mi_addarc(-1.760582, -0.948868, -0.948868, -1.760582, 33.355001, 2.5)
mi_addarc(-0.573969, -1.915871, 0.573969, -1.91587, 33.355001, 2.5)
mi_addarc(1.760582, 0.948868, 0.948868, 1.760582, 33.355001, 2.5)
mi_addarc(0.573969, 1.915871, -0.573969, 1.91587, 33.355001, 2.5)
mi_addarc(-0.948868, 1.760582, -1.760582, 0.948868, 33.355001, 2.5)
-- Outer domain boundary: two 180° arcs at r=2.4 in (A=0 BC applied below)
mi_addarc(2.217311, -0.91844, -2.217311, 0.91844, 180.0, 2.5)
mi_addarc(-2.217311, 0.91844, 2.217311, -0.91844, 180.0, 2.5)
-- Rotor inner bore: two 180° arcs at r=0.6 in
mi_addarc(0.554328, -0.22961, -0.554328, 0.22961, 180.0, 2.5)
mi_addarc(-0.554328, 0.22961, 0.554328, -0.22961, 180.0, 2.5)
-- Remaining outer stator face arcs
mi_addarc(0.948868, -1.760582, 1.760582, -0.948868, 33.355001, 2.5)
mi_addarc(1.915871, -0.573969, 1.91587, 0.573969, 33.355001, 2.5)

-- ── Apply A=0 boundary condition to outer circle arcs ─────────────────────
-- Outer boundary arcs are at r=2.4 in (nodes 34/35).
-- Midpoints of the two 180° arcs: at angles +67.5° and +247.5°.
mi_selectarcsegment(0.918, 2.217)
mi_selectarcsegment(-0.918, -2.217)
mi_setarcsegmentprop(2.5, "A=0", 0, 0)
mi_clearselected()

-- ── Block labels ─────────────────────────────────────────────────────────
-- 16 coil blocks (18 AWG) with circuits and ±80 turns
-- Right pole (i1): outer coils +80, inner coils -80
mi_addblocklabel(1.588257, -0.268216)
mi_selectlabel(1.588257, -0.268216)
mi_setblockprop("18 AWG", 0, 0.05, "i1", 0, 0, 80)
mi_clearselected()

mi_addblocklabel(1.557868, 0.285567)
mi_selectlabel(1.557868, 0.285567)
mi_setblockprop("18 AWG", 0, 0.05, "i1", 0, 0, 80)
mi_clearselected()

mi_addblocklabel(1.276426, -0.864255)
mi_selectlabel(1.276426, -0.864255)
mi_setblockprop("18 AWG", 0, 0.05, "i1", 0, 0, -80)
mi_clearselected()

mi_addblocklabel(1.314986, 0.927368)
mi_selectlabel(1.314986, 0.927368)
mi_setblockprop("18 AWG", 0, 0.05, "i1", 0, 0, -80)
mi_clearselected()

-- Top pole (i2): outer coils +80, inner coils -80
mi_addblocklabel(0.292106, 1.567538)
mi_selectlabel(0.292106, 1.567538)
mi_setblockprop("18 AWG", 0, 0.05, "i2", 0, 0, 80)
mi_clearselected()

mi_addblocklabel(-0.289394, 1.548629)
mi_selectlabel(-0.289394, 1.548629)
mi_setblockprop("18 AWG", 0, 0.05, "i2", 0, 0, 80)
mi_clearselected()

mi_addblocklabel(0.885631, 1.354163)
mi_selectlabel(0.885631, 1.354163)
mi_setblockprop("18 AWG", 0, 0.05, "i2", 0, 0, -80)
mi_clearselected()

mi_addblocklabel(-0.898067, 1.281201)
mi_selectlabel(-0.898067, 1.281201)
mi_setblockprop("18 AWG", 0, 0.05, "i2", 0, 0, -80)
mi_clearselected()

-- Left pole (i3): outer coils +80, inner coils -80
mi_addblocklabel(-1.552887, 0.275213)
mi_selectlabel(-1.552887, 0.275213)
mi_setblockprop("18 AWG", 0, 0.05, "i3", 0, 0, 80)
mi_clearselected()

mi_addblocklabel(-1.507847, -0.295463)
mi_selectlabel(-1.507847, -0.295463)
mi_setblockprop("18 AWG", 0, 0.05, "i3", 0, 0, 80)
mi_clearselected()

mi_addblocklabel(-1.296489, 0.894213)
mi_selectlabel(-1.296489, 0.894213)
mi_setblockprop("18 AWG", 0, 0.05, "i3", 0, 0, -80)
mi_clearselected()

mi_addblocklabel(-1.270377, -0.924198)
mi_selectlabel(-1.270377, -0.924198)
mi_setblockprop("18 AWG", 0, 0.05, "i3", 0, 0, -80)
mi_clearselected()

-- Bottom pole (i4, 0A): outer coils +80, inner coils -80
mi_addblocklabel(-0.227434, -1.594325)
mi_selectlabel(-0.227434, -1.594325)
mi_setblockprop("18 AWG", 0, 0.05, "i4", 0, 0, 80)
mi_clearselected()

mi_addblocklabel(0.328591, -1.532393)
mi_selectlabel(0.328591, -1.532393)
mi_setblockprop("18 AWG", 0, 0.05, "i4", 0, 0, 80)
mi_clearselected()

mi_addblocklabel(0.912718, -1.298093)
mi_selectlabel(0.912718, -1.298093)
mi_setblockprop("18 AWG", 0, 0.05, "i4", 0, 0, -80)
mi_clearselected()

mi_addblocklabel(-0.837195, -1.341754)
mi_selectlabel(-0.837195, -1.341754)
mi_setblockprop("18 AWG", 0, 0.05, "i4", 0, 0, -80)
mi_clearselected()

-- Iron blocks: rotor (inner, r=0.6..1.0 in) and stator yoke (outer, r≈2.0 in)
mi_addblocklabel(0.287013, 0.69291)
mi_selectlabel(0.287013, 0.69291)
mi_setblockprop("M-19 Steel", 0, 0.04999999, "<None>", 0, 0, 0)
mi_clearselected()

mi_addblocklabel(0.765367, 1.847759)
mi_selectlabel(0.765367, 1.847759)
mi_setblockprop("M-19 Steel", 0, 0.04999999, "<None>", 0, 0, 0)
mi_clearselected()

-- Air blocks: bore interior (shaft) and outer domain
mi_addblocklabel(0.0, 0.0)
mi_selectlabel(0.0, 0.0)
mi_setblockprop("Air", 0, 0.04999999, "<None>", 0, 0, 0)
mi_clearselected()

mi_addblocklabel(1.362606, 1.329777)
mi_selectlabel(1.362606, 1.329777)
mi_setblockprop("Air", 0, 0.05, "<None>", 0, 0, 0)
mi_clearselected()

-- ── Solve ─────────────────────────────────────────────────────────────────
mi_saveas(outdir .. "\\sim.fem")
mi_analyze(1)
mi_loadsolution()

-- ── Circuit properties ────────────────────────────────────────────────────
-- Note: avoid variable name "I" — it is FEMM's imaginary unit constant
I1, V1, lam1 = mo_getcircuitproperties("i1")
I2, V2, lam2 = mo_getcircuitproperties("i2")
I3, V3, lam3 = mo_getcircuitproperties("i3")
I4, V4, lam4 = mo_getcircuitproperties("i4")

-- Inductance = flux linkage / current (only valid when I != 0)
L1_mH = lam1 / I1 * 1000
L2_mH = lam2 / I2 * 1000
L3_mH = lam3 / I3 * 1000

-- ── Point values at air gap centres ──────────────────────────────────────
-- Air gap spans r = 1.0 in (rotor) to r ≈ 1.04 in (stator bore).
-- Sample at r = 1.02 in at each pole centre angle.
--   mo_getpointvalues returns: A, Bx, By, Sig, E, Hx, Hy

A_r, Bx_r, By_r, sig_r, E_r, Hx_r, Hy_r = mo_getpointvalues( 1.02,  0)
A_t, Bx_t, By_t, sig_t, E_t, Hx_t, Hy_t = mo_getpointvalues( 0,     1.02)
A_l, Bx_l, By_l, sig_l, E_l, Hx_l, Hy_l = mo_getpointvalues(-1.02,  0)
A_b, Bx_b, By_b, sig_b, E_b, Hx_b, Hy_b = mo_getpointvalues( 0,    -1.02)

-- Radial (outward) component of B at each pole centre
Br_right  =  Bx_r
Br_top    =  By_t
Br_left   = -Bx_l
Br_bottom = -By_b

-- ── Flux density inside rotor iron ───────────────────────────────────────
-- Block label at (0.287013, 0.69291), r≈0.75 in, in rotor iron body
A_rotor, Bx_rotor, By_rotor = mo_getpointvalues(0.287013, 0.69291)
B_rotor = sqrt(Bx_rotor^2 + By_rotor^2)

-- ── Write structured key=value results ───────────────────────────────────
writeto(outdir .. "\\results.txt")

write("I1_A="     .. format("%.10f\n", I1))
write("V1_V="     .. format("%.10f\n", V1))
write("lam1_Wb="  .. format("%.10f\n", lam1))
write("L1_mH="    .. format("%.10f\n", L1_mH))

write("I2_A="     .. format("%.10f\n", I2))
write("V2_V="     .. format("%.10f\n", V2))
write("lam2_Wb="  .. format("%.10f\n", lam2))
write("L2_mH="    .. format("%.10f\n", L2_mH))

write("I3_A="     .. format("%.10f\n", I3))
write("V3_V="     .. format("%.10f\n", V3))
write("lam3_Wb="  .. format("%.10f\n", lam3))
write("L3_mH="    .. format("%.10f\n", L3_mH))

write("I4_A="     .. format("%.10f\n", I4))
write("V4_V="     .. format("%.10f\n", V4))
write("lam4_Wb="  .. format("%.10f\n", lam4))

write("Bx_right_T="  .. format("%.10f\n", Bx_r))
write("By_right_T="  .. format("%.10f\n", By_r))
write("Bx_top_T="    .. format("%.10f\n", Bx_t))
write("By_top_T="    .. format("%.10f\n", By_t))
write("Bx_left_T="   .. format("%.10f\n", Bx_l))
write("By_left_T="   .. format("%.10f\n", By_l))
write("Bx_bottom_T=" .. format("%.10f\n", Bx_b))
write("By_bottom_T=" .. format("%.10f\n", By_b))

write("Br_right_T="  .. format("%.10f\n", Br_right))
write("Br_top_T="    .. format("%.10f\n", Br_top))
write("Br_left_T="   .. format("%.10f\n", Br_left))
write("Br_bottom_T=" .. format("%.10f\n", Br_bottom))

write("B_rotor_T="   .. format("%.10f\n", B_rotor))

writeto()

if interactive ~= "1" then
    mo_close()
    quit()
end
