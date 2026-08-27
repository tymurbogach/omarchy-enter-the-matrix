#version 440

// Digital rain for the matrix theme.
//
// Started from bjarneo/quickshell's `matrix.frag` (MIT,
// https://github.com/bjarneo/quickshell): the cell structure, the per-column
// offset hashed from the id and the scanlines all come from there.
//
// Changed from the original: that one drew procedural 3x5 pixel blocks. Here an
// atlas of the real halfwidth katakana is sampled instead -- exactly the ones
// `ttfx matrix --rain-symbols` uses, the effect behind Omarchy's screensaver.
// The colours are its own too (--highlight-color and --rain-color-gradient),
// and the head goes at the BOTTOM, which is where ttfx puts it ("color for the
// bottom of the rain column").

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float iTime;
    vec2 iResolution;
    vec4 colBg;
    vec4 colHead;
    vec4 colRainA;
    vec4 colRainB;
    float cellH;
};

layout(binding = 1) uniform sampler2D atlas;

const float ATLAS_COLS = 8.0;
const float ATLAS_ROWS = 7.0;
const float GLYPHS = 50.0;

float hash11(float n) {
    return fract(sin(n) * 43758.5453);
}

float hash12(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

void main() {
    vec2 frag = qt_TexCoord0 * iResolution;

    // A terminal cell is far taller than it is wide; 0.47 is the ratio measured
    // off a screenshot of the real screensaver (29x64 native px).
    float cellW = cellH * 0.47;
    vec2 cell = vec2(cellW, cellH);
    vec2 cellId = floor(frag / cell);
    vec2 cellUV = fract(frag / cell);

    // Per-column traits, hashed from the id: different speed, offset and streak
    // length are what stop neighbouring columns falling in step.
    float speed = 5.0 + hash11(cellId.x * 1.31 + 0.7) * 13.0;
    float phase = hash11(cellId.x * 7.13 + 4.7) * 400.0;
    float tail = 16.0 + hash11(cellId.x * 2.91 + 1.7) * 22.0;

    float rowsTotal = iResolution.y / cellH + tail;
    float headRow = mod(iTime * speed + phase, rowsTotal);

    // Positive = above the head, which is where the trail goes.
    float above = headRow - cellId.y;
    float vis = step(0.0, above) * step(above, tail);
    float t = clamp(above / tail, 0.0, 1.0);

    // ttfx never fades the trail to nothing: each character takes a random
    // green from the gradient and stays. The floor of 0.30 keeps that body while
    // still letting the fall read.
    float bright = mix(1.0, 0.30, pow(t, 0.75)) * vis;

    // The glyph is redrawn every 250 ms, offset per cell so they do not all
    // flicker at once.
    float tick = floor(iTime * 4.0 + hash12(cellId * 1.7) * 8.0);
    float gi = floor(hash12(vec2(cellId.x * 3.1 + cellId.y * 7.7, tick)) * GLYPHS);
    vec2 slot = vec2(mod(gi, ATLAS_COLS), floor(gi / ATLAS_COLS));
    float a = texture(atlas, (slot + cellUV) / vec2(ATLAS_COLS, ATLAS_ROWS)).a;

    // Character colour: a random point on the gradient, fixed per cell.
    vec3 rain = mix(colRainA.rgb, colRainB.rgb, hash12(cellId + 3.7));
    float isHead = step(above, 0.5) * vis;
    vec3 glyph = mix(rain, colHead.rgb, isHead);

    vec3 col = colBg.rgb + glyph * a * bright;

    // A gentle scanline, so it reads like the output of a CRT.
    col *= 0.93 + 0.07 * sin(frag.y * 3.14159);

    fragColor = vec4(col, 1.0) * qt_Opacity;
}
