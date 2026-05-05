# Palette

**Web:** https://akashdhruv.github.io/Palette

**Free, ready-to-use math tools for the high school classroom.**

Palette is a set of interactive calculators that cover common topics in algebra, pre-calculus, and statistics. Every tool runs directly in the browser -- no accounts, no installs, no app stores.

## What's included

### Graph Calculator (`calc/graph.html`)
Let students type equations and see them plotted instantly. Supports explicit functions (`y = x^2`), implicit equations (`x^2 + y^2 = 25`), and multiple graphs at once. The calculator automatically finds and labels intersection points, renders equations in proper math notation (LaTeX), and adjusts the viewing window to fit the curves. Students can scroll to zoom and use undo/clear to experiment freely.

**Useful for:** graphing linear and quadratic functions, systems of equations, circles and conics, exploring transformations.

### Normal Distribution Calculator (`calc/distribution.html`)
A visual z-table replacement. Students set the mean and standard deviation, then switch between three modes:

- **Z to P** -- enter a z-score, see the cumulative probability and shaded area.
- **P(Range)** -- enter two z-scores, see the probability between them broken down step-by-step.
- **P to Z** -- enter a probability, find the corresponding z-score (inverse normal).

The graph updates in real time as inputs change, so students can build intuition for how the curve and shaded region respond to different values.

**Useful for:** introducing the normal distribution, replacing printed z-tables, checking homework answers, exam review.

### Grouped Data Calculator (`calc/grouped-data.html`)
Students enter class intervals and frequencies into a table. The calculator fills in midpoints, cumulative frequencies, and f*x products automatically, then computes:

- **Mean** (weighted by midpoints)
- **Median** (interpolation formula, with the median class identified)
- **Mode** (interpolation formula, with the modal class highlighted)

A histogram with overlaid mean/median/mode lines and a cumulative frequency curve appears alongside the results. An example dataset is built in so students can see how it works before entering their own data.

**Useful for:** grouped frequency distributions, measures of central tendency for grouped data, ogive curves.

## How to use

The calculator is available at https://akashdhruv.github.io/Palette -- just open it in any browser.

To run locally:

1. **Download or clone** this repository.
2. **Open `index.html`** in a browser (Chrome, Safari, Edge, Firefox all work).
3. Navigate to any calculator from the landing page.

## Project structure

```
index.html          Landing page with links to all calculators
calc/               Individual calculator pages
css/shared.css      Shared styles
js/nav.js           Shared navigation
```

## Requirements

- A modern web browser (any device -- laptop, tablet, or phone)
- Internet connection (for PyScript-based calculators on first load)
- No server, no build tools, no software installation

## License

MIT License -- free to use, modify, and redistribute. See [LICENSE](LICENSE) for details.
