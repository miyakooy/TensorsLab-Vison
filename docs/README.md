# TensorsLab Vision Pages

`index.html` is the static GitHub Pages landing page for this repository.

After pushing the workflow, enable **Settings → Pages → Build and deployment → Source: GitHub Actions**. This repository currently has no Pages site until that one-time setting is enabled; without it, the `Configure Pages` step returns 404 and the deployment stops before uploading `docs/`. GitHub will publish the page at the repository's Pages URL, normally `https://miyakooy.github.io/TensorsLab-Vison/`.

The page uses no build step. It presents the active image/video API endpoints, current workflow scenarios, direct repository installation, and a showcase that reuses public imagery from `miaodashi.com`. Every showcase card distinguishes a runnable repository workflow from a reference or best-effort capability.

If a run is already marked failed, enable the source above and use **Actions → Deploy GitHub Pages → Run workflow** to re-run it. No code change is required for that settings-only fix.

Discovery files published with the page:

- `robots.txt` allows public search crawling and explicitly allows `OAI-SearchBot`.
- `sitemap.xml` contains the canonical page URL.
- `llms.txt` is an experimental navigation summary, not a claimed ranking signal.
- `discoverability.md` explains the evidence and the remaining manual Search Console, Bing and GitHub topic steps.
