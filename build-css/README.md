# CSS build (dev-time only)

`meta_coder/static/app.css` is a compiled Tailwind v4 + daisyUI bundle, vendored
into the repo like a static asset — the app itself never runs Node, at install or
at launch. This directory is only for regenerating that file during development.

Regenerate it whenever a template uses a Tailwind utility class that isn't already
in the compiled output (Tailwind v4 scans the templates listed in `input.css`'s
`@source` directive and only includes classes it actually finds):

```sh
cd build-css
npm install   # first time only
npm run build
```

Then commit the updated `meta_coder/static/app.css`.
