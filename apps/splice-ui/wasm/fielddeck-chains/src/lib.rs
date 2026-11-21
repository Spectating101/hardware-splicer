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

/// V8's `Math.round`: round half towards +∞ (ceil, then step back when that overshoots by more than ½).
#[inline]
fn round_js(x: f64) -> f64 {
    let up = x.ceil();
    if up - 0.5 > x {
        up - 1.0
    } else {
        up
    }
}

/// three.js `EdgesGeometry(geometry, thresholdAngle)` (r187) for a float32 position attribute with
/// an optional index. `threshold_dot` is `Math.cos(DEG2RAD * thresholdAngle)`, computed by the
/// caller in JavaScript so the cosine is V8's. Returns segment pairs as float32, in three's order.
pub fn edges_geometry(positions: &[f32], index: Option<&[u32]>, threshold_dot: f64) -> Vec<f32> {
    const PRECISION: f64 = 10_000.0;
    type Hash = (i64, i64, i64);
    struct Edge {
        index0: usize,
        index1: usize,
        normal: Point,
    }
    let vertex = |i: usize| -> Point {
        [positions[i * 3] as f64, positions[i * 3 + 1] as f64, positions[i * 3 + 2] as f64]
    };
    let hash = |v: &Point| -> Hash {
        (
            round_js(v[0] * PRECISION) as i64,
            round_js(v[1] * PRECISION) as i64,
            round_js(v[2] * PRECISION) as i64,
        )
    };
    let count = match index {
        Some(index) => index.len(),
        None => positions.len() / 3,
    };
    // An insertion-ordered map, as three's Map: key → slot in `entries`; a matched edge becomes None.
    let mut slots: HashMap<(Hash, Hash), usize> = HashMap::new();
    let mut entries: Vec<Option<Edge>> = Vec::new();
    let mut vertices: Vec<f32> = Vec::new();
    let mut i = 0;
    while i + 3 <= count {
        let ids = match index {
            Some(index) => [index[i] as usize, index[i + 1] as usize, index[i + 2] as usize],
            None => [i, i + 1, i + 2],
        };
        i += 3;
        let tri = [vertex(ids[0]), vertex(ids[1]), vertex(ids[2])];
        // Triangle.getNormal: (c - b) × (a - b), normalised by 1 / sqrt(lengthSq).
        let t = difference(&tri[2], &tri[1]);
        let u = difference(&tri[0], &tri[1]);
        let mut normal = [t[1] * u[2] - t[2] * u[1], t[2] * u[0] - t[0] * u[2], t[0] * u[1] - t[1] * u[0]];
        let length_sq = normal[0] * normal[0] + normal[1] * normal[1] + normal[2] * normal[2];
        if length_sq > 0.0 {
            let scale = 1.0 / length_sq.sqrt();
            normal = [normal[0] * scale, normal[1] * scale, normal[2] * scale];
        } else {
            normal = [0.0, 0.0, 0.0];
        }
        let hashes = [hash(&tri[0]), hash(&tri[1]), hash(&tri[2])];
        if hashes[0] == hashes[1] || hashes[1] == hashes[2] || hashes[2] == hashes[0] {
            continue;
        }
        for j in 0..3 {
            let next = (j + 1) % 3;
            let forward = (hashes[j], hashes[next]);
            let reverse = (hashes[next], hashes[j]);
            let sibling = slots.get(&reverse).copied().filter(|&slot| entries[slot].is_some());
            if let Some(slot) = sibling {
                let other = entries[slot].as_ref().map(|e| e.normal).unwrap_or([0.0; 3]);
                if normal[0] * other[0] + normal[1] * other[1] + normal[2] * other[2] <= threshold_dot {
                    for p in [&tri[j], &tri[next]] {
                        vertices.extend([p[0] as f32, p[1] as f32, p[2] as f32]);
                    }
                }
                entries[slot] = None;
            } else if !slots.contains_key(&forward) {
                slots.insert(forward, entries.len());
                entries.push(Some(Edge { index0: ids[j], index1: ids[next], normal }));
            }
        }
    }
    for edge in entries.iter().flatten() {
        for id in [edge.index0, edge.index1] {
            vertices.extend_from_slice(&positions[id * 3..id * 3 + 3]);
        }
    }
    vertices
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

/// Byte buffers for the float32 and index inputs of `fd_edges`, 8-byte aligned.
#[no_mangle]
pub extern "C" fn fd_alloc_bytes(len: usize) -> *mut u8 {
    let mut buffer = Vec::<u64>::with_capacity(len.div_ceil(8).max(1));
    let ptr = buffer.as_mut_ptr() as *mut u8;
    std::mem::forget(buffer);
    ptr
}

/// # Safety
/// `ptr` and `len` must come from one `fd_alloc_bytes` call.
#[no_mangle]
pub unsafe extern "C" fn fd_free_bytes(ptr: *mut u8, len: usize) {
    drop(Vec::from_raw_parts(ptr as *mut u64, 0, len.div_ceil(8).max(1)));
}

#[repr(C)]
pub struct EdgesResult {
    points_ptr: *mut f32,
    points_len: usize,
}

/// `new EdgesGeometry(geometry, angle)` positions. `index_len` 0 means a non-indexed geometry.
///
/// # Safety
/// The pointers must address `positions_len` f32 and `index_len` u32 initialised values, and every
/// index must address a vertex inside `positions`.
#[no_mangle]
pub unsafe extern "C" fn fd_edges(
    positions_ptr: *const f32,
    positions_len: usize,
    index_ptr: *const u32,
    index_len: usize,
    threshold_dot: f64,
) -> *mut EdgesResult {
    let positions = if positions_len == 0 { &[][..] } else { std::slice::from_raw_parts(positions_ptr, positions_len) };
    let index = if index_len == 0 { None } else { Some(std::slice::from_raw_parts(index_ptr, index_len)) };
    let vertex_count = positions.len() / 3;
    if index.is_some_and(|ids| ids.iter().any(|&id| id as usize >= vertex_count)) {
        return std::ptr::null_mut();
    }
    let mut points = edges_geometry(positions, index, threshold_dot).into_boxed_slice();
    let result = Box::new(EdgesResult { points_ptr: points.as_mut_ptr(), points_len: points.len() });
    std::mem::forget(points);
    Box::into_raw(result)
}

/// # Safety
/// `result` must come from `fd_edges` and be freed once.
#[no_mangle]
pub unsafe extern "C" fn fd_free_edges(result: *mut EdgesResult) {
    if result.is_null() {
        return;
    }
    let result = Box::from_raw(result);
    drop(Box::from_raw(std::ptr::slice_from_raw_parts_mut(result.points_ptr, result.points_len)));
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
    fn a_cube_has_twelve_feature_edges() {
        // Two triangles per face, non-indexed; coplanar diagonals are culled at 1°.
        let c = |x: f32, y: f32, z: f32| [x, y, z];
        let quads = [
            [c(0., 0., 0.), c(1., 0., 0.), c(1., 1., 0.), c(0., 1., 0.)],
            [c(0., 0., 1.), c(0., 1., 1.), c(1., 1., 1.), c(1., 0., 1.)],
            [c(0., 0., 0.), c(0., 0., 1.), c(1., 0., 1.), c(1., 0., 0.)],
            [c(0., 1., 0.), c(1., 1., 0.), c(1., 1., 1.), c(0., 1., 1.)],
            [c(0., 0., 0.), c(0., 1., 0.), c(0., 1., 1.), c(0., 0., 1.)],
            [c(1., 0., 0.), c(1., 0., 1.), c(1., 1., 1.), c(1., 1., 0.)],
        ];
        let mut positions = Vec::new();
        for q in quads {
            for v in [q[0], q[2], q[1], q[0], q[3], q[2]] {
                positions.extend(v);
            }
        }
        let edges = edges_geometry(&positions, None, (1.0_f64).to_radians().cos());
        assert_eq!(edges.len(), 12 * 6);
    }

    #[test]
    fn js_rounding_goes_half_up() {
        assert_eq!(round_js(-2.5), -2.0);
        assert_eq!(round_js(2.5), 3.0);
        assert_eq!(round_js(0.49999999999999994), 0.0);
        assert_eq!(round_js(-0.4), -0.0);
    }

    #[test]
    fn unknown_kind_is_refused() {
        assert!(run_job(9, &[], &[]).is_none());
    }
}
