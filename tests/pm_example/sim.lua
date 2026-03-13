-- tests/pm_example/sim.lua
-- N42 NdFeB bar magnet regression simulation.
-- Ref: https://www.femm.info/wiki/PermanentMagnetExample
--
-- Magnet: 0.5" wide x 0.25" thick, centered at origin, magnetized in +Y.
-- Open boundary: mi_makeABC(7, 1, 0, 0, 0) — 7-shell Kelvin transform, R=1"
--
-- Accepts /lua-var=outdir=Z:\path\to\outputdir
-- (FEMM lowercases all /lua-var values, so outdir must be a lowercase path)
-- Optionally /lua-var=interactive=1 to skip quit() and leave the window open.
-- Writes:
--   outdir/sim.fem        — problem definition
--   outdir/sim.ans        — solution
--   outdir/results.txt    — key=value scalar results for test runner

if outdir == nil then outdir = "z:\\tmp\\femm_test_pm_example" end
if interactive == nil then interactive = "0" end

newdocument(0)
mi_probdef(0, "inches", "planar", 1e-8, 2, 30)

-- ── Materials ──────────────────────────────────────────────────────────────
-- N42 NdFeB: mu_r = 1.05, Hc = 1,006,582 A/m
-- mi_makeABC will add its own "u1","u2",... materials; no boundary prop needed here.
mi_addmaterial("N42", 1.05, 1.05, 1006582, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0)
mi_addmaterial("Air", 1, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0)

-- ── Magnet: 0.5" wide x 0.25" thick, centered at origin ───────────────────
-- mi_drawrectangle is a convenience wrapper defined in init.lua
mi_drawrectangle(-0.25, -0.125, 0.25, 0.125)

-- ── Block labels ───────────────────────────────────────────────────────────
-- Magnet: magnetization at 90° (+Y direction, North pole up)
mi_addblocklabel(0, 0)
mi_selectlabel(0, 0)
mi_setblockprop("N42", 0, 0.02, "", 90, 0, 0)
mi_clearselected()

-- Air: interior region surrounding the magnet, inside the ABC circle
mi_addblocklabel(0, 0.5)
mi_selectlabel(0, 0.5)
mi_setblockprop("Air", 0, 0.1, "", 0, 0, 0)
mi_clearselected()

-- ── Open boundary ──────────────────────────────────────────────────────────
-- Must be called after interior geometry is drawn.
-- n=7 shells, R=1", centered at origin, bc=0 (Dirichlet A=0 on outermost arc).
-- Internally creates concentric arc rings with Kelvin-transform materials "u1".."u7"
-- and applies A=0 on the outer arc — do NOT add a separate "A=0" boundary prop.
mi_makeABC(7, 1, 0, 0, 0)

-- ── Solve ──────────────────────────────────────────────────────────────────
mi_saveas(outdir .. "\\sim.fem")
mi_analyze(1)
mi_loadsolution()

-- ── Point values ──────────────────────────────────────────────────────────
-- mo_getpointvalues returns: A, Bx, By, Sig, E, Hx, Hy, Je, Js, Mu_x, Mu_y, Pe, Ph

-- Center of magnet
A_c, Bx_c, By_c = mo_getpointvalues(0, 0)

-- In air above top surface (0.25" above y=0.125 → y=0.375)
A_a, Bx_a, By_a = mo_getpointvalues(0, 0.375)

-- In air below bottom surface (0.25" below y=-0.125 → y=-0.375)
A_b, Bx_b, By_b = mo_getpointvalues(0, -0.375)

-- ── Energy integrals ───────────────────────────────────────────────────────
-- Energy in magnet only
mo_clearblock()
mo_selectblock(0, 0)
W_magnet = mo_blockintegral(2)
mo_clearblock()

-- Energy in air interior (inside ABC circle, outside magnet)
mo_selectblock(0, 0.5)
W_air = mo_blockintegral(2)
mo_clearblock()

-- ── Write results ──────────────────────────────────────────────────────────
writeto(outdir .. "\\results.txt")

write("By_center_T=" .. format("%.10f\n", By_c))
write("Bx_center_T=" .. format("%.10f\n", Bx_c))
write("By_above_T="  .. format("%.10f\n", By_a))
write("By_below_T="  .. format("%.10f\n", By_b))
write("W_magnet_J="  .. format("%.10e\n", W_magnet))
write("W_air_J="     .. format("%.10e\n", W_air))

writeto()

if interactive ~= "1" then
  mo_close()
  quit()
end
