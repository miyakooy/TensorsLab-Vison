# TensorsLab Vision Pages

`index.html` is the static GitHub Pages landing page for this repository.

After pushing the workflow, enable **Settings → Pages → Build and deployment → Source: GitHub Actions**. This repository currently has no Pages site until that one-time setting is enabled; without it, the `Configure Pages` step returns 404 and the deployment stops before uploading `docs/`. GitHub will publish the page at the repository's Pages URL, normally `https://miyakooy.github.io/TensorsLab-Vison/`.

The page uses no build step and no product imagery. It presents the active image/video API endpoints, all current Miaodashi workflow scenarios, direct repository installation, and the Miaodashi product handoff. The workflow cards distinguish planned capabilities such as local replacement from directly executable API paths.

If a run is already marked failed, enable the source above and use **Actions → Deploy GitHub Pages → Run workflow** to re-run it. No code change is required for that settings-only fix.
