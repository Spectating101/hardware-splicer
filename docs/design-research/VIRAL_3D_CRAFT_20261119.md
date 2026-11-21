# Visual craft behind widely shared 3D / engineering interfaces

Prepared 2026-11-19 for the Hardware Splicer hero scene (Fielddeck exploded display swap).
All paths below are under `/home/phyrexian/.cache/tmp/claude-1000/-home-phyrexian-Downloads-llm-automation-project-portfolio-Hardware-Splicer/4b35ef01-debd-4af2-beff-4450d0563dd3/scratchpad/ui-research-viral/` (call it `$R`).

## 0. How to read the evidence tags

- **[SEEN]** I loaded the live page headlessly (Playwright, chromium headless, swiftshader for WebGL), saved a screenshot, and looked at it downscaled. Computed fonts come from `getComputedStyle` in the same run.
- **[CSS]** Read from the site's own downloaded stylesheet (`$R/raw/ap.css`, Apple).
- **[DOCS]** Read from a blog, case study, README or docs page through a fetch or search. Secondary sources are named as such.
- **[MEMORY]** My background knowledge, not re-verified today. Treat as a lead.
- **[MINE]** A judgement or a number I am proposing, or something I rendered in `$R/proto/index.html` to test it.
- **[BLOCKED]** I tried and could not see it (bot wall, 403, wrong URL). I say so rather than describe it.

Limits that matter: swiftshader captures are single frames, so I could see stills, not motion. Every motion timing quoted for third parties is either read from CSS or marked as unavailable. I saw no scroll-sequence exploded view live (IYO's exploded section needs real scroll through video-like pinned sections and my wheel steps only reached the intro and feature chips).

---

## 1. What the best published work actually does

### 1.1 Catalogue (one block per reference)

**Apple, AirPods Pro 3 page** https://www.apple.com/airpods-pro/
- [SEEN] `shots/airpods-0.png`, `airpods-2.png`, `airpods-3.png`. Hero product on a pale grey field (exact hex not read; the CSS lists `#EDEDF2` among its greys), heavy soft diffuse light, no outline, no hard shadow, the product is the only saturated-free object. Headline 56-64px class, tight tracking, black on grey. Numerals are huge and plain ("2x more", "4x more") with a small caption underneath and a thin hairline above: the "stat" pattern with no card.
- [DOCS] The page is built from still image sets with `startframe`/`endframe` names plus an HLS film, not a live 3D scene. The one teardown-ish asset is labelled "guts"/"internal architecture" (page fetch). [DOCS] Third-party tutorials describe the Apple scroll effect as canvas image sequences of 60-180 frames; I found no source for Apple's exact frame count.
- [CSS] `overview.built.css`: font stack `SF Pro Display, SF Pro Icons, Helvetica Neue, Helvetica, Arial`; computed body 17px, headline 21/24/28/32px steps, text colours `#1d1d1f` and `#6e6e73`, link/accent `#0071e3` (39 uses), `#272729` for dark surface. Easings actually used: `cubic-bezier(0.33,1,0.68,1)` (easeOutCubic), `cubic-bezier(0,0,0.5,1)` (`transform .3s`), `cubic-bezier(0.3,2,0.5,1)` and `(0.34,2.16,0.64,1)` (overshoot springs, 2 uses each), `opacity 400ms ease-in-out`, `opacity 100ms linear, transform .2s ease`.
- Takeaway: the premium feel is restraint plus offline-rendered lighting. Nothing glows.

**Teenage Engineering** https://teenage.engineering/
- [SEEN] `shots/te-0.png`. Near-black stage with one soft spotlight pool behind the product and a vignette, a real photographic/render of a device, a single orange accent from the product itself, navigation as tiny lowercase text under line-art pictograms. No gradient fills, no glow on UI. Fonts computed: `te-20` (custom, 16px) and `TechnoType` (39.7px display, 13.2px labels).
- Takeaway: dark does not need a hologram. A pooled light and a very quiet type system do the work. The accent colour comes from the object.

**Nothing** https://nothing.tech/
- [SEEN] `shots/nothing2-0.png` (after dismissing the region modal; `nothing-0.png` is the modal). Transparent and exposed-internals products shot macro on a white seamless; internal components are the visual interest. UI is small mono caps with sparse yellow buttons (hex not sampled). Fonts computed: `NType82` (body/display), `Ndot` (dot-matrix display), `Geist Mono Variable` (11-14px labels), `LatteraMonoLL`.
- Takeaway: the "see the insides" aesthetic is photographic honesty about real components, and mono micro-labels. That is the vocabulary of an engineering app, minus any invented data.

**iyO (VAD Pro, Awwwards case study)** https://www.iyo.ai/vad-pro and https://www.awwwards.com/iyo-case-study-selling-the-worlds-first-audio-computer.html
- [SEEN] `shots/iyo-vad-1.png`, `iyo-vad-2.png`, `iyo-1.png`. Near-black page, matte grey-white product with soft gradient shading, glass pill nav, feature chips as small glass pills with an icon and 12px text, overline labels in 9-10px mono ("OVERVIEW", "DETAILS"). Fonts computed: `Magnetik` (display 33-42px), `Roobert Regular` (14-16px), `Nbarchitekproneue` (9.6px micro labels).
- [DOCS] Case study: the exploded view is scroll-driven, parts separate along Z, hover floats a part forward with a hotspot label; the model was "down-rezzed from the device's CAD to the major components a customer would actually see", fine detail baked to textures, Draco glTF; 27 materials rebuilt (titanium, glass, steel mesh, a dichroic coat); particle count scales by device (quarter on old phones), a slightly lower pixel ratio on retina "cut the shader workload by roughly 44%"; stack is three.js, GSAP, Lenis, taxi.js. The page publishes no durations or easings.
- Takeaway: the exploded view is a simplified model with a handful of named parts, not full CAD. That is exactly the right lesson for HS: fewer, better-lit parts.

**Oryzo AI (Lusion)** https://oryzo.ai/ and https://blog.lusion.co/oryzo-bts-part-2-7-3d-design-and-motion-graphics
- [SEEN] `shots/oryzo-2.png`, crop `shots/c_oryzo-annot.png`. A macro of a cork coaster with real depth of field. Over it, a thin dashed-ellipse and a rectangular bounding box with small edge handles, drawn in the object's own orange. This is the single most reusable 2D-over-3D idea I found: an annotation that looks like a drafting mark, not a UI chip. Fonts: `halyard-display-variable` (up to 123px), `Literata` serif accents.
- [DOCS] Lusion's own post: the imagery is rendered offline in Houdini/Redshift; they tried image sequences, then real-time PBR, and chose Gaussian splats because real-time PBR "did not reach the target quality" and sequences "lacked the interactivity". Camera data exported as COLMAP; hybrid splats only for props (about 78k desktop, 45k mobile). Note the product is a satirical fictional coaster: craft is real, product is a joke.
- Takeaway: the shot you admire is often not real-time PBR. For HS, match the look with a restrained real-time rig plus baked or analytic cues, and never imply the picture is more than the data.

**Bruno Simon portfolio** https://bruno-simon.com/
- [SEEN] `shots/bruno-0.png`, `bruno2-0.png`. This is the loading/intro screen: a glowing ring on a dark grid of `x` marks, blue/magenta gradient. Fonts `Amatic SC` and `Nunito`. I did not get into the world itself.
- [DOCS] Search snippet of his Medium case study (403 on direct fetch): static shadows baked in Blender and stored as small PNG-8; moving objects need separate dynamic shadows.
- Takeaway: baked shadow is the cheap premium trick; the neon ring is exactly the "hologram costume" register to avoid.

**three.js official examples (these are the vocabulary the viral sites build on)**
- [SEEN] `shots/three-contactshadow-0.png` https://threejs.org/examples/webgl_shadow_contact.html : soft blurred contact shadows on white; objects look grounded with no visible floor plane. `shots/three-gltf-0.png` https://threejs.org/examples/webgl_loader_gltf.html : PBR helmet lit by an HDR photo; reflections convincing but the busy photo background steals attention (anti-reference for us). `shots/three-outline-0.png` https://threejs.org/examples/webgl_postprocessing_outline.html : OutlinePass on saturated unlit-looking primitives with a debug panel; shows the "selection outline" idea, also shows how quickly post outlines look toy-like if colours are saturated.
- [SEEN] The console of my own render in r187 warned: `PCFSoftShadowMap has been removed. Using PCFShadowMap instead.`

**model-viewer (Google)** https://modelviewer.dev/examples/annotations/
- [SEEN] `shots/modelviewer-annot-0.png`: default hotspots are plain coloured dots and a grey rounded box. Typefaces Rubik/Roboto Mono. This is the baseline to beat, not a target.
- [DOCS] Hotspots are DOM children with `slot="hotspot-*"`, `data-position` (model coordinates), `data-normal`, and a `--min-hotspot-opacity` that fades when facing away; `data-visibility-attribute` and a `hotspot-visibility` event; dimension lines are an SVG overlay updated from hotspot positions and "always render on top of the model and don't get occlusion".

**Rerun** https://rerun.io/ and https://rerun.io/viewer
- [SEEN] `shots/rerun-0.png`: a white-background hero with a matte white clay-looking robot arm and a spectral trail ribbon; type is system sans plus `JetBrains Mono`; black buttons with mono caps. `shots/rerun-viewer-0.png`: the web viewer welcome screen, light UI, small mono tags on recording cards. I could not open an example recording (click did not navigate; `rerun-urdf-*.png` are identical to the welcome screen).
- Takeaway: for engineering data, the credible look is neutral clay model plus data-coloured overlays, with UI in a mono face.

**Foxglove** https://foxglove.dev/
- [SEEN] `shots/foxglove-0.png`: dark UI, purple accent (hex not sampled) on a primary button and the word "Physical AI", Soehne/Inter plus `Soehne Mono`/`IBM Plex Mono` micro-labels, dense panels. [DOCS] The 3D panel docs state few defaults (URDF display mode Auto, point shape Circle, cube outlines Off, transform history 10,000 messages); grid colour and background have no documented default.

**Framework, Rivian, Tesla, Prusa, Bambu** 
- [BLOCKED] `shots/framework16-*.png` are blank (7 KB, no fonts loaded), Bambu returned a Cloudflare "Just a moment" page. I did not see Rivian, Tesla or Prusa. [DOCS] A search on configurator tech found only generic statements: real-time WebGL vs server-rendered pixel streaming vs image banks, and colour changes done by swapping the material on a surface (the ZeroLight/Lamborghini example). No source confirmed Framework has a live 3D exploded view; I won't claim it.

**Spline, FWA/Awwwards 2025-2026**
- [DOCS] Awwwards case-study pages and a roundup (https://www.utsubo.com/blog/best-threejs-websites-2026) list Oryzo, IVRESS (WebGPU renderer with WebGL fallback, TSL shaders), Hubtown (glowing monolith, cursor reveal), Cartier Watches & Wonders (six 3D alcoves; three.js, GLSL, GSAP, Lenis, Web Audio). The roundup says almost nothing about lighting or materials. A secondary blog claims 29 of 47 Q1-2026 SOTD winners used three.js; I could not verify against Awwwards. I did not capture Spline showcases.

**Vision Pro CAD** https://www.shapr3d.com/blog/introducing-shapr3d-for-apple-vision-pro
- [DOCS] Vendor marketing only: native visionOS, shared review sessions, models shown with different materials, Parasolid kernel. It says nothing on selection highlights, labels or lighting; "unbeatable visual clarity" is unsupported. I found no Onshape Vision Pro app.

**Dribbble/Behance "digital twin", "HUD", "3D dashboard"**
- [DOCS] Search results only (profiles and shots such as "Robot Arm 3D Digital Twin", "Futuristic HUD" ~89k views, "East China Power Grid GIS big screen" ~111k views, tagged dark ui / HUD / big screen). I did not view the images. These are concept shots by definition: no source for the data, tags like "concept". Treat as the costume register (see section 2).

### 1.2 Technique table across the sample

| Technique | What the strongest examples do | Where seen |
|---|---|---|
| Light | Large soft source plus a pooled spot or gradient; no hard-edged hotspot highlights on matte parts; one directional accent from behind | Apple, TE, IYO [SEEN]; Lusion Houdini [DOCS] |
| Environment | Studio-style env for reflections, but the env is not the visible background (three.js gltf example shows why) | three-gltf [SEEN] |
| Material | Matte clay or satin for context parts, real metal/glass only on hero parts; 27 materials rebuilt for IYO because generic PBR looked wrong | IYO [DOCS], Rerun [SEEN] |
| Shadow | Soft contact shadow under the object, no ground plane; baked where static | three contact example [SEEN]; Bruno [DOCS] |
| Edges | Almost none in the premium product shots; thin drafting lines only on annotation overlays (Oryzo dashed ellipse) | Oryzo [SEEN] |
| Depth of field | Used as photographic realism in macro hero shots, offline-rendered | Oryzo [SEEN/DOCS] |
| Post | Little. Bloom/glow appears in "tech" intros (Bruno ring, TE none, Apple none) | [SEEN] |
| Background | Flat near-black or flat pale grey, with one soft radial pool; no grid floor under products | TE, IYO, Apple [SEEN] |
| Accent | One accent per page, taken from the product or brand, used on state not decoration | TE orange, Foxglove purple, Nothing yellow [SEEN] |
| Type | Neutral grotesk for text, a mono or dot-matrix face for labels and numerals; display sizes 40-120px; labels 9-12px caps with wide tracking | Nothing, Rerun, Foxglove, IYO, Oryzo [SEEN, computed] |
| Motion | Easings are out-curves (easeOutCubic family) with 200-400ms UI transitions; scroll-driven camera for 3D with inertial smoothing | Apple [CSS]; Oryzo, IYO [DOCS] |
| Hover | Part floats forward along the explode axis with a label (IYO); hotspot fades when facing away (model-viewer) | [DOCS] |
| Performance | Retopologised/down-rezzed CAD, baked detail, Draco glTF, lower pixel ratio on retina, scale particle count by device | IYO [DOCS] |

---

## 2. Craft versus fakery

### 2.1 What is craft (copy it)
1. Soft, large light with a quiet rim, correct exposure, reflections from a neutral studio env. [SEEN]
2. A contact shadow that grounds each object with no floor plane drawn. [SEEN]
3. Reduction: IYO cut CAD down to the parts a viewer needs. [DOCS]
4. Hierarchy by size and weight, not colour; mono micro-labels. [SEEN]
5. One accent used semantically. [SEEN]
6. Drafting-style annotation marks (Oryzo dashed bounding shapes, corner handles). [SEEN]
7. Out-curve easing, short UI transitions, long smoothed camera moves. [CSS, DOCS]

### 2.2 What reads as hologram costume (avoid)
[SEEN] in Bruno's intro ring and the intro grid of crosses; [DOCS] in the Dribbble "HUD / digital twin / big screen" tags; [MEMORY] generally:
- Additive glow (bloom, neon outlines, drop-shadow glow on text) applied to everything.
- Cyan-on-navy with a perspective grid floor under the model.
- Decorative arcs, radar rings, scan lines, "data rain", gauges with no data behind them.
- Fake telemetry: random numbers, sparkline loops, status lights that never change.
- Text in wide sci-fi display faces for body content.
- Wireframe-everything to mean "technical".

### 2.3 Which viral shots are concepts, and what fails for real
- Dribbble/Behance digital-twin and HUD shots: concept compositions, tagged as such ("concept", "enterprise client concept") [DOCS]. What fails when built: labels overlap as soon as there are 30 real parts; text on glow is unreadable at 11px; 3D HUD overlays cost frame time; no state for "unknown".
- Oryzo-style hero: rendered offline; a literal real-time port would not match the look (Lusion tried) [DOCS].
- Apple scroll pages: image sequences, not live 3D [DOCS]. A live scene cannot replicate that finish; it must borrow the lighting restraint instead.
- Scroll-jacked exploded views: motion triggered by scroll/parallax can cause vestibular discomfort; WCAG 2.3.3 (AAA) says interaction-triggered motion must be disable-able unless essential and names `prefers-reduced-motion` as the sufficient technique (C39) [DOCS, via W3C pages and secondary summaries; the vestibular rationale is from secondary sources]. For an engineering tool, scroll-jacking also hurts precision tasks.
- Hotspot label overload (model-viewer docs themselves note dimension lines have no occlusion) [DOCS]: labels over geometry cannot tell which part they refer to when occluded. My own render confirms leader lines cross other parts (section 5 screenshot `shots/proto2-explode1.png`) [MINE/SEEN].
- Screen-space AO: transparent objects with depthWrite off do not occlude, offscreen geometry cannot occlude, WebGL2 required, hardware MSAA does not work with it (N8AO README) [DOCS]. HS has many transparent/ghost parts, so AO must exclude them.
- Part-count: IYO showed only "the major components"; HS must say so when it simplifies ("n of m parts shown").

---

## 3. three.js implementation notes (techniques worth adopting)

Versions checked on the npm registry today (2026-11-19) [SEEN via `npm view`]:

| Package | Version | Notes |
|---|---|---|
| `three` | 0.187.0 (modified 2026-10-30) | I tested the rig on exactly this. Pin it. |
| `postprocessing` (pmndrs) | 6.39.6 | peer `three >=0.168 <0.188`: stay on three 0.187.x until it moves. Only needed if you use n8ao. |
| `n8ao` | 2.1.0 (2026-11-15) | peers `three >=0.137`, `postprocessing >=6.30`; recommends three r161+. |
| `camera-controls` | 3.1.2 | peer `three >=0.126.1`. |
| `gsap` | 3.15.1 | licence is the GSAP "standard no charge" licence, check before shipping a paid product. |
| `three-mesh-bvh` | 0.9.18 | fast raycasting for hover/pick on many meshes. |
| `@google/model-viewer` | 4.4.0 | only if you want its hotspot system instead of your own. |
| `@react-three/fiber` | 9.8.2 needs React `>=19 <19.4`; 8.18.0 is the React-18 line | The repo has React 18.3.1 (`apps/splice-ui/package.json` [SEEN]): either use plain three in an effect-managed component, upgrade React, or use fiber 8.x. |
| `@react-three/drei` | 10.7.9 needs React ^19 | same issue. |
| `@pmndrs/vanilla` | 1.25.0 | has AccumulativeShadows, Outlines, Grid, Billboard, pcss; no ContactShadows, so write the one in the three example. |
| `three-viewport-gizmo` | 2.2.0 | orientation cube if wanted. |

Repo state [SEEN]: `apps/splice-ui` has React 18.3.1 + Vite 6 and no `three` dependency yet; the existing tokens in `styles.css` are a light theme (`--bg #eef1f4`, `--accent #0b6e4f`). The hero scene is a dark "stage" panel inside that app; do not restyle the whole app dark for it.

Addon paths confirmed present in 0.187.0 via the jsDelivr file listing [SEEN]: `examples/jsm/environments/RoomEnvironment.js`, `postprocessing/{EffectComposer,RenderPass,OutlinePass,GTAOPass,SSAOPass,SMAAPass,OutputPass,BokehPass}.js`, `renderers/CSS2DRenderer.js`, `lines/{LineSegments2,Line2,LineMaterial,Wireframe,WireframeGeometry2}.js`, `helpers/ViewHelper.js`, `geometries/RoundedBoxGeometry.js`, `loaders/{GLTFLoader,DRACOLoader,KTX2Loader,HDRLoader,RGBELoader}.js`, `tsl/display/{OutlineNode,GTAONode}.js` (WebGPU/TSL path), `src/geometries/EdgesGeometry.js`. Meshopt is not under that name, check `MeshoptDecoder` in `examples/jsm/libs/` before relying on it.

### 3.1 Lighting and environment
- `PMREMGenerator.fromScene(new RoomEnvironment(), 0.04)` into `scene.environment`, `scene.environmentIntensity` about 0.5-0.6; keep `scene.background = null` and put the backdrop in CSS. [MINE, rendered in the rig, `shots/proto2-explode1.png`]. RoomEnvironment gives clean softbox reflections without a photo background (contrast with `three-gltf-0.png`).
- `renderer.toneMapping = THREE.NeutralToneMapping` (Khronos PBR Neutral) so authored part colours are not shifted by a filmic curve. [MINE; the constant exists in r187, rig rendered fine]. ACES would shift the hue of the changed/removed accent colours, which matters because colour is evidence here.
- One directional key (shadow caster), one cool rim from behind, no fill: the env map is the fill.
- Shadow type: `PCFSoftShadowMap` was removed in r187 [SEEN in console]. Use `PCFShadowMap` plus `light.shadow.radius` and `blurSamples` for softness, or `VSMShadowMap`; set `shadow.normalBias` about 0.02 to stop acne on thin boards.

### 3.2 Shadows and AO
- Ground as `ShadowMaterial` (opacity about 0.4) so no floor plane is visible. Add a soft radial contact blob on a transparent plane just above y=0. [MINE rig]. The three example `webgl_shadow_contact` shows the depth-render-and-blur contact shadow, which is the better version; write it, since neither `three` nor `@pmndrs/vanilla` ships one (the drei `ContactShadows` is React-only).
- AO choices: core `GTAOPass` (no extra dependency, ran in my rig without errors; I could not see a strong effect at this scale, so verify visually before keeping its cost) or `n8ao` 2.1.0 (`N8AOPass`, `configuration.aoRadius`, `distanceFalloff`, `intensity` 2-5, `halfRes`, `accumulate`, `setQualityMode`; needs SMAA because MSAA does not work with AO) [DOCS]. Exclude transparent ghost/envelope meshes from the AO input.
- Static layouts can bake AO into textures as IYO and Lusion do [DOCS].

### 3.3 Edges and outlines
- `EdgesGeometry(geometry, thresholdAngle)` with 25-30 degrees for CAD parts (default is 1, which shows tessellation lines); `LineSegments` with a `LineBasicMaterial` (1 px; WebGL line width is fixed) for the solid edges. [DOCS: forum guidance 15-20 degrees; I used 28 in the rig].
- Dashed envelope/removed: `LineDashedMaterial` with `computeLineDistances()` on the `LineSegments`; the dash lengths are in world units, so scale them to the part size. [MINE rig, renders correctly]. For thick or screen-space-width lines use `LineSegments2` + `LineMaterial` (`worldUnits:false`, `linewidth` in px) from `lines/`.
- Changed-part highlight: an inverted-hull mesh (BackSide, flat colour, scale 1.02-1.035) gives a crisp amber outline with no post pass [MINE rig, `shots/proto2-explode1.png`]. Use `OutlinePass` only for hover/selection of arbitrary objects (set `edgeGlow` to 0 to avoid glow; `edgeThickness` 1-2; `pulsePeriod` 0). Note OutlinePass forces extra passes. Forum reports that visible-only edge overlays z-fight and that a depth bias can reveal hidden edges [DOCS]; keep edges on the part's own mesh with `polygonOffset` on the fill material rather than a global overlay.

### 3.4 Labels and leader lines
- `CSS2DRenderer` (or hand-projected DOM + one SVG overlay as in my rig) keeps text crisp and selectable. Project with `Vector3.project(camera)`; draw an elbow `polyline` anchor -> knee -> box edge with a 3.5 px ring at the anchor.
- Limits seen in my rig: boxes collided at `explode=0` (`shots/proto2-explode0.png`, two callouts stacked over each other), and leaders crossed other parts. Fix: lay out callouts in two columns with a simple vertical sweep that enforces a minimum gap, route leaders to the nearest column, and render the anchor ring hollow with 40% opacity when the anchor is occluded (raycast the anchor with `three-mesh-bvh`). [MINE, not built].
- model-viewer hotspots (slot + `data-normal`, `--min-hotspot-opacity`) are a documented pattern for fading when facing away [DOCS]; replicate that rule.

### 3.5 Motion and camera
- Explode: animate a single scalar `e` in [0,1] and derive each part's offset with a per-part stagger and `easeOutCubic` (`1-(1-t)^3` equals Apple's `cubic-bezier(.33,1,.68,1)` [CSS]). Per-part positions along a stored `y0 -> y1` explode vector. [MINE rig].
- Tween with GSAP 3.15.1 (`ease:"power3.out"`) or a hand-rolled critically damped spring; for render-on-demand, request a frame while `e` changes.
- Camera: `camera-controls` 3.1.2 `setLookAt(..., true)` and `fitToBox(box, true, {padding...})` return Promises, so a tour is `await`-chained; `smoothTime` default 0.25 s (dragging 0.125 s); call `update(delta)` every tick and render when it returns true; `rest` event signals arrival. [DOCS, README].
- Narrow FOV (24-28 degrees) reads as a product lens and reduces perspective distortion of an exploded stack. [MINE rig used 26; also standard product-render practice, MEMORY].
- Respect `prefers-reduced-motion`: set durations to 0 and snap the camera. [DOCS WCAG C39].

### 3.6 Performance
- Down-resolve CAD to the parts that matter, Draco-compress GLBs (`DRACOLoader`), cap pixel ratio at 2, 1.5 on mid-range (IYO's roughly 44% shader saving came from a slightly lower DPR) [DOCS].
- Render on demand, not continuously, because the scene is static between interactions; only the explode, tour and hover need frames.
- Swiftshader rendered the rig in seconds per frame, which is not a performance measurement of real GPUs. I have no real-GPU numbers.

---

## 4. Visual spec: Hardware Splicer hero scene (Fielddeck exploded display swap)

[MINE] throughout, derived from the evidence above and tested in a placeholder rig. A rendered sample is `shots/proto2-explode1.png` (exploded) and `shots/proto2-explode0.png` (assembled). The rig uses placeholder boxes labelled as such; it must not be mistaken for Fielddeck data.

### 4.1 Honesty rules that constrain the look
1. Every visual class maps to a data class the backend returns. No class exists only for decoration.
2. Colour is never the only carrier: each class also differs in surface treatment, edge pattern and a text tag in its callout.
3. Anything unlinked to geometry says "not linked" in the list, not a guess in the scene.
4. Ghost/envelope geometry is never solid-lit, so it cannot be mistaken for a CAD part.
5. The footer of the stage states the scene is a view, not a promotion of authority (matches `docs/MODEL3D.md` language).

### 4.2 Stage and background
- A dark graphite stage panel embedded in the app, not a full-bleed page takeover. CSS only: `radial-gradient(120% 90% at 50% 38%, #1b222b 0%, #12161b 45%, #0b0d10 100%)`. No grid floor, no star field, no scan lines, no vignette banding (add 1% noise or dither if banding shows on the gradient).
- `scene.background = null`; canvas is `alpha: true`.

### 4.3 Lighting rig
- Environment: RoomEnvironment through PMREM, `environmentIntensity` 0.55.
- Key: `DirectionalLight` colour `#fff1e0`, intensity 2.6, position (-4, 9, 5), shadow 2048, `shadow.radius` 6, `normalBias` 0.02.
- Rim: `DirectionalLight` colour `#9fc0ff`, intensity 1.4, from (5, 3, -6). Needed so dark plastics (the bezel in my render nearly disappeared into the background) keep a readable edge.
- No fill, no point lights, no coloured gels.
- Tone mapping: Neutral, exposure 1.0.
- Camera: perspective FOV 26 degrees, 3/4 view from (8.2, 6.4, 9.6) looking at (0, 2.05, 0) for the exploded stack; no more than 35 degrees azimuth drift during the hero.

### 4.4 Materials (the five states must stay distinct)

| State | Fill | Edges | Extra | Callout tag |
|---|---|---|---|---|
| Real CAD part (authored in the project) | `MeshPhysicalMaterial`; metal parts `metalness .9 roughness .32-.36`, plastics `metalness 0 roughness .46 clearcoat .25` | solid 1 px, `#e8ecf1` at 0.45-0.5 alpha, `thresholdAngle` 28 | casts and receives shadow | `CAD PART` + evidence label |
| Vendor model (third-party, unverified geometry) | `MeshStandardMaterial` flat-shaded matte clay, `roughness .82`, cool grey `#7f93a6` | solid 1 px light edges | no clearcoat, no metal; looks plainly less finished by design | `VENDOR MODEL, UNVERIFIED` |
| Dashed envelope (permitted/estimated volume) | nothing solid: `MeshBasicMaterial` `#8fa8c4` at about 0.012 alpha (a trace), `depthWrite:false` | **dashed** `#8fa8c4`, dash 0.16, gap 0.10 (world units, scale to scene) | casts no shadow, excluded from AO | `ENVELOPE` + source |
| Changed (rev B differs from rev A) | the part keeps its real class material | solid amber edges `#f2b84b` plus an inverted-hull outline at scale 1.022 | no glow | `CHANGED` + what changed |
| Removed ghost (in rev A, absent in rev B) | `#ff7a6b` at 0.035 alpha, `depthWrite:false`, unlit | **dashed** `#ff7a6b` dash 0.13, gap 0.09 | casts no shadow, hairline strike in the list | `REMOVED` + rev |

Distinction test from my render: removed = red dashed with a faint fill, envelope = blue dashed with almost no fill, changed = amber solid hull. They read apart at 50% scale. Two failures to fix: the envelope fill was visible as a blue tint where it overlapped the removed ghost (lower to 0.008 or drop the fill entirely), and a dark bezel nearly vanished (raise base lightness above `#2a3038` or increase rim).
Added/new parts (not drawn in my rig): `#4cc2a8` hull plus a `NEW` tag; reserve green for added only.

### 4.5 Callouts and leader lines
- Card: 196-236 px wide, `background rgba(18,22,27,.86)`, 1 px border `#2a323c`, 4 px radius, `backdrop-filter: blur(6px)`, padding 8/10/9.
- Row 1: state tag, 10 px `JetBrains Mono` 500, uppercase, letter-spacing .08em, colour `#6f7b89`, preceded by a 8 px ring in the state colour (dashed ring for envelope).
- Row 2: part name, Inter 13 px 600 `#e8ecf1`.
- Row 3: evidence line, JetBrains Mono 11 px 400 `#a6b0bc` with `font-variant-numeric: tabular-nums`; the value words (`measured`, `datasheet`, `authored CAD`) in `#e8ecf1` 500. Authority text is whatever the backend returned; the UI never computes it.
- Leader: 1 px, state colour for changed/removed/envelope, `#6f7b89` otherwise; elbow polyline (anchor -> 36 px knee -> card edge); 3.5 px hollow ring at the anchor with `#0b0d10` fill. Hollow-dim (40%) when the anchor is occluded.
- Placement: two columns left and right, vertical sweep with min 10 px gap, max 4 cards visible at once in hero; the rest appear on hover/selection.
- Legend bottom-left, five rows, swatches that replicate each class's treatment (solid metal, clay, dashed, amber, red dashed). No legend means no honest scene.

### 4.6 Type scale (stage and chrome)
Faces: Inter (400/500/600) for names and prose, JetBrains Mono (400/500) for tags, numbers, ids. Both are used by Rerun/Foxglove-style engineering UIs [SEEN: JetBrains Mono on Rerun, Inter on Foxglove]. Self-host rather than hot-link in production.

| Role | Size / weight / tracking |
|---|---|
| Stage title (hero caption) | Inter 28 px 600, -0.01em, `#e8ecf1` |
| Callout title | Inter 13 px 600 |
| Body in stage | Inter 12 px 400, `#a6b0bc` |
| Tag / overline | Mono 10 px 500 uppercase, +0.08em |
| Evidence / numeric | Mono 11 px 400, tabular figures |
| Big stat (revision compare delta) | Inter 40-56 px 600, tabular figures, with a 1 px hairline above and a 11-12 px caption below (the Apple "2x more" pattern, [SEEN]) |
| Legend | Mono 11 px |

### 4.7 Colour tokens (dark stage)
```
--bg-0 #0b0d10   --bg-1 #12161b   --bg-2 #1a2027
--line #2a323c   --line-strong #3b4552
--text #e8ecf1   --text-2 #a6b0bc   --text-3 #6f7b89
--cad #c9d1da    --vendor #7f93a6   --envelope #8fa8c4
--changed #f2b84b  --removed #ff7a6b  --added #4cc2a8  --focus #8ab4ff
```
Rules: one accent colour per meaning; `--focus` is for hover/selection only; contrast of `--text-2` on `--bg-1` is above 7:1 (check with a tool before shipping, I did not run one); no gradients on UI, no glow.

### 4.8 Motion timings and easings (all [MINE], anchored to Apple's CSS easings and camera-controls defaults)

| Interaction | Duration | Easing |
|---|---|---|
| Explode (assembled to exploded) | 1100 ms total, per-part stagger 70 ms of the range, each part runs the rest | `cubic-bezier(.33,1,.68,1)` (easeOutCubic) |
| Collapse | 800 ms | `cubic-bezier(.65,0,.35,1)` (easeInOutCubic) |
| Compare A/B cross-state | 450 ms opacity at `ease-in-out`; changed hull fades in 250 ms after parts settle | opacity `ease-in-out`, geometry easeOutCubic |
| Hover on part | 120 ms emphasis, part drifts 0.08 units along its explode axis | `cubic-bezier(0,0,.5,1)` |
| Select | 160 ms outline in, camera does not move unless user asked | same |
| Tour step (camera to next open problem) | 1400-1800 ms, `camera-controls` `smoothTime` about 0.5 for the tour only, then 0.25 restored; dwell 1.2 s before callout appears, 6 s default auto-advance with a visible pause control | damped (critically damped spring) |
| Callout in/out | 180 ms opacity + 6 px translate | easeOutCubic |
| Reduced motion | all geometry moves snap (0 ms); opacity crossfade 100 ms linear | n/a |

Never: continuous idle rotation, scroll-jacked explode, camera shake, pulsing outlines. The user must be able to drive `e` with a slider as well as play it.

### 4.9 The 5-second hero moment
Honest sequence for the Fielddeck display swap, composed only of real state:
- 0.0 s: stage loads with the assembled Fielddeck at rev A, camera at the 3/4 pose, no labels, legend visible. Poster frame is a pre-rendered still of the same pose (shown immediately, replaced by live canvas without a visible jump).
- 0.4 s: explode starts (1.1 s, staggered from bottom).
- 1.6 s: layers settled. The removed ghost (rev A display) shows dashed coral; the envelope dashed blue; hull outlines nothing yet.
- 1.8 s: compare switches to rev B (450 ms): ghost stays, the new display part arrives with its amber hull.
- 2.4 s: first callout (CHANGED display) appears with its evidence line, e.g. whatever the backend says; if unknown it says `evidence: none`.
- 3.2 s: second callout (REMOVED) appears; envelope callout on hover only.
- 4.2 s: camera eases 18 degrees toward the display layer, FOV unchanged.
- 5.0 s: rests, controls visible: explode slider, rev A/B toggle, "Start tour" button. No auto-loop.

The "moment" is the stack separating and the single amber outline arriving on the one part that changed. Everything else stays neutral.

### 4.10 Reference images the team should match (paths under `$R/shots/`)

Match (look and restraint):
1. `te-0.png` pooled light on near-black, accent from the product, tiny lowercase labels.
2. `airpods-0.png`, `airpods-3.png` product restraint and the big-numeral-with-hairline stat pattern (for compare deltas).
3. `three-contactshadow-0.png` the contact shadow quality target (soft, no visible floor).
4. `c_oryzo-annot.png` (crop of `oryzo-2.png`) drafting-style annotation marks in the object's own colour.
5. `iyo-vad-1.png`, `iyo-vad-2.png` near-black stage, matte product, glass chips, mono overlines.
6. `rerun-0.png` neutral clay model plus data-coloured overlay, mono-set UI.
7. `foxglove-0.png` dark engineering chrome with a single purple accent and mono micro-labels.
8. `proto2-explode1.png` / `proto2-explode0.png` the five-state rig test (placeholder geometry, to be improved: bigger spacing between callouts, better bezel visibility, hollow occluded anchors).

Avoid (counter-references):
- `bruno-0.png` / `bruno2-0.png` neon ring and cross-grid floor (costume register).
- `three-gltf-0.png` busy photographic background competing with the model.
- `three-outline-0.png` saturated primitives with a debug panel look (toy register).
- `modelviewer-annot-0.png` default coloured dot hotspots (baseline to beat).

---

## 5. What I would do next (ordered)
1. Build the contact shadow as in the three example and A/B against `ShadowMaterial` only; decide whether GTAO earns its cost on a real GPU.
2. Implement callout column layout with min gap and occlusion-aware anchors before polishing anything else; that is where my rig failed.
3. Capture a real-GPU frame-time trace of the Fielddeck scene at DPR 1 and 2; I only have swiftshader stills.
4. Pick React strategy: plain three in a ref (keeps React 18) or fiber 8.18 on React 18; fiber 9/drei 10 require React 19.
5. Run the repo gate (`impeccable detect <url>` on the running page; anti-slop only sees an empty shell for this SPA) and screenshot at 1440 and 390 widths. I have not run these; the rig is a standalone page, not the app.
6. Re-capture IYO's pinned exploded scroll sections with a scripted slow scroll and a real GPU if one is available; I only reached the intro and the feature chips.

## 6. Source list
Live pages seen: https://www.apple.com/airpods-pro/ , https://teenage.engineering/ , https://nothing.tech/ , https://www.iyo.ai/vad-pro , https://iyo.ai/ , https://oryzo.ai/ , https://bruno-simon.com/ , https://rerun.io/ , https://rerun.io/viewer , https://foxglove.dev/ , https://modelviewer.dev/examples/annotations/ , https://threejs.org/examples/webgl_shadow_contact.html , https://threejs.org/examples/webgl_loader_gltf.html , https://threejs.org/examples/webgl_materials_physical_clearcoat.html (`three-clearcoat-0.png`), https://threejs.org/examples/webgl_postprocessing_outline.html .
Docs/articles read: https://www.awwwards.com/iyo-case-study-selling-the-worlds-first-audio-computer.html , https://www.utsubo.com/blog/best-threejs-websites-2026 , https://blog.lusion.co/oryzo-bts-part-2-7-3d-design-and-motion-graphics , https://github.com/N8python/n8ao , https://github.com/yomotsu/camera-controls , https://www.shapr3d.com/blog/introducing-shapr3d-for-apple-vision-pro , https://docs.foxglove.dev/docs/visualization/panels/3d , https://w3c.github.io/wcag/understanding/animation-from-interactions (via search summary), https://www.utsubo.com/blog/photorealistic-3d-web-product-visualization-guide (no numbers), Sketchfab viewer API search results (unverified details), Dribbble search results (not viewed).
Blocked or unverified: Codrops (403), Medium Bruno case study (403), Bambu (Cloudflare), Framework (blank), Sketchfab (my guessed URL was wrong), Rivian/Tesla/Prusa (not tried live), Spline (not tried), Awwwards SOTD 2026 list (search only).
Scripts and artefacts: `$R/cap.cjs` (capture), `$R/proto.cjs` + `$R/proto/index.html` (rig), `$R/t1..t5.json` (target lists), `$R/raw/ap.css` (Apple CSS).
