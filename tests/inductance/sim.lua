-- tests/inductance/sim.lua
-- Gapped EI-core inductance regression simulation.
-- Ref: https://www.femm.info/wiki/InductanceExample
--
-- Accepts /lua-var=outdir=Z:\path\to\outputdir
-- (FEMM lowercases all /lua-var values, so outdir must be a lowercase path)
-- Writes:
--   outdir/sim.fem        — problem definition
--   outdir/sim.ans        — solution (created automatically by FEMM)
--   outdir/results.txt    — key=value scalar results for test runner

if outdir == nil then outdir = "z:\\tmp\\femm_test_inductance" end

newdocument(0)
mi_probdef(0, "inches", "planar", 1e-8, 1, 30)

-- Materials
mi_addmaterial("Core Iron", 2500, 2500, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0)
mi_addmaterial("Air", 1, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0)
mi_addmaterial("18 AWG", 1, 1, 0, 0, 58, 0, 0, 1, 3, 0, 0, 1, 1.0239652968433499)

mi_addboundprop("A=0", 0, 0, 0, 0, 0, 0, 0, 0, 0)
mi_addcircprop("icoil", 1, 1)

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

-- I core
mi_drawline(-0.75, -0.025,  0.75, -0.025)
mi_drawline( 0.75, -0.025,  0.75, -0.275)
mi_drawline( 0.75, -0.275, -0.75, -0.275)
mi_drawline(-0.75, -0.275, -0.75, -0.025)

-- Boundary conditions
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

-- Solve
mi_saveas(outdir .. "\\sim.fem")
mi_analyze(1)
mi_loadsolution()

-- ── Circuit properties ────────────────────────────────────────────────────
-- Note: avoid "I" — it is FEMM's imaginary unit constant
Icoil, Vcoil, lambda = mo_getcircuitproperties("icoil")
L_flux = lambda / Icoil

-- ── Energy integral ───────────────────────────────────────────────────────
mo_clearblock()
mo_selectblock(    0,  0.5)
mo_selectblock(    0, -0.125)
mo_selectblock(-0.375, 0.25)
mo_selectblock( 0.375, 0.25)
mo_selectblock(    0,  1)
W = mo_blockintegral(2)
L_energy = 2 * W / (Icoil * Icoil)

-- ── Point values at key locations ─────────────────────────────────────────
-- mo_getpointvalues returns: A, B1(x), B2(y), Sig, E, H1(x), H2(y), Je, Js, Mu1, Mu2, Pe, Ph

-- Center of air gap (midpoint between E bottom y=0 and I top y=-0.025)
A_gap, Bx_gap, By_gap, sig_gap, E_gap, Hx_gap, Hy_gap = mo_getpointvalues(0, -0.0125)

-- Center of center pole (midpoint of pole: x=0, y=0 to 0.5)
A_pole, Bx_pole, By_pole, sig_pole, E_pole, Hx_pole, Hy_pole = mo_getpointvalues(0, 0.25)

-- Center of top yoke (above coil windows: x=0, y=0.625)
A_yoke, Bx_yoke, By_yoke, sig_yoke, E_yoke, Hx_yoke, Hy_yoke = mo_getpointvalues(0, 0.625)

-- Center of I core
A_icore, Bx_icore, By_icore, sig_ic, E_ic, Hx_icore, Hy_icore = mo_getpointvalues(0, -0.15)

-- ── Write structured key=value results ───────────────────────────────────
writeto(outdir .. "\\results.txt")

-- Circuit / inductance
write("Icoil_A="     .. format("%.10f\n", Icoil))
write("Vcoil_V="     .. format("%.10f\n", Vcoil))
write("lambda_Wb="   .. format("%.10f\n", lambda))
write("L_flux_mH="   .. format("%.10f\n", L_flux   * 1000))
write("W_J="         .. format("%.10e\n", W))
write("L_energy_mH=" .. format("%.10f\n", L_energy * 1000))

-- Point values: air gap center (0, -0.0125)
write("A_gap_Wbm="   .. format("%.10e\n", A_gap))
write("By_gap_T="    .. format("%.10f\n", By_gap))
write("Hy_gap_Am="   .. format("%.10f\n", Hy_gap))

-- Point values: center pole center (0, 0.25)
write("A_pole_Wbm="  .. format("%.10e\n", A_pole))
write("By_pole_T="   .. format("%.10f\n", By_pole))
write("Hy_pole_Am="  .. format("%.10f\n", Hy_pole))

-- Point values: top yoke center (0, 0.625)
write("By_yoke_T="   .. format("%.10f\n", By_yoke))
write("Hy_yoke_Am="  .. format("%.10f\n", Hy_yoke))

-- Point values: I core center (0, -0.15)
write("By_icore_T="  .. format("%.10f\n", By_icore))
write("Hy_icore_Am=" .. format("%.10f\n", Hy_icore))

writeto()

mo_close()
quit()
