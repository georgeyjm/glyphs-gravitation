from __future__ import division, print_function, unicode_literals
import objc
from GlyphsApp import *
from GlyphsApp.plugins import *

from fontTools.pens.statisticsPen import StatisticsPen


class Gravitation(ReporterPlugin):

    @objc.python_method
    def settings(self):
        self.menuName = Glyphs.localize({
            'en': 'Gravitation',
            'zh': '重力区域',
            'de': 'Gravitation',
            'fr': 'Gravitation',
            'es': 'Gravitación',
            'pt': 'Gravitação',
            })
        self.keyboardShortcut = 'v'

        self.cached = {}
        self.cachedPath = None


    @objc.python_method
    def start(self):
        pass


    @objc.python_method
    def foreground(self, layer):
        if not self.conditionsAreMetForDrawing() or not layer.paths:
            return
        if layer.bezierPath == self.cachedPath:
            self.draw_gravitation(self.cached.get(layer.parent.name + layer.layerId), True)
        else:
            metrics = self.calculate_gravitation(layer)
            self.draw_gravitation(metrics, True)
            self.cachedPath = layer.bezierPath
            self.cached[layer.parent.name + layer.layerId] = metrics


    @objc.python_method
    def inactiveLayerForeground(self, layer):
        if not self.conditionsAreMetForDrawing() or not layer.paths:
            return
        if layer.parent.name + layer.layerId in self.cached:
            self.draw_gravitation(self.cached.get(layer.parent.name + layer.layerId), False)
        else:
            metrics = self.calculate_gravitation(layer)
            self.draw_gravitation(metrics, False)
            self.cached[layer.parent.name + layer.layerId] = metrics


    def draw_gravitation(self, metrics, is_active=False):
        if not metrics:
            return
        if is_active:
            color = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.9, 0.4, 0.0, 0.35)
        else:
            color = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.2, 0.2, 0.8, 0.3)
        color.set()
        # Draw gravitation area
        bounds = NSMakeRect(*metrics)
        circle = NSBezierPath.bezierPathWithOvalInRect_(bounds)
        circle.fill()
        # Draw center of gravity line
        center_y = metrics[1] + metrics[3] / 2
        start = NSMakePoint(-100000, center_y)
        end = NSMakePoint(100000, center_y)
        path = NSBezierPath.bezierPath()
        path.moveToPoint_(start)
        path.lineToPoint_(end)
        path.setLineWidth_(1)
        path.stroke()


    def calculate_gravitation(self, layer):
        """
        Return the (x, y, width, height) of an ellipse spanning one standard
        deviation of the ink around its center of mass, in glyph units.

        The moments are integrated exactly from the outlines (Green's theorem),
        so no rasterization is needed. Overlaps are removed first so that
        overlapping strokes are not counted twice.
        """
        cleanLayer = layer.copyDecomposedLayer()
        cleanLayer.removeOverlap()
        pen = StatisticsPen()
        cleanLayer.draw(pen)
        if not pen.area:
            return None
        return (
            pen.meanX - pen.stddevX,
            pen.meanY - pen.stddevY,
            pen.stddevX * 2,
            pen.stddevY * 2,
        )


    @objc.python_method
    def conditionsAreMetForDrawing(self):
        """
        Don't activate if text or pan (hand) tool are active.
        """
        currentController = self.controller.view().window().windowController()
        if currentController:
            tool = currentController.toolDrawDelegate()
            textToolIsActive = tool.isKindOfClass_(NSClassFromString("GlyphsToolText"))
            handToolIsActive = tool.isKindOfClass_(NSClassFromString("GlyphsToolHand"))
            if not textToolIsActive:# and not handToolIsActive: 
                return True
        return False


    @objc.python_method
    def __file__(self):
        """Please leave this method unchanged"""
        return __file__
