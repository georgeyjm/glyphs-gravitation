import numpy as np
from PIL import Image, ImageDraw
from cairosvg import svg2png

svg_code = open('char.svg').read()
svg2png(bytestring=svg_code, write_to=open('output.png', 'wb'))

# im = Image.open('char.png').convert('L')
im = Image.open('output.png')
bg = Image.new('RGBA', im.size, 'WHITE')
bg.paste(im, (0, 0), im)
im = bg.convert('L')
arr = np.array(im)
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

print(center_x, center_y, var_x, var_y)

overlay = Image.new('RGBA', im.size)
draw = ImageDraw.Draw(overlay)
draw.ellipse(((center_x - var_x, center_y - var_y), (center_x + var_x, center_y + var_y)), fill=(50, 50, 200, 100))
im = Image.alpha_composite(im.convert('RGBA'), overlay)
im.save('processed.png', 'PNG')
