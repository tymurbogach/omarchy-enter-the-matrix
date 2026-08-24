#version 440

// Lluvia digital del tema matrix.
//
// Partiendo del shader `matrix.frag` de bjarneo/quickshell (MIT,
// https://github.com/bjarneo/quickshell): de ahi vienen la estructura de
// celdas, el desfase por columna hasheado del id y las lineas de barrido.
//
// Cambiado respecto al original: aquel dibujaba bloques de 3x5 pixeles
// procedurales. Aqui se muestrea un atlas con los katakana de media anchura
// reales, que son exactamente los de `ttfx matrix --rain-symbols` -- el efecto
// del screensaver de Omarchy. Los colores tambien son los suyos
// (--highlight-color y --rain-color-gradient), y la cabeza va ABAJO, que es
// donde ttfx la pone ("color for the bottom of the rain column").

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

    // La celda del terminal es mucho mas alta que ancha; 0.47 es la relacion
    // medida sobre una captura del screensaver real (29x64 px nativos).
    float cellW = cellH * 0.47;
    vec2 cell = vec2(cellW, cellH);
    vec2 cellId = floor(frag / cell);
    vec2 cellUV = fract(frag / cell);

    // Rasgos por columna, hasheados del id: velocidad, desfase y longitud de
    // reguero distintas hacen que las columnas vecinas no vayan a la vez.
    float speed = 5.0 + hash11(cellId.x * 1.31 + 0.7) * 13.0;
    float phase = hash11(cellId.x * 7.13 + 4.7) * 400.0;
    float tail = 22.0 + hash11(cellId.x * 2.91 + 1.7) * 26.0;

    float rowsTotal = iResolution.y / cellH + tail;
    float headRow = mod(iTime * speed + phase, rowsTotal);

    // Positivo = por encima de la cabeza, que es donde va el reguero.
    float above = headRow - cellId.y;
    float vis = step(0.0, above) * step(above, tail);
    float t = clamp(above / tail, 0.0, 1.0);

    // ttfx no apaga el reguero hasta desaparecer: cada caracter lleva un verde
    // al azar del degradado y se queda. El suelo conserva ese cuerpo y deja que
    // se siga viendo caer. Medido contra una captura del screensaver real: con
    // 0.30 el campo salia a 1.4 de brillo medio contra los 5.2 del original.
    float bright = mix(1.0, 0.62, pow(t, 0.75)) * vis;

    // El glifo se resortea cada 250 ms, desfasado por celda para que no
    // parpadeen todos a la vez.
    float tick = floor(iTime * 4.0 + hash12(cellId * 1.7) * 8.0);
    float gi = floor(hash12(vec2(cellId.x * 3.1 + cellId.y * 7.7, tick)) * GLYPHS);
    vec2 slot = vec2(mod(gi, ATLAS_COLS), floor(gi / ATLAS_COLS));
    float a = texture(atlas, (slot + cellUV) / vec2(ATLAS_COLS, ATLAS_ROWS)).a;

    // Color del caracter: un punto al azar del degradado, fijo por celda.
    vec3 rain = mix(colRainA.rgb, colRainB.rgb, hash12(cellId + 3.7));
    float isHead = step(above, 0.5) * vis;
    vec3 glyph = mix(rain, colHead.rgb, isHead);

    vec3 col = colBg.rgb + glyph * a * bright;

    // Barrido suave, para que lea como salida de un CRT.
    col *= 0.93 + 0.07 * sin(frag.y * 3.14159);

    fragColor = vec4(col, 1.0) * qt_Opacity;
}
