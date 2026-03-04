-- =============================================================================
-- Inductance Calculation Example
-- Ref: https://www.femm.info/wiki/InductanceExample
--
-- Gapped EI-core inductor:
--   Center pole 0.5" wide, outer poles 0.25" wide, air gap 0.025"
--   66 turns of 18 AWG wire, core mu_r = 2500, depth = 1 inch
--   Applied current: 1 A (series circuit)
--
-- Expected results:
--   Magnetic circuit theory:  1.39 mH
--   FE (Flux/Current):        1.73 mH
--   FE (Energy integral):     1.73 mH
-- =============================================================================

newdocument(0)   -- new magnetics problem

-- Problem definition: DC (0 Hz), inches, 2D planar, depth=1", precision=1e-8
mi_probdef(0, "inches", "planar", 1e-8, 1, 30)

-- Materials ------------------------------------------------------------------

-- Linear ferromagnetic core, mu_r = 2500
mi_addmaterial("Core Iron", 2500, 2500, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0)
-- Free space / air
mi_addmaterial("Air", 1, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0)
-- 18 AWG copper: sigma=58 MS/m, LamType=3 (round stranded), D=1.024 mm, 1 strand
mi_addmaterial("18 AWG", 1, 1, 0, 0, 58, 0, 0, 1, 3, 0, 0, 1, 1.0239652968433499)

-- Boundary condition: A=0 (Dirichlet) on outer domain edges -----------------
mi_addboundprop("A=0", 0, 0, 0, 0, 0, 0, 0, 0, 0)

-- Circuit: series coil, 1 A total current -----------------------------------
mi_addcircprop("icoil", 1, 1)

-- Geometry -------------------------------------------------------------------
--
-- Cross-section layout (not to scale):
--
--  y= 1.25 +------------------------------+   <- domain top
--          |                              |
--  y= 0.75 |  +------------------------+ |   <- E core top yoke
--          |  |   |              |   | | |
--  y= 0.50 |  |   +----+    +----+   | | |   <- top of coil windows
--          |  |   |left|    |rght|   | | |   <- coil regions
--  y= 0    |  +---+----+----+----+---+ | |   <- E core bottom (gap face)
--          |       [   air gap   ]      | |
--  y=-0.025|  +------------------------+ |   <- I core top
--          |  |       I  core          | |
--  y=-0.275|  +------------------------+ |   <- I core bottom
--          |                              |
--  y=-0.75 +------------------------------+   <- domain bottom
--          x=-1.25                   x=1.25
--
-- E core legs:  left outer x∈[-0.75,-0.50], center x∈[-0.25, 0.25],
--               right outer x∈[0.50, 0.75]

-- Outer domain box: x ∈ [-1.25, 1.25],  y ∈ [-0.75, 1.25]
mi_drawline(-1.25, -0.75, -1.25,  1.25)
mi_drawline(-1.25,  1.25,  1.25,  1.25)
mi_drawline( 1.25,  1.25,  1.25, -0.75)
mi_drawline( 1.25, -0.75, -1.25, -0.75)

-- E core outer boundary
mi_drawline(-0.75,  0,    -0.75,  0.75)  -- left outer leg, left side
mi_drawline(-0.75,  0.75,  0.75,  0.75)  -- top yoke
mi_drawline( 0.75,  0.75,  0.75,  0)     -- right outer leg, right side

-- E core bottom face: 5 contiguous segments along y=0
--   (the two middle segments also close the coil window bottoms)
mi_drawline(-0.75,  0,    -0.5,   0)     -- below left outer leg
mi_drawline(-0.5,   0,    -0.25,  0)     -- left coil window bottom
mi_drawline(-0.25,  0,     0.25,  0)     -- center pole bottom
mi_drawline( 0.25,  0,     0.5,   0)     -- right coil window bottom
mi_drawline( 0.5,   0,     0.75,  0)     -- below right outer leg

-- Left coil window walls  (x ∈ [-0.50, -0.25],  y ∈ [0, 0.50])
mi_drawline(-0.5,   0,    -0.5,   0.5)   -- outer wall
mi_drawline(-0.5,   0.5,  -0.25,  0.5)   -- top wall
mi_drawline(-0.25,  0,    -0.25,  0.5)   -- inner wall (= center pole left face)

-- Right coil window walls  (x ∈ [0.25, 0.50],  y ∈ [0, 0.50])
mi_drawline( 0.25,  0,     0.25,  0.5)   -- inner wall (= center pole right face)
mi_drawline( 0.25,  0.5,   0.5,   0.5)   -- top wall
mi_drawline( 0.5,   0.5,   0.5,   0)     -- outer wall

-- I core (return path):  y ∈ [-0.275, -0.025],  x ∈ [-0.75, 0.75]
-- Note: no segments on the sides between y=-0.025 and y=0, so the air gap
-- is an open region connected to the surrounding air domain.
mi_drawline(-0.75, -0.025,  0.75, -0.025)  -- top face (lower edge of air gap)
mi_drawline( 0.75, -0.025,  0.75, -0.275)  -- right side
mi_drawline( 0.75, -0.275, -0.75, -0.275)  -- bottom face
mi_drawline(-0.75, -0.275, -0.75, -0.025)  -- left side

-- Apply A=0 to domain boundary (select by midpoint of each edge) ------------
mi_selectsegment(-1.25,  0.25)
mi_selectsegment(    0,  1.25)
mi_selectsegment( 1.25,  0.25)
mi_selectsegment(    0, -0.75)
mi_setsegmentprop("A=0", 0, 1, 0, 0)
mi_clearselected()

-- Block labels ---------------------------------------------------------------

-- E core (label in yoke/center-pole area; y=0.5 is solidly inside the iron)
mi_addblocklabel(0, 0.5)
mi_selectlabel(0, 0.5)
mi_setblockprop("Core Iron", 0, 0.05, "", 0, 0, 0)
mi_clearselected()

-- I core
mi_addblocklabel(0, -0.125)
mi_selectlabel(0, -0.125)
mi_setblockprop("Core Iron", 0, 0.05, "", 0, 0, 0)
mi_clearselected()

-- Left coil window: current flowing in (+66 turns)
mi_addblocklabel(-0.375, 0.25)
mi_selectlabel(-0.375, 0.25)
mi_setblockprop("18 AWG", 0, 0.05, "icoil", 0, 0, 66)
mi_clearselected()

-- Right coil window: current flowing out (-66 turns)
mi_addblocklabel(0.375, 0.25)
mi_selectlabel(0.375, 0.25)
mi_setblockprop("18 AWG", 0, 0.05, "icoil", 0, 0, -66)
mi_clearselected()

-- Surrounding air (also covers the open air gap between E and I cores)
mi_addblocklabel(0, 1)
mi_selectlabel(0, 1)
mi_setblockprop("Air", 0, 0.05, "", 0, 0, 0)
mi_clearselected()

-- Solve ----------------------------------------------------------------------
mi_saveas("induct1a.fem")
mi_analyze(1)       -- 1 = suppress progress window
mi_loadsolution()

-- Post-processing: Method 1 — Flux linkage / current ------------------------
-- Note: avoid variable name "I" — it is FEMM's built-in imaginary unit constant
Icoil, Vcoil, lambda = mo_getcircuitproperties("icoil")
L_flux = lambda / Icoil

-- Post-processing: Method 2 — Magnetic field energy integral ----------------
mo_clearblock()
mo_selectblock(    0,  0.5)    -- E core
mo_selectblock(    0, -0.125)  -- I core
mo_selectblock(-0.375, 0.25)   -- left coil
mo_selectblock( 0.375, 0.25)   -- right coil
mo_selectblock(    0,  1)      -- air (exterior + open air gap)
W = mo_blockintegral(2)        -- integral type 2 = magnetic field energy (J)
L_energy = 2 * W / (Icoil * Icoil)

-- Results --------------------------------------------------------------------
-- Note: FEMM uses Lua 4-style globals: format() not string.format()
--       writeto()/write() for file output, not io.open/io.write
--
-- Output path is configurable via /lua-var=resultfile=Z:\path\to\file.txt
-- so automated tests can redirect output to a known location.
-- FEMM lowercases all /lua-var values, so use only lowercase paths.
if resultfile == nil then resultfile = "inductance_results.txt" end
writeto(resultfile)
write(format("Magnetic circuit theory:  L = 1.3900 mH  (reference)\n"))
write(format("Method 1 (Flux/Current):  L = %.6f mH\n", L_flux   * 1000))
write(format("Method 2 (Energy):        L = %.6f mH\n", L_energy * 1000))
writeto()  -- restore stdout

mo_close()
quit()
