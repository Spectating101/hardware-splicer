use crate::ffi::{CCurrentLoad, CCurrentSource, CLdo, CPowerLoad, CResistor, CVoltageSource};

#[derive(Clone)]
pub struct OpSettings {
    pub max_iters: u32,
    pub tol_v: f64,
    pub tol_a: f64,
    pub damping_v: f64,
    pub damping_i: f64,
}

fn gaussian_solve(mut a: Vec<Vec<f64>>, mut b: Vec<f64>) -> Option<Vec<f64>> {
    let n = b.len();
    for row in &a {
        if row.len() != n {
            return None;
        }
    }

    for col in 0..n {
        let mut pivot = col;
        let mut best = a[col][col].abs();
        for r in (col + 1)..n {
            let v = a[r][col].abs();
            if v > best {
                best = v;
                pivot = r;
            }
        }
        if best < 1e-14 {
            return None;
        }
        if pivot != col {
            a.swap(col, pivot);
            b.swap(col, pivot);
        }

        let piv = a[col][col];
        for j in col..n {
            a[col][j] /= piv;
        }
        b[col] /= piv;

        for r in (col + 1)..n {
            let factor = a[r][col];
            if factor == 0.0 {
                continue;
            }
            for j in col..n {
                a[r][j] -= factor * a[col][j];
            }
            b[r] -= factor * b[col];
        }
    }

    let mut x = vec![0.0; n];
    for i in (0..n).rev() {
        let mut sum = 0.0;
        for j in (i + 1)..n {
            sum += a[i][j] * x[j];
        }
        x[i] = b[i] - sum;
    }
    Some(x)
}

fn solve_dc_numeric(
    num_nodes: u32,
    ground: u32,
    resistors: &[CResistor],
    current_sources: &[CCurrentSource],
    voltage_sources: &[CVoltageSource],
) -> Option<(Vec<f64>, Vec<f64>)> {
    let n_nodes = num_nodes as usize;
    let g = ground as usize;

    // unknown voltages exclude ground
    let mut map = vec![usize::MAX; n_nodes];
    let mut rev: Vec<usize> = vec![];
    let mut idx = 0usize;
    for node in 0..n_nodes {
        if node == g {
            continue;
        }
        map[node] = idx;
        rev.push(node);
        idx += 1;
    }

    let n = rev.len();
    let m = voltage_sources.len();
    let size = n + m;

    let mut a = vec![vec![0.0; size]; size];
    let mut z = vec![0.0; size];

    // resistors
    for r in resistors {
        if r.ohms <= 0.0 {
            return None;
        }
        let n1 = r.n1 as usize;
        let n2 = r.n2 as usize;
        let gval = 1.0 / r.ohms;

        if n1 != g {
            let i1 = map[n1];
            a[i1][i1] += gval;
        }
        if n2 != g {
            let i2 = map[n2];
            a[i2][i2] += gval;
        }
        if n1 != g && n2 != g {
            let i1 = map[n1];
            let i2 = map[n2];
            a[i1][i2] -= gval;
            a[i2][i1] -= gval;
        }
    }

    // current sources: inject +I into n_minus, -I into n_plus
    for cs in current_sources {
        let p = cs.n_plus as usize;
        let nnode = cs.n_minus as usize;
        let i = cs.amps;
        if p != g {
            z[map[p]] -= i;
        }
        if nnode != g {
            z[map[nnode]] += i;
        }
    }

    // voltage sources
    for (k, vs) in voltage_sources.iter().enumerate() {
        let p = vs.n_plus as usize;
        let nnode = vs.n_minus as usize;
        let row = n + k;

        if p != g {
            let ip = map[p];
            a[ip][row] += 1.0;
            a[row][ip] += 1.0;
        }
        if nnode != g {
            let inx = map[nnode];
            a[inx][row] -= 1.0;
            a[row][inx] -= 1.0;
        }

        z[row] = vs.volts;
    }

    let x = gaussian_solve(a, z)?;

    let mut node_v = vec![0.0; n_nodes];
    node_v[g] = 0.0;
    for (u_idx, node) in rev.iter().enumerate() {
        node_v[*node] = x[u_idx];
    }

    let mut v_i = vec![0.0; m];
    for k in 0..m {
        v_i[k] = x[n + k];
    }

    Some((node_v, v_i))
}

pub fn solve_operating_point_numeric(
    num_nodes: u32,
    ground: u32,
    resistors: &[CResistor],
    base_isources: &[CCurrentSource],
    base_vsources: &[CVoltageSource],
    ldos: &[CLdo],
    loads_cc: &[CCurrentLoad],
    loads_cp: &[CPowerLoad],
    settings: OpSettings,
) -> Option<(Vec<f64>, Vec<f64>, bool, u32, f64, f64)> {
    let n_nodes = num_nodes as usize;
    let g = ground;

    let mut vout_set: Vec<f64> = ldos.iter().map(|l| l.vout_nom_v).collect();
    let mut iin_set: Vec<f64> = vec![0.0; ldos.len()];

    let mut prev_node_v: Option<Vec<f64>> = None;
    let mut converged = false;

    let mut last_max_dv = f64::INFINITY;
    let mut last_max_di = f64::INFINITY;

    let mut final_node_v = vec![0.0; n_nodes];
    let mut final_vsrc_i: Vec<f64> = vec![];

    for it in 1..=settings.max_iters {
        // Build current sources for this iteration
        let mut isources: Vec<CCurrentSource> = Vec::new();
        isources.extend_from_slice(base_isources);

        // CC loads (with optional brownout cutoff)
        for l in loads_cc {
            let mut amps = l.amps.max(0.0);
            if l.min_v_off.is_finite() {
                if let Some(ref pv) = prev_node_v {
                    let v = pv[l.node as usize] - pv[l.gnd as usize];
                    if v < l.min_v_off {
                        amps = 0.0;
                    }
                }
            }
            isources.push(CCurrentSource { n_plus: l.node, n_minus: l.gnd, amps });
        }

        // CP loads converted to current based on prev solution
        for pl in loads_cp {
            let node = pl.node as usize;
            let gnd = pl.gnd as usize;
            let mut watts = pl.watts.max(0.0);

            let mut v = if let Some(ref pv) = prev_node_v {
                pv[node] - pv[gnd]
            } else {
                1.0
            };

            if pl.min_v_off.is_finite() {
                if let Some(ref pv) = prev_node_v {
                    let vv = pv[node] - pv[gnd];
                    if vv < pl.min_v_off {
                        watts = 0.0;
                    }
                }
            }

            v = v.max(pl.v_min.max(1e-12));
            let mut amps = if v > 0.0 { watts / v } else { 0.0 };
            if pl.max_amps.is_finite() {
                amps = amps.min(pl.max_amps);
            }

            isources.push(CCurrentSource {
                n_plus: pl.node,
                n_minus: pl.gnd,
                amps,
            });
        }

        // LDO input current draws
        for (k, ldo) in ldos.iter().enumerate() {
            let iin = iin_set[k].max(0.0);
            if iin > 0.0 {
                isources.push(CCurrentSource {
                    n_plus: ldo.vin,
                    n_minus: ldo.gnd,
                    amps: iin,
                });
            }
        }

        // Build voltage sources (base + LDO outputs)
        let mut vsources: Vec<CVoltageSource> = Vec::new();
        vsources.extend_from_slice(base_vsources);
        for (k, ldo) in ldos.iter().enumerate() {
            vsources.push(CVoltageSource {
                n_plus: ldo.vout,
                n_minus: ldo.gnd,
                volts: vout_set[k],
            });
        }

        let (node_v, v_i) = solve_dc_numeric(num_nodes, g, resistors, &isources, &vsources)?;

        // Update LDO setpoints
        let mut max_dv: f64 = 0.0;
        let mut max_di: f64 = 0.0;

        for (k, ldo) in ldos.iter().enumerate() {
            let vin_v = node_v[ldo.vin as usize] - node_v[ldo.gnd as usize];
            let vout_target = ldo.vout_nom_v.min((vin_v - ldo.dropout_v).max(0.0));

            let v_prev = vout_set[k];
            let v_new = v_prev + settings.damping_v * (vout_target - v_prev);
            vout_set[k] = v_new;
            max_dv = max_dv.max((v_new - v_prev).abs());

            // LDO output current is the current through the *corresponding* voltage source.
            // Its index is base_vsources.len() + k.
            let iout = v_i[base_vsources.len() + k].abs();
            let iin_target = iout + ldo.quiescent_current_a.max(0.0);

            let i_prev = iin_set[k];
            let i_new = i_prev + settings.damping_i * (iin_target - i_prev);
            iin_set[k] = i_new;
            max_di = max_di.max((i_new - i_prev).abs());
        }

        // Check node convergence
        let mut max_vnode: f64 = 0.0;
        if let Some(ref pv) = prev_node_v {
            for n in 0..n_nodes {
                max_vnode = max_vnode.max((node_v[n] - pv[n]).abs());
            }
        }

        last_max_dv = max_dv.max(max_vnode);
        last_max_di = max_di;

        final_node_v = node_v;
        final_vsrc_i = v_i;

        if prev_node_v.is_some() && last_max_dv < settings.tol_v && last_max_di < settings.tol_a {
            converged = true;
            return Some((final_node_v, final_vsrc_i, true, it, last_max_dv, last_max_di));
        }

        prev_node_v = Some(final_node_v.clone());
    }

    Some((final_node_v, final_vsrc_i, converged, settings.max_iters, last_max_dv, last_max_di))
}
