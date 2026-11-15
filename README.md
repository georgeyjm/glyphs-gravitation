# Gravitation

> A Glyphs Plugin.


## Introduction

Gravitation helps type designers (especially those designing CJK typefaces) to visualize the "visual center" of a glyph. This provides a quantifiable and intuitive method to help balance the weights within glyphs.


## Usage

Turn it on with *View > Show Gravitation* (⇧⌘V).

For every glyph in the edit view, Gravitation draws:

- **Ellipse**: where the ink is spread, one standard deviation around the center of mass horizontally and vertically.
- **Crosshair and center lines**: the center of mass, with lines across the glyph's face (advance width × ascender–descender).

The active glyph is orange and shows its center below the baseline, as a percentage of the face's width and height.

Right-click in the edit view for the settings panel and two commands:

- **Show numbers**, **Show on inactive glyphs**: what to draw.
- **Tilt ellipse with the ink**: rotates the ellipse along the directions of most and least spread, so glyphs whose weight leans diagonally (e.g. 戈, 女) show it.
- **Extend center line across the line**: draws the horizontal center line across the whole line of text, for comparing heights between neighbors.
- **Show font reference lines**: dashed gray lines at the font's typical center (after computing the reference).
- *Compute Font Reference*: measures every exporting glyph in the current master (only the CJK ideographs if the font has enough of them).
- *Show Off-Center Glyphs in New Tab*: opens a tab with the 30 glyphs whose center differs most from the rest of the font. A list with scores is printed to the Macro panel.
