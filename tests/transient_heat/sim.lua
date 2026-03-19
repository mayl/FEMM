-- tests/transient_heat/sim.lua
-- Transient heat conduction in a 2024-T6 Aluminum cylinder.
-- Ref: https://www.femm.info/wiki/TransientHeat
--
-- 4" diameter x 4" tall cylinder (axisymmetric).
-- Initial condition: uniform 300 K.
-- At t=0, all external boundaries stepped to 400 K.
-- 20 time steps of 1 second each (implicit Euler).
--
-- Accepts /lua-var=outdir=Z:\path\to\outputdir
-- Writes:
--   outdir/T0.feh .. T20.feh  -- problem files for each step
--   outdir/T0.anh .. T20.anh  -- solution files
--   outdir/results.txt        -- key=value scalar results for test runner

if outdir == nil then outdir = "z:\\tmp\\femm_test_transient_heat" end
if interactive == nil then interactive = "0" end

-- Helper for file paths
function fp(name) return outdir .. "\\" .. name end

-- ── Create heat flow document ───────────────────────────────────────
newdocument(2)

-- Material: 2024-T6 Aluminum
-- k  = 177 W/(m*K)          thermal conductivity
-- kt = rho*cp = 2780 * 875  = 2,432,500 J/(m^3*K) = 2.4325 MJ/(m^3*K)
hi_addmaterial("2024-T6", 177, 177, 0, 2.4325)

-- Boundary conditions
hi_addboundprop("T300", 0, 300, 0, 0, 0, 0)
hi_addboundprop("T400", 0, 400, 0, 0, 0, 0)

-- ── Geometry ────────────────────────────────────────────────────────
-- 4" diameter x 4" tall cylinder, axisymmetric cross-section:
-- r = 0..2 in, z = 0..4 in
hi_addnode(0, 0)
hi_addnode(2, 0)
hi_addnode(2, 4)
hi_addnode(0, 4)

hi_addsegment(0, 0, 2, 0)   -- bottom
hi_addsegment(2, 0, 2, 4)   -- outer surface
hi_addsegment(2, 4, 0, 4)   -- top
hi_addsegment(0, 4, 0, 0)   -- axis of symmetry (no BC needed)

-- Apply T300 boundary to external surfaces (bottom, outer, top).
-- Axis of symmetry (left edge) has no BC => natural insulation.
hi_selectsegment(1, 0)    -- bottom
hi_selectsegment(2, 2)    -- outer surface
hi_selectsegment(1, 4)    -- top
hi_setsegmentprop("T300", 0, 1, 0, 0, "<None>")
hi_clearselected()

-- Block label
hi_addblocklabel(1, 2)
hi_selectlabel(1, 2)
hi_setblockprop("2024-T6", 0, 0.1, 0)
hi_clearselected()

-- Problem definition: steady-state, axisymmetric, inches
hi_probdef("inches", "axi", 1e-8, 1, 30)

-- ── Step 0: steady-state at 300 K (initial condition) ───────────────
hi_saveas(fp("T0.feh"))
hi_analyze(1)

-- ── Change boundary to 400 K for transient steps ───────────────────
hi_selectsegment(1, 0)    -- bottom
hi_selectsegment(2, 2)    -- outer surface
hi_selectsegment(1, 4)    -- top
hi_setsegmentprop("T400", 0, 1, 0, 0, "<None>")
hi_clearselected()

-- ── Transient loop: 20 steps x 1 second ────────────────────────────
-- Collect results at t = 5, 10, 15, 20 s
T_center = {}
T_midrad = {}
T_avg_block = {}

for n = 1, 20 do
    hi_probdef("inches", "axi", 1e-8, 1, 30, fp("T" .. (n-1) .. ".anh"), 1)
    hi_saveas(fp("T" .. n .. ".feh"))
    hi_analyze(1)

    -- Load solution for every step: save BMP frame for animation
    hi_loadsolution()

    -- Temperature density plot: 300-400 K colour scale
    ho_showdensityplot(1, 0, 0, 400, 300)
    ho_savebitmap(fp("T" .. n .. ".bmp"))

    if n == 5 or n == 10 or n == 15 or n == 20 then
        -- Temperature at centre of cylinder (r=0, z=2)
        T_c, Fx_c, Fy_c, Gx_c, Gy_c, kx_c, ky_c = ho_getpointvalues(0, 2)
        T_center[n] = T_c

        -- Temperature at mid-radius (r=1, z=2)
        T_m, Fx_m, Fy_m, Gx_m, Gy_m, kx_m, ky_m = ho_getpointvalues(1, 2)
        T_midrad[n] = T_m

        -- Average temperature over the whole block
        ho_selectblock(1, 2)
        T_avg_block[n] = ho_blockintegral(0)
        ho_clearblock()
    end

    ho_close()
end

-- ── Final step (t=20): extra extraction points ──────────────────────
-- Reopen the final solution for additional measurements
hi_loadsolution()

-- Near-surface temperature (r=1.8, z=2)
T_near_surf, Fx_ns, Fy_ns = ho_getpointvalues(1.8, 2)

-- Quarter-height centre (r=0, z=1)
T_quarter, Fx_q, Fy_q = ho_getpointvalues(0, 1)

-- Heat flux at mid-radius (r=1, z=2)
T_tmp, Fx_mid, Fy_mid, Gx_mid, Gy_mid = ho_getpointvalues(1, 2)

-- ── Write structured key=value results ──────────────────────────────
writeto(fp("results.txt"))

-- Temperatures at centre (r=0, z=2) at various times
write("T_center_5s_K="  .. format("%.10f\n", T_center[5]))
write("T_center_10s_K=" .. format("%.10f\n", T_center[10]))
write("T_center_15s_K=" .. format("%.10f\n", T_center[15]))
write("T_center_20s_K=" .. format("%.10f\n", T_center[20]))

-- Temperatures at mid-radius (r=1, z=2) at various times
write("T_midrad_5s_K="  .. format("%.10f\n", T_midrad[5]))
write("T_midrad_10s_K=" .. format("%.10f\n", T_midrad[10]))
write("T_midrad_15s_K=" .. format("%.10f\n", T_midrad[15]))
write("T_midrad_20s_K=" .. format("%.10f\n", T_midrad[20]))

-- Average temperature over block at various times
write("T_avg_5s_K="  .. format("%.10f\n", T_avg_block[5]))
write("T_avg_10s_K=" .. format("%.10f\n", T_avg_block[10]))
write("T_avg_15s_K=" .. format("%.10f\n", T_avg_block[15]))
write("T_avg_20s_K=" .. format("%.10f\n", T_avg_block[20]))

-- Additional point values at t=20s
write("T_near_surf_20s_K=" .. format("%.10f\n", T_near_surf))
write("T_quarter_20s_K="   .. format("%.10f\n", T_quarter))

-- Heat flux components at mid-radius at t=20s (W/m^2)
write("Fx_midrad_20s="     .. format("%.10e\n", Fx_mid))
write("Fy_midrad_20s="     .. format("%.10e\n", Fy_mid))

-- Temperature gradient at mid-radius at t=20s (K/m)
write("Gx_midrad_20s="     .. format("%.10e\n", Gx_mid))

writeto()

if interactive ~= "1" then
    ho_close()
    quit()
end
