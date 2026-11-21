//! Edge welding and coincidence culling for the Fielddeck scene.
//!
//! This is a line-for-line port of `weldEdgeChains`, `simplifyEdgeChain`, `cullCoincidentChains`
//! and `cullIsolatedChains` in `src/components/fielddeckLogic.js`. The JavaScript stays the
//! reference and the fallback: this port must return the same chains, point for point, in the same
//! order. Every floating-point step follows the JavaScript order of operations, and lengths use
//! V8's own `Math.hypot` algorithm, so tolerance comparisons resolve the same way on both sides.
//! `tests/parity.test.js` in the UI checks this against the JavaScript on captured scene data.

use std::collections::HashMap;

pub type Point = [f64; 3];
pub type Chain = Vec<Point>;

/// V8's `Math.hypot`: scale by the largest magnitude, then a Kahan-compensated sum of squares.
pub fn hypot(values: &[f64]) -> f64 {
    let mut max = 0.0_f64;
    let mut nan = false;
    for value in values {
        let magnitude = value.abs();
        if magnitude.is_nan() {
            nan = true;
        } else if magnitude > max {
            max = magnitude;
        }
    }
    if max == f64::INFINITY {
        return f64::INFINITY;
    }
    if nan {
        return f64::NAN;
    }
    if max == 0.0 {
        return 0.0;
    }
    let mut sum = 0.0_f64;
    let mut compensation = 0.0_f64;
    for value in values {
        let n = value.abs() / max;
        let summand = n * n - compensation;
        let preliminary = sum + summand;
        compensation = (preliminary - sum) - summand;
        sum = preliminary;
    }
    sum.sqrt() * max
}

#[inline]
fn difference(a: &Point, b: &Point) -> Point {
    [a[0] - b[0], a[1] - b[1], a[2] - b[2]]
}

#[inline]
fn dot(a: &Point, b: &Point) -> f64 {
    // `reduce((sum, value, axis) => sum + value * b[axis], 0)`
    ((0.0 + a[0] * b[0]) + a[1] * b[1]) + a[2] * b[2]
}

#[inline]
fn length(v: &Point) -> f64 {
    hypot(v)
}

#[inline]
fn point_at(positions: &[f64], i: usize) -> Point {
    [positions[i], positions[i + 1], positions[i + 2]]
}

fn chain_length(points: &[Point]) -> f64 {
    let mut sum = 0.0;
    for i in 1..points.len() {
        sum += length(&difference(&points[i], &points[i - 1]));
    }
    sum
}

/// `weldEdgeChains(positions, tolerance)`: segment pairs → chains of welded points.
pub fn weld_edge_chains(positions: &[f64], tolerance: f64) -> Vec<Chain> {
    let mut cells: HashMap<(i64, i64, i64), Vec<usize>> = HashMap::new();
    let mut points: Vec<Point> = Vec::new();
    // Neighbours keep insertion order, as a JavaScript Map does: (vertex, edge).
    let mut neighbors: Vec<Vec<(usize, usize)>> = Vec::new();
    let mut used: Vec<bool> = Vec::new();

    let vertex_for = |point: Point,
                          cells: &mut HashMap<(i64, i64, i64), Vec<usize>>,
                          points: &mut Vec<Point>,
                          neighbors: &mut Vec<Vec<(usize, usize)>>|
     -> usize {
        let x = (point[0] / tolerance).floor() as i64;
        let y = (point[1] / tolerance).floor() as i64;
        let z = (point[2] / tolerance).floor() as i64;
        for dx in -1..=1 {
            for dy in -1..=1 {
                for dz in -1..=1 {
                    if let Some(cell) = cells.get(&(x + dx, y + dy, z + dz)) {
                        for &vertex in cell {
                            if length(&difference(&points[vertex], &point)) <= tolerance {
                                return vertex;
                            }
                        }
                    }
                }
            }
        }
        let vertex = points.len();
        points.push(point);
        neighbors.push(Vec::new());
        cells.entry((x, y, z)).or_default().push(vertex);
        vertex
    };

    let mut i = 0;
    while i + 6 <= positions.len() {
        let a = vertex_for(point_at(positions, i), &mut cells, &mut points, &mut neighbors);
        let b = vertex_for(point_at(positions, i + 3), &mut cells, &mut points, &mut neighbors);
        i += 6;
        if a == b || neighbors[a].iter().any(|&(v, _)| v == b) {
            continue;
        }
        let edge = used.len();
        used.push(false);
        neighbors[a].push((b, edge));
        neighbors[b].push((a, edge));
    }

    let mut chains: Vec<Chain> = Vec::new();
    let mut trace = |start: usize, mut next: usize, mut edge: usize, used: &mut Vec<bool>| {
        let mut chain = vec![points[start]];
        while !used[edge] {
            used[edge] = true;
            chain.push(points[next]);
            if neighbors[next].len() != 2 {
                break;
            }
            match neighbors[next].iter().find(|&&(_, candidate)| !used[candidate]) {
                Some(&(vertex, onward)) => {
                    next = vertex;
                    edge = onward;
                }
                None => break,
            }
        }
        chains.push(chain);
    };

    let order: Vec<usize> = (0..points.len())
        .filter(|&v| neighbors[v].len() != 2)
        .chain(0..points.len())
        .collect();
    for start in order {
        for k in 0..neighbors[start].len() {
            let (next, edge) = neighbors[start][k];
            if !used[edge] {
                trace(start, next, edge, &mut used);
            }
        }
    }
    chains
}

/// `simplifyEdgeChain(points, tolerance)`: Douglas–Peucker that keeps short closed loops whole.
pub fn simplify_edge_chain(points: &[Point], tolerance: f64) -> Chain {
    if points.len() < 3 {
        return points.to_vec();
    }
    let last = points.len() - 1;
    let mut keep = vec![false; points.len()];
    keep[0] = true;
    keep[last] = true;
    let mut kept = if last == 0 { 1 } else { 2 };
    let mut spans = vec![(0usize, last)];
    while let Some((from, to)) = spans.pop() {
        let axis = difference(&points[to], &points[from]);
        let squared = dot(&axis, &axis);
        let mut farthest = tolerance;
        let mut split = from;
        for i in (from + 1)..to {
            let offset = difference(&points[i], &points[from]);
            let t = if squared != 0.0 {
                (dot(&offset, &axis) / squared).max(0.0).min(1.0)
            } else {
                0.0
            };
            let distance = length(&[
                offset[0] - t * axis[0],
                offset[1] - t * axis[1],
                offset[2] - t * axis[2],
            ]);
            if distance <= farthest {
                continue;
            }
            farthest = distance;
            split = i;
        }
        if split == from {
            continue;
        }
        if !keep[split] {
            keep[split] = true;
            kept += 1;
        }
        spans.push((from, split));
        spans.push((split, to));
    }
    let closed = points[0] == points[last];
    if closed && kept < 4 {
        return points.to_vec();
    }
    points
        .iter()
        .enumerate()
        .filter(|(i, _)| keep[*i])
        .map(|(_, p)| *p)
        .collect()
}

struct Coincidence<'a> {
    positions: &'a [f64],
    bins: HashMap<i64, Vec<usize>>,
    epsilon: f64,
    seen: Vec<u32>,
    stamp: u32,
    spans: Vec<(f64, f64)>,
}

#[inline]
fn bin(x: f64) -> i64 {
    (x / 5.0).floor() as i64
}

impl<'a> Coincidence<'a> {
    fn new(positions: &'a [f64], tolerance: f64) -> Self {
        let mut bins: HashMap<i64, Vec<usize>> = HashMap::new();
        let mut i = 0;
        while i + 6 <= positions.len() {
            let (ax, bx) = (positions[i], positions[i + 3]);
            for j in bin(ax.min(bx) - tolerance)..=bin(ax.max(bx) + tolerance) {
                bins.entry(j).or_default().push(i);
            }
            i += 6;
        }
        Coincidence {
            positions,
            bins,
            epsilon: tolerance.min(0.0001),
            seen: vec![0; positions.len() / 6 + 1],
            stamp: 0,
            spans: Vec::new(),
        }
    }

    /// `coincides(a, b)`: is segment a→b covered end to end by collinear edges of the other revision?
    fn coincides(&mut self, a: &Point, b: &Point) -> bool {
        let axis = difference(b, a);
        let size = length(&axis);
        if size == 0.0 || size.is_nan() {
            return true;
        }
        let direction = [axis[0] / size, axis[1] / size, axis[2] / size];
        self.stamp = self.stamp.wrapping_add(1);
        if self.stamp == 0 {
            self.seen.iter_mut().for_each(|s| *s = 0);
            self.stamp = 1;
        }
        self.spans.clear();
        let epsilon = self.epsilon;
        for j in bin(a[0].min(b[0]))..=bin(a[0].max(b[0])) {
            let Some(edges) = self.bins.get(&j) else { continue };
            for &e in edges {
                let slot = e / 6;
                if self.seen[slot] == self.stamp {
                    continue;
                }
                self.seen[slot] = self.stamp;
                let o0 = difference(&point_at(self.positions, e), a);
                let o1 = difference(&point_at(self.positions, e + 3), a);
                let start = dot(&o0, &direction);
                let end = dot(&o1, &direction);
                if start.max(end) < 0.0 || start.min(end) > size {
                    continue;
                }
                let off = |v: &Point, s: f64| {
                    length(&[v[0] - s * direction[0], v[1] - s * direction[1], v[2] - s * direction[2]])
                };
                if off(&o0, start) > epsilon || off(&o1, end) > epsilon {
                    continue;
                }
                self.spans.push((start.min(end), start.max(end)));
            }
        }
        // Stable sort by start, as Array.prototype.sort is.
        self.spans.sort_by(|x, y| x.0.partial_cmp(&y.0).unwrap_or(std::cmp::Ordering::Equal));
        let mut covered = 0.0_f64;
        for &(start, end) in &self.spans {
            if start > covered + epsilon {
                break;
            }
            covered = covered.max(end);
            if covered >= size - epsilon {
                return true;
            }
        }
        false
    }
}

/// `cullCoincidentChains(chains, positions, { tolerance, simplify })`.
pub fn cull_coincident_chains(chains: &[Chain], positions: &[f64], tolerance: f64, simplify: bool) -> Vec<Chain> {
    let mut index = Coincidence::new(positions, tolerance);
    let mut remaining: Vec<Chain> = Vec::new();
    let mut append = |run: Chain, index: &mut Coincidence| {
        if run.len() < 2 {
            return;
        }
        if !simplify {
            remaining.push(run);
            return;
        }
        let shorter = simplify_edge_chain(&run, 0.2);
        let hides_change = shorter.len() < run.len()
            && (1..shorter.len()).any(|i| index.coincides(&shorter[i - 1], &shorter[i]));
        remaining.push(if hides_change { run } else { shorter });
    };
    for points in chains {
        if points.is_empty() {
            continue;
        }
        let mut run = vec![points[0]];
        for i in 1..points.len() {
            if index.coincides(&points[i - 1], &points[i]) {
                append(std::mem::replace(&mut run, vec![points[i]]), &mut index);
            } else {
                run.push(points[i]);
            }
        }
        append(run, &mut index);
    }
    remaining
}

/// `cullIsolatedChains(chains, { minLength, weld })`.
pub fn cull_isolated_chains(chains: Vec<Chain>, min_length: f64, weld: f64) -> Vec<Chain> {
    let ends: Vec<[Point; 2]> = chains.iter().map(|c| [c[0], c[c.len() - 1]]).collect();
    let touches = |i: usize| {
        (0..chains.len()).any(|j| {
            j != i
                && ends[i]
                    .iter()
                    .any(|a| ends[j].iter().any(|b| length(&difference(a, b)) <= weld))
        })
    };
    let keep: Vec<bool> = (0..chains.len())
        .map(|i| chain_length(&chains[i]) >= min_length || touches(i))
        .collect();
    chains
        .into_iter()
        .zip(keep)
        .filter_map(|(c, k)| k.then_some(c))
        .collect()
}

pub const KIND_DIFF: u32 = 1;
pub const KIND_OVERLAY: u32 = 2;

/// `runChainJob` for the "diff" and "overlay" kinds. "removed" stays in JavaScript.
pub fn run_job(kind: u32, edges: &[f64], paired: &[f64]) -> Option<Vec<Chain>> {
    let simplify = match kind {
        KIND_DIFF => false,
        KIND_OVERLAY => true,
        _ => return None,
    };
    let welded = weld_edge_chains(edges, 0.01);
    let culled = cull_coincident_chains(&welded, paired, 0.15, simplify);
    Some(cull_isolated_chains(culled, 2.0, 0.01))
}

// ---- WebAssembly interface: plain exports, no bindings generator. -------------------------------
// The caller allocates f64 buffers with `fd_alloc`, runs a job, reads the result header
// [points_ptr, points_len, sizes_ptr, sizes_len] (points as x,y,z f64; sizes as i32 points per
// chain), copies out, then frees everything it allocated.

#[no_mangle]
pub extern "C" fn fd_alloc(len: usize) -> *mut f64 {
    let mut buffer = Vec::<f64>::with_capacity(len.max(1));
    let ptr = buffer.as_mut_ptr();
    std::mem::forget(buffer);
    ptr
}

/// # Safety
/// `ptr` and `len` must come from one `fd_alloc` call.
#[no_mangle]
pub unsafe extern "C" fn fd_free(ptr: *mut f64, len: usize) {
    drop(Vec::from_raw_parts(ptr, 0, len.max(1)));
}

#[repr(C)]
pub struct JobResult {
    points_ptr: *mut f64,
    points_len: usize,
    sizes_ptr: *mut i32,
    sizes_len: usize,
}

/// # Safety
/// The pointers must address `edges_len` and `paired_len` initialised f64 values.
#[no_mangle]
pub unsafe extern "C" fn fd_run(
    kind: u32,
    edges_ptr: *const f64,
    edges_len: usize,
    paired_ptr: *const f64,
    paired_len: usize,
) -> *mut JobResult {
    let edges = if edges_len == 0 { &[][..] } else { std::slice::from_raw_parts(edges_ptr, edges_len) };
    let paired = if paired_len == 0 { &[][..] } else { std::slice::from_raw_parts(paired_ptr, paired_len) };
    match run_job(kind, edges, paired) {
        Some(chains) => encode(chains),
        None => std::ptr::null_mut(),
    }
}

/// `weldEdgeChains(positions, tolerance)` on its own, for the change-accent outlines.
///
/// # Safety
/// `positions_ptr` must address `positions_len` initialised f64 values.
#[no_mangle]
pub unsafe extern "C" fn fd_weld(positions_ptr: *const f64, positions_len: usize, tolerance: f64) -> *mut JobResult {
    let positions = if positions_len == 0 { &[][..] } else { std::slice::from_raw_parts(positions_ptr, positions_len) };
    encode(weld_edge_chains(positions, tolerance))
}

fn encode(chains: Vec<Chain>) -> *mut JobResult {
    let mut points: Vec<f64> = Vec::with_capacity(chains.iter().map(|c| c.len() * 3).sum());
    let mut sizes: Vec<i32> = Vec::with_capacity(chains.len());
    for chain in &chains {
        sizes.push(chain.len() as i32);
        for p in chain {
            points.extend_from_slice(p);
        }
    }
    let mut points = points.into_boxed_slice();
    let mut sizes = sizes.into_boxed_slice();
    let result = Box::new(JobResult {
        points_ptr: points.as_mut_ptr(),
        points_len: points.len(),
        sizes_ptr: sizes.as_mut_ptr(),
        sizes_len: sizes.len(),
    });
    std::mem::forget(points);
    std::mem::forget(sizes);
    Box::into_raw(result)
}

/// # Safety
/// `result` must come from `fd_run` and be freed once.
#[no_mangle]
pub unsafe extern "C" fn fd_free_result(result: *mut JobResult) {
    if result.is_null() {
        return;
    }
    let result = Box::from_raw(result);
    drop(Box::from_raw(std::ptr::slice_from_raw_parts_mut(result.points_ptr, result.points_len)));
    drop(Box::from_raw(std::ptr::slice_from_raw_parts_mut(result.sizes_ptr, result.sizes_len)));
}

#[cfg(test)]
mod tests {
    use super::*;

    fn segments(points: &[Point]) -> Vec<f64> {
        points.windows(2).flat_map(|w| w[0].iter().chain(w[1].iter()).copied().collect::<Vec<_>>()).collect()
    }

    #[test]
    fn hypot_matches_plain_sqrt_on_exact_cases() {
        assert_eq!(hypot(&[3.0, 4.0, 0.0]), 5.0);
        assert_eq!(hypot(&[0.0, 0.0, 0.0]), 0.0);
        assert!(hypot(&[f64::NAN, 1.0, 0.0]).is_nan());
        assert_eq!(hypot(&[f64::INFINITY, f64::NAN, 0.0]), f64::INFINITY);
    }

    #[test]
    fn welds_a_square_into_one_closed_chain() {
        let square = [[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [10.0, 10.0, 0.0], [0.0, 10.0, 0.0], [0.0, 0.0, 0.0]];
        let chains = weld_edge_chains(&segments(&square), 0.01);
        assert_eq!(chains.len(), 1);
        assert_eq!(chains[0].len(), 5);
        assert_eq!(chains[0][0], chains[0][4]);
    }

    #[test]
    fn identical_revisions_cull_to_nothing() {
        let line = [[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [20.0, 5.0, 0.0]];
        let edges = segments(&line);
        let chains = weld_edge_chains(&edges, 0.01);
        assert!(cull_coincident_chains(&chains, &edges, 0.15, false).is_empty());
    }

    #[test]
    fn a_moved_segment_survives_culling() {
        let old = segments(&[[0.0, 0.0, 0.0], [10.0, 0.0, 0.0]]);
        let new = segments(&[[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [10.0, 3.0, 0.0]]);
        let chains = weld_edge_chains(&new, 0.01);
        let left = cull_coincident_chains(&chains, &old, 0.15, false);
        assert_eq!(left, vec![vec![[10.0, 0.0, 0.0], [10.0, 3.0, 0.0]]]);
    }

    #[test]
    fn unknown_kind_is_refused() {
        assert!(run_job(9, &[], &[]).is_none());
    }
}
