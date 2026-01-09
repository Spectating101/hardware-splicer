//! Circuit-AI Physics (Rust)
//!
//! Goal: a std-only, deterministic DC solver core (MNA) that we can later
//! integrate into Python (FFI/PyO3) when desired.
//!
//! Supported elements:
//! - Resistors
//! - Independent current sources
//! - Independent voltage sources

use std::collections::HashMap;

mod ffi;
mod op;

#[derive(Debug, Clone)]
pub struct Resistor {
    pub name: String,
    pub n1: String,
    pub n2: String,
    pub ohms: f64,
}

#[derive(Debug, Clone)]
pub struct CurrentSource {
    pub name: String,
    pub n_plus: String,
    pub n_minus: String,
    pub amps: f64,
}

#[derive(Debug, Clone)]
pub struct VoltageSource {
    pub name: String,
    pub n_plus: String,
    pub n_minus: String,
    pub volts: f64,
}

#[derive(Debug, Clone)]
pub struct Circuit {
    pub resistors: Vec<Resistor>,
    pub current_sources: Vec<CurrentSource>,
    pub voltage_sources: Vec<VoltageSource>,
    pub ground: String,
}

impl Default for Circuit {
    fn default() -> Self {
        Self {
            resistors: vec![],
            current_sources: vec![],
            voltage_sources: vec![],
            ground: "0".to_string(),
        }
    }
}

#[derive(Debug, Clone)]
pub struct Solution {
    pub node_v: HashMap<String, f64>,
    pub vsource_i: HashMap<String, f64>,
}

#[derive(Debug)]
pub enum SolveError {
    Singular,
    InvalidElement(String),
}

fn is_ground(n: &str) -> bool {
    matches!(n.trim().to_uppercase().as_str(), "0" | "GND" | "GROUND")
}

fn normalize(n: &str) -> String {
    if is_ground(n) {
        "0".to_string()
    } else {
        n.trim().to_string()
    }
}

fn gaussian_solve(mut a: Vec<Vec<f64>>, mut b: Vec<f64>) -> Result<Vec<f64>, SolveError> {
    let n = b.len();
    for row in &a {
        if row.len() != n {
            return Err(SolveError::Singular);
        }
    }

    for col in 0..n {
        // pivot
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
            return Err(SolveError::Singular);
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

    // back-sub
    let mut x = vec![0.0; n];
    for i in (0..n).rev() {
        let mut sum = 0.0;
        for j in (i + 1)..n {
            sum += a[i][j] * x[j];
        }
        x[i] = b[i] - sum;
    }
    Ok(x)
}

pub fn solve_dc(circuit: &Circuit) -> Result<Solution, SolveError> {
    let gnd = normalize(&circuit.ground);

    // collect nodes
    let mut nodes: Vec<String> = vec!["0".to_string()];
    let mut push_node = |n: &str| {
        let nn = normalize(n);
        if !nodes.contains(&nn) {
            nodes.push(nn);
        }
    };

    for r in &circuit.resistors {
        push_node(&r.n1);
        push_node(&r.n2);
    }
    for i in &circuit.current_sources {
        push_node(&i.n_plus);
        push_node(&i.n_minus);
    }
    for v in &circuit.voltage_sources {
        push_node(&v.n_plus);
        push_node(&v.n_minus);
    }

    // unknown node voltages exclude ground
    let node_list: Vec<String> = nodes.into_iter().filter(|n| n != &gnd).collect();
    let n = node_list.len();
    let m = circuit.voltage_sources.len();
    let size = n + m;

    let mut node_index: HashMap<String, usize> = HashMap::new();
    for (i, name) in node_list.iter().enumerate() {
        node_index.insert(name.clone(), i);
    }

    let mut a = vec![vec![0.0; size]; size];
    let mut z = vec![0.0; size];

    let idx = |node: &str, map: &HashMap<String, usize>| -> usize { map[node] };

    // resistors
    for r in &circuit.resistors {
        if r.ohms <= 0.0 {
            return Err(SolveError::InvalidElement(r.name.clone()));
        }
        let n1 = normalize(&r.n1);
        let n2 = normalize(&r.n2);
        let g = 1.0 / r.ohms;

        if n1 != gnd {
            let i1 = idx(&n1, &node_index);
            a[i1][i1] += g;
        }
        if n2 != gnd {
            let i2 = idx(&n2, &node_index);
            a[i2][i2] += g;
        }
        if n1 != gnd && n2 != gnd {
            let i1 = idx(&n1, &node_index);
            let i2 = idx(&n2, &node_index);
            a[i1][i2] -= g;
            a[i2][i1] -= g;
        }
    }

    // current sources: inject +I into n_minus, -I into n_plus
    for cs in &circuit.current_sources {
        let p = normalize(&cs.n_plus);
        let nnode = normalize(&cs.n_minus);
        let i = cs.amps;
        if p != gnd {
            z[idx(&p, &node_index)] -= i;
        }
        if nnode != gnd {
            z[idx(&nnode, &node_index)] += i;
        }
    }

    // voltage sources
    for (k, vs) in circuit.voltage_sources.iter().enumerate() {
        let p = normalize(&vs.n_plus);
        let nnode = normalize(&vs.n_minus);
        let row = n + k;

        if p != gnd {
            let ip = idx(&p, &node_index);
            a[ip][row] += 1.0;
            a[row][ip] += 1.0;
        }
        if nnode != gnd {
            let inx = idx(&nnode, &node_index);
            a[inx][row] -= 1.0;
            a[row][inx] -= 1.0;
        }

        z[row] = vs.volts;
    }

    let x = gaussian_solve(a, z)?;

    let mut node_v: HashMap<String, f64> = HashMap::new();
    node_v.insert(gnd.clone(), 0.0);
    for (name, i) in &node_index {
        node_v.insert(name.clone(), x[*i]);
    }

    let mut vsource_i: HashMap<String, f64> = HashMap::new();
    for (k, vs) in circuit.voltage_sources.iter().enumerate() {
        vsource_i.insert(vs.name.clone(), x[n + k]);
    }

    Ok(Solution { node_v, vsource_i })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn voltage_divider_half() {
        let mut c = Circuit::default();
        c.voltage_sources.push(VoltageSource {
            name: "V1".into(),
            n_plus: "VIN".into(),
            n_minus: "0".into(),
            volts: 10.0,
        });
        c.resistors.push(Resistor {
            name: "R1".into(),
            n1: "VIN".into(),
            n2: "VOUT".into(),
            ohms: 1000.0,
        });
        c.resistors.push(Resistor {
            name: "R2".into(),
            n1: "VOUT".into(),
            n2: "0".into(),
            ohms: 1000.0,
        });

        let sol = solve_dc(&c).unwrap();
        let vout = sol.node_v.get("VOUT").copied().unwrap_or(0.0);
        assert!((vout - 5.0).abs() < 1e-9);
    }

    #[test]
    fn current_source_into_resistor() {
        let mut c = Circuit::default();
        c.current_sources.push(CurrentSource {
            name: "I1".into(),
            n_plus: "0".into(),
            n_minus: "N".into(),
            amps: 0.001,
        });
        c.resistors.push(Resistor {
            name: "R".into(),
            n1: "N".into(),
            n2: "0".into(),
            ohms: 1000.0,
        });

        let sol = solve_dc(&c).unwrap();
        let v = sol.node_v.get("N").copied().unwrap_or(0.0);
        assert!((v - 1.0).abs() < 1e-9);
    }

    #[test]
    fn singular_circuit_errors() {
        let mut c = Circuit::default();
        c.voltage_sources.push(VoltageSource {
            name: "V1".into(),
            n_plus: "A".into(),
            n_minus: "B".into(),
            volts: 1.0,
        });

        match solve_dc(&c) {
            Err(SolveError::Singular) => {}
            other => panic!("expected singular error, got: {:?}", other),
        }
    }
}

