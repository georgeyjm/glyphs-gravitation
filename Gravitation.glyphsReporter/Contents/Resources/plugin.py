from __future__ import division, print_function, unicode_literals
import math
import statistics
import time

import objc
from AppKit import NSButton, NSFont, NSMakeRect, NSTextField, NSView
from GlyphsApp import *
from GlyphsApp.plugins import *

from fontTools.pens.statisticsPen import StatisticsPen


PREFIX = 'com.georgeyu.Gravitation.'
SHOW_NUMBERS = PREFIX + 'showNumbers'
SHOW_INACTIVE = PREFIX + 'showInactive'
TILT_ELLIPSE = PREFIX + 'tiltEllipse'
EXTEND_LINE = PREFIX + 'extendCenterLine'
SHOW_REFERENCE = PREFIX + 'showReference'

def localized(en, zh, zh_hant, ja):
    """Pick the string for Glyphs' interface language (English, Simplified/Traditional Chinese, Japanese)."""
    return Glyphs.localize({'en': en, 'zh': zh, 'zh-Hans': zh, 'zh-Hant': zh_hant, 'ja': ja})


# Checkboxes in the right-click settings panel:
# (defaults key, default, (English, Simplified Chinese, Traditional Chinese, Japanese))
OPTIONS = (
    (SHOW_NUMBERS, True, ('Show numbers', '显示数值', '顯示數值', '数値を表示')),
    (SHOW_INACTIVE, True, ('Show on inactive glyphs', '在非活动字形上显示', '在非作用中字形上顯示', '非アクティブなグリフにも表示')),
    (TILT_ELLIPSE, False, ('Tilt ellipse with the ink', '椭圆随墨迹倾斜', '橢圓隨墨跡傾斜', '楕円をインクの傾きに合わせる')),
    (EXTEND_LINE, False, ('Extend center line across the line', '重心线延伸至整行', '重心線延伸至整行', '重心線を行全体に延長')),
    (SHOW_REFERENCE, True, ('Show font reference lines', '显示全字库参考线', '顯示全字庫參考線', 'フォント全体の基準線を表示')),
)

MEASURES = ('relX', 'relY')
OUTLIER_COUNT = 30
FAR = 100000  # "infinite" line length in font units
NS_SWITCH_BUTTON = 3  # NSButtonTypeSwitch (checkbox)


# --- Pure helpers (no Glyphs objects, so they can be tested outside Glyphs) ---

def ellipse_axes(metrics, tilt):
    """
    The ellipse to draw: (r1, r2, theta) = radii along its own x and y axes, and
    the angle of its x axis in radians.

    Without tilt this is simply the horizontal and vertical standard deviations.
    With tilt it follows the principal axes of the covariance matrix
    [[varX, cov], [cov, varY]]: its eigenvalues are the variances along the
    directions of most and least spread, and theta is the direction of most.
    """
    a, b, c = metrics['varX'], metrics['cov'], metrics['varY']
    if not tilt:
        return math.sqrt(max(a, 0)), math.sqrt(max(c, 0)), 0.0
    half_trace = (a + c) / 2
    d = math.hypot((a - c) / 2, b)
    r1 = math.sqrt(max(half_trace + d, 0))
    r2 = math.sqrt(max(half_trace - d, 0))
    theta = 0.5 * math.atan2(2 * b, a - c)
    return r1, r2, theta


def robust_center(values):
    """Median and scaled median absolute deviation (comparable to a standard deviation)."""
    median = statistics.median(values)
    mad = statistics.median(abs(v - median) for v in values) * 1.4826
    return median, mad


def outlier_scores(values_by_name, reference):
    """
    Score each glyph by its largest robust z-score across MEASURES.
    Returns [(score, measure, name)] sorted from most to least unusual.
    """
    scores = []
    for name, metrics in values_by_name.items():
        best = (0.0, None)
        for key in MEASURES:
            median, mad = reference[key]
            if mad > 0:
                z = abs(metrics[key] - median) / mad
                if z > best[0]:
                    best = (z, key)
        scores.append((best[0], best[1], name))
    scores.sort(key=lambda s: -s[0])
    return scores


def stats_from_pen(pen, width, descender, ascender):
    """Turn a filled StatisticsPen into the plugin's metrics dict (None if there is no ink)."""
    if not pen.area:
        return None
    face_height = ascender - descender
    return {
        'meanX': pen.meanX,
        'meanY': pen.meanY,
        'varX': pen.varianceX,
        'varY': pen.varianceY,
        'cov': pen.covariance,
        'width': width,
        'descender': descender,
        'ascender': ascender,
        'relX': pen.meanX / width if width else 0.0,
        'relY': (pen.meanY - descender) / face_height if face_height else 0.0,
    }


# --- Glyphs helpers --------------------------------------------------------------

def layer_face(layer):
    """(descender, ascender) of the layer's master, from the layer's metrics if available."""
    ascender = descender = None
    try:
        for metric in layer.metrics:
            # Metric types: ascender (1), descender (7)
            if metric.metric.type == 1:
                ascender = metric.position
            elif metric.metric.type == 7:
                descender = metric.position
    except Exception:
        pass
    master = layer.master
    if ascender is None:
        ascender = master.ascender
    if descender is None:
        descender = master.descender
    return descender, ascender


def layer_signature(layer, face):
    """
    Cheap fingerprint of everything that affects the measurement of this layer.

    Glyphs caches each layer's outline as an NSBezierPath and hands back the
    same object until the outline changes, so comparing it (== is identity for
    NSBezierPath) is a near-free "did the paths change?" check. The bezierPath
    leaves out components, so those are fingerprinted separately.
    """
    components = tuple((component.componentName, tuple(component.transform)) for component in layer.components)
    return (layer.bezierPath, layer.width, face, components)


def component_dependencies(layer, seen=None):
    """Names of all glyphs this layer uses as components, recursively."""
    seen = set() if seen is None else seen
    for component in layer.components:
        name = component.componentName
        if name in seen:
            continue
        seen.add(name)
        base = component.component
        if base is not None:
            base_layer = base.layers[layer.associatedMasterId]
            if base_layer is not None:
                component_dependencies(base_layer, seen)
    return frozenset(seen)


def measure_layer(layer, face):
    """
    Measure the ink of a layer exactly from its outlines (Green's theorem), so no
    rasterization is needed. Works on a copy: components are decomposed, overlaps
    removed (so overlapping strokes count once), and path direction corrected
    (the integrals are signed, so a stroke drawn clockwise by mistake would
    subtract its area). Open contours enclose no area and are skipped.
    """
    clean_layer = layer.copyDecomposedLayer()
    clean_layer.removeOverlap()
    clean_layer.correctPathDirection()
    pen = StatisticsPen()
    for path in clean_layer.paths:
        if path.closed:
            path.draw(pen)
    descender, ascender = face
    return stats_from_pen(pen, layer.width, descender, ascender)


# --- Plugin ----------------------------------------------------------------------

class Gravitation(ReporterPlugin):

    @objc.python_method
    def settings(self):
        self.menuName = Glyphs.localize({
            'en': 'Gravitation',
            'zh': '重心区域',
            'zh-Hans': '重心区域',
            'zh-Hant': '重心區域',
            'ja': '重心エリア',
            'ko': '무게중심 영역',
            'de': 'Gravitation',
            'fr': 'Gravitation',
            'es': 'Gravitación',
            'pt': 'Gravitação',
            'ru': 'Зона центра тяжести',
            'ar': 'منطقة مركز الثقل',
            })
        self.keyboardShortcut = 'v'
        Glyphs.registerDefaults({key: default for key, default, _ in OPTIONS})
        # (glyph name, layer id) -> {'signature', 'metrics', 'dependencies'}
        self.cache = {}
        # master id -> {'count', 'relX': (median, mad), 'relY': ..., 'values': {name: metrics}}
        self.reference = {}
        self.settingsView = None
        self.checkboxes = []


    @objc.python_method
    def start(self):
        pass


    # --- Measuring with a cache ---------------------------------------------

    @objc.python_method
    def metrics_for(self, layer):
        """
        Cached metrics for a layer, re-measured only when its signature changes.
        When a glyph changes, cached glyphs that use it as a component are
        invalidated too (their own signature can't see that change).
        """
        glyph = layer.parent
        if glyph is None:
            return None
        key = (glyph.name, layer.layerId)
        entry = self.cache.get(key)
        face = layer_face(layer)
        signature = layer_signature(layer, face)
        if entry is not None and entry['signature'] == signature:
            return entry['metrics']
        metrics = measure_layer(layer, face)
        self.cache[key] = {
            'signature': signature,
            'metrics': metrics,
            'dependencies': component_dependencies(layer),
        }
        if entry is not None:
            for other_key in [k for k, e in self.cache.items() if glyph.name in e['dependencies']]:
                del self.cache[other_key]
        return metrics


    # --- Drawing -------------------------------------------------------------

    @objc.python_method
    def foreground(self, layer):
        if not self.conditionsAreMetForDrawing() or not layer.shapes:
            return
        self.draw_gravitation(layer, self.metrics_for(layer), is_active=True)


    @objc.python_method
    def inactiveLayerForeground(self, layer):
        if not Glyphs.defaults[SHOW_INACTIVE] or not self.conditionsAreMetForDrawing() or not layer.shapes:
            return
        self.draw_gravitation(layer, self.metrics_for(layer), is_active=False)


    @objc.python_method
    def draw_gravitation(self, layer, metrics, is_active=False):
        if not metrics:
            return
        scale = self.getScale() or 1.0
        hairline = 1.0 / scale
        mean_x, mean_y = metrics['meanX'], metrics['meanY']
        width, descender, ascender = metrics['width'], metrics['descender'], metrics['ascender']

        if is_active:
            red, green, blue = 0.9, 0.4, 0.0
        else:
            red, green, blue = 0.2, 0.2, 0.8

        # Reference lines: where the font's typical center sits, mapped onto this glyph's face
        reference = self.reference.get(layer.associatedMasterId)
        if reference and Glyphs.defaults[SHOW_REFERENCE]:
            ref_x = reference['relX'][0] * width
            ref_y = descender + reference['relY'][0] * (ascender - descender)
            NSColor.colorWithCalibratedWhite_alpha_(0.4, 0.6).set()
            for start, end in (((0, ref_y), (width, ref_y)), ((ref_x, descender), (ref_x, ascender))):
                line = NSBezierPath.bezierPath()
                line.moveToPoint_(NSMakePoint(*start))
                line.lineToPoint_(NSMakePoint(*end))
                line.setLineWidth_(hairline)
                line.setLineDash_count_phase_([4 * hairline, 3 * hairline], 2, 0)
                line.stroke()

        # Ellipse of 1 standard deviation: axis-aligned, or tilted along the ink's principal axes
        r1, r2, theta = ellipse_axes(metrics, tilt=bool(Glyphs.defaults[TILT_ELLIPSE]))
        ellipse = NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(-r1, -r2, 2 * r1, 2 * r2))
        transform = NSAffineTransform.transform()
        transform.translateXBy_yBy_(mean_x, mean_y)
        transform.rotateByRadians_(theta)
        ellipse.transformUsingAffineTransform_(transform)
        NSColor.colorWithCalibratedRed_green_blue_alpha_(red, green, blue, 0.12).set()
        ellipse.fill()
        NSColor.colorWithCalibratedRed_green_blue_alpha_(red, green, blue, 0.8).set()
        ellipse.setLineWidth_(hairline)
        ellipse.stroke()

        # Center lines (the horizontal one optionally across the whole line of text),
        # plus a crosshair at the center of mass
        if Glyphs.defaults[EXTEND_LINE]:
            left, right = -FAR, FAR
        else:
            left, right = 0, width
        NSColor.colorWithCalibratedRed_green_blue_alpha_(red, green, blue, 0.35).set()
        lines = NSBezierPath.bezierPath()
        lines.moveToPoint_(NSMakePoint(left, mean_y))
        lines.lineToPoint_(NSMakePoint(right, mean_y))
        lines.moveToPoint_(NSMakePoint(mean_x, descender))
        lines.lineToPoint_(NSMakePoint(mean_x, ascender))
        lines.setLineWidth_(hairline)
        lines.stroke()
        arm = 8 * hairline
        NSColor.colorWithCalibratedRed_green_blue_alpha_(red, green, blue, 1.0).set()
        cross = NSBezierPath.bezierPath()
        cross.moveToPoint_(NSMakePoint(mean_x - arm, mean_y))
        cross.lineToPoint_(NSMakePoint(mean_x + arm, mean_y))
        cross.moveToPoint_(NSMakePoint(mean_x, mean_y - arm))
        cross.lineToPoint_(NSMakePoint(mean_x, mean_y + arm))
        cross.setLineWidth_(1.5 * hairline)
        cross.stroke()

        if is_active and Glyphs.defaults[SHOW_NUMBERS]:
            self.draw_numbers(metrics, reference, hairline)


    @objc.python_method
    def draw_numbers(self, metrics, reference, hairline):
        text = localized(
            'center {x:.1%} · {y:.1%}',
            '重心 {x:.1%} · {y:.1%}',
            '重心 {x:.1%} · {y:.1%}',
            '重心 {x:.1%} · {y:.1%}',
        ).format(x=metrics['relX'], y=metrics['relY'])
        if reference:
            text += localized(
                '   (font: {x:.1%} · {y:.1%})',
                '   （字库：{x:.1%} · {y:.1%}）',
                '   （字庫：{x:.1%} · {y:.1%}）',
                '   （フォント全体：{x:.1%} · {y:.1%}）',
            ).format(x=reference['relX'][0], y=reference['relY'][0])
        position = NSMakePoint(metrics['width'] / 2, metrics['descender'] - 6 * hairline)
        self.drawTextAtPoint(text, position, fontSize=11, align='topcenter')


    # --- Font reference and outliers -------------------------------------------

    @objc.python_method
    def compute_reference(self, font, master_id):
        started = time.time()
        candidates = []
        for glyph in font.glyphs:
            if not glyph.export:
                continue
            layer = glyph.layers[master_id]
            if layer is None or not layer.shapes:
                continue
            candidates.append((glyph, layer))
        # Compare CJK glyphs with each other when there are enough of them
        han = [(g, l) for g, l in candidates if g.script == 'han']
        if len(han) >= 10:
            candidates = han
        values = {}
        for glyph, layer in candidates:
            metrics = self.metrics_for(layer)
            if metrics:
                values[glyph.name] = metrics
        if len(values) < 3:
            print('Gravitation: not enough glyphs with outlines to build a reference.')
            return None
        reference = {'count': len(values), 'values': values}
        for key in MEASURES:
            reference[key] = robust_center([m[key] for m in values.values()])
        self.reference[master_id] = reference
        print('Gravitation: reference from {} glyphs in {:.1f} s — center {:.1%} · {:.1%}'.format(
            len(values), time.time() - started, reference['relX'][0], reference['relY'][0]))
        return reference


    def computeReference_(self, sender):
        font = Glyphs.font
        if font is None:
            return
        self.compute_reference(font, font.selectedFontMaster.id)
        Glyphs.redraw()


    def showOutliers_(self, sender):
        font = Glyphs.font
        if font is None:
            return
        master_id = font.selectedFontMaster.id
        reference = self.reference.get(master_id) or self.compute_reference(font, master_id)
        if not reference:
            return
        top = outlier_scores(reference['values'], reference)[:OUTLIER_COUNT]
        print('Gravitation: most off-center glyphs (robust z-score, measure):')
        for score, key, name in top:
            print('  {}\t{:.1f}\t{}'.format(name, score, key or '-'))
        font.newTab(''.join('/' + name for _, _, name in top))


    # --- Right-click menu: a settings panel plus two commands --------------------

    @objc.python_method
    def build_settings_view(self):
        row_height, padding, width = 22, 6, 300
        height = padding * 2 + row_height * (len(OPTIONS) + 1)
        view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, width, height))
        y = height - padding - row_height
        title = NSTextField.labelWithString_(self.menuName)
        title.setFont_(NSFont.boldSystemFontOfSize_(NSFont.smallSystemFontSize()))
        title.setFrame_(NSMakeRect(20, y + 2, width - 30, 17))
        view.addSubview_(title)
        self.checkboxes = []
        for index, (key, _, labels) in enumerate(OPTIONS):
            y -= row_height
            checkbox = NSButton.alloc().initWithFrame_(NSMakeRect(18, y, width - 28, row_height))
            checkbox.setButtonType_(NS_SWITCH_BUTTON)
            checkbox.setTitle_(localized(*labels))
            checkbox.setTag_(index)
            checkbox.setTarget_(self)
            checkbox.setAction_('toggleOption:')
            view.addSubview_(checkbox)
            self.checkboxes.append(checkbox)
        return view


    @objc.python_method
    def conditionalContextMenus(self):
        if self.settingsView is None:
            self.settingsView = self.build_settings_view()
        for checkbox, (key, _, _) in zip(self.checkboxes, OPTIONS):
            checkbox.setState_(1 if Glyphs.defaults[key] else 0)
        # Prefix commands with the plugin's localized name, e.g. "重心区域：计算全字库参考"
        prefix = self.menuName + localized(': ', '：', '：', '：')
        compute = localized('Compute Font Reference', '计算全字库参考', '計算全字庫參考', 'フォント全体の基準値を計算')
        outliers = localized(
            'Show Off-Center Glyphs in New Tab',
            '在新标签页显示重心偏离的字形',
            '在新分頁顯示重心偏離的字形',
            '重心がずれたグリフを新しいタブで表示',
        )
        return [
            {'view': self.settingsView},
            {'name': prefix + compute, 'action': self.computeReference_},
            {'name': prefix + outliers, 'action': self.showOutliers_},
        ]


    def toggleOption_(self, sender):
        key = OPTIONS[sender.tag()][0]
        Glyphs.defaults[key] = bool(sender.state())
        Glyphs.redraw()


    # --- Misc ----------------------------------------------------------------------

    @objc.python_method
    def conditionsAreMetForDrawing(self):
        """
        Don't activate if the text tool is active.
        """
        currentController = self.controller.view().window().windowController()
        if currentController:
            tool = currentController.toolDrawDelegate()
            textToolIsActive = tool.isKindOfClass_(NSClassFromString("GlyphsToolText"))
            if not textToolIsActive:
                return True
        return False


    @objc.python_method
    def __file__(self):
        """Please leave this method unchanged"""
        return __file__
