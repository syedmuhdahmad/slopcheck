# slopfence brand assets

| File | Use |
|---|---|
| `logo-light.svg` | Horizontal logo for light backgrounds |
| `logo-dark.svg` | Horizontal logo for dark backgrounds |
| `icon.svg` | Square icon on a dark tile (avatars, favicons) |
| `social-preview.svg` / `.png` | 1280×640 card for the GitHub social preview and link previews |

The mark is a picket fence with slop splattered on it: the fence stops the slop.

- **Colours:** violet `#8B5CF6` / `#6D28D9` for the fence, lime `#A3E635` for the slop, and `#1E1E2E` for dark backgrounds.
- **Wordmark:** [JetBrains Mono](https://github.com/JetBrains/JetBrainsMono) Bold, licensed under the SIL Open Font License 1.1. It's converted to paths, so the SVGs look the same everywhere without the font installed.

## Regenerating

```bash
pip install fonttools
python docs/brand/build.py path/to/JetBrainsMono-Bold.ttf
```

Then render `social-preview.png` from `social-preview.svg` at 1280×640, for example with headless Chrome.
