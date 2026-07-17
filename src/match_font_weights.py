import sys
import os
import math
import skia
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen
from fontTools.pens.t2CharStringPen import T2CharStringPen

class SkiaPathPen(BasePen):
    def __init__(self, glyphSet):
        super().__init__(glyphSet)
        self.path = skia.Path()
        
    def _moveTo(self, pt):
        self.path.moveTo(pt[0], pt[1])
        
    def _lineTo(self, pt):
        self.path.lineTo(pt[0], pt[1])
        
    def _curveToOne(self, pt1, pt2, pt3):
        self.path.cubicTo(pt1[0], pt1[1], pt2[0], pt2[1], pt3[0], pt3[1])
        
    def _qCurveToOne(self, pt1, pt2):
        self.path.quadTo(pt1[0], pt1[1], pt2[0], pt2[1])
        
    def _closePath(self):
        self.path.close()

def skia_to_pen(path, pen):
    iterator = skia.Path.Iter(path, False)
    for verb, pts in iterator:
        if verb == skia.Path.kMove_Verb:
            pen.moveTo((pts[0].x(), pts[0].y()))
        elif verb == skia.Path.kLine_Verb:
            pen.lineTo((pts[1].x(), pts[1].y()))
        elif verb == skia.Path.kQuad_Verb:
            pen.qCurveTo((pts[1].x(), pts[1].y()), (pts[2].x(), pts[2].y()))
        elif verb == skia.Path.kCubic_Verb:
            pen.curveTo((pts[1].x(), pts[1].y()), (pts[2].x(), pts[2].y()), (pts[3].x(), pts[3].y()))
        elif verb == skia.Path.kClose_Verb:
            pen.closePath()

def transform_path(path, weight_diff):
    if weight_diff == 0:
        return path
    
    stroke_width = abs(weight_diff)
    paint = skia.Paint(
        Style=skia.Paint.kStroke_Style,
        StrokeWidth=stroke_width,
        StrokeJoin=skia.Paint.kRound_Join,
        StrokeCap=skia.Paint.kRound_Cap
    )
    stroke_path = skia.Path()
    paint.getFillPath(path, stroke_path)
    
    if weight_diff > 0: # Union to thicken
        out_path = skia.Op(path, stroke_path, skia.PathOp.kUnion_PathOp)
    else: # Difference to thin
        out_path = skia.Op(path, stroke_path, skia.PathOp.kDifference_PathOp)
        
    if out_path is None:
        return path
    return out_path

def generate_weight(base_font_path, inter_font_path, out_path, weight_diff):
    print(f"\n--- Generating {out_path} ---")
    ref_font = TTFont(inter_font_path)
    target_font = TTFont(base_font_path)
    
    ref_upm = ref_font['head'].unitsPerEm
    ref_os2 = ref_font['OS/2']
    ref_cap_height = ref_os2.sCapHeight
    
    target_upm = target_font['head'].unitsPerEm
    target_os2 = target_font['OS/2']
    target_cap_height = getattr(target_os2, 'sCapHeight', 866)
    
    new_upm = int(round(target_cap_height * ref_upm / ref_cap_height))
    target_font['head'].unitsPerEm = new_upm
    metric_scale = new_upm / ref_upm
    
    target_os2.sTypoAscender = int(round(ref_os2.sTypoAscender * metric_scale))
    target_os2.sTypoDescender = int(round(ref_os2.sTypoDescender * metric_scale))
    target_os2.sTypoLineGap = int(round(ref_os2.sTypoLineGap * metric_scale))
    target_os2.usWinAscent = int(round(ref_os2.usWinAscent * metric_scale))
    target_os2.usWinDescent = int(round(ref_os2.usWinDescent * metric_scale))
    target_os2.sxHeight = int(round(ref_os2.sxHeight * metric_scale))
    target_os2.sCapHeight = int(round(ref_cap_height * metric_scale))
    
    ref_hhea = ref_font['hhea']
    target_hhea = target_font['hhea']
    target_hhea.ascent = int(round(ref_hhea.ascent * metric_scale))
    target_hhea.descent = int(round(ref_hhea.descent * metric_scale))
    target_hhea.lineGap = int(round(ref_hhea.lineGap * metric_scale))
    
    ref_cmap = ref_font.getBestCmap()
    target_cmap = target_font.getBestCmap()
    ref_hmtx = ref_font['hmtx'].metrics
    target_hmtx = target_font['hmtx'].metrics
    
    glyph_set = target_font.getGlyphSet()
    cff = target_font['CFF '].cff
    top_dict = cff.topDictIndex[0]
    charstrings = top_dict.CharStrings
    
    count = 0
    for code, target_glyph_name in target_cmap.items():
        if code in ref_cmap:
            ref_glyph_name = ref_cmap[code]
            if ref_glyph_name in ref_hmtx and target_glyph_name in target_hmtx:
                ref_adv, ref_lsb = ref_hmtx[ref_glyph_name]
                new_adv = int(round(ref_adv * metric_scale))
                
                # Update metrics
                old_adv, old_lsb = target_hmtx[target_glyph_name]
                target_hmtx[target_glyph_name] = (new_adv, old_lsb)
                
                # Transform path
                if weight_diff != 0:
                    glyph = glyph_set[target_glyph_name]
                    skia_pen = SkiaPathPen(glyph_set)
                    glyph.draw(skia_pen)
                    
                    new_skia_path = transform_path(skia_pen.path, weight_diff)
                    
                    # Write back to CFF
                    old_charstring = charstrings[target_glyph_name]
                    t2_pen = T2CharStringPen(old_adv, glyph_set)
                    skia_to_pen(new_skia_path, t2_pen)
                    new_charstring = t2_pen.getCharString()
                    new_charstring.private = old_charstring.private
                    new_charstring.globalSubrs = getattr(old_charstring, 'globalSubrs', None)
                    charstrings[target_glyph_name] = new_charstring
                
                count += 1
                
    print(f"Processed {count} glyphs for {out_path}.")
    target_font.save(out_path)

if __name__ == "__main__":
    base_stray = r"C:\Users\gjuin\Documents\Dev\monfinary3\AI STUDIO\src\assets\fonts\stray.otf"
    inter_base = r"C:\Users\gjuin\Documents\Dev\monfinary3\fonts\node_modules\@fontsource\inter\files"
    out_dir = r"C:\Users\gjuin\Documents\Dev\monfinary3\AI STUDIO\src\assets\fonts"
    
    weights = {
        200: ("inter-latin-200-normal.woff", -30),
        300: ("inter-latin-300-normal.woff", -15),
        400: ("inter-latin-400-normal.woff", 0),
        500: ("inter-latin-500-normal.woff", 15),
        600: ("inter-latin-600-normal.woff", 35),
        700: ("inter-latin-700-normal.woff", 60)
    }
    
    for weight, (inter_file, weight_diff) in weights.items():
        inter_path = os.path.join(inter_base, inter_file)
        out_file = os.path.join(out_dir, f"stray-matched-{weight}.otf")
        generate_weight(base_stray, inter_path, out_file, weight_diff)
