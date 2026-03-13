-- tests/ac_force/sim.lua
-- EI-core AC force regression simulation.
-- Ref: https://www.femm.info/wiki/ACForceExample
--
-- Runs two solves on the same geometry:
--   1) DC (0 Hz, 1 A)  — static force on I-core
--   2) AC (60 Hz, 1 A peak) — time-averaged and 2ω force components
--
-- Accepts /lua-var=outdir=Z:\path\to\outputdir
-- (FEMM lowercases all /lua-var values, so outdir must be a lowercase path)
-- Optionally /lua-var=interactive=1 to skip quit() and leave the window open.
-- Writes:
--   outdir/sim_dc.fem      — DC problem definition
--   outdir/sim_dc.ans      — DC solution
--   outdir/sim.fem         — AC problem definition  (runner checks sim.ans)
--   outdir/sim.ans         — AC solution
--   outdir/results.txt     — key=value scalar results for test runner

if outdir == nil then outdir = "z:\\tmp\\femm_test_ac_force" end
if interactive == nil then interactive = "0" end

-- ── Geometry builder ───────────────────────────────────────────────────────
-- Identical EI-core geometry for both DC and AC solves; only freq differs.

function build_geometry(freq)
    newdocument(0)
    mi_probdef(freq, "inches", "planar", 1e-8, 1, 30)

    -- Materials
    mi_addmaterial("Core Iron", 2500, 2500, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0)
    mi_addmaterial("Air", 1, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0)
    mi_addmaterial("18 AWG", 1, 1, 0, 0, 58, 0, 0, 1, 3, 0, 0, 1, 1.0239652968433499)

    mi_addboundprop("A=0", 0, 0, 0, 0, 0, 0, 0, 0, 0)
    mi_addcircprop("icoil", 1, 1)  -- 1 A total (DC or peak for AC)

    -- Domain boundary
    mi_drawline(-1.25, -0.75, -1.25,  1.25)
    mi_drawline(-1.25,  1.25,  1.25,  1.25)
    mi_drawline( 1.25,  1.25,  1.25, -0.75)
    mi_drawline( 1.25, -0.75, -1.25, -0.75)

    -- E core outer boundary
    mi_drawline(-0.75,  0,    -0.75,  0.75)
    mi_drawline(-0.75,  0.75,  0.75,  0.75)
    mi_drawline( 0.75,  0.75,  0.75,  0)

    -- E core bottom (5 segments along y=0)
    mi_drawline(-0.75,  0,    -0.5,   0)
    mi_drawline(-0.5,   0,    -0.25,  0)
    mi_drawline(-0.25,  0,     0.25,  0)
    mi_drawline( 0.25,  0,     0.5,   0)
    mi_drawline( 0.5,   0,     0.75,  0)

    -- Left coil window
    mi_drawline(-0.5,   0,    -0.5,   0.5)
    mi_drawline(-0.5,   0.5,  -0.25,  0.5)
    mi_drawline(-0.25,  0,    -0.25,  0.5)

    -- Right coil window
    mi_drawline( 0.25,  0,     0.25,  0.5)
    mi_drawline( 0.25,  0.5,   0.5,   0.5)
    mi_drawline( 0.5,   0.5,   0.5,   0)

    -- I core (gap = 0.025" below E core)
    mi_drawline(-0.75, -0.025,  0.75, -0.025)
    mi_drawline( 0.75, -0.025,  0.75, -0.275)
    mi_drawline( 0.75, -0.275, -0.75, -0.275)
    mi_drawline(-0.75, -0.275, -0.75, -0.025)

    -- Boundary conditions on outer edges
    mi_selectsegment(-1.25,  0.25)
    mi_selectsegment(    0,  1.25)
    mi_selectsegment( 1.25,  0.25)
    mi_selectsegment(    0, -0.75)
    mi_setsegmentprop("A=0", 0, 1, 0, 0)
    mi_clearselected()

    -- Block labels
    mi_addblocklabel(0, 0.5)
    mi_selectlabel(0, 0.5)
    mi_setblockprop("Core Iron", 0, 0.05, "", 0, 0, 0)
    mi_clearselected()

    mi_addblocklabel(0, -0.125)
    mi_selectlabel(0, -0.125)
    mi_setblockprop("Core Iron", 0, 0.05, "", 0, 0, 0)
    mi_clearselected()

    mi_addblocklabel(-0.375, 0.25)
    mi_selectlabel(-0.375, 0.25)
    mi_setblockprop("18 AWG", 0, 0.05, "icoil", 0, 0, 66)
    mi_clearselected()

    mi_addblocklabel(0.375, 0.25)
    mi_selectlabel(0.375, 0.25)
    mi_setblockprop("18 AWG", 0, 0.05, "icoil", 0, 0, -66)
    mi_clearselected()

    mi_addblocklabel(0, 1)
    mi_selectlabel(0, 1)
    mi_setblockprop("Air", 0, 0.05, "", 0, 0, 0)
    mi_clearselected()
end

-- ── DC solve (0 Hz) ────────────────────────────────────────────────────────
build_geometry(0)
mi_saveas(outdir .. "\\sim_dc.fem")
mi_analyze(1)
mi_loadsolution()

-- Select I-core block (label at 0, -0.125; block spans y=-0.275 to -0.025)
mo_clearblock()
mo_selectblock(0, -0.125)
Fy_dc = mo_blockintegral(19)   -- y-direction MST force [N], real for DC
mo_clearblock()
mo_close()
mi_close()

-- ── AC solve (60 Hz) ───────────────────────────────────────────────────────
-- Save as sim.fem so runner can find sim.ans.
build_geometry(60)
mi_saveas(outdir .. "\\sim.fem")
mi_analyze(1)
mi_loadsolution()

-- Force on I-core: mo_blockintegral(19) returns a single real value in AC mode
-- (the time-averaged force). There is no second return value for the 2ω component.
mo_clearblock()
mo_selectblock(0, -0.125)
Fy_ac_dc_comp = mo_blockintegral(19)
mo_clearblock()

-- ── Write results ──────────────────────────────────────────────────────────
writeto(outdir .. "\\results.txt")

write("Fy_dc_N="    .. format("%.10f\n", Fy_dc))
write("Fy_ac_dc_N=" .. format("%.10f\n", Fy_ac_dc_comp))

writeto()

if interactive ~= "1" then
  mo_close()
  quit()
end
