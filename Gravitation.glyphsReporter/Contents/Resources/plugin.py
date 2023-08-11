from __future__ import division, print_function, unicode_literals
import objc
from GlyphsApp import *
from GlyphsApp.plugins import *

import numpy as np
from PIL import Image, ImageDraw
from cairosvg import svg2png


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

		self.cached = {}
		self.cachedPath = None


	@objc.python_method
	def start(self):
		pass


	@objc.python_method
	def background(self, layer):
		if not self.conditionsAreMetForDrawing():
			return
		if layer.bezierPath == self.cachedPath:
			self.draw_gravitation(self.cached.get(layer.parent.unicode + layer.layerId))
		else:
			metrics = self.calculate_gravitation(layer)
			self.draw_gravitation(metrics)
			self.cachedPath = layer.bezierPath
			self.cached[layer.parent.unicode + layer.layerId] = metrics
	

	@objc.python_method
	def inactiveLayerBackground(self, layer):
		if not self.conditionsAreMetForDrawing():
			return
		if layer.parent.unicode + layer.layerId in self.cached:
			self.draw_gravitation(self.cached.get(layer.parent.unicode + layer.layerId))
		else:
			metrics = self.calculate_gravitation(layer)
			self.draw_gravitation(metrics)
			self.cached[layer.parent.unicode + layer.layerId] = metrics
	

	def draw_gravitation(self, metrics):
		bounds = NSMakeRect(*metrics)
		color = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.2, 0.2, 0.8, 0.3)
		color.set()
		circle = NSBezierPath.bezierPathWithOvalInRect_(bounds)
		circle.fill()
	

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
		svg = '<svg width="{}" height="{}" xmlns="http://www.w3.org/2000/svg">'.format(width, height)
		for path in layer.paths:
			path_d = 'M {} {} '.format(path.nodes[-1].position.x, height - path.nodes[-1].position.y - descender)
			i = 0
			while i < len(path.nodes) - 1:
				node = path.nodes[i]
				if node.type == 'offcurve':
					assert path.nodes[i + 1].type == 'offcurve'
					assert path.nodes[i + 2].type == 'curve'
					path_d += 'C {} {}, {} {}, {} {} '.format(node.position.x, height - node.position.y - descender, path.nodes[i + 1].position.x, height - path.nodes[i + 1].position.y - descender, path.nodes[i + 2].position.x, height - path.nodes[i + 2].position.y - descender)
					i += 2
				elif node.type == 'line':
					path_d += 'L {} {} '.format(node.position.x, height - node.position.y - descender)
				elif node.type == 'curve':
					raise ValueError
				i += 1
			path_d += 'Z'
			svg += '<path d="{}" fill="black" fill-rule="evenodd"/>'.format(path_d)
		svg += '</svg>'

		# Calculate gravitation from SVG file
		print('draw')
		center_x, center_y, var_x, var_y = self.calculate_gravitation_from_svg(svg)
		center_y = height - center_y - descender # Different axis system
		return center_x - var_x, center_y - var_y, var_x * 2, var_y * 2


	def calculate_gravitation_from_svg(self, svg_code):
		# Convert SVG to PNG with white background
		svg2png(bytestring=svg_code, write_to=open('/Users/george/Downloads/output.png', 'wb'))
		im = Image.open('/Users/george/Downloads/output.png')
		bg = Image.new('RGBA', im.size, 'WHITE')
		bg.paste(im, (0, 0), im)
		im = bg.convert('L')
		arr = np.array(im)
		arr = (255 - arr) / 255
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
