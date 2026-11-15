# Gravitation

> A Glyphs Plugin.


## Introduction

Gravitation helps type designers (especially those designing CJK typefaces) to visualize the "visual center" of a glyph. This provides a quantifiable and intuitive method to help balance the weights within glyphs.


## Installation

1. In Glyphs, open *Window > Plugin Manager > Modules* and install **Python** and **FontTools**. Then select the Python version marked "(Glyphs)" in *Settings > Addons* and restart Glyphs.

2. Double-click `Gravitation.glyphsReporter` to install it, then restart Glyphs.

No other third-party libraries are needed: the center of gravity and spread are calculated directly from the outlines with fontTools' `StatisticsPen`.
