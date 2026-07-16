import sys
import math
from fontTools.ttLib import TTFont

def match_fonts(ref_path, target_path, out_path):
    print(f"Loading reference font: {ref_path}")
    ref_font = TTFont(ref_path)
    
    print(f"Loading target font: {target_path}")
    target_font = TTFont(target_path)
    
    # 1. Calculate UPM scaling to match CapHeight
    ref_upm = ref_font['head'].unitsPerEm
    ref_os2 = ref_font['OS/2']
    ref_cap_height = ref_os2.sCapHeight
    
    target_upm = target_font['head'].unitsPerEm
    target_os2 = target_font['OS/2']
    # If Stray font doesn't have sCapHeight set properly, we might need a fallback.
    # Usually sCapHeight is set, but let's be safe.
    target_cap_height = getattr(target_os2, 'sCapHeight', 0)
    if target_cap_height == 0:
        target_cap_height = getattr(target_os2, 'usWinAscent', target_upm * 0.8) # Fallback approximation
        
    print(f"Reference: UPM={ref_upm}, CapHeight={ref_cap_height}")
    print(f"Target: UPM={target_upm}, CapHeight={target_cap_height}")
    
    # New UPM for target so that (target_cap_height / new_upm) == (ref_cap_height / ref_upm)
    # new_upm = target_cap_height * ref_upm / ref_cap_height
    new_upm = int(round(target_cap_height * ref_upm / ref_cap_height))
    print(f"New Target UPM to match scaling: {new_upm}")
    
    # Apply new UPM
    target_font['head'].unitsPerEm = new_upm
    
    # Scale factor for metrics (we copy ref metrics, but must scale them to the new UPM)
    metric_scale = new_upm / ref_upm
    
    # 2. Copy Vertical Metrics (scaled)
    print("Updating vertical metrics...")
    
    # OS/2 table
    target_os2.sTypoAscender = int(round(ref_os2.sTypoAscender * metric_scale))
    target_os2.sTypoDescender = int(round(ref_os2.sTypoDescender * metric_scale))
    target_os2.sTypoLineGap = int(round(ref_os2.sTypoLineGap * metric_scale))
    target_os2.usWinAscent = int(round(ref_os2.usWinAscent * metric_scale))
    target_os2.usWinDescent = int(round(ref_os2.usWinDescent * metric_scale))
    target_os2.sxHeight = int(round(ref_os2.sxHeight * metric_scale))
    target_os2.sCapHeight = int(round(ref_cap_height * metric_scale))
    
    # hhea table
    ref_hhea = ref_font['hhea']
    target_hhea = target_font['hhea']
    target_hhea.ascent = int(round(ref_hhea.ascent * metric_scale))
    target_hhea.descent = int(round(ref_hhea.descent * metric_scale))
    target_hhea.lineGap = int(round(ref_hhea.lineGap * metric_scale))
    
    # 3. Match horizontal advance widths
    print("Matching horizontal advance widths...")
    ref_cmap = ref_font.getBestCmap()
    target_cmap = target_font.getBestCmap()
    
    ref_hmtx = ref_font['hmtx'].metrics
    target_hmtx = target_font['hmtx'].metrics
    
    # For every character in target font, if it exists in ref font, copy the advance width
    count = 0
    for code, target_glyph_name in target_cmap.items():
        if code in ref_cmap:
            ref_glyph_name = ref_cmap[code]
            if ref_glyph_name in ref_hmtx and target_glyph_name in target_hmtx:
                ref_adv, ref_lsb = ref_hmtx[ref_glyph_name]
                
                # Scale the advance width to the new UPM
                new_adv = int(round(ref_adv * metric_scale))
                
                # Update the target's hmtx
                old_adv, old_lsb = target_hmtx[target_glyph_name]
                target_hmtx[target_glyph_name] = (new_adv, old_lsb)
                count += 1
                
    print(f"Updated advance widths for {count} glyphs.")
    
    # Save the modified font
    print(f"Saving to {out_path}...")
    target_font.save(out_path)
    print("Done!")

if __name__ == "__main__":
    import os
    ref = os.path.join("node_modules", "@fontsource", "inter", "files", "inter-latin-400-normal.woff")
    stray = r"C:\Users\gjuin\Documents\Dev\monfinary3\AI STUDIO\src\assets\fonts\stray.otf"
    out = r"C:\Users\gjuin\Documents\Dev\monfinary3\AI STUDIO\src\assets\fonts\stray-matched.otf"
    match_fonts(ref, stray, out)
