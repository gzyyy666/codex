# Fitness Ledger Resource Audit

Audit date: 2026-08-10

The audit used the formal desktop-launcher directory as the business baseline,
then checked exact filename references across maintained source, tests, HTML,
CSS, JavaScript, WXML, WXSS, and documentation.

## Removed from the active D installation

These were confirmed to have no source or test references. They were moved to
`D:\FitnessLedger\archive\obsolete-assets-20260810` before removal from the
active D source and application:

- unused alternate desktop icons: `assets/fitness-ledger-icon-v2.png`,
  `assets/fitness-ledger-v2.ico`;
- superseded Movement artwork variants: `movement-art-arms-core.png`,
  `movement-art-back-v2.png`, `movement-art-chest.png`,
  `movement-art-legs-v2.png`, `movement-art-legs.png`,
  `movement-art-pull.png`, `movement-art-push.png`;
- unused Guardian decoration GIFs: `ghost_body_tartan.gif`,
  `ghost_eyes.gif`.
- an unreferenced `mobile_viewer/pwa/candidateMatcher.js` source candidate;
- the old root and Web `design-qa.md` reports.

The retained `movement-art-core.png`, five `body-themes-v2` images, current
training collages, trophy artwork, and current champion audio remain in use.
Audio files referenced by `tools/guardian_pet_test.py` were retained even when
they are not the default runtime asset.

## Removed from active source, retained as archive

- browser profiles under `web_desktop\.edge-profile` and `web_desktop\.qa-edge*`;
- the `work\edge-cloud-sync-qa` QA copy;
- Python bytecode and generated local files;
- old root-level QA screenshots and `design-qa.md`;
- generated Cloud Sync output and local provider configuration from the Git
  source tree.

The formal D application retains local Cloud Sync state where needed for local
operation. It is not copied into Git.

## Intentionally retained pending a separate decision

- `web_desktop/frontend/motion-lab/` and its GLB/Three.js assets: the current
  Guardian Pet route still loads these assets;
- mobile and Mini Program `themes-v2` WebP files: both viewers construct their
  paths dynamically;
- `training-archive-collage.png` and `training-archive-collage-v2.png`: both
  are referenced by the current stylesheet and need a visual comparison before
  one can be removed;
- historical design evidence that is explicitly linked from current documents.

## Future audit rule

An asset is removable only when both static reference scanning and a route-level
smoke/visual check show that it is not loaded. Dynamic path construction,
third-party bundles, tests, and manual launch resources must be checked before
deletion. Uncertain candidates should be reported with size and references,
not deleted opportunistically.
