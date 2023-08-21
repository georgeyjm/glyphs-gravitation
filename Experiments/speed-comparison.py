import time
import json

import numpy as np
from PIL import Image, ImageDraw
from cairosvg import svg2png
import pyvips


def glyph2svg(glyph_data, scaling=1):
    layer = glyph_data['layers'][0]
    width = layer['width']
    ascender = 840
    descender = 160
    height = ascender + descender

    svg_code = '<svg width="{}" height="{}" xmlns="http://www.w3.org/2000/svg"><rect width="100%" height="100%" fill="white"/>'.format(width * scaling, height * scaling)
    for path in layer['shapes']:
        path_d = 'M {} {} '.format(path['nodes'][-1][0] * scaling, (height - path['nodes'][-1][1] - descender) * scaling)
        i = 0
        while i < len(path['nodes']) - 1:
            node = path['nodes'][i]
            if node[2] == 'o':
                assert path['nodes'][i + 1][2] == 'o'
                assert path['nodes'][i + 2][2] in ('c', 'cs')
                path_d += 'C {} {}, {} {}, {} {} '.format(node[0] * scaling, (height - node[1] - descender) * scaling, path['nodes'][i + 1][0] * scaling, (height - path['nodes'][i + 1][1] - descender) * scaling, path['nodes'][i + 2][0] * scaling, (height - path['nodes'][i + 2][1] - descender) * scaling)
                i += 2
            elif node[2] == 'l':
                path_d += 'L {} {} '.format(node[0] * scaling, (height - node[1] - descender) * scaling)
            elif node[2] == 'c':
                raise ValueError
            i += 1
        path_d += 'Z'
        svg_code += '<path d="{}" fill="black" fill-rule="evenodd"/>'.format(path_d)
    svg_code += '</svg>'
    return svg_code


def svg2arr(svg_code, method):
    '''Convert SVG code string to NumPy array'''
    assert method in ('cairo', 'aggdraw', 'pyvips')
    if method == 'cairo':
        svg2png(bytestring=svg_code, write_to=open('output.png', 'wb'))
        im = Image.open('output.png').convert('L')
        return np.asarray(im)
    elif method == 'aggdraw':
        raise NotImplementedError
    elif method == 'pyvips':
        im = pyvips.Image.svgload_buffer(bytes(svg_code, 'utf-8')) # dpi, scale
        return im.numpy()[:, :, 0]


##### Step 1: Convert glyph paths to SVG
start = time.time()
glyph_data = json.load(open('test-glyph.json'))
svg_code = glyph2svg(glyph_data, scaling=1)
end = time.time()
print('Step 1: {:.4f}ms'.format((end - start) * 1000))

##### Step 2: Convert SVG to PNG
start = time.time()
arr = svg2arr(svg_code, 'cairo')
end = time.time()
print('Step 2: {:.4f}ms'.format((end - start) * 1000))

##### Step 3: Calculate center
start = time.time()
arr = (255 - arr) / 255
height, width = arr.shape
total_sum = arr.sum()

# Horizontal distribution (summing vertically)
dist = arr.sum(axis=0)
vals = np.arange(1, width + 1)
center_x = np.dot(dist, vals) / total_sum
var_x = np.sqrt((dist * (vals - np.average(vals, weights=dist)) ** 2).sum() / total_sum)

# Vertical distribution (summing horizontally)
dist = arr.sum(axis=1)
vals = np.arange(1, height + 1)
center_y = np.dot(dist, vals) / total_sum
var_y = np.sqrt((dist * (vals - np.average(vals, weights=dist)) ** 2).sum() / total_sum)

end = time.time()
print('Step 3: {:.4f}ms'.format((end - start) * 1000))
print('Result: H:{:.1f}±{:.1f} V:{:.1f}±{:.1f}'.format(center_x, center_y, var_x, var_y))

im = Image.fromarray(255 - (arr * 255))
overlay = Image.new('RGBA', im.size)
draw = ImageDraw.Draw(overlay)
draw.ellipse(((center_x - var_x, center_y - var_y), (center_x + var_x, center_y + var_y)), fill=(50, 50, 200, 100))
im = Image.alpha_composite(im.convert('RGBA'), overlay)
im.save('processed.png', 'PNG')
