# Third-party notices

The Tools surface adapts interaction ideas and small behavior patterns from
these open-source projects. The product data, copy, colors, and local ghost
sprites remain project-owned.

## Gentelella v4 page anatomy

Source: https://github.com/ColorlibHQ/gentelella

The Tools, Cloud Sync, and Data Check surfaces adapt the MIT-licensed
Gentelella v4 admin page anatomy: shared page headers, status badges,
operation panels, route/status rows, review queues, and progressive disclosure
for diagnostics. The existing Fitness Ledger shell, local API contracts, and
data semantics remain project-owned; Gentelella is not bundled as a runtime or
dependency.

## Three.js CSS3DRenderer reference

Source: https://threejs.org/docs/pages/CSS3DRenderer.html

The CSS3D panel controller follows the documented approach of applying
hierarchical 3D transforms to ordinary DOM elements. It does not copy the
Three.js runtime or ship a canvas renderer; the existing HTML buttons remain
the accessible interaction authority.

## Mouse Follower

Source: https://github.com/ArtBIT/mouse-follower

Copyright (c) 2017 Djordje Ungar

The current Tools companion uses the spring/inertia cursor-following behavior
and eyes-following pattern. Its tartan ghost sprite assets are local project
assets.

## three-mesh-ui reference

Source: https://github.com/felixmariotto/three-mesh-ui

The interactive-button and nested-panel examples informed the depth and
pressed-state treatment. The library itself is not bundled because it targets
VR mesh UI and would replace the page's semantic HTML controls.

## React Bits reference

Source: https://github.com/DavidHDev/react-bits

The soft-aurora, spotlight, and compositional background patterns informed
the low-contrast archive field. React Bits is not bundled; the local surface
is implemented with project CSS and vanilla JavaScript. The repository is
licensed MIT + Commons Clause; no React Bits source is copied into this app.

## Motion Lab / Invisigrid reference

Source: https://invisigrid.live/

The Tools atmosphere adapts the site's documented motion patterns: a quiet
grid, pointer-reactive lighting, restrained scroll reveals, and category-led
navigation. No Motion Lab assets or runtime are bundled; the local layer uses
existing project CSS and vanilla JavaScript and remains reduced-motion safe.

## Collective OS reference

Source: https://collectiveos.vercel.app/

The Tools overview adapts the visible dashboard relationship of a workspace
rail, KPI strip, content area, and progressive sections. The source's copy,
images, branding, and application code are not copied; Fitness Ledger keeps its
own data contracts, labels, assets, and navigation.

## Easy Bugs demo

Source: https://github.com/bandinopla/threejs-easybugs

The Motion Lab bundles a production build of the public Easy Bugs demo. Its
`BugRig`, CCDIK, raycast-cage, and instanced-animation implementation is
licensed under MIT, Copyright (c) 2026 Pablo Bandinopla. The demo build is
used as the read-only visual inside the Movement Dictionary preview; it does
not read or write archive data. The local build is kept in
`motion-lab/easybugs/`; Easy Bugs remains the isolated head/IK reference and
dictionary preview. The global pet now uses a direct transparent canvas from
the separate `motion-lab/guardian/` full-body scene, avoiding an opaque iframe
compositing layer.

The bundled `man.packed.glb` and `roach.packed.glb` files are separate
third-party model assets and are not covered by the Easy Bugs MIT license.
The demo credits the head scan to yaro.pro and the cockroach to the linked
Sketchfab page; those attribution links are retained in the demo. Confirm
the model licenses before moving this experiment into a formal business
surface.

## 3D Wave Grid demo

Source: https://github.com/franky-adl/3d-wave-grid
Article: https://tympanus.net/codrops/2026/07/09/building-an-interactive-wave-propagation-cube-grid-with-three-js/

The Motion Lab bundles the public 3D Wave Grid build in
`motion-lab/wave-grid/`. The Three.js, GLSL, GSAP, and interaction source is
MIT-licensed, Copyright (c) 2026 franky-adl. The local wrapper changes only
the surrounding copy and palette for Fitness Ledger; the demo remains
isolated from archive data and is used only as a low-opacity accent inside the
existing Archive Health module.

## Guardian pose deck / Three.js + bodybuilder asset

Sources:
- https://threejs.org/
- https://github.com/andrisgauracs/bodybuilder_unity
- https://tympanus.net/codrops/2019/10/14/how-to-create-an-interactive-3d-character-with-three-js/

The Guardian Pose Deck bundles the Three.js ES module runtime, GLTF loader,
and five low-poly static-pose GLBs for a local full-body preview. The global
pet uses the same low-poly asset catalog through a direct transparent canvas
mount. Its optional fallback is the
MIT-licensed exaggerated bodybuilder asset by Andris Gauracs, converted from
the repository's FBX for local GLB loading and paired with its included
texture. Codrops' open interactive-character pattern supplies the mouse-follow
and click-to-animation architecture. This fallback is not a representation of
Nick Walker; the low-poly static catalog is the default review asset.

## Radix Context Menu reference

Source: https://www.radix-ui.com/primitives/docs/components/context-menu

The global Guardian menu follows the documented context-menu behavior: pointer
anchoring, collision-aware placement, dismissal, and keyboard activation.
Radix itself is not bundled because this project is vanilla JavaScript.

## MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
