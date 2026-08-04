# Third-party notices

The Tools surface adapts interaction ideas and small behavior patterns from
these open-source projects. The product data, copy, colors, and local ghost
sprites remain project-owned.

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

## Radix Context Menu reference

Source: https://www.radix-ui.com/primitives/docs/components/context-menu

The global ghost menu follows the documented context-menu behavior: pointer
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
