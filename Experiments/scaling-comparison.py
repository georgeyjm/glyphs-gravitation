import time
import json

import numpy as np
from PIL import Image, ImageDraw
import matplotlib.pyplot as plt
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


def svg2arr(svg_code, method, scaling=1, dpi=72):
    '''Convert SVG code string to NumPy array'''
    assert method in ('cairo', 'aggdraw', 'pyvips')
    if method == 'cairo':
        svg2png(bytestring=svg_code, write_to=open('output.png', 'wb'))
        im = Image.open('output.png').convert('L')
        return np.asarray(im)
    elif method == 'aggdraw':
        raise NotImplementedError
    elif method == 'pyvips':
        im = pyvips.Image.svgload_buffer(bytes(svg_code, 'utf-8'), scale=scaling, dpi=dpi)
        return im.numpy()[:, :, 0]


def calculate_gravitation(arr, scaling=1):
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

    return center_x / scaling, center_y / scaling, var_x / scaling, var_y / scaling


glyph_data = json.load(open('test-glyph.json'))

# Cairo scaling comparison
scalings = np.linspace(1, 0.2, 101)
times = []
results = []
for scaling in scalings:
    start = time.time()
    svg_code = glyph2svg(glyph_data, scaling=scaling)
    arr = svg2arr(svg_code, 'cairo', scaling=scaling)
    result = calculate_gravitation(arr, scaling=scaling)
    end = time.time()
    elapsed = (end - start) * 1000
    times.append(elapsed)
    results.append(result)
diff_results = np.asarray(results) - results[0]
plt.xlim(1, 0.2)
plt.plot(scalings, diff_results, label='differences')
plt.show()
plt.xlim(1, 0.2)
plt.plot(scalings, times, label='times')
plt.show()


# Pyvips scaling comparison
scalings = np.linspace(1, 0.2, 101)
times = []
results = []
for scaling in scalings:
    start = time.time()
    svg_code = glyph2svg(glyph_data, scaling=scaling)
    arr = svg2arr(svg_code, 'pyvips', scaling=1) # These 2 steps require one and only one scaling factor
    result = calculate_gravitation(arr, scaling=scaling)
    end = time.time()
    elapsed = (end - start) * 1000
    times.append(elapsed)
    results.append(result)
diff_results = np.asarray(results) - results[0]
plt.xlim(1, 0.2)
plt.plot(scalings, diff_results, label='differences')
plt.show()
plt.xlim(1, 0.2)
plt.plot(scalings, times, label='times')
plt.show()


# # Pyvips DPI comparison
# dpis = np.arange(1, 301)
# times = []
# results = []
# for dpi in dpis:
#     start = time.time()
#     svg_code = glyph2svg(glyph_data, scaling=1)
#     arr = svg2arr(svg_code, 'pyvips', dpi=dpi)
#     result = calculate_gravitation(arr, scaling=1)
#     end = time.time()
#     elapsed = (end - start) * 1000
#     times.append(elapsed)
#     results.append(result)
# diff_results = np.asarray(results) - results[0]
# plt.plot(dpis, diff_results, label='differences')
# plt.show()
# plt.plot(dpis, times, label='times')
# plt.show()
