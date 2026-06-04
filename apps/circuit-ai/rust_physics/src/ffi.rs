use std::slice;

#[repr(C)]
#[derive(Clone, Copy)]
pub struct CResistor {
    pub n1: u32,
    pub n2: u32,
    pub ohms: f64,
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct CCurrentSource {
    pub n_plus: u32,
    pub n_minus: u32,
    pub amps: f64,
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct CCurrentLoad {
    pub node: u32,
    pub gnd: u32,
    pub amps: f64,
    pub min_v_off: f64, // use +inf if unused
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct CVoltageSource {
    pub n_plus: u32,
    pub n_minus: u32,
    pub volts: f64,
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct CLdo {
    pub vin: u32,
    pub vout: u32,
    pub gnd: u32,
    pub vout_nom_v: f64,
    pub dropout_v: f64,
    pub quiescent_current_a: f64,
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct CPowerLoad {
    pub node: u32,
    pub gnd: u32,
    pub watts: f64,
    pub v_min: f64,
    pub max_amps: f64,  // use +inf if no cap
    pub min_v_off: f64, // use +inf if unused
}

#[no_mangle]
pub extern "C" fn circuit_ai_solve_dc(
    num_nodes: u32,
    ground: u32,
    resistors: *const CResistor,
    num_resistors: u32,
    current_sources: *const CCurrentSource,
    num_current_sources: u32,
    voltage_sources: *const CVoltageSource,
    num_voltage_sources: u32,
    out_node_v: *mut f64,
    out_vsource_i: *mut f64,
) -> i32 {
    use crate::op::solve_operating_point_numeric;
    use crate::op::OpSettings;

    let resistors = if resistors.is_null() || num_resistors == 0 {
        &[]
    } else {
        unsafe { slice::from_raw_parts(resistors, num_resistors as usize) }
    };

    let current_sources = if current_sources.is_null() || num_current_sources == 0 {
        &[]
    } else {
        unsafe { slice::from_raw_parts(current_sources, num_current_sources as usize) }
    };

    let voltage_sources = if voltage_sources.is_null() || num_voltage_sources == 0 {
        &[]
    } else {
        unsafe { slice::from_raw_parts(voltage_sources, num_voltage_sources as usize) }
    };

    if out_node_v.is_null() {
        return 2;
    }

    let settings = OpSettings {
        max_iters: 1,
        tol_v: 0.0,
        tol_a: 0.0,
        damping_v: 0.0,
        damping_i: 0.0,
    };

    let (node_v, v_i, _conv, _iters, _dv, _di) = match solve_operating_point_numeric(
        num_nodes,
        ground,
        resistors,
        current_sources,
        voltage_sources,
        &[],
        &[],
        &[],
        settings,
    ) {
        Some(x) => x,
        None => return 1,
    };

    unsafe {
        for i in 0..(num_nodes as usize) {
            *out_node_v.add(i) = node_v[i];
        }
        if !out_vsource_i.is_null() {
            for i in 0..(num_voltage_sources as usize) {
                *out_vsource_i.add(i) = v_i[i];
            }
        }
    }

    0
}

#[no_mangle]
pub extern "C" fn circuit_ai_solve_operating_point(
    num_nodes: u32,
    ground: u32,
    resistors: *const CResistor,
    num_resistors: u32,
    current_sources: *const CCurrentSource,
    num_current_sources: u32,
    voltage_sources: *const CVoltageSource,
    num_voltage_sources: u32,
    ldos: *const CLdo,
    num_ldos: u32,
    loads_cc: *const CCurrentLoad,
    num_loads_cc: u32,
    loads_cp: *const CPowerLoad,
    num_loads_cp: u32,
    max_iters: u32,
    tol_v: f64,
    tol_a: f64,
    damping_v: f64,
    damping_i: f64,
    out_converged: *mut u32,
    out_iters: *mut u32,
    out_max_delta_v: *mut f64,
    out_max_delta_a: *mut f64,
    out_node_v: *mut f64,
    out_vsource_i: *mut f64,
) -> i32 {
    use crate::op::{solve_operating_point_numeric, OpSettings};

    if num_nodes == 0 || ground >= num_nodes {
        return 2;
    }
    if out_node_v.is_null() {
        return 2;
    }

    let resistors = if resistors.is_null() || num_resistors == 0 {
        &[]
    } else {
        unsafe { slice::from_raw_parts(resistors, num_resistors as usize) }
    };
    let current_sources = if current_sources.is_null() || num_current_sources == 0 {
        &[]
    } else {
        unsafe { slice::from_raw_parts(current_sources, num_current_sources as usize) }
    };
    let voltage_sources = if voltage_sources.is_null() || num_voltage_sources == 0 {
        &[]
    } else {
        unsafe { slice::from_raw_parts(voltage_sources, num_voltage_sources as usize) }
    };
    let ldos = if ldos.is_null() || num_ldos == 0 {
        &[]
    } else {
        unsafe { slice::from_raw_parts(ldos, num_ldos as usize) }
    };
    let loads_cc = if loads_cc.is_null() || num_loads_cc == 0 {
        &[]
    } else {
        unsafe { slice::from_raw_parts(loads_cc, num_loads_cc as usize) }
    };
    let loads_cp = if loads_cp.is_null() || num_loads_cp == 0 {
        &[]
    } else {
        unsafe { slice::from_raw_parts(loads_cp, num_loads_cp as usize) }
    };

    let settings = OpSettings {
        max_iters: max_iters.max(1),
        tol_v,
        tol_a,
        damping_v,
        damping_i,
    };

    let (node_v, v_i, conv, iters, dv, di) = match solve_operating_point_numeric(
        num_nodes,
        ground,
        resistors,
        current_sources,
        voltage_sources,
        ldos,
        loads_cc,
        loads_cp,
        settings,
    ) {
        Some(x) => x,
        None => return 1,
    };

    unsafe {
        for i in 0..(num_nodes as usize) {
            *out_node_v.add(i) = node_v[i];
        }

        if !out_vsource_i.is_null() {
            let total_vs = (num_voltage_sources + num_ldos) as usize;
            for i in 0..total_vs {
                *out_vsource_i.add(i) = v_i[i];
            }
        }

        if !out_converged.is_null() {
            *out_converged = if conv { 1 } else { 0 };
        }
        if !out_iters.is_null() {
            *out_iters = iters;
        }
        if !out_max_delta_v.is_null() {
            *out_max_delta_v = dv;
        }
        if !out_max_delta_a.is_null() {
            *out_max_delta_a = di;
        }
    }

    0
}
