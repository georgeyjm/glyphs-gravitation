from __future__ import division, print_function, unicode_literals
import objc
from GlyphsApp import *
from GlyphsApp.plugins import *

import numpy as np
import pyvips


class Gravitation(ReporterPlugin):

    @objc.python_method
    def settings(self):
        self.menuName = Glyphs.localize({
            'en': 'Gravitation',
            'zh': '重力区域',
            'de': 'Mein Plugin',
            'fr': 'Ma extension',
            'es': 'Mi plugin',
            'pt': 'Meu plug-in',
            })
        self.keyboardShortcut = 'v'

        self.cached = {}
        self.cachedPath = None

        self.scalar = 0.5 # Scale the SVG image for faster performance


    @objc.python_method
    def start(self):
        pass


    @objc.python_method
    def foreground(self, layer):
        if not self.conditionsAreMetForDrawing() or not layer.paths:
            return
        if layer.bezierPath == self.cachedPath:
            self.draw_gravitation(self.cached.get(layer.parent.unicode + layer.layerId), True)
        else:
            metrics = self.calculate_gravitation(layer)
            self.draw_gravitation(metrics, True)
            self.cachedPath = layer.bezierPath
            self.cached[layer.parent.unicode + layer.layerId] = metrics


    @objc.python_method
    def inactiveLayerForeground(self, layer):
        if not self.conditionsAreMetForDrawing() or not layer.paths:
            return
        if layer.parent.unicode + layer.layerId in self.cached:
            self.draw_gravitation(self.cached.get(layer.parent.unicode + layer.layerId), False)
        else:
            metrics = self.calculate_gravitation(layer)
            self.draw_gravitation(metrics, False)
            self.cached[layer.parent.unicode + layer.layerId] = metrics


    def draw_gravitation(self, metrics, is_active=False):
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
        # Get dimensions of SVG
        width = layer.width
        height = 0
        descender = 0
        for metric in layer.metrics:
            if metric.name == 'Ascender, Han':
                height += metric.position
            elif metric.name == 'Descender, Han':
                height -= metric.position
                descender = -metric.position
        
        # Draw all SVG paths
        svg = '<svg width="{}" height="{}" xmlns="http://www.w3.org/2000/svg"><rect width="100%" height="100%" fill="white"/>'.format(width, height)
        path_d = ''
        for path in layer.paths:
            path_d += 'M {} {} '.format(path.nodes[-1].position.x, (height - path.nodes[-1].position.y - descender))
            i = 0
            while i < len(path.nodes) - 1:
                node = path.nodes[i]
                if node.type == 'offcurve':
                    assert path.nodes[i + 1].type == 'offcurve'
                    assert path.nodes[i + 2].type == 'curve'
                    path_d += 'C {} {}, {} {}, {} {} '.format(node.position.x, (height - node.position.y - descender), path.nodes[i + 1].position.x, (height - path.nodes[i + 1].position.y - descender), path.nodes[i + 2].position.x, (height - path.nodes[i + 2].position.y - descender))
                    i += 2
                elif node.type == 'line':
                    path_d += 'L {} {} '.format(node.position.x, (height - node.position.y - descender))
                elif node.type == 'curve':
                    raise ValueError
                i += 1
            path_d += 'Z '
        svg += '<path d="{}" fill="black"/></svg>'.format(path_d)

        # Calculate gravitation from SVG file (with scaling accounted for)
        # print('draw', layer.parent.name)
        center_x, center_y, var_x, var_y = self.calculate_gravitation_from_svg(svg)
        center_y = height * self.scalar - center_y - descender * self.scalar # Different axis system
        return (center_x - var_x) / self.scalar, (center_y - var_y) / self.scalar, var_x * 2 / self.scalar, var_y * 2 / self.scalar


    def calculate_gravitation_from_svg(self, svg_code):
        # Convert SVG code to NumPy array
        im = pyvips.Image.svgload_buffer(bytes(svg_code, 'utf-8'), scale=self.scalar)
        arr = (255 - im.numpy()[:, :, 0]) / 255
        height, width = arr.shape
        total_sum = arr.sum()

        # Calculate horizontal distribution (summing vertically)
        dist = arr.sum(axis=0)
        vals = np.arange(1, width + 1)
        center_x = np.dot(dist, vals) / total_sum
        var_x = np.sqrt((dist * (vals - np.average(vals, weights=dist)) ** 2).sum() / total_sum)

        # Calculate vertical distribution (summing horizontally)
        dist = arr.sum(axis=1)
        vals = np.arange(1, height + 1)
        center_y = np.dot(dist, vals) / total_sum
        var_y = np.sqrt((dist * (vals - np.average(vals, weights=dist)) ** 2).sum() / total_sum)

        return center_x, center_y, var_x, var_y


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
