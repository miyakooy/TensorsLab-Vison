# Search and GEO discoverability

This document records the repository's discoverability choices and separates established search practices from experimental AI-discovery conventions.

## Implemented in this repository

- One canonical project name: **TensorsLab Vision Skills**.
- Separate English, Simplified Chinese, Japanese, and Korean README URLs with visible language navigation.
- Descriptive headings, tables, examples, and image alt text written for people first.
- A static, server-rendered GitHub Pages document with a canonical URL, Open Graph metadata, and JSON-LD describing the source repository.
- `robots.txt` allowing public crawling, including `OAI-SearchBot`, and pointing to `sitemap.xml`.
- `sitemap.xml` listing the canonical Pages URL.
- `llms.txt` as an experimental navigation aid. It is not treated as a ranking signal.
- A capability matrix that distinguishes implemented APIs, local workflow code, best-effort model behavior, and missing functionality.

## What improves AI-search visibility

There is no reliable “GEO hack.” The durable approach is the same foundation used by search engines:

1. Keep pages public, fast, and crawlable.
2. State exactly what the software does and does not do.
3. Provide concrete commands, inputs, outputs, limitations, and test evidence.
4. Use stable URLs, clear headings, descriptive link text, and consistent product naming.
5. Publish meaningful updates and submit the sitemap through Google Search Console and Bing Webmaster Tools.
6. Add accurate GitHub repository topics so GitHub search can classify the project.

Recommended GitHub topics:

```text
tensorslab, agent-skills, claude-code, image-generation, video-generation,
text-to-image, image-to-video, ecommerce, creative-workflow, python
```

## Crawler notes

- Google states that normal SEO practices apply to generative search and that useful, original, well-structured content matters more than AI-only formatting. Google also states that `llms.txt` neither helps nor harms Google Search visibility.
- OpenAI states that public pages should not block `OAI-SearchBot` if they should be eligible for ChatGPT search summaries and citations.
- Bing recommends sitemaps for coverage and IndexNow for freshness. IndexNow requires a verified key and should be configured only after the Pages site is live.
- Multilingual website pages should have distinct URLs and `hreflang`. GitHub README files already have distinct URLs, but GitHub controls their HTML head; the hosted Pages site should add locale-specific pages before adding `hreflang` alternates.

## Manual actions after Pages is live

1. Enable **Settings → Pages → Source: GitHub Actions**.
2. Verify `https://miyakooy.github.io/TensorsLab-Vison/robots.txt` and `/sitemap.xml` return HTTP 200.
3. Add the Pages property to Google Search Console and submit `/sitemap.xml`.
4. Add the site to Bing Webmaster Tools and submit the same sitemap.
5. Add the GitHub topics above from the repository's **About** settings.
6. Track queries and citations; improve pages that lack clear examples or evidence instead of producing keyword variants.

## Primary guidance used

- [GitHub: About the repository README file](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes)
- [GitHub: Classifying a repository with topics](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics)
- [Google: Optimizing for generative AI features](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide)
- [Google: Managing multilingual sites](https://developers.google.com/search/docs/advanced/crawling/managing-multi-regional-sites)
- [Google: Build and submit a sitemap](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap)
- [OpenAI: Publishers and developers FAQ](https://help.openai.com/en/articles/12627856)
- [Bing: Sitemaps in AI-powered search](https://blogs.bing.com/webmaster/July-2025/Keeping-Content-Discoverable-with-Sitemaps-in-AI-Powered-Search)
- [Bing: IndexNow](https://www.bing.com/webmasters/help/indexnow-0z209wby)
